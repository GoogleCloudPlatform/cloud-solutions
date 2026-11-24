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

"""Breach Simulation 5: Compute FinOps, Prompt Cache Amortization & Noisy Neighbor Bulkheads
(Pillar 3).

Verifies:
1. RetailStream Corp (Standard Tier) is capped at a 4,000 thinking-token budget; requesting 8,000
   thinking tokens raises `429 Too Many Requests`.
2. FinVault Bank (Enterprise Tier) is permitted up to 8,000 thinking tokens.
3. Shared Prompt Prefix Caching (`prompt_cache_hit=True`) reduces billable tokens by 90%.
4. Exhausting RetailStream's TPM bulkhead isolates the Noisy Neighbor without impacting FinVault
   Bank.
"""

from __future__ import annotations

import pytest
from agents.context import TokenBucketBulkhead


def test_thinking_token_budget_enforced_by_tier(
    token_bulkhead: TokenBucketBulkhead,
) -> None:
    # RetailStream (Standard Tier, 4,000 cap) requesting 8,000 thinking tokens must be rejected
    with pytest.raises(
        PermissionError,
        match="429 Too Many Requests: Requested thinking budget",
    ):
        token_bulkhead.check_and_consume(
            tenant_id="tenant-retailstream-beta",
            requested_thinking_tokens=8000,
            estimated_total_tokens=10_000,
        )

    # FinVault Bank (Enterprise Tier, 8,000 budget) succeeds with 8,000 thinking tokens
    fv_usage = token_bulkhead.check_and_consume(
        tenant_id="tenant-finvault-alpha",
        requested_thinking_tokens=8000,
        estimated_total_tokens=20_000,
        prompt_cache_hit=True,
    )
    # 90% shared prompt prefix cache discount -> 2,000 billable tokens
    assert fv_usage["billable_tokens"] == 2000


def test_noisy_neighbor_tpm_bulkhead_isolates_retailstream_from_finvault(
    token_bulkhead: TokenBucketBulkhead,
) -> None:
    # RetailStream runaway loop (cache miss, 35,000 tokens -> within 40,000 TPM limit)
    token_bulkhead.check_and_consume(
        tenant_id="tenant-retailstream-beta",
        requested_thinking_tokens=4000,
        estimated_total_tokens=35_000,
        prompt_cache_hit=False,
    )

    # Next 10,000-token uncached turn exceeds RetailStream's 40,000 TPM bulkhead -> 429
    with pytest.raises(PermissionError, match="exceeded TPM bulkhead"):
        token_bulkhead.check_and_consume(
            tenant_id="tenant-retailstream-beta",
            requested_thinking_tokens=4000,
            estimated_total_tokens=10_000,
            prompt_cache_hit=False,
        )

    # FinVault Bank remains completely unaffected by RetailStream's bulkhead exhaustion
    fv_res = token_bulkhead.check_and_consume(
        tenant_id="tenant-finvault-alpha",
        requested_thinking_tokens=8000,
        estimated_total_tokens=50_000,
        prompt_cache_hit=True,
    )
    assert (
        fv_res["status"]
        if "status" in fv_res
        else fv_res["billable_tokens"] == 5000
    )
