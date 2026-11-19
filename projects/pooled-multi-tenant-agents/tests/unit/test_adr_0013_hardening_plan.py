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

# pylint: disable=line-too-long

"""Tests for ADR-0013 and the runtime failure mode hardening plan."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ADR_README_PATH = REPO_ROOT / "docs" / "adr" / "README.md"
ADR_0013_PATH = (
    REPO_ROOT
    / "docs"
    / "adr"
    / "0013-runtime-failure-modes-and-hardening-plan.md"
)
TDD_0013_PATH = (
    REPO_ROOT / "docs" / "tdd_runtime_failure_modes_and_hardening_plan.md"
)
if not TDD_0013_PATH.is_file():
    pytest.skip(
        "Internal TDD omitted from public export.", allow_module_level=True
    )


@pytest.mark.parametrize(
    "failure_mode", [f"FM-{idx:02d}" for idx in range(1, 13)]
)
def test_adr_0013_and_tdd_cover_all_twelve_failure_modes(
    failure_mode: str,
) -> None:
    """Both ADR-0013 and the TDD must document FM-01 through FM-12."""
    adr_text = ADR_0013_PATH.read_text(encoding="utf-8")
    tdd_text = TDD_0013_PATH.read_text(encoding="utf-8")

    assert failure_mode in adr_text
    assert failure_mode in tdd_text


def test_adr_readme_indexes_adr_0013() -> None:
    """docs/adr/README.md must list ADR-0013."""
    readme_text = ADR_README_PATH.read_text(encoding="utf-8")
    assert "0013-runtime-failure-modes-and-hardening-plan.md" in readme_text


def test_adr_0013_and_tdd_map_pr_da1_to_pr26_and_pr25_with_exact_symbols() -> (
    None
):
    """PR-DA1 must point to #26 and #25 with exact symbol and test references."""
    adr_text = ADR_0013_PATH.read_text(encoding="utf-8")
    tdd_text = TDD_0013_PATH.read_text(encoding="utf-8")

    assert "`PR-DA1` (`#26` + `#25`)" in adr_text
    assert "`PR-DA1` (`#26` + `#25`)" in tdd_text
    for expected_ref in (
        "app/gateway_tokens.py:105-188",
        "verify_request()",
        "_metering(req)",
        "_LIVE_MA_RETRY_AT",
        "E_MODEL_ARMOR_REQUEST_REJECTED",
        "test_live_cloud_permission_error_returns_403_and_non_sandbox_outage_returns_503",
        "test_bulkhead_reports_the_effective_thinking_budget",
        "test_live_sql_only_references_columns_in_schema",
    ):
        assert expected_ref in tdd_text


def test_adr_0013_and_tdd_omit_meta_prompt_jargon() -> None:
    """ADR-0013 and the TDD must not include internal meta-prompt terms."""
    combined_text = (
        ADR_0013_PATH.read_text(encoding="utf-8")
        + "\n"
        + TDD_0013_PATH.read_text(encoding="utf-8")
    ).lower()

    for forbidden_term in (
        "devil's advocate",
        "devils_advocate",
        "goldfish",
        "elephant",
        "zero-decision rule",
    ):
        assert forbidden_term not in combined_text
