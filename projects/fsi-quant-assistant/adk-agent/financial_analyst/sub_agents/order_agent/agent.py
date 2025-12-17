# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Order agent module."""
import base64
import json
import logging
import os
import time

import google.auth
import requests
from google.adk.agents.llm_agent import Agent
from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2 import id_token

from .prompt import ORDER_AGENT_PROMPT

ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL")
ENABLE_ORDER_SERVICE_ID_TOKEN_AUTH = (
    os.getenv("ENABLE_ORDER_SERVICE_ID_TOKEN_AUTH", "false").lower() == "true"
)

_token_cache = {}


def get_auth_headers(url: str) -> dict:
    """
    Get the authentication headers for the request, with caching.

    Args:
        url: The URL to get the ID token for.

    Returns:
        A dictionary containing the authentication headers.
    """
    if not ENABLE_ORDER_SERVICE_ID_TOKEN_AUTH:
        return {}

    # Check cache
    if url in _token_cache:
        logging.info("Using cached token for URL: %s", url)
        token_data = _token_cache[url]
        if token_data["expiry"] > time.time() + 60:  # Buffer of 60 seconds
            # Use single quotes for inner dict access to be consistent
            # or extract the value if nested quotes are problematic
            token_val = token_data["token"]
            return {"Authorization": f"Bearer {token_val}"}

    try:
        token = None
        logging.info("Fetching ID token for URL: %s", url)
        # 1. Try fetch_id_token (Service Account / Metadata Server)
        try:
            auth_req = Request()
            token = id_token.fetch_id_token(auth_req, url)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging.warning("fetch_id_token failed: %s. Trying fallback...", e)

            # 2. Try fallback (User Credentials)
            credentials, _ = google.auth.default()
            session = AuthorizedSession(credentials)
            request = Request(session)
            credentials.refresh(request)
            if hasattr(credentials, "id_token"):
                token = getattr(credentials, "id_token", None)

        if token:
            # Decode token to get expiry
            # JWT is header.payload.signature
            payload = token.split(".")[1]
            # Add padding if needed
            payload += "=" * (-len(payload) % 4)
            decoded_payload = json.loads(
                base64.b64decode(payload).decode("utf-8")
            )
            expiry = decoded_payload.get("exp", 0)

            _token_cache[url] = {"token": token, "expiry": expiry}
            return {"Authorization": f"Bearer {token}"}

    except Exception as e:  # pylint: disable=broad-exception-caught
        logging.error("Failed to get ID token for URL %s: %s", url, e)
        return {}

    return {}


def deposit_funds(user_name: str, amount: float, symbol: str = "USD") -> dict:
    """
    Deposit funds into a user's account.

    Args:
        user_name: The name of the user.
        amount: The amount to deposit.
        symbol: The currency symbol (default: USD).

    Returns:
        The result of the deposit operation.
    """
    url = f"{ORDER_SERVICE_URL}/users/{user_name}/deposit"
    payload = {"amount": amount, "symbol": symbol}
    logging.info("Depositing funds: %s", payload)
    response = requests.post(url, json=payload, headers=get_auth_headers(url))
    response.raise_for_status()
    return response.json()


def seed_stock(user_name: str, amount: float, symbol: str) -> dict:
    """
    Seed a stock into a user's account.

    Args:
        user_name: The name of the user.
        amount: The amount to deposit.
        symbol: The stock symbol.

    Returns:
        The result of the deposit operation.
    """
    url = f"{ORDER_SERVICE_URL}/users/{user_name}/deposit"
    payload = {"amount": amount, "symbol": symbol}
    logging.info("Depositing funds: %s", payload)
    response = requests.post(url, json=payload, headers=get_auth_headers(url))
    response.raise_for_status()
    return response.json()


def get_orders(user_name: str) -> list[dict]:
    """
    Get all orders for a specific user.

    Args:
        user_name: The name of the user.

    Returns:
        A list of orders for the user.
    """
    url = f"{ORDER_SERVICE_URL}/users/{user_name}/orders"
    logging.info("Getting orders for user: %s, URL: %s", user_name, url)
    response = requests.get(url, headers=get_auth_headers(url))
    response.raise_for_status()
    return response.json()


