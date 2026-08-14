#  Copyright 2026 Google LLC
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""State manager to load, save, and clear migration checkpoints."""

import json
import logging
import os
from typing import Any, Dict

import config

STATE_FILE = os.path.join(config.SKILL_DIR, ".migration-state.json")


def load_state() -> Dict[str, Any]:
    """Loads migration state from the local state file."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logging.warning(
                "Failed to load migration state: %s. Starting fresh.", e
            )
    return {}


def save_state(state: Dict[str, Any]) -> None:
    """Saves the active migration state to the local state file."""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except OSError as e:
        logging.error("Failed to save migration state: %s", e)


def clear_state() -> None:
    """Removes the local migration state file."""
    if os.path.exists(STATE_FILE):
        try:
            os.remove(STATE_FILE)
        except OSError as e:
            logging.error("Failed to delete migration state file: %s", e)
