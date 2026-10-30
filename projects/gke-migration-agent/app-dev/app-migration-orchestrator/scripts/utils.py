# Copyright 2026 Google LLC
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
"""Shared utility functions for preflight validation scripts."""

import json
import logging
import os
from pathlib import Path

import jsonschema

logger = logging.getLogger("validate_platform_readiness")


def load_json(file_path: Path) -> dict:
    """Loads JSON file from disk.

    Args:
        file_path: Path to the JSON file to load.

    Returns:
        Dictionary containing the JSON data.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("File not found: %s", file_path)
        raise
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JSON in %s: %s", file_path, e)
        raise


def validate_schema(data: dict, schema_path: Path) -> None:
    """Validates the handoff data against JSON schema.

    Args:
        data: The handoff data to validate.
        schema_path: Path to the schema file to validate against.

    Raises:
        SystemExit(1): If schema validation fails or schema path is invalid.
    """
    if not schema_path.exists():
        logger.error(
            "Schema file not found at '%s'. Check file path.", schema_path
        )
        raise SystemExit(1)

    schema = load_json(schema_path)

    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.exceptions.ValidationError as e:
        logger.error(
            "Schema validation failed for data against '%s':\n%s",
            schema_path.name,
            e.message,
        )
        raise SystemExit(1) from e


def find_file_recursively(directory: Path, filename: str) -> Path | None:
    """Recursively searches for a file in the directory and its subdirectories.

    Returns the first matching file Path found, or None.
    """
    for root, dirs, files in os.walk(directory):
        # Ignore hidden directories (e.g. .terraform, .git)
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        if filename in files:
            return Path(root) / filename
    return None


def find_any_file_recursively(
    directory: Path, filenames: list[str]
) -> Path | None:
    """Recursively searches for any of the filenames in the directory.

    Returns the first matching file Path found, or None.
    """
    for name in filenames:
        found = find_file_recursively(directory, name)
        if found:
            return found
    return None