def get_balances(user_name: str) -> list[dict]:
    """
    Get the current balances for a specific user.

    Args:
        user_name: The name of the user.

    Returns:
        A list of balances for the user.
    """
    url = f"{ORDER_SERVICE_URL}/users/{user_name}/balances"
    logging.info("Getting balances for user: %s, URL: %s", user_name, url)
    response = requests.get(url, headers=get_auth_headers(url))
    response.raise_for_status()
    return response.json()


def place_order(
    user: str,
    symbol: str,
    side: str,
    order_type: str,
    size: int,
    price: str = "",
) -> dict:
    """
    Place a new order.

    Args:
        user: The name of the user placing the order.
        symbol: The symbol to trade (e.g., AAPL).
        side: The side of the order (BUY or SELL).
        order_type: The type of the order (MARKET or LIMIT).
        size: The quantity to trade.
        price: The price for LIMIT orders (optional for MARKET orders).

    Returns:
        The result of the order placement.
    """

    price_float = None
    if price and price != "":
        try:
            # Remove currency symbols and commas, then convert to float
            cleaned_price = str(price).replace("$", "").replace(",", "")
            price_float = float(cleaned_price)
        except ValueError:
            return (
                f"Invalid price format: {price}. "
                "Please provide a numeric value."
            )

    url = f"{ORDER_SERVICE_URL}/orders"
    payload = {
        "user": user,
        "symbol": symbol,
        "side": side,
        "type": order_type,
        "size": size,
        "price": price_float,
    }
    logging.info("Placing order: %s", payload)
    response = requests.post(url, json=payload, headers=get_auth_headers(url))
    response.raise_for_status()
    return response.json()


def get_order_status(order_id: int) -> dict:
    """
    Get the status of a specific order.

    Args:
        order_id: The ID of the order.

    Returns:
        The status and details of the order.
    """
    url = f"{ORDER_SERVICE_URL}/orders/{order_id}"
    logging.info("Getting order status for ID: %s, URL: %s", order_id, url)
    response = requests.get(url, headers=get_auth_headers(url))
    response.raise_for_status()
    return response.json()


def get_bbo(symbol: str) -> dict:
    """
    Get the Best Bid and Offer (BBO) for a symbol.

    Args:
        symbol: The symbol to get BBO for.

    Returns:
        The BBO data.
    """
    url = f"{ORDER_SERVICE_URL}/market/bbo/{symbol}"
    logging.info("Getting BBO for symbol: %s, URL: %s", symbol, url)
    response = requests.get(url, headers=get_auth_headers(url))
    response.raise_for_status()
    return response.json()


def get_last_sale(symbol: str) -> dict:
    """
    Get the last sale information for a symbol.

    Args:
        symbol: The symbol to get last sale for.

    Returns:
        The last sale data.
    """
    url = f"{ORDER_SERVICE_URL}/market/last-sale/{symbol}"
    logging.info("Getting last sale for symbol: %s, URL: %s", symbol, url)
    response = requests.get(url, headers=get_auth_headers(url))
    response.raise_for_status()
    return response.json()


def get_order_book(symbol: str) -> list[dict]:
    """
    Get the order book for a symbol.

    Args:
        symbol: The symbol to get the order book for.

    Returns:
        The order book entries.
    """
    url = f"{ORDER_SERVICE_URL}/market/order-book/{symbol}"
    logging.info("Getting order book for symbol: %s, URL: %s", symbol, url)
    response = requests.get(url, headers=get_auth_headers(url))
    response.raise_for_status()
    return response.json()


order_agent = Agent(
    name="order_agent",
    model="gemini-2.5-flash",
    description=(
        "Agent that can place orders for stocks, get the current portfolio, "
        "get the current watchlist, and get the current available cash."
    ),
    instruction=ORDER_AGENT_PROMPT,
    tools=[
        deposit_funds,
        seed_stock,
        get_orders,
        get_balances,
        place_order,
        get_order_status,
        get_bbo,
        get_last_sale,
        get_order_book,
    ],
)
