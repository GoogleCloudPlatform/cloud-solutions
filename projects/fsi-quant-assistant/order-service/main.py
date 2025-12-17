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

"""Main module for the Order Gateway API."""

import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from model.Balance import Balance
from model.BestBidOffer import BestBidOffer
from model.DepositRequest import DepositRequest
from model.DepositResult import DepositResult
from model.LastSale import LastSale
from model.Order import Order
from model.OrderBookEntry import OrderBookEntry
from model.OrderResult import OrderResult
from model.OrderState import OrderState
from processing.Execution import (
    deposit_funds,
    get_balances,
    get_bbo,
    get_last_sale,
    get_order_book,
    get_order_status,
    get_orders,
    place_order,
)

load_dotenv()

app = FastAPI(
    title="Order Gateway API",
    description=(
        "Order Gateway API for placing orders and managing user accounts."
    ),
    version="0.0.1",
)


@app.post(
    "/users/{user_name}/deposit",
    response_model=DepositResult,
    response_model_exclude_none=True,
    summary="Deposit funds into a user's account",
    description="Deposit funds into a user's account.",
)
async def deposit_funds_endpoint(user_name: str, request: DepositRequest):
    return deposit_funds(user_name, request)


@app.get(
    "/users/{user_name}/orders",
    response_model=list[OrderState],
    response_model_exclude_none=True,
    summary="Get a list of orders for a specific user",
    description="Get a list of orders for a specific user.",
)
async def get_orders_endpoint(user_name: str):
    return get_orders(user_name)


@app.get(
    "/users/{user_name}/balances",
    response_model=list[Balance],
    response_model_exclude_none=True,
    summary="Get a list of balances for a specific user",
    description="Get a list of balances for a specific user.",
)
async def get_balances_endpoint(user_name: str):
    return get_balances(user_name)


@app.post(
    "/orders",
    response_model=OrderResult,
    response_model_exclude_none=True,
    summary="Place a new order",
    description="Place a new order.",
)
async def create_order_endpoint(order: Order):
    return place_order(order)


@app.get(
    "/orders/{order_id}",
    response_model=OrderState,
    response_model_exclude_none=True,
    summary="Get the status of a specific order",
    description="Get the status of a specific order.",
)
async def get_order_status_endpoint(order_id: int):
    status = get_order_status(order_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return status


@app.get(
    "/market/bbo/{symbol}",
    response_model=BestBidOffer,
    response_model_exclude_none=False,
    summary="Get the best bid and offer for a specific symbol",
    description="Get the best bid and offer for a specific symbol.",
)
async def get_bbo_endpoint(symbol: str):
    bbo = get_bbo(symbol)
    if bbo is None:
        return BestBidOffer(symbol=symbol)
    return bbo


@app.get(
    "/market/last-sale/{symbol}",
    response_model=LastSale,
    response_model_exclude_none=False,
    summary="Get the last sale for a specific symbol",
    description="Get the last sale for a specific symbol.",
)
async def get_last_sale_endpoint(symbol: str):
    last_sale = get_last_sale(symbol)
    if last_sale is None:
        return LastSale(symbol=symbol)
    return last_sale


@app.get(
    "/market/order-book/{symbol}",
    response_model=list[OrderBookEntry],
    response_model_exclude_none=True,
    summary="Get the order book for a specific symbol",
    description="Get the order book for a specific symbol.",
)
async def get_order_book_endpoint(symbol: str):
    return get_order_book(symbol)


@app.get("/health", summary="Health check", description="Health check.")
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8090)),
        reload=True,
    )
