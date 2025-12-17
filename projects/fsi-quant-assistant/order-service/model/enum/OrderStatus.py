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

"""OrderStatus enum module."""

from enum import Enum


class OrderStatus(str, Enum):
    """Enum for order status."""

    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    REJECTED_INVALID_ARGS = "REJECTED_INVALID_ARGS"
    REJECTED_INSUFFICIENT_FUNDS = "REJECTED_INSUFFICIENT_FUNDS"
    REJECTED_INSUFFICIENT_POSITION = "REJECTED_INSUFFICIENT_POSITION"
    REJECTED_STP = "REJECTED_STP"
    FILLED = "FILLED"
    NO_LIQUIDITY = "NO_LIQUIDITY"
    PLACED = "PLACED"
    PARTIAL_IOC = "PARTIAL_IOC"
    PARTIAL = "PARTIAL"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"
