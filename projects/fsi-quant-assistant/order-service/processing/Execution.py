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

"""Execution logic for order processing."""

from data.DatabaseService import DatabaseService
from model.Balance import Balance
from model.BestBidOffer import BestBidOffer
from model.DepositRequest import DepositRequest
from model.DepositResult import DepositResult
from model.enum.OrderStatus import OrderStatus
from model.enum.OrderType import OrderType
from model.enum.RejectReason import RejectReason
from model.LastSale import LastSale
from model.Order import Order
from model.OrderBookEntry import OrderBookEntry
from model.OrderResult import OrderResult
from model.OrderState import OrderState
from model.OrderValidation import OrderValidation


def place_order(order: Order) -> OrderResult:
    orderValidation = validate_order(order)
    if not orderValidation.isValid:
        return OrderResult(
            order=order,
            orderId=None,
            status=OrderStatus.REJECTED,
            reason=orderValidation.reason,
        )

    db_service = DatabaseService()
    return db_service.insert_order(order)


def deposit_funds(user_name: str, request: DepositRequest) -> DepositResult:
    db_service = DatabaseService()
    return db_service.deposit_funds(user_name, request)


def get_order_status(order_id: int) -> OrderState | None:
    db_service = DatabaseService()
    return db_service.get_order_status(order_id)


def get_orders(user_name: str) -> list[OrderState]:
    db_service = DatabaseService()
    return db_service.get_orders(user_name)


def get_balances(user_name: str) -> list[Balance]:
    db_service = DatabaseService()
    return db_service.get_balances(user_name)


def get_bbo(symbol: str) -> BestBidOffer | None:
    db_service = DatabaseService()
    return db_service.get_bbo(symbol)


def get_last_sale(symbol: str) -> LastSale | None:
    db_service = DatabaseService()
    return db_service.get_last_sale(symbol)


def get_order_book(symbol: str) -> list[OrderBookEntry]:
    db_service = DatabaseService()
    return db_service.get_order_book(symbol)


def validate_order(order: Order) -> OrderValidation:
    if order.type == OrderType.LIMIT and order.price is None:
        return OrderValidation(
            isValid=False, reason=RejectReason.LIMIT_MISSING_PRICE
        )
    if order.type == OrderType.MARKET and order.price is not None:
        return OrderValidation(
            isValid=False, reason=RejectReason.MARKET_WITH_PRICE
        )
    if order.size <= 0:
        return OrderValidation(isValid=False, reason=RejectReason.INVALID_SIZE)
    return OrderValidation(isValid=True, reason=RejectReason.NONE)
