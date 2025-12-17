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

"""Execution tests module."""

import pytest
from model.enum.OrderType import OrderType
from model.enum.RejectReason import RejectReason
from model.enum.Side import Side
from model.Order import Order
from processing.Execution import validate_order


@pytest.fixture
def base_order():
    return Order(
        user="user1",
        symbol="AAPL",
        side=Side.BUY,
        type=OrderType.LIMIT,
        size=10,
        price=100.0,
    )


def test_validate_order_valid_limit(
    base_order,
):  # pylint: disable=redefined-outer-name
    validation = validate_order(base_order)
    assert validation.isValid
    assert validation.reason == RejectReason.NONE


def test_validate_order_invalid_limit_no_price(
    base_order,
):  # pylint: disable=redefined-outer-name
    base_order.price = None
    validation = validate_order(base_order)
    assert not validation.isValid
    assert validation.reason == RejectReason.LIMIT_MISSING_PRICE


def test_validate_order_valid_market(
    base_order,
):  # pylint: disable=redefined-outer-name
    base_order.type = OrderType.MARKET
    base_order.price = None
    validation = validate_order(base_order)
    assert validation.isValid
    assert validation.reason == RejectReason.NONE


def test_validate_order_invalid_market_with_price(
    base_order,
):  # pylint: disable=redefined-outer-name
    base_order.type = OrderType.MARKET
    base_order.price = 100.0
    validation = validate_order(base_order)
    assert not validation.isValid
    assert validation.reason == RejectReason.MARKET_WITH_PRICE


def test_validate_order_invalid_size(
    base_order,
):  # pylint: disable=redefined-outer-name
    base_order.size = 0
    validation = validate_order(base_order)
    assert not validation.isValid
    assert validation.reason == RejectReason.INVALID_SIZE
