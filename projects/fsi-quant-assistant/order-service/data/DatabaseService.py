# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Database service module for handling database connections and operations."""

import os

import sqlalchemy
from google.cloud.alloydb.connector import Connector, IPTypes
from model.Balance import Balance
from model.BestBidOffer import BestBidOffer
from model.DepositRequest import DepositRequest
from model.DepositResult import DepositBalance, DepositResult
from model.enum.OrderStatus import OrderStatus
from model.enum.RejectReason import RejectReason
from model.Fill import Fill
from model.LastSale import LastSale
from model.Offer import Offer
from model.Order import Order
from model.OrderBookEntry import OrderBookEntry
from model.OrderResult import OrderResult
from model.OrderState import OrderState
from sqlalchemy.engine import Engine


class DatabaseService:
    """Service class for interacting with the database."""

    _instance = None
    _engine = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseService, cls).__new__(cls)
        return cls._instance

    def get_engine(self) -> Engine:
        if self._engine is None:
            self._engine = self._init_connection_pool()
        return self._engine

    def _init_connection_pool(self) -> Engine:
        # Retrieve environment variables
        user = os.environ.get("ALLOYDB_USER")
        password = os.environ.get("ALLOYDB_PASSWORD")
        db_name = os.environ.get("ALLOYDB_DATABASE", "postgres")
        db_host = os.environ.get("DB_HOST")

        if db_host:
            # Use standard connection for local/SSH tunnel
            db_port = os.environ.get("DB_PORT", "5432")
            engine = sqlalchemy.create_engine(
                f"postgresql+pg8000://{user}:{password}@"
                f"{db_host}:{db_port}/{db_name}"
            )
            self._set_search_path_on_connect(engine)
            return engine

        # Fallback to AlloyDB Connector
        project_id = os.environ.get("PROJECT_ID")
        region = os.environ.get("REGION")
        cluster_name = os.environ.get("ALLOYDB_CLUSTER")
        instance_name = os.environ.get("ALLOYDB_INSTANCE")
        use_iam_auth = os.environ.get("USE_IAM_AUTH", "false").lower() == "true"

        required_vars = [project_id, region, cluster_name, instance_name, user]
        if not all(required_vars):
            raise ValueError(
                "Missing required environment variables for AlloyDB connection"
            )

        if not use_iam_auth and not password:
            raise ValueError(
                "ALLOYDB_PASSWORD is required when IAM auth is not enabled"
            )

        instance_connection_name = (
            f"projects/{project_id}/locations/{region}/clusters/"
            f"{cluster_name}/instances/{instance_name}"
        )

        connector = Connector()

        def getconn():
            kwargs = {"user": user, "db": db_name, "ip_type": IPTypes.PRIVATE}
            if use_iam_auth:
                kwargs["enable_iam_auth"] = True
            else:
                kwargs["password"] = password

            return connector.connect(
                instance_connection_name, "pg8000", **kwargs
            )

        pool = sqlalchemy.create_engine(
            "postgresql+pg8000://",
            creator=getconn,
        )
        self._set_search_path_on_connect(pool)
        return pool

    def _set_search_path_on_connect(self, engine: Engine):
        @sqlalchemy.event.listens_for(engine, "connect")
        def set_search_path(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("SET search_path TO exchange")
            cursor.close()

    def insert_order(self, order: Order) -> OrderResult:
        engine = self.get_engine()
        with engine.connect() as conn:
            try:
                result = conn.execute(
                    sqlalchemy.text(
                        "SELECT exchange.match_order(:_user_name, :_symbol, "
                        ":_side, :_type, :_price, :_amount)"
                    ),
                    {
                        "_user_name": order.user,
                        "_symbol": order.symbol,
                        "_side": order.side.value,
                        "_type": order.type.value,
                        "_price": order.price,
                        "_amount": order.size,
                    },
                )
                row = result.fetchone()
                conn.commit()
                if row and row[0]:
                    match_result = row[0]
                    status_str = match_result.get("status")
                    try:
                        status = OrderStatus(status_str)
                    except ValueError:
                        status = OrderStatus.UNKNOWN

                    return OrderResult(
                        order=order,
                        orderId=(
                            str(match_result.get("order_id"))
                            if match_result.get("order_id")
                            else None
                        ),
                        status=status,
                        reason=match_result.get("reason"),
                        fills=(
                            [Fill(**f) for f in match_result.get("fills", [])]
                            if match_result.get("fills")
                            else []
                        ),
                        new_offer=(
                            Offer(**match_result.get("new_offer"))
                            if match_result.get("new_offer")
                            else None
                        ),
                    )
                return OrderResult(
                    order=order,
                    orderId=None,
                    status=OrderStatus.REJECTED,
                    reason=RejectReason.UNKNOWN,
                )
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"Error inserting order: {e}")
                return OrderResult(
                    order=order,
                    orderId=None,
                    status=OrderStatus.REJECTED,
                    reason=RejectReason.UNKNOWN,
                )

    def get_order_status(self, order_id: int) -> OrderState | None:
        engine = self.get_engine()
        with engine.connect() as conn:
            result = conn.execute(
                sqlalchemy.text(
                    "SELECT order_id, created, user_name, symbol, side, type, "
                    "status, order_price, total_qty, offer_id, "
                    "remaining_open_qty, is_active_on_book, "
                    "calculated_filled_qty FROM exchange.v_order_summary "
                    "WHERE order_id = :p_order_id"
                ),
                {"p_order_id": order_id},
            )
            row = result.fetchone()
            if row:
                return OrderState(
                    order_id=row[0],
                    created=row[1],
                    user_name=row[2],
                    symbol=row[3],
                    side=row[4],
                    type=row[5],
                    status=row[6],
                    order_price=row[7],
                    total_qty=row[8],
                    offer_id=row[9],
                    remaining_open_qty=row[10],
                    is_active_on_book=row[11],
                    calculated_filled_qty=row[12],
                )
            return None

    def get_orders(self, user_name: str) -> list[OrderState]:
        engine = self.get_engine()
        with engine.connect() as conn:
            result = conn.execute(
                sqlalchemy.text(
                    """
                    SELECT v.order_id, v.created, v.user_name, v.symbol,
                           v.side, v.type, v.status, v.order_price, v.total_qty,
                           v.offer_id, v.remaining_open_qty,
                           v.is_active_on_book, v.calculated_filled_qty
                    FROM exchange.v_order_summary v
                    WHERE v.user_name = :p_user_name
                    ORDER BY v.order_id DESC LIMIT 10
                    """
                ),
                {"p_user_name": user_name},
            )
            rows = result.fetchall()
            orders = []
            for row in rows:
                orders.append(
                    OrderState(
                        order_id=row[0],
                        created=row[1],
                        user_name=row[2],
                        symbol=row[3],
                        side=row[4],
                        type=row[5],
                        status=row[6],
                        order_price=row[7],
                        total_qty=row[8],
                        offer_id=row[9],
                        remaining_open_qty=row[10],
                        is_active_on_book=row[11],
                        calculated_filled_qty=row[12],
                    )
                )
            return orders

    def get_bbo(self, symbol: str) -> BestBidOffer | None:
        engine = self.get_engine()
        with engine.connect() as conn:
            result = conn.execute(
                sqlalchemy.text(
                    "SELECT symbol, bid_price, bid_size, ask_price, ask_size "
                    "FROM exchange.v_bbo WHERE symbol = :symbol"
                ),
                {"symbol": symbol},
            )
            row = result.fetchone()
            if row:
                return BestBidOffer(
                    symbol=row[0],
                    bid_price=row[1],
                    bid_size=row[2],
                    ask_price=row[3],
                    ask_size=row[4],
                )
            return None

    def get_last_sale(self, symbol: str) -> LastSale | None:
        engine = self.get_engine()
        with engine.connect() as conn:
            result = conn.execute(
                sqlalchemy.text(
                    "SELECT symbol, last_price, last_size, trade_time "
                    "FROM exchange.v_last_sale WHERE symbol = :symbol"
                ),
                {"symbol": symbol},
            )
            row = result.fetchone()
            if row:
                return LastSale(
                    symbol=row[0],
                    last_price=row[1],
                    last_size=row[2],
                    trade_time=row[3],
                )
            return None

    def get_order_book(self, symbol: str) -> list[OrderBookEntry]:
        engine = self.get_engine()
        with engine.connect() as conn:
            result = conn.execute(
                sqlalchemy.text(
                    "SELECT symbol, side, price, quantity, order_count "
                    "FROM exchange.get_order_book(:symbol)"
                ),
                {"symbol": symbol},
            )
            rows = result.fetchall()
            book = []
            for row in rows:
                book.append(
                    OrderBookEntry(
                        symbol=row[0],
                        side=row[1],
                        price=row[2],
                        quantity=row[3],
                        order_count=row[4],
                    )
                )
            return book

    def get_balances(self, user_name: str) -> list[Balance]:
        engine = self.get_engine()
        with engine.connect() as conn:
            result = conn.execute(
                sqlalchemy.text(
                    """
                    SELECT v.user_name, v.symbol, v.available, v.locked, v.total
                    FROM exchange.v_balances v
                    WHERE v.user_name = :p_user_name
                """
                ),
                {"p_user_name": user_name},
            )
            rows = result.fetchall()
            balances = []
            for row in rows:
                balances.append(
                    Balance(
                        user_name=row[0],
                        symbol=row[1],
                        available=row[2],
                        locked=row[3],
                        total=row[4],
                    )
                )
            return balances

    def deposit_funds(
        self, user_name: str, request: DepositRequest
    ) -> DepositResult:
        engine = self.get_engine()
        with engine.connect() as conn:
            try:
                result = conn.execute(
                    sqlalchemy.text(
                        "SELECT exchange.deposit_funds(:user_name, :amount, "
                        ":symbol)"
                    ),
                    {
                        "user_name": user_name,
                        "amount": request.amount,
                        "symbol": request.symbol,
                    },
                )
                row = result.fetchone()
                conn.commit()
                if row and row[0]:
                    res = row[0]
                    new_balance = None
                    if res.get("new_balance"):
                        new_balance = DepositBalance(
                            available=res["new_balance"]["available"],
                            locked=res["new_balance"]["locked"],
                            total=res["new_balance"]["total"],
                        )

                    return DepositResult(
                        status=res.get("status"),
                        transaction_id=res.get("transaction_id"),
                        user=res.get("user"),
                        symbol=res.get("symbol"),
                        deposited=res.get("deposited"),
                        new_balance=new_balance,
                        reason=res.get("reason"),
                    )
                return DepositResult(status="ERROR", reason="Unknown error")
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"Error depositing funds: {e}")
                return DepositResult(status="ERROR", reason=str(e))
