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

"""Balances tests module."""

from unittest.mock import patch

from fastapi.testclient import TestClient
from main import app
from model.Balance import Balance

client = TestClient(app)


def test_get_balances_endpoint():
    mock_balances = [
        Balance(
            user_name="Mark",
            symbol="AAPL",
            available=100.0,
            locked=10.0,
            total=110.0,
        ),
        Balance(
            user_name="Mark",
            symbol="GOOG",
            available=50.0,
            locked=0.0,
            total=50.0,
        ),
    ]

    with patch(
        "main.get_balances", return_value=mock_balances
    ) as mock_get_balances:
        response = client.get("/users/Mark/balances")
        assert response.status_code == 200
        assert len(response.json()) == 2
        assert response.json()[0]["user_name"] == "Mark"
        assert response.json()[0]["symbol"] == "AAPL"
        mock_get_balances.assert_called_once_with("Mark")


def test_get_balances_empty():
    with patch("main.get_balances", return_value=[]) as mock_get_balances:
        response = client.get("/users/Unknown/balances")
        assert response.status_code == 200
        assert response.json() == []
        mock_get_balances.assert_called_once_with("Unknown")
