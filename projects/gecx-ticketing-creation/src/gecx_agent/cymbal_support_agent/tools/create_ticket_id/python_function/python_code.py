# Copyright 2026 Google LLC
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



# pylint: skip-file
"""Module containing GECX python code logic."""
import time

# Best Practice: Use a fixed custom epoch (Jan 1, 2026) to future-proof 32-bit limits.
# 1767225600 is the UNIX timestamp for 2026-01-01 00:00:00 UTC.
CUSTOM_EPOCH = 1767225600


def create_ticket_id() -> str:
    """Generates an exactly 8-character uppercase hex string from the current time.

    This function is future-proofed against 32-bit overflow until the year 2162.
    """
    # 1. Get current UNIX timestamp in seconds
    current_time = int(time.time())

    # 2. Calculate offset from custom epoch to stay well under the 32-bit limit
    elapsed_seconds = current_time - CUSTOM_EPOCH

    # 3. Format to exactly 8 characters with zero-padding
    hex_string = f"{elapsed_seconds:08X}"

    # 4. Defensive Guard: Ensure it is exactly 8 characters before returning
    if len(hex_string) > 8:
        raise OverflowError("Timestamp delta exceeds 8-character hex capacity.")

    return hex_string
