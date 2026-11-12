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

"""Tests for the semantic maps that ground NL2SQL and the SQL allowlist."""

from collections.abc import Iterator
from typing import Any

import pytest
import sqlglot
from oracle_ebs_scm_agentic_ai import semantic_mapping
from sqlglot import exp

CUSTOM_MAPS: tuple[dict[str, Any], ...] = (
    {
        "module": "Test Oracle",
        "description": "Oracle test map",
        "dialect": "oracle",
        "tables": [
            {"table_name": "vw_test_view", "description": "View"},
            {
                "table_name": "inv.mtl_test",
                "business_name": "Items",
                "description": "Table",
                "columns": [{"name": "ITEM_ID", "description": "Item"}],
            },
        ],
    },
    {
        "module": "Test BigQuery",
        "description": "BigQuery test map",
        "dialect": "bigquery",
        "tables": [{"table_name": "test_ds.signals", "description": "View"}],
        "common_joins": [
            {"description": "Join", "join_condition": "a.id = b.id"}
        ],
    },
)


@pytest.fixture(name="custom_maps")
def fixture_custom_maps(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Serve the custom maps instead of the files, with fresh caches."""
    monkeypatch.setattr(
        semantic_mapping, "load_semantic_maps", lambda: CUSTOM_MAPS
    )
    semantic_mapping.documented_objects.cache_clear()
    semantic_mapping.build_semantic_context.cache_clear()
    yield
    semantic_mapping.documented_objects.cache_clear()
    semantic_mapping.build_semantic_context.cache_clear()


def test_semantic_maps_cover_framework_and_scm_modules() -> None:
    modules = [smap["module"] for smap in semantic_mapping.load_semantic_maps()]
    assert len(modules) == 5
    assert "Inventory (INV)" in modules
    assert "Purchasing (PO)" in modules
    oracle = semantic_mapping.documented_objects("oracle")
    bigquery = semantic_mapping.documented_objects("bigquery")
    for name in (
        "VW_SCM_NET_AVAILABILITY",
        "VW_SCM_SLA_CONTRACT_LOCKS",
        "VW_SCM_OPEN_NOTIFICATIONS",
        "VW_SCM_ACTIVE_POS",
        "VW_SCM_APPROVED_SUPPLIERS",
        "MTL_SYSTEM_ITEMS_B",
    ):
        assert ("APPS", name) in oracle
    for name in (
        "TIMESFM_HUB_BURN_FORECAST",
        "HUB_SEARCH_SIGNALS",
        "HUB_MARKET_AREAS",
        "FREIGHT_LANE_RATES",
    ):
        assert ("EBS_SCM_AGENTIC_AI", name) in bigquery
    assert not {name for _, name in oracle} & {name for _, name in bigquery}
    assert "STOCKOUT_MITIGATION_ROI_RANKING" not in str(oracle | bigquery)
    assert "TRANSIT_CORRIDOR_ECONOMICS" not in str(oracle | bigquery)


def test_semantic_context_renders_tables_joins_and_examples() -> None:
    context = semantic_mapping.build_semantic_context()
    assert context.startswith(semantic_mapping.CONTEXT_PREAMBLE)
    assert "Module: Supply Chain Resiliency (Oracle EBS APPS views)" in context
    assert "Common Joins:" in context
    assert "detection_gap_days" in context
    assert "R12" not in context


def test_every_map_declares_its_dialect() -> None:
    dialects = {
        smap["dialect"] for smap in semantic_mapping.load_semantic_maps()
    }
    assert dialects == {"oracle", "bigquery"}


def test_oracle_examples_read_only_documented_columns() -> None:
    """Oracle examples read only the columns that the maps document.

    The documented columns match the Oracle EBS R12.2 data dictionary, so an
    example that reads only those columns can't fail with ORA-00904.
    """
    maps = [
        smap
        for smap in semantic_mapping.load_semantic_maps()
        if smap["dialect"] == "oracle"
    ]
    documented: dict[str, set[str]] = {}
    for smap in maps:
        for table in smap["tables"]:
            name = table["table_name"].rpartition(".")[2].upper()
            documented.setdefault(name, set()).update(
                column["name"].upper() for column in table["columns"]
            )
    for smap in maps:
        for example in smap["example_queries"]:
            tree = sqlglot.parse_one(example["sql"], read="oracle")
            tables = {
                (table.alias or table.name).upper(): table.name.upper()
                for table in tree.find_all(exp.Table)
            }
            for column in tree.find_all(exp.Column):
                table_name = tables.get(column.table.upper(), "")
                if table_name in documented:
                    assert column.name.upper() in documented[table_name], (
                        example["description"],
                        column.sql(),
                    )


@pytest.mark.usefixtures("custom_maps")
def test_documented_objects_qualify_names_per_dialect() -> None:
    assert semantic_mapping.documented_objects("oracle") == {
        ("APPS", "VW_TEST_VIEW"),
        ("INV", "MTL_TEST"),
    }
    assert semantic_mapping.documented_objects("bigquery") == {
        ("TEST_DS", "SIGNALS")
    }
    assert semantic_mapping.documented_objects("postgres") == frozenset()


@pytest.mark.usefixtures("custom_maps")
def test_semantic_context_renders_missing_fields_as_empty() -> None:
    context = semantic_mapping.build_semantic_context()
    assert "  - vw_test_view (): View" in context
    assert "  - inv.mtl_test (Items): Table" in context
    assert "      * ITEM_ID: Item" in context
    assert "  - Join: a.id = b.id" in context
    assert "Example Queries:" not in context
