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


# pylint: disable=C0114, C0301
import os

from dotenv import load_dotenv

load_dotenv()

def get_required_env_var(var_name: str) -> str:
    """Gets a required environment variable or raises a clear exception."""
    value = os.getenv(var_name)
    if value is None:
        raise ValueError(f"Environment variable '{var_name}' is missing and is required.")
    return value


def get_optional_env_var(var_name: str, default_val: str) -> str:
    """Gets an optional environment variable or returns default."""
    value = os.getenv(var_name)
    return value or default_val
