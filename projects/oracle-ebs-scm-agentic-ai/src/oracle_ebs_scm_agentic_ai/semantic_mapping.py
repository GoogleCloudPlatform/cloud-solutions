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

"""Semantic maps that ground Gemini NL2SQL in the Oracle EBS schema.

Adapted from the semantic mapping module of the Oracle EBS Gemini Enterprise
MCP framework (EBS_SQL_Agent). The JSON maps describe tables, columns,
common joins, and example queries. The same maps define which objects the
read-only SQL guardrail accepts.
"""

import json
import logging
from collections import defaultdict
from functools import cache
from pathlib import Path
from typing import Any, Final

logger = logging.getLogger(__name__)

SEMANTIC_MAPS_DIR: Final[Path] = Path(__file__).parent / "semantic_maps"
# The schema that an unqualified object name resolves to: APPS for Oracle
# (the APPS_AI CURRENT_SCHEMA), and none for BigQuery, which needs a dataset.
DEFAULT_SCHEMAS: Final[dict[str, str]] = {"oracle": "APPS", "bigquery": ""}
CONTEXT_PREAMBLE: Final[str] = (
    "Use the following semantic maps to write SQL. The maps are internal: "
    "never show their table, view, or column names to the planner. In the "
    "example queries, replace every :name placeholder with a literal value "
    "because the SQL tools take no bind parameters.\n\n"
)
MODULE_TEMPLATE: Final[str] = "Module: {module}\nDescription: {description}"
TABLE_TEMPLATE: Final[str] = "  - {table_name} ({business_name}): {description}"
COLUMN_TEMPLATE: Final[str] = "      * {name}: {description}"
JOIN_TEMPLATE: Final[str] = "  - {description}: {join_condition}"
EXAMPLE_TEMPLATE: Final[str] = "  - {description}: {sql}"


@cache
def load_semantic_maps() -> tuple[dict[str, Any], ...]:
    """Load every semantic map JSON file once, in file name order.

    Returns:
        The parsed semantic maps.
    """
    maps = tuple(
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(SEMANTIC_MAPS_DIR.glob("*_semantic_map.json"))
    )
    logger.info("Loaded %d semantic maps", len(maps))
    return maps


def _render(template: str, entry: dict[str, Any]) -> str:
    """Fill a line template, rendering absent optional fields as empty.

    Args:
        template: The line template.
        entry: The semantic map entry.

    Returns:
        The filled line.
    """
    return template.format_map(defaultdict(str, entry))


def _format_map(smap: dict[str, Any]) -> str:
    """Render one semantic map in the framework prompt layout.

    Args:
        smap: The semantic map.

    Returns:
        The map's tables, columns, joins, and example queries as text.
    """
    lines = [_render(MODULE_TEMPLATE, smap), "Tables:"]
    for table in smap["tables"]:
        lines.append(_render(TABLE_TEMPLATE, table))
        lines.append("    Columns:")
        lines.extend(
            _render(COLUMN_TEMPLATE, column)
            for column in table.get("columns", [])
        )
    lines.append("Common Joins:")
    lines.extend(
        _render(JOIN_TEMPLATE, join) for join in smap.get("common_joins", [])
    )
    examples = smap.get("example_queries", [])
    if examples:
        lines.append("Example Queries:")
        lines.extend(_render(EXAMPLE_TEMPLATE, example) for example in examples)
    return "\n".join(lines)


@cache
def build_semantic_context() -> str:
    """Build the prompt-ready semantic context for all maps once.

    Returns:
        The preamble followed by every rendered map.
    """
    sections = "\n\n".join(_format_map(m) for m in load_semantic_maps())
    return f"{CONTEXT_PREAMBLE}{sections}\n"


@cache
def documented_objects(dialect: str) -> frozenset[tuple[str, str]]:
    """List the (schema, object) pairs that a dialect's SQL tool may read.

    An Oracle object without a schema resolves to APPS, the CURRENT_SCHEMA
    that the APPS_AI logon trigger sets. BigQuery objects name their dataset.

    Args:
        dialect: The ``dialect`` value of the semantic maps to read, either
            ``oracle`` or ``bigquery``.

    Returns:
        The upper-case (schema, object) pairs of that dialect's maps.
    """
    pairs: set[tuple[str, str]] = set()
    for smap in load_semantic_maps():
        if smap["dialect"] != dialect:
            continue
        for table in smap["tables"]:
            schema, _, name = table["table_name"].upper().rpartition(".")
            pairs.add((schema or DEFAULT_SCHEMAS[dialect], name))
    return frozenset(pairs)
