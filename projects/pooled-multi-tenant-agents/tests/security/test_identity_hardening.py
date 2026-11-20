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

# pylint: disable=import-outside-toplevel,line-too-long,protected-access
# pylint: disable=redefined-outer-name,reimported

"""Identity, session and config hardening (the non-memory half of the data-plane review).

- **#2:** the OBO signature covers every field that drives an access decision, and sub-agent hops
  refuse unsigned state.
- **#3:** "global" and the platform key name are reserved and cannot be claimed by a tenant.
- **#6:** a KMS outage stays an availability error instead of masquerading as an isolation denial.
- **#16:** platform config follows `CYMBAL_ENV`, live mode has one definition, and the
  shared-identity
  escape hatch is flagged in live mode.
- ADK sessions use `"{tenant}:{sub}"`, so equal IdP subjects at two tenants never collide.
- CEL conditions reference only configured tenants.
"""

from __future__ import annotations

import dataclasses
import re
import time
import uuid
from typing import Any

import pytest
from agents import platform_config as pc
from agents.context import (
    TENANT_DIRECTORY,
    ContextEnvelope,
    EdgeAuthVerifier,
    propagate_to_subagent,
    register_tenant,
    tenant_qualified_user_id,
)

FV = "tenant-finvault-alpha"
RS = "tenant-retailstream-beta"
TENANT_MEMORY_WRITE_SCOPE = "memory:tenant.write"


def _env(
    tenant_id: str, sub: str, role: str | None = "sre_admin"
) -> ContextEnvelope:
    claims: dict[str, Any] = {
        "iss": str(TENANT_DIRECTORY[tenant_id]["iss"]),
        "sub": sub,
        "tenant_id": tenant_id,
        "exp": int(time.time()) + 3600,
    }
    if role is not None:
        claims["user_role"] = role
    return EdgeAuthVerifier().exchange_obo_token(
        verified_idp_claims=claims,
        dpop_proof={"jkt": f"jkt-{sub}", "jti": uuid.uuid4().hex},
        session_id="sess-1",
    )


# --- #2 OBO signature covers access-deciding fields --------------------------------------------


@pytest.mark.parametrize("field", ["authorized_scopes", "cmek_key_name"])
def test_02_forged_scopes_or_key_fail_signature_verification(
    field: str,
) -> None:
    verifier = EdgeAuthVerifier()
    env = verifier.exchange_obo_token(
        verified_idp_claims={
            "iss": str(TENANT_DIRECTORY[FV]["iss"]),
            "sub": "c@finvault.com",
            "tenant_id": FV,
            "user_role": "compliance_officer",
            "exp": int(time.time()) + 3600,
        },
        dpop_proof={"jkt": "jkt", "jti": uuid.uuid4().hex},
    )
    forged_value: Any = (
        (*env.tenant.authorized_scopes, TENANT_MEMORY_WRITE_SCOPE)
        if field == "authorized_scopes"
        else TENANT_DIRECTORY[RS]["cmek_key_name"]
    )
    forged = dataclasses.replace(
        env, tenant=dataclasses.replace(env.tenant, **{field: forged_value})
    )
    with pytest.raises(PermissionError, match="E_INVALID_OBO_SIGNATURE"):
        verifier.verify_obo_envelope(forged, "jkt")


def test_02_forged_scopes_detected_across_subagent_hop() -> None:
    state = _env(FV, "c@finvault.com", role="compliance_officer").to_adk_state()
    state["temp:authorized_scopes"] = [
        *state["temp:authorized_scopes"],
        "memory:tenant.write",
    ]
    with pytest.raises(PermissionError, match="E_SUBAGENT_STATE_TAMPERING"):
        propagate_to_subagent(state)


@pytest.mark.parametrize(
    ("key", "forged_value"),
    [
        ("temp:user_role", "sre_admin"),
        ("temp:idp_provider", "okta_enterprise_oidc"),
    ],
)
def test_02_forged_role_or_idp_provider_detected_across_subagent_hop(
    key: str, forged_value: str
) -> None:
    state = _env(FV, "c@finvault.com", role="compliance_officer").to_adk_state()
    state[key] = forged_value
    with pytest.raises(PermissionError, match="E_SUBAGENT_STATE_TAMPERING"):
        propagate_to_subagent(state)


def test_02_unsigned_parent_state_is_refused() -> None:
    state = _env(FV, "a@finvault.com").to_adk_state()
    state.pop("temp:context_token")
    with pytest.raises(PermissionError, match="E_SUBAGENT_UNSIGNED_STATE"):
        propagate_to_subagent(state)


# --- #3 reserved "global" namespace -------------------------------------------------------------


def test_03_tenant_cannot_be_named_global() -> None:
    with pytest.raises(ValueError, match="reserved"):
        register_tenant(tenant_id="global", display_name="Evil")


def test_03_config_rejects_reserved_tenant_and_key() -> None:
    base = {"tenant_id": "global", "display_name": "X", "tier": "standard"}
    base["identity"] = {"issuer": "https://idp.example.com"}
    with pytest.raises(ValueError, match="reserved"):
        pc.TenantSpec.model_validate({**base, "cmek_key": "k"})
    with pytest.raises(ValueError, match="reserved"):
        pc.TenantSpec.model_validate(
            {
                **base,
                "tenant_id": "tenant-x",
                "cmek_key": "cymbal-platform-global",
            }
        )


# --- #6 KMS errors --------------------------------------------------------------------------------


