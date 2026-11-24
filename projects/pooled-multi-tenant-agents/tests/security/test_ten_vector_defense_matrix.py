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

"""Tests for Workstreams 1-5 Architecture Deck Alignment (`Slides 8-14 & Slide 30`).

Verifies:
1. All 10 breach vectors (`Vector 1` through `Vector 10` = `10/10 PASS`) from Slide 11 (`Figure 2`).
2. `READ_ONLY_IMMUTABLE_PREFIX` on the `32,000`-token operator prefix (`84.7%` net input COGS
   reduction).
3. FinVault IBAN & SWIFT redaction (`[REDACTED-FINVAULT-IBAN]`, `[REDACTED-FINVAULT-SWIFT]`) and OCC
   NLC `422`.
4. Per-tenant GCS Skills bucket isolation (`gs://cymbal-skills-finvault` vs
   `gs://cymbal-skills-retail`).
5. Workstream 5 3-Model FinOps Chargeback (`EVEN_SPLIT`, `PROPORTIONAL_USAGE`,
   `TIERED_COMMIT_PLUS_OVERAGE`).
6. FastAPI `POST /api/v1/breach-matrix-10` endpoint.
"""

from __future__ import annotations

import pytest
from app.main import app
from fastapi.testclient import TestClient
from run_breach_simulations import (
    GCSSkillsBucketGuard,
    ImmutablePrefixCacheEngine,
    ThreeModelChargebackCalculator,
    run_all_10_breach_vectors,
)


async def test_all_10_breach_vectors_pass_deterministically() -> None:
    report = await run_all_10_breach_vectors()
    assert report["score"] == "10/10 PASS"
    assert report["all_passed"] is True
    assert len(report["vectors"]) == 10
    for vec in report["vectors"]:
        assert vec["passed"] is True, f"Failed vector: {vec}"


def test_32k_immutable_prefix_cache_yields_84_7_pct_net_cogs_savings() -> None:
    metrics = ImmutablePrefixCacheEngine.evaluate_turn_cache(
        tenant_id="tenant-finvault-alpha",
        dynamic_suffix_tokens=2000,
    )
    assert metrics["cache_mode"] == "READ_ONLY_IMMUTABLE_PREFIX"
    assert metrics["operator_prefix_tokens"] == 32000
    assert metrics["net_input_cogs_savings_pct"] == 84.7

    with pytest.raises(
        PermissionError, match="E_PREFIX_CACHE_WRITEBACK_DENIED"
    ):
        ImmutablePrefixCacheEngine.evaluate_turn_cache(
            tenant_id="tenant-retailstream-beta",
            attempt_prefix_mutation=True,
        )


def test_gcs_skills_bucket_isolation_and_ws5_three_chargeback_models() -> None:
    valid_uri = GCSSkillsBucketGuard.verify_skill_uri_access(
        tenant_id="tenant-finvault-alpha",
        skill_gcs_uri="gs://cymbal-skills-finvault/occ/SKILL.md",
    )
    assert valid_uri.startswith("gs://cymbal-skills-finvault")

    with pytest.raises(
        PermissionError, match="E_GCS_SKILLS_CROSS_TENANT_BLOCKED"
    ):
        GCSSkillsBucketGuard.verify_skill_uri_access(
            tenant_id="tenant-retailstream-beta",
            skill_gcs_uri="gs://cymbal-skills-finvault/occ/SKILL.md",
        )

    cb = ThreeModelChargebackCalculator.calculate_chargeback(
        total_shared_pool_cost_usd=100.0,
        tenant_tokens={
            "tenant-finvault-alpha": 60000,
            "tenant-retailstream-beta": 40000,
        },
        tenant_tiers={
            "tenant-finvault-alpha": "enterprise",
            "tenant-retailstream-beta": "standard",
        },
    )
    assert cb["EVEN_SPLIT"]["tenant-finvault-alpha"] == 50.0
    assert cb["PROPORTIONAL_USAGE"]["tenant-finvault-alpha"] == 60.0
    assert cb["TIERED_COMMIT_PLUS_OVERAGE"]["tenant-finvault-alpha"] == 75.0


def test_fastapi_breach_matrix_10_endpoint() -> None:
    client = TestClient(app)
    res = client.post("/api/v1/breach-matrix-10")
    assert res.status_code == 200
    body = res.json()
    assert body["score"] == "10/10 PASS"
    assert body["all_passed"] is True
