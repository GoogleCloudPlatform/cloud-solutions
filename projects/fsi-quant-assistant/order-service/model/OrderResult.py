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

"""OrderResult model module."""

from model.enum.OrderStatus import OrderStatus
from model.Fill import Fill
from model.Offer import Offer
from model.Order import Order


class OrderResult(Order):
    """Result of an order placement or execution."""

    orderId: str | None
    status: OrderStatus
    reason: str | None
    fills: list[Fill] = []
    new_offer: Offer | None = None

    def __init__(self, order: Order, **kwargs):
        if order:
            order_data = order.model_dump()
            for key, value in order_data.items():
                if key not in kwargs:
                    kwargs[key] = value
        super().__init__(**kwargs)
