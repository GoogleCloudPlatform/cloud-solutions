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

"""Tests for ADR-0012 and the compute scaling / workstream alignment TDD."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ADR_0012_PATH = (
    REPO_ROOT
    / "docs"
    / "adr"
    / "0012-compute-sandbox-scale-and-workstream-alignment.md"
)
TDD_0012_PATH = (
    REPO_ROOT / "docs" / "tdd_compute_sandbox_scale_and_workstream_alignment.md"
)
if not TDD_0012_PATH.is_file():
    pytest.skip(
        "Internal TDD omitted from public export.", allow_module_level=True
    )


@pytest.mark.parametrize("slice_id", ["PR-S1", "PR-S2", "PR-S3", "PR-S4"])
def test_adr_0012_and_tdd_cover_all_four_pr_slices(slice_id: str) -> None:
    """Both ADR-0012 and the TDD must document PR-S1 through PR-S4."""
    adr_text = ADR_0012_PATH.read_text(encoding="utf-8")
    tdd_text = TDD_0012_PATH.read_text(encoding="utf-8")

    assert slice_id in adr_text
    assert slice_id in tdd_text


def test_adr_0012_and_tdd_document_modelrouter_preconditions_and_canonical_roles() -> (
    None
):
    """ADR-0012 and the TDD must specify the 3 modelrouter preconditions and canonical roles."""
    tdd_text = TDD_0012_PATH.read_text(encoding="utf-8")

    for required_term in (
        "tenant_scoped_cache",
        "explicit_sa_registry",
        "fail_closed_ratelimit",
        "sre_admin",
        "compliance_officer",
        "read_only_analyst",
        "N/A (code execution not in scope at freeze-f1)",
    ):
        assert required_term in tdd_text


def test_adr_0012_and_tdd_omit_meta_prompt_jargon() -> None:
    """ADR-0012 and the TDD must not include internal meta-prompt terms."""
    combined_text = (
        ADR_0012_PATH.read_text(encoding="utf-8")
        + "\n"
        + TDD_0012_PATH.read_text(encoding="utf-8")
    ).lower()

    for forbidden_term in (
        "devil's advocate",
        "devils_advocate",
        "goldfish",
        "elephant",
        "zero-decision rule",
        "simple software mandate",
    ):
        assert forbidden_term not in combined_text
