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

"""Helper utilities for initializing and updating the markdown report."""

import datetime
import os
import shutil

from config import ANALYSIS_PATH, TEMPLATE_PATH, MigrationError


def initialize_report_from_template() -> None:
    """Initializes the migration report file from the master markdown template.

    Copies the report template to the target output directory and populates
    the timestamp placeholder with the current date and time.

    Raises:
        MigrationError: If the master report template file does not exist.
    """
    if not os.path.exists(TEMPLATE_PATH):
        raise MigrationError(f"Master template missing: {TEMPLATE_PATH}")
    os.makedirs(os.path.dirname(ANALYSIS_PATH), exist_ok=True)
    shutil.copyfile(TEMPLATE_PATH, ANALYSIS_PATH)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    update_report_placeholder("[Dynamic Date/Time]", timestamp)


def update_report_placeholder(placeholder: str, content: str) -> None:
    """Replaces a placeholder string in the report file with new content.

    If the report file does not exist at ANALYSIS_PATH, this function
    returns silently without taking any action.

    Args:
        placeholder: The exact text string or token to search for and replace.
        content: The replacement text to insert in place of the placeholder.
    """
    if not os.path.exists(ANALYSIS_PATH):
        return
    with open(ANALYSIS_PATH, "r", encoding="utf-8") as f:
        file_text = f.read()
    with open(ANALYSIS_PATH, "w", encoding="utf-8") as f:
        f.write(file_text.replace(placeholder, content))