def test_06_kms_outage_is_not_reported_as_an_isolation_denial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx
    from agents import gcp_live_bridge as bridge

    class _Resp:
        status_code = 503

        def raise_for_status(self) -> None:
            raise httpx.HTTPStatusError("503", request=None, response=None)  # type: ignore[arg-type]

    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp())
    monkeypatch.setattr(bridge, "_legacy_adc_headers", lambda _p: {})
    kms = bridge.LiveCloudKMSCMEKVerifier(project_id=pc.resolve_project_id())
    with pytest.raises(httpx.HTTPStatusError):
        kms.decrypt_for_tenant(
            kms_key_name=TENANT_DIRECTORY[FV]["cmek_key_name"],
            tenant_id=FV,
            ciphertext=b"x",
            envelope=_env(FV, "a@finvault.com"),
        )


# --- #10 identifiers ------------------------------------------------------------------------------


def test_10_empty_subject_is_rejected() -> None:
    with pytest.raises(ValueError, match=r"non-empty sub"):
        tenant_qualified_user_id(FV, "  ")
    with pytest.raises(ValueError, match="colon-free"):
        tenant_qualified_user_id("tenant:evil", "00u123")


def test_equal_subjects_at_two_tenants_get_distinct_session_users() -> None:
    assert tenant_qualified_user_id(FV, "00u123") != tenant_qualified_user_id(
        RS, "00u123"
    )


def test_adk_runner_uses_tenant_qualified_user_ids() -> None:
    from pathlib import Path

    src = Path("agents/gcp_live_bridge.py").read_text(encoding="utf-8") + Path(
        "agents/adapters/vertex_runner.py"
    ).read_text(encoding="utf-8")
    assert "user_id=envelope.security.sub" not in src
    assert src.count("user_id=tenant_qualified_user_id(") == 2


# --- #15 CEL conditions -------------------------------------------------------------------------


def test_cel_conditions_reference_only_configured_tenants() -> None:
    from agents.memory_bank_iam_and_residency import MemoryBankIAMCELGuard

    for binding in MemoryBankIAMCELGuard()._bindings.values():
        for tenant in re.findall(
            r"\['tenant_id'\] == '([^']+)'", binding.cel_expression
        ):
            assert tenant in TENANT_DIRECTORY, tenant
            assert tenant == binding.required_scope_kv["tenant_id"]


# --- #16 config -----------------------------------------------------------------------------------


def test_16_platform_config_follows_cymbal_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CYMBAL_ENV", "sandbox")
    assert pc.get_platform_config().environment == "sandbox"
    monkeypatch.setenv("CYMBAL_ENV", "customer.example")
    assert pc.get_platform_config().environment != "sandbox"


def test_16_live_mode_has_a_single_definition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agents import gcp_live_bridge as bridge

    monkeypatch.setenv("CYMBAL_LIVE_GCP", "1")
    monkeypatch.setenv("CYMBAL_OFFLINE_CI", "1")
    assert pc.is_live_mode() is False
    assert bridge.is_live_gcp_enabled() is False


def test_16_escape_hatch_is_flagged_in_live_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agents import runtime_env

    monkeypatch.setattr(runtime_env, "is_live_mode", lambda: True)
    monkeypatch.setattr(
        runtime_env, "resolve_project_id", lambda: "cymbal-multitenancy-example"
    )
    monkeypatch.setenv("DLP_INSPECT_TEMPLATE", "x")
    monkeypatch.setenv("DLP_DEIDENTIFY_TEMPLATE", "y")
    monkeypatch.setenv("CYMBAL_TENANT_SCOPED_CREDENTIALS", "0")
    with pytest.raises(
        RuntimeError, match="CYMBAL_TENANT_SCOPED_CREDENTIALS=0"
    ):
        runtime_env.validate_runtime_environment()


def test_delegation_depth_cannot_be_reset_by_a_hop() -> None:
    from agents.context import propagate_to_subagent

    root = _env(FV, "a@finvault.com").to_adk_state()
    hop2 = propagate_to_subagent(propagate_to_subagent(root))
    assert hop2["temp:delegation_depth"] == 2
    hop2["temp:delegation_depth"] = 0  # try to earn more hops
    with pytest.raises(PermissionError, match="E_SUBAGENT_STATE_TAMPERING"):
        propagate_to_subagent(hop2)


def test_mcp_wire_refuses_forged_scopes_or_tenant() -> None:
    import asyncio

    from mcp_server.server import handle_mcp_jsonrpc_request

    def call(state: dict[str, Any]) -> dict[str, Any]:
        return asyncio.run(
            handle_mcp_jsonrpc_request(
                {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                verified_adk_state=state,
            )
        )

    good = _env(RS, "ops@retailstream.com").to_adk_state()
    assert "result" in call(good)

    forged_scopes = {
        **good,
        "temp:authorized_scopes": [
            *good["temp:authorized_scopes"],
            "3lo:jira.incidents.write",
        ],
    }
    forged_tenant = {**good, "temp:tenant_id": FV}
    bad_budget_type = {**good, "temp:thinking_budget": "not-an-int"}
    bad_scopes_type = {**good, "temp:authorized_scopes": 123}
    forged_depth = {**good, "temp:delegation_depth": 2}
    for state in (
        forged_scopes,
        forged_tenant,
        bad_budget_type,
        bad_scopes_type,
        forged_depth,
    ):
        assert call(state)["error"]["code"] == -32001
