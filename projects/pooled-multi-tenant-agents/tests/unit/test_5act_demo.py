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

# pylint: disable=import-outside-toplevel,line-too-long

"""Hermetic tests for the 5-Act Architecture & Live Demo Runner (`scripts/run_5act_demo.py`)."""

from __future__ import annotations

from scripts.run_5act_demo import run_5act_demo


def test_5act_demo_executes_all_five_acts_cleanly() -> None:
    report = run_5act_demo()
    assert report["status"] == "ALL_5_ACTS_VERIFIED"
    acts = report["acts"]
    assert len(acts) == 5

    # Act 1: Unit economics
    assert acts[0]["input_token_cogs_reduction_pct"] == 84.71
    assert acts[0]["infra_cost_reduction_pct"] > 98.0

    # Act 2: Hop 0 + RFC 9449 DPoP + Per-Tenant SA Blast Radius
    assert acts[1]["dpop_whoami_tenant"] == "tenant-finvault-alpha"
    assert acts[1]["unauthenticated_request_http"] == 401
    assert acts[1]["body_identity_field_rejected_http"] == 422
    assert acts[1]["cross_tenant_private_agent_http"] == 403
    assert acts[1]["retailstream_compromised_sa_blast_radius"] == [
        "tenant-retailstream-beta"
    ]
    assert acts[1]["finvault_compromised_sa_blast_radius"] == [
        "tenant-finvault-alpha"
    ]

    # Act 3: KMS v2 Memory + RAG Quarantine + MCP Wire Signature
    assert acts[2]["cross_tenant_memory_read_blocked"] is True
    assert acts[2]["intra_tenant_cross_user_read_blocked"] is True
    assert acts[2]["indirect_injection_quarantined_on_read"] is True
    assert acts[2]["mcp_forged_scope_jsonrpc_code"] == -32001

    # Act 4: Deterministic Claim Verifier & Statistical Evals
    assert acts[3]["deterministic_verifier_passed"] is True
    assert acts[3]["deterministic_verifier_latency_ms"] < 20.0
    assert acts[3]["routine_turns_not_judged_pct"] > 80.0
    assert acts[3]["modeled_net_daily_saving_usd"] > 0.0

    # Act 5: Scorecard covers every live check and all pass
    assert acts[4]["total"] == 12
    assert acts[4]["passed"] == acts[4]["total"]
    assert all(acts[4]["checks"].values())


def test_act5_scorecard_flags_a_failed_check() -> None:
    """The scorecard must report a failing check (pure function: no extra requests)."""
    from scripts.run_5act_demo import FV, RS, run_act5_scorecard

    act2 = {
        "dpop_whoami_tenant": FV,
        "unauthenticated_request_http": 401,
        "body_identity_field_rejected_http": 422,
        "cross_tenant_private_agent_http": 403,
        "retailstream_compromised_sa_blast_radius": [RS],
        "finvault_compromised_sa_blast_radius": [FV],
    }
    act3 = {
        "cross_tenant_memory_read_blocked": False,  # simulated regression
        "intra_tenant_cross_user_read_blocked": True,
        "indirect_injection_quarantined_on_read": True,
        "mcp_forged_scope_jsonrpc_code": -32001,
        "private_agent_pruned_and_denied": True,
    }
    act4 = {"deterministic_verifier_passed": True}
    card = run_act5_scorecard(act2, act3, act4)
    assert card["passed"] == card["total"] - 1
    assert card["checks"]["cross_tenant_memory_read_blocked"] is False


def test_tuesday_demos_page_and_3b1b_video_endpoints_serve_cleanly() -> None:
    """Both `/demos` and `/assets/cymbal_3b1b_walkthrough.mp4` serve valid content."""
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    for route in ("/demos", "/tuesday"):
        html_response = client.get(route)
        assert html_response.status_code == 200
        assert "text/html" in html_response.headers["content-type"]
        assert "cymbal_3b1b_walkthrough.mp4" in html_response.text
        assert "jumpToChapter(" in html_response.text

    video_response = client.get("/assets/cymbal_3b1b_walkthrough.mp4")
    assert video_response.status_code == 200
    assert video_response.headers["content-type"] == "video/mp4"
    assert len(video_response.content) > 500_000
    assert b"ftyp" in video_response.content[:32]
