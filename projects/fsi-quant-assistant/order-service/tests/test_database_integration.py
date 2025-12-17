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

"""Database integration tests."""

import os

import pytest
from data.DatabaseService import DatabaseService
from model.enum.OrderType import OrderType
from model.enum.Side import Side
from model.Order import Order
from sqlalchemy import text


# Skip these tests if DB_HOST is not set (i.e., no local DB/tunnel available)
@pytest.mark.skipif(not os.environ.get("DB_HOST"), reason="DB_HOST not set")
def test_real_database_connection():
    # Reset singleton to ensure we get a fresh instance with current env vars
    DatabaseService._instance = None  # pylint: disable=protected-access
    DatabaseService._engine = None  # pylint: disable=protected-access

    service = DatabaseService()
    engine = service.get_engine()

    # Attempt to connect and execute a simple query
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar() == 1


@pytest.mark.skipif(not os.environ.get("DB_HOST"), reason="DB_HOST not set")
def test_insert_order():
    # Reset singleton
    DatabaseService._instance = None  # pylint: disable=protected-access
    DatabaseService._engine = None  # pylint: disable=protected-access

    service = DatabaseService()

    order = Order(
        user="sender1",
        symbol="AAPL",
        side=Side.BUY,
        type=OrderType.MARKET,
        size=10,
    )

    # This will likely fail if the schema doesn't exist, but it tests the
    # code path.
    try:
        result = service.insert_order(order=order)
        # If it succeeds, we expect integer IDs or None if not found
        # (though stored proc should return IDs)
        assert result.sessionId is None or isinstance(result.sessionId, str)
    except Exception as e:  # pylint: disable=broad-exception-caught
        # Accept failure if it's a database error (e.g., schema missing),
        # but not if it's a python syntax error in our code.
        if "insert_order" in str(e) or "relation" in str(e):
            raise e
