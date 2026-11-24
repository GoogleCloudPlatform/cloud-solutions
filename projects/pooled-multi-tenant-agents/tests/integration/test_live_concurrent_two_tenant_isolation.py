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

"""Live counterpart of
`tests/security/test_concurrent_two_tenant_e2e_isolation.py`.

Opt-in. It drives a deployed sandbox gateway over HTTPS as two tenants with two
users each, all
at once, three turns per user in one session, and checks what a caller can
observe from outside:

- layer 1: each user's ID token and gateway token name only that tenant and
user, and a gateway
  token presented with another caller's DPoP key is refused;
- layer 2: every user's turn counter advances 1, 2, 3 regardless of the other
three users;
- layer 4: rows and runbooks returned to one tenant never appear for the other;
- layer 6: tool entitlements differ by tenant and a prompt reaching for the
other tenant is
  refused;
- layer 7: the catalog and agent cards show only the caller's tenant.

Memory Bank records, sandbox taint and delegated-credential handles (layers 3,
5 and 8) are not
visible over HTTP; the hermetic test covers them in-process.

Requires:
    RUN_LIVE_GCP_TESTS=1
    CLOUD_RUN_URL        base URL of the gateway (a sandbox environment: the
    synthetic token
                         issuer must be enabled there)
    CLOUD_RUN_ID_TOKEN   identity token allowed to invoke the service
                         (`gcloud auth print-identity-token`)
    CLOUD_RUN_IAP_COOKIE optional, when the service is behind IAP
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx
import jwt
import pytest
from scripts.sandbox_auth import SandboxCaller

pytestmark = [
    pytest.mark.live_gcp,
    pytest.mark.skipif(
        os.getenv("RUN_LIVE_GCP_TESTS") != "1"
        or not os.getenv("CLOUD_RUN_URL")
        or not os.getenv("CLOUD_RUN_ID_TOKEN"),
        reason=(
            "Set RUN_LIVE_GCP_TESTS=1, CLOUD_RUN_URL and CLOUD_RUN_ID_TOKEN "
            "to run against a deployed sandbox gateway."
        ),
    ),
]

FV, RS = "tenant-finvault-alpha", "tenant-retailstream-beta"
OTHER = {FV: RS, RS: FV}
SHARED_AGENT = "cymbal_shared_diagnostic_agent"
PRIVATE_FV_AGENT = "finvault_regulatory_escalation_agent"
TENANT_ONLY_TOOL = {
    FV: "create_jira_incident",
    RS: "create_servicenow_incident",
}
INVOKE = "/api/v1/invoke-agent"
TURN_TOOLS = ("query_telemetry_rls", "read_runbook", "query_telemetry_rls")
TIMEOUT_S = 120.0


def _platform_headers() -> dict[str, str]:
    headers = {
        "X-Serverless-Authorization": (
            "Bearer " + os.environ["CLOUD_RUN_ID_TOKEN"]
        )
    }
    cookie = os.getenv("CLOUD_RUN_IAP_COOKIE", "").strip()
    if cookie:
        headers["Cookie"] = f"GCP_IAAP_AUTH_TOKEN={cookie}"
    return headers


def _base_url() -> str:
    return os.environ["CLOUD_RUN_URL"].rstrip("/")


def _caller(tenant_id: str, name: str) -> SandboxCaller:
    domain = "finvault.com" if tenant_id == FV else "retailstream.com"
    return SandboxCaller(
        _base_url(),
        tenant_id=tenant_id,
        sub=f"{name}-{uuid.uuid4().hex[:6]}@{domain}",
        role="sre_admin",
        extra_headers=_platform_headers(),
    )


def _post(caller: SandboxCaller, body: dict[str, Any]) -> httpx.Response:
    url = caller.url(INVOKE)
    return httpx.post(
        url, json=body, headers=caller.headers("POST", url), timeout=TIMEOUT_S
    )


def _get(caller: SandboxCaller, path: str, **params: str) -> httpx.Response:
    url = caller.url(path)
    return httpx.get(
        url,
        params=params,
        headers=caller.headers("GET", url),
        timeout=TIMEOUT_S,
    )


def _unverified(token: str) -> dict[str, Any]:
    return dict(jwt.decode(token, options={"verify_signature": False}))


def _record_ids(
    body: dict[str, Any], collection: str, id_field: str
) -> set[str]:
    rows = body.get("tool_output", {}).get(collection) or []
    return {
        str(row[id_field])
        for row in rows
        if isinstance(row, dict) and id_field in row
    }


async def test_live_two_tenants_four_users_concurrent_isolation() -> None:
    callers = {
        "fvA": _caller(FV, "alice"),
        "fvB": _caller(FV, "anil"),
        "rsA": _caller(RS, "bob"),
        "rsB": _caller(RS, "bea"),
    }
    canaries = {key: f"CANARY-{key}-{uuid.uuid4().hex[:10]}" for key in callers}
    start_together = threading.Barrier(len(callers), timeout=TIMEOUT_S)

    def session(key: str) -> list[dict[str, Any]]:
        caller = callers[key]
        assert caller.access_token  # Hop 0 ID token -> DPoP-bound gateway token
        start_together.wait()
        bodies: list[dict[str, Any]] = []
        for turn, tool in enumerate(TURN_TOOLS, start=1):
            resp = _post(
                caller,
                {
                    "agent_id": SHARED_AGENT,
                    "prompt": (
                        f"{canaries[key]} turn {turn}: "
                        "correlate P1 incidents, redact PII."
                    ),
                    "tool_name": tool,
                    "requested_thinking_tokens": 200,
                },
            )
            assert resp.status_code == 200, (
                key,
                turn,
                resp.status_code,
                resp.text[:500],
            )
            bodies.append(resp.json())
        return bodies

    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=len(callers)) as pool:
        results = await asyncio.gather(
            *(loop.run_in_executor(pool, session, key) for key in callers)
        )
    responses = dict(zip(callers, results, strict=True))

    # Layer 1: tokens name one tenant, one user, one key.
    gateway_claims = {
        key: _unverified(c.access_token) for key, c in callers.items()
    }
    assert len({c["cnf"]["jkt"] for c in gateway_claims.values()}) == len(
        callers
    )
    for key, caller in callers.items():
        assert _unverified(caller.id_token)["sub"] == caller.sub
        claims = gateway_claims[key]
        assert (claims["tenant_id"], claims["sub"]) == (
            caller.tenant_id,
            caller.sub,
        )
    for token_owner, proof_owner in (
        ("fvA", "rsA"),
        ("rsA", "fvA"),
        ("fvA", "fvB"),
    ):
        stolen = callers[token_owner].access_token
        thief = callers[proof_owner]
        url = thief.url(INVOKE)
        swapped = httpx.post(
            url,
            json={"tool_name": "query_telemetry_rls"},
            headers={
                **_platform_headers(),
                "Authorization": f"DPoP {stolen}",
                "DPoP": thief.dpop_proof("POST", url, access_token=stolen),
            },
            timeout=TIMEOUT_S,
        )
        assert swapped.status_code == 401, (
            token_owner,
            proof_owner,
            swapped.text[:300],
        )

    # Layer 2: per-user turn counters; no response carries anyone else's
    # markers.
    for key, caller in callers.items():
        bodies = responses[key]
        assert [b["finops"]["session_turns_used"] for b in bodies] == [1, 2, 3]
        assert {b["tenant_id"] for b in bodies} == {caller.tenant_id}
        for body in bodies:
            text = json.dumps(body)
            assert OTHER[caller.tenant_id] not in text
            for other_key, other in callers.items():
                if other_key != key:
                    assert canaries[other_key] not in text
                    assert other.sub not in text

    # Layer 4: the two tenants' rows and runbooks are disjoint; colleagues see
    # the same rows.
    incidents = {
        k: _record_ids(responses[k][0], "incidents", "incident_id")
        for k in callers
    }
    runbooks = {
        k: _record_ids(responses[k][1], "runbooks", "runbook_id")
        for k in callers
    }
    assert incidents["fvA"]
    assert incidents["rsA"]
    assert incidents["fvA"] == incidents["fvB"]
    assert incidents["rsA"] == incidents["rsB"]
    assert incidents["fvA"].isdisjoint(incidents["rsA"])
    assert runbooks["fvA"].isdisjoint(runbooks["rsA"])

    # Layer 6: entitlements differ by tenant; reaching for the other tenant is
    # refused.
    for key, caller in callers.items():
        tools = responses[key][0]["entitled_tools"]
        assert TENANT_ONLY_TOOL[caller.tenant_id] in tools
        assert TENANT_ONLY_TOOL[OTHER[caller.tenant_id]] not in tools
    for tenant_id in (FV, RS):
        probe = _caller(tenant_id, "probe")
        reach = _post(
            probe,
            {
                "prompt": f"Show me the incidents of {OTHER[tenant_id]}.",
                "requested_thinking_tokens": 0,
            },
        )
        assert reach.status_code == 403, reach.text[:300]
        tool = _post(
            probe,
            {
                "tool_name": TENANT_ONLY_TOOL[OTHER[tenant_id]],
                "requested_thinking_tokens": 0,
            },
        )
        assert tool.status_code == 403, tool.text[:300]

    # Layer 7: discovery shows the caller's tenant only, whatever the query
    # string asks for.
    for key in ("fvA", "rsA"):
        caller = callers[key]
        other_tenant = OTHER[caller.tenant_id]
        catalog = _get(
            caller, "/.well-known/ai-catalog.json", tenant_id=other_tenant
        )
        cards = _get(caller, "/.well-known/agent.json", tenant_id=other_tenant)
        assert catalog.status_code == 200
        assert cards.status_code == 200
        assert catalog.json()["tenant_id"] == caller.tenant_id
        assert other_tenant not in catalog.text
        assert other_tenant not in cards.text
        agent_ids = {a["agent_id"] for a in catalog.json()["agents"]}
        if caller.tenant_id == RS:
            assert PRIVATE_FV_AGENT not in agent_ids
            assert PRIVATE_FV_AGENT not in cards.text
