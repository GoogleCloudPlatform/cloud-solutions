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

"""OrderState model module."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class OrderState(BaseModel):
    """State of an order."""

    order_id: int
    created: datetime
    user_name: str
    symbol: str
    side: str
    type: str
    status: str
    order_price: Optional[float] = None
    total_qty: float
    offer_id: Optional[int] = None
    remaining_open_qty: Optional[float] = None
    is_active_on_book: Optional[bool] = None
    calculated_filled_qty: float
