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

"""Deposit tests module."""

from unittest.mock import patch

from fastapi.testclient import TestClient
from main import app
from model.DepositResult import DepositBalance, DepositResult

client = TestClient(app)


def test_deposit_funds_success():
    mock_result = DepositResult(
        status="SUCCESS",
        transaction_id=123,
        user="Mark",
        symbol="USD",
        deposited=1000.0,
        new_balance=DepositBalance(available=1000.0, locked=0.0, total=1000.0),
    )

    with patch("main.deposit_funds", return_value=mock_result) as mock_deposit:
        response = client.post(
            "/users/Mark/deposit", json={"amount": 1000.0, "symbol": "USD"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "SUCCESS"
        assert data["transaction_id"] == 123
        assert data["new_balance"]["total"] == 1000.0

        # Verify call arguments
        # We can't easily verify the Pydantic object equality directly without
        # more complex matching,
        # but we can verify it was called.
        assert mock_deposit.called


def test_deposit_funds_error():
    mock_result = DepositResult(
        status="ERROR", reason="Amount must be positive"
    )

    with patch(
        "main.deposit_funds", return_value=mock_result
    ) as mock_deposit:  # pylint: disable=unused-variable
        response = client.post(
            "/users/Mark/deposit", json={"amount": -100.0, "symbol": "USD"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ERROR"
        assert data["reason"] == "Amount must be positive"
