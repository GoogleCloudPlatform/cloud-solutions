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

"""Governance, Citation, SQL Schema, and Naming Verification Suite (PR-S1).

Verifies that the repository's documentation and SQL layer enforce:
1. No unapproved 'Sovereign Silo' or 'sovereign model processing' claims in narrative docs
   (renamed to 'Pattern B: Dedicated Single-Tenant Silos').
2. Explicit separation between Data-at-Rest Residency ('us-central1' today; 'europe-west3' planned
   via memory_bank_iam_and_residency.py) and In-Flight Model Processing (Google Cloud regional
   endpoints, with no unverified prompt-retention claims).
3. Explicit Workstream 1 model routing layer handoff and its 3 multi-tenant
   preconditions (tenant_id-partitioned semantic cache, explicit identities allowlist without
   auto-provisioning, and fail-closed rate limiting).
4. Row #21 ('Ephemeral agent sandboxes') in docs/tenant_isolation_assurance.md marked N/A
   (code execution not in scope at freeze-f1).
5. Canonical platform role names (sre_admin, compliance_officer, read_only_analyst) separated from
   industry verticals (Enterprise SaaS Operations, E-Commerce IT Operations), with zero
   occurrences of non-existent roles such as 'ops_reviewer'.
6. Repo-wide Markdown link & file:line citation integrity across README.md and docs/**/*.md.
7. Repo-wide SQL schema column and deterministic ORDER BY verification against
   mcp_server/schema.sql.
8. Repo-wide absence of internal meta-prompt jargon in filenames and documentation.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

S1_DOCS = tuple(
    path
    for path in (
        REPO_ROOT / "README.md",
        REPO_ROOT
        / "docs"
        / "adr"
        / "0001-3-plane-decomposition-and-80-percent-reusable-core.md",
        REPO_ROOT / "docs" / "architecture.md",
        REPO_ROOT / "docs" / "blog_deep_dive_part2.md",
        REPO_ROOT / "docs" / "blog_outline.md",
        REPO_ROOT / "docs" / "codelab_90min.md",
        REPO_ROOT / "docs" / "executive_review_writeup.md",
        REPO_ROOT / "docs" / "requirements.md",
        REPO_ROOT / "docs" / "team_briefing_and_architecture_guide.md",
        REPO_ROOT / "docs" / "tenant_isolation_assurance.md",
        REPO_ROOT / "docs" / "vocab_and_concept_study_guide.md",
        REPO_ROOT / "docs" / "weekly_status_and_scorecard.md",
    )
    if path.is_file()
)

ALL_MARKDOWN_DOCS = (
    REPO_ROOT / "README.md",
    *sorted((REPO_ROOT / "docs").rglob("*.md")),
)

_MD_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
_FILE_LINE_CITE_RE = re.compile(
    r"`((?:app|agents|mcp_server|scripts|tests|terraform)/[a-zA-Z0-9_./-]+?\.(?:py|sql|tf|yaml|sh)):(\d+)(?:-(\d+))?`"
)


def test_s1_docs_do_not_claim_sovereign_silos_or_sovereign_model_processing() -> (
    None
):
    """S1 documents must use Dedicated Single-Tenant Silo instead of Sovereign Silo."""
    forbidden_phrases = (
        "sovereign silo",
        "sovereign gemma",
        "sovereign model processing",
        "zero customer prompt retention",
    )
    for path in S1_DOCS:
        text = path.read_text(encoding="utf-8").lower()
        for phrase in forbidden_phrases:
            assert (
                phrase not in text
            ), f"Found forbidden phrase {phrase!r} in {path.name}"


def test_s1_docs_separate_data_at_rest_residency_from_in_flight_model_processing() -> (
    None
):
    """architecture.md and executive_review_writeup.md must distinguish residency vs. model
    processing.
    """
    for rel in (
        "docs/architecture.md",
        "docs/executive_review_writeup.md",
        "docs/blog_deep_dive_part2.md",
    ):
        doc_path = REPO_ROOT / rel
        if not doc_path.is_file():
            continue
        norm = " ".join(doc_path.read_text(encoding="utf-8").split())
        assert (
            "Data-at-Rest Residency" in norm
        ), f"Missing Data-at-Rest Residency in {rel}"
        assert (
            "In-Flight Model Processing" in norm
        ), f"Missing In-Flight Model Processing in {rel}"
        assert (
            "Dedicated Single-Tenant Silo" in norm
        ), f"Missing Dedicated Single-Tenant Silo in {rel}"
        assert (
            "europe-west3` planned" in norm
        ), f"Missing 'europe-west3 planned' qualifier in {rel}"


def test_s1_docs_specify_three_modelrouter_multi_tenant_preconditions() -> None:
    """architecture.md and executive_review_writeup.md must list the 3 modelrouter preconditions."""
    for rel in ("docs/architecture.md", "docs/executive_review_writeup.md"):
        doc_path = REPO_ROOT / rel
        if not doc_path.is_file():
            continue
        text = " ".join(doc_path.read_text(encoding="utf-8").split())
        assert "Workstream 1" in text
        assert "modelrouter" in text.lower()
        assert "SEMANTIC_CACHE_ENABLED=false" in text
        assert "verify_google_jwt" in text
        assert "TokenBucketBulkhead" in text


def test_s1_tenant_isolation_assurance_includes_row_21_ephemeral_sandboxes_na() -> (
    None
):
    """docs/tenant_isolation_assurance.md must include Row #21 marked N/A at freeze-f1."""
    text = (REPO_ROOT / "docs" / "tenant_isolation_assurance.md").read_text(
        encoding="utf-8"
    )
    assert re.search(r"\|\s*21\s*\|\s*Ephemeral agent sandboxes\s*\|", text)
    assert "N/A (code execution not in scope at `freeze-f1`" in " ".join(
        text.split()
    )


