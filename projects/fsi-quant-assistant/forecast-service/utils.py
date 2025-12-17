"""Financial analyst utilities."""

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

import os


def is_env_flag_enabled(var_name: str) -> bool:
    """
    Checks if an environment variable is set to a "true" value.

    This is a case-insensitive check for the values 'true' or '1'.

    Args:
      var_name: The name of the environment variable to check.

    Returns:
      True if the variable is set to 'true' or '1', False otherwise.
    """
    value = os.getenv(var_name)

    if not value:
        return False

    return value.lower() in ("true", "1")
