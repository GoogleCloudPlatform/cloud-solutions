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

"""Order model module."""

from model.enum.OrderType import OrderType
from model.enum.Side import Side
from pydantic import BaseModel


class Order(BaseModel):
    user: str
    symbol: str
    side: Side
    type: OrderType
    size: int
    price: float | None = None

    def getSignedSize(self) -> int:
        return self.size if self.side == Side.BUY else -self.size
