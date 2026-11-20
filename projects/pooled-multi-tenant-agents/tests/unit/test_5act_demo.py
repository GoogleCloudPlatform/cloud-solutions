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

# pylint: disable=protected-access
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


def test_demos_page_and_optional_walkthrough_video_serve_cleanly() -> None:
    """`/demos` (and its legacy alias) always serves; the MP4 is optional and the page adapts.

    The rendered video is not part of every distribution of this repository, so this passes both
    when `docs/assets/cymbal_architecture_walkthrough.mp4` is present and when it is absent.
    """
    from app.main import app
    from app.ui import walkthrough_page
    from fastapi.testclient import TestClient

    client = TestClient(app)
    video_url = f"/assets/{walkthrough_page.WALKTHROUGH_VIDEO_FILENAME}"
    has_video = walkthrough_page.walkthrough_video_available()

    for route in ("/demos", "/tuesday"):
        html_response = client.get(route)
        assert html_response.status_code == 200
        assert "text/html" in html_response.headers["content-type"]
        assert "jumpToChapter(" in html_response.text
        assert 'id="interactive-math-canvas"' in html_response.text
        assert (video_url in html_response.text) is has_video
        assert (
            f"const VIDEO_AVAILABLE = {str(has_video).lower()};"
            in html_response.text
        )
        assert "__VIDEO_" not in html_response.text

    video_response = client.get(video_url)
    if has_video:
        assert video_response.status_code == 200
        assert video_response.headers["content-type"] == "video/mp4"
        assert len(video_response.content) > 500_000
        assert b"ftyp" in video_response.content[:32]
    else:
        assert video_response.status_code == 404


def test_demos_page_without_the_video_references_no_video_asset_and_opens_the_canvas() -> (
    None
):
    from app.ui import walkthrough_page

    with_video = walkthrough_page.render_walkthrough_html(video_available=True)
    without_video = walkthrough_page.render_walkthrough_html(
        video_available=False
    )
    name = walkthrough_page.WALKTHROUGH_VIDEO_FILENAME

    assert (
        with_video.count(name) == 3
    )  # <source>, download href, download filename
    assert "⬇ Download MP4" in with_video
    assert "const VIDEO_AVAILABLE = true;" in with_video

    assert name not in without_video
    assert ".mp4" not in without_video
    assert "⬇ Download MP4" not in without_video
    assert "const VIDEO_AVAILABLE = false;" in without_video
    assert 'setStudioMode("canvas");' in without_video
    # Everything else is identical: only the three video hooks differ.
    assert len(with_video) - len(without_video) == len(
        walkthrough_page._VIDEO_SOURCE_TAG
        + walkthrough_page._VIDEO_DOWNLOAD_LINK
    ) + len("true") - len("false")


def test_ui_pages_carry_no_third_party_or_internal_event_branding() -> None:
    from app.ui import walkthrough_page, workbench_page

    for html in (
        walkthrough_page.render_walkthrough_html(video_available=True),
        workbench_page.render_workbench_html(),
    ):
        lowered = html.lower()
        # Spelled in pieces so this file does not itself contain the names it bans.
        for term in ("3blue" + "1brown", "3b" + "1b", "tues" + "day"):
            assert term not in lowered, term


def test_pages_offer_no_control_for_a_diagram_that_is_not_shipped() -> None:
    """Without the optional phase-comparison diagram, neither page links to it or leaves script
    that looks up the removed button."""
    from app.ui import walkthrough_page, workbench_page

    without = (
        workbench_page.render_workbench_html(modularity_diagram=False),
        walkthrough_page.render_walkthrough_html(
            video_available=False, modularity_diagram=False
        ),
    )
    for html in without:
        assert workbench_page.MODULARITY_DIAGRAM not in html
        assert "svg-btn-mod" not in html
        assert "__MODULARITY_LINK__" not in html
    # The two "Inspect Phase" buttons remain and now show a diagram that exists.
    assert "runPrereqCheck('google-only');" in without[0]
    assert "/diagrams/ws2_pooled_5hop_architecture.svg" in without[0]

    with_diagram = (
        workbench_page.render_workbench_html(modularity_diagram=True),
        walkthrough_page.render_walkthrough_html(
            video_available=False, modularity_diagram=True
        ),
    )
    for html in with_diagram:
        assert f"/diagrams/{workbench_page.MODULARITY_DIAGRAM}.svg" in html
    assert 'id="svg-btn-mod"' in with_diagram[0]