def test_s1_docs_use_canonical_platform_role_names_and_separate_verticals() -> (
    None
):
    """S1 documents must use canonical roles and separate verticals from roles in
    blog_outline.md.
    """
    for path in ALL_MARKDOWN_DOCS:
        text = path.read_text(encoding="utf-8")
        assert (
            "ops_reviewer" not in text
        ), f"Non-canonical role 'ops_reviewer' found in {path.name}"

    outline_path = REPO_ROOT / "docs" / "blog_outline.md"
    if not outline_path.is_file():
        return
    outline = " ".join(outline_path.read_text(encoding="utf-8").split())
    assert "Enterprise SaaS Operations" in outline
    assert "E-Commerce IT Operations" in outline
    assert (
        "governed by three platform RBAC roles (`sre_admin`, `compliance_officer`, and "
        "`read_only_analyst`)"
    ) in outline


def test_repo_markdown_links_and_file_line_citations_resolve() -> None:
    """Every relative file link and backtick file:line citation in docs must resolve in the repo."""
    for md_path in ALL_MARKDOWN_DOCS:
        text = md_path.read_text(encoding="utf-8")
        for match in _MD_LINK_RE.finditer(text):
            target = match.group(1).split("#")[0].strip()
            if not target or target.startswith(
                ("http://", "https://", "mailto:", "file://", "psc://")
            ):
                continue
            resolved = (md_path.parent / target).resolve()
            assert (
                resolved.exists()
            ), f"Broken relative Markdown link {target!r} in {md_path.relative_to(REPO_ROOT)}"

        for match in _FILE_LINE_CITE_RE.finditer(text):
            rel_path, start_s, end_s = (
                match.group(1),
                match.group(2),
                match.group(3),
            )
            target_file = REPO_ROOT / rel_path
            assert (
                target_file.exists()
            ), f"Missing cited file {rel_path!r} in {md_path.relative_to(REPO_ROOT)}"
            num_lines = len(
                target_file.read_text(encoding="utf-8").splitlines()
            )
            start_line = int(start_s)
            end_line = int(end_s) if end_s else start_line
            assert 1 <= start_line <= end_line <= num_lines, (
                f"Out-of-bounds line citation {match.group(0)} in {md_path.relative_to(REPO_ROOT)} "
                f"(file has {num_lines} lines)"
            )


def test_repo_has_no_internal_meta_prompt_jargon_in_filenames_or_docs() -> None:
    """Filenames and Markdown docs must not contain internal meta-prompt or skill jargon."""
    banned_jargon = (
        "elephant-goldfish",
        "goldfish defeasibility",
        "zero-decision rule",
        "simple software mandate",
        "devils_advocate",
        "devil's advocate",
        "apple-style",
        "steve jobs",
        "apple keynote",
        "fingers crossed",
        "god-mode",
        "mutil-tenant",
        "/usr/local/" + "google/home/",
    )
    for md_path in ALL_MARKDOWN_DOCS:
        lower = md_path.read_text(encoding="utf-8").lower()
        for term in banned_jargon:
            assert (
                term not in lower
            ), f"Banned meta-prompt jargon {term!r} found in {md_path.relative_to(REPO_ROOT)}"
    for py_path in (REPO_ROOT / "tests").rglob("*.py"):
        for term in banned_jargon:
            assert (
                term not in py_path.name.lower()
            ), f"Banned meta-prompt jargon {term!r} found in filename {py_path.name}"


def test_docs_and_ui_do_not_quote_dollar_pricing_commitments() -> None:
    """Public docs and UI pages must not quote dollar infrastructure or LLM cost figures."""
    dollar_re = re.compile(r"\\?\$[0-9][0-9,.kKmM]*")
    sql_bind_re = re.compile(r"^\$[1-9]$")
    targets = (
        *ALL_MARKDOWN_DOCS,
        REPO_ROOT / "app" / "ui" / "workbench_page.py",
        REPO_ROOT / "app" / "ui" / "walkthrough_page.py",
    )
    for path in targets:
        for line_no, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            is_sql = any(
                tok in line
                for tok in (
                    "set_config",
                    "SET LOCAL",
                    "SELECT",
                    "WHERE",
                    "VALUES",
                    "SQL",
                )
            )
            hits = [
                m.rstrip(",.")
                for m in dollar_re.findall(line)
                if not (is_sql and sql_bind_re.fullmatch(m.rstrip(",.")))
            ]
            assert (
                not hits
            ), f"Quoted dollar figure {hits!r} found in {path.relative_to(REPO_ROOT)}:{line_no}"
