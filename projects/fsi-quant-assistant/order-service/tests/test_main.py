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

"""Main tests module."""

from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient
from main import app
from model.enum.OrderStatus import OrderStatus
from model.enum.OrderType import OrderType
from model.enum.Side import Side
from model.Order import Order
from model.OrderResult import OrderResult
from model.OrderState import OrderState

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_order():
    with patch("main.place_order") as mock_place_order:
        mock_place_order.return_value = OrderResult(
            order=Order(
                user="user1",
                symbol="AAPL",
                side=Side.BUY,
                type=OrderType.LIMIT,
                size=10,
                price=100.0,
            ),
            orderId="123",
            status=OrderStatus.ACCEPTED,
            reason=None,
        )

        order_data = {
            "user": "user1",
            "symbol": "AAPL",
            "side": "BUY",
            "type": "LIMIT",
            "size": 10,
            "price": 100.0,
        }
        response = client.post("/orders", json=order_data)
        assert response.status_code == 200
        data = response.json()
        assert data["orderId"] == "123"
        assert data["status"] == "Accepted"
        assert "reason" not in data


def test_get_order_status_found():
    with patch("main.get_order_status") as mock_get_order_status:
        mock_get_order_status.return_value = OrderState(
            order_id=1,
            created=datetime.now(),
            user_name="user1",
            symbol="AAPL",
            side="buy",
            type="limit",
            status="Partially Filled",
            order_price=100.0,
            total_qty=100.0,
            offer_id=1,
            remaining_open_qty=50.0,
            is_active_on_book=True,
            calculated_filled_qty=50.0,
        )
        response = client.get("/orders/1")
        assert response.status_code == 200
        data = response.json()
        assert data["order_id"] == 1
        assert data["status"] == "Partially Filled"


def test_get_order_status_not_found():
    with patch("main.get_order_status") as mock_get_order_status:
        mock_get_order_status.return_value = None
        response = client.get("/orders/999")
        assert response.status_code == 404


def test_get_orders():
    with patch("main.get_orders") as mock_get_orders:
        mock_get_orders.return_value = [
            OrderState(
                order_id=1,
                created=datetime.now(),
                user_name="user1",
                symbol="AAPL",
                side="buy",
                type="limit",
                status="Partially Filled",
                order_price=100.0,
                total_qty=100.0,
                offer_id=1,
                remaining_open_qty=50.0,
                is_active_on_book=True,
                calculated_filled_qty=50.0,
            )
        ]
        response = client.get("/users/user1/orders")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["order_id"] == 1
        assert data[0]["status"] == "Partially Filled"


def test_get_signed_size_buy():
    order = Order(
        user="user1",
        symbol="AAPL",
        side=Side.BUY,
        type=OrderType.MARKET,
        size=10,
        price=150.0,
    )
    assert order.getSignedSize() == 10


def test_get_signed_size_sell():
    order = Order(
        user="user1",
        symbol="AAPL",
        side=Side.SELL,
        type=OrderType.LIMIT,
        size=5,
        price=150.0,
    )
    assert order.getSignedSize() == -5


def test_get_signed_size_large_numbers():
    order = Order(
        user="user1",
        symbol="AAPL",
        side=Side.BUY,
        type=OrderType.MARKET,
        size=1000000,
        price=150.0,
    )
    assert order.getSignedSize() == 1000000

    order = Order(
        user="user1",
        symbol="AAPL",
        side=Side.SELL,
        type=OrderType.LIMIT,
        size=1000000,
        price=150.0,
    )
    assert order.getSignedSize() == -1000000
