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

"""RejectReason enum module."""

from enum import Enum


class RejectReason(str, Enum):
    LIMIT_MISSING_PRICE = "Limit order must have a price"
    MARKET_WITH_PRICE = "Market order must not have a price"
    INVALID_SIZE = "Order size must be greater than 0"
    NONE = "Valid"
    UNKNOWN = "Unknown reason"
