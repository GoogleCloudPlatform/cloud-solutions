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

"""Database service tests module."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from data.DatabaseService import DatabaseService
from model.enum.OrderStatus import OrderStatus
from model.enum.OrderType import OrderType
from model.enum.RejectReason import RejectReason
from model.enum.Side import Side
from model.Order import Order


@pytest.fixture
def mock_engine():
    with patch("sqlalchemy.create_engine") as mock_create, patch(
        "sqlalchemy.event.listens_for"
    ):
        mock_eng = MagicMock()
        mock_create.return_value = mock_eng
        yield mock_eng


@pytest.fixture
def database_service(
    mock_engine,
):  # pylint: disable=redefined-outer-name, unused-argument
    # Reset singleton
    DatabaseService._instance = None  # pylint: disable=protected-access
    DatabaseService._engine = None  # pylint: disable=protected-access
    with patch.dict(
        "os.environ",
        {
            "DB_HOST": "localhost",
            "ALLOYDB_USER": "user",
            "ALLOYDB_PASSWORD": "password",
            "ALLOYDB_DATABASE": "db",
        },
    ):
        return DatabaseService()


def test_insert_order_success(
    database_service, mock_engine
):  # pylint: disable=redefined-outer-name
    # Mock connection and execution
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_result = MagicMock()
    mock_result.fetchone.return_value = (
        {"status": "PENDING", "order_id": 123},
    )  # JSONB return
    mock_conn.execute.return_value = mock_result

    order = Order(
        user="sender1",
        symbol="AAPL",
        side=Side.BUY,
        type=OrderType.MARKET,
        size=100,
    )

    result = database_service.insert_order(order)

    assert result.orderId == "123"


def test_insert_order_failure(
    database_service, mock_engine
):  # pylint: disable=redefined-outer-name
    # Mock connection and execution with no result
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_result = MagicMock()
    mock_result.fetchone.return_value = None
    mock_conn.execute.return_value = mock_result

    order = Order(
        user="sender1",
        symbol="AAPL",
        side=Side.BUY,
        type=OrderType.MARKET,
        size=100,
    )

    result = database_service.insert_order(order)

    assert result.orderId is None
    assert result.status == OrderStatus.REJECTED
    assert result.reason == RejectReason.UNKNOWN


def test_get_order_status_found(
    database_service, mock_engine
):  # pylint: disable=redefined-outer-name
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_result = MagicMock()
    mock_result.fetchone.return_value = (
        1,
        datetime.now(),
        "user1",
        "AAPL",
        "buy",
        "limit",
        "Partially Filled",
        100.0,
        100.0,
        1,
        50.0,
        True,
        50.0,
    )
    mock_conn.execute.return_value = mock_result

    result = database_service.get_order_status(1)
    assert result.order_id == 1
    assert result.user_name == "user1"
    assert result.status == "Partially Filled"


def test_get_order_status_not_found(
    database_service, mock_engine
):  # pylint: disable=redefined-outer-name
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_result = MagicMock()
    mock_result.fetchone.return_value = None
    mock_conn.execute.return_value = mock_result

    result = database_service.get_order_status(999)
    assert result is None


def test_get_orders(
    database_service, mock_engine
):  # pylint: disable=redefined-outer-name
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_result = MagicMock()
    now = datetime.now()
    mock_result.fetchall.return_value = [
        (
            2,
            now,
            "user1",
            "MSFT",
            "sell",
            "limit",
            "New",
            200.0,
            200.0,
            2,
            200.0,
            True,
            0.0,
        ),
        (
            1,
            now,
            "user1",
            "AAPL",
            "buy",
            "limit",
            "Partially Filled",
            100.0,
            100.0,
            1,
            50.0,
            True,
            50.0,
        ),
    ]
    mock_conn.execute.return_value = mock_result

    result = database_service.get_orders(1)
    assert len(result) == 2
    assert result[0].order_id == 2
    assert result[1].order_id == 1
