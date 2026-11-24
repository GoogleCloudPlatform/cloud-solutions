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

# pylint: disable=line-too-long,protected-access,redefined-outer-name

"""End-to-end and guard-branch tests for configurable token-expiry and session call policies.

Verifies `token_policy` (`config/base.yaml`), per-tenant limit/lifetime overrides, Cloud Run
environment overrides (`agents/runtime_env.py`), Terraform `var.token_and_session_policy` presets,
and live HTTP enforcement across `/api/v1/sandbox/token`, `/api/v1/auth/token`, `/api/v1/whoami`,
`/api/v1/invoke-agent`, `TenantCredentialBroker`, and `broker_service.main.create_app`.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import jwt
import pytest
import yaml
from agents import context as agent_context
from agents import context_signing as cs
from agents import context_token as ct
from agents import hop0_idp_federation as hop0
from agents import platform_config as pc
from agents import runtime_env
from agents import tenant_credentials as tc
from agents.context_exchange import ContextTokenExchange
from agents.tenant_identity import tenant_service_account_email
from app import auth
from app import gateway_tokens as gt
from app.main import EDGE_VERIFIER, TOKEN_BULKHEAD, app
from broker_service.core import CredentialBroker, MintedCredential
from broker_service.main import create_app as create_broker_app
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from pydantic import ValidationError
from scripts.sandbox_auth import SandboxCaller

REPO_ROOT = Path(__file__).resolve().parents[2]
TERRAFORM_DIR = REPO_ROOT / "terraform"
BASE_URL = "http://testserver"
FINVAULT_TENANT_ID = "tenant-finvault-alpha"
RETAILSTREAM_TENANT_ID = "tenant-retailstream-beta"

_POLICY_ENV_VARS = (
    "GATEWAY_TOKEN_TTL_SECONDS",
    "DPOP_PROOF_MAX_AGE_SECONDS",
    "TENANT_SA_TOKEN_TTL_SECONDS",
    "TENANT_SA_REFRESH_MARGIN_SECONDS",
    "IDP_BROKER_MAX_TOKEN_LIFETIME_SECONDS",
    "IDP_DIRECT_MAX_TOKEN_LIFETIME_SECONDS",
    "STANDARD_MAX_TURNS_PER_SESSION",
    "ENTERPRISE_MAX_TURNS_PER_SESSION",
)


@pytest.fixture(autouse=True)
def reset_policy_caches(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Restores cached Hop 0, gateway token, bulkhead, and tenant directory state after each
    test.
    """
    for env_name in _POLICY_ENV_VARS:
        monkeypatch.delenv(env_name, raising=False)
    monkeypatch.setenv(
        "GOOGLE_CLOUD_PROJECT",
        pc.load_platform_config("sandbox").gcp.project_id,
    )
    pc._cached_platform_config.cache_clear()
    auth.reset_hop0_cache()
    gt._SERVICES.clear()
    agent_context.reset_dynamic_tenants()
    TOKEN_BULKHEAD.evict_tenant(FINVAULT_TENANT_ID)
    TOKEN_BULKHEAD.evict_tenant(RETAILSTREAM_TENANT_ID)
    yield
    for env_name in _POLICY_ENV_VARS:
        monkeypatch.delenv(env_name, raising=False)
    pc._cached_platform_config.cache_clear()
    auth.reset_hop0_cache()
    gt._SERVICES.clear()
    agent_context.reset_dynamic_tenants()
    TOKEN_BULKHEAD.evict_tenant(FINVAULT_TENANT_ID)
    TOKEN_BULKHEAD.evict_tenant(RETAILSTREAM_TENANT_ID)


def _write_custom_config_tree(
    root: Path,
    *,
    env_overrides: dict[str, Any] | None = None,
    tenants: dict[str, dict[str, Any]] | None = None,
) -> Path:
    (root / "environments").mkdir(parents=True, exist_ok=True)
    (root / "tenants" / "custom").mkdir(parents=True, exist_ok=True)
    (root / "base.yaml").write_text(
        (REPO_ROOT / "config" / "base.yaml").read_text()
    )
    environment_payload: dict[str, Any] = {
        "environment": "custom",
        "data_classification": "synthetic",
        "tenants_dir": "tenants/custom",
        "gcp": {"project_id": "custom-proj"},
        **(env_overrides or {}),
    }
    (root / "environments" / "custom.yaml").write_text(
        yaml.safe_dump(environment_payload)
    )
    tenant_specs = tenants or {
        "tenant-alpha": {
            "tenant_id": "tenant-alpha",
            "display_name": "Alpha Co",
            "tier": "enterprise",
            "identity": {"issuer": "https://idp.alpha.example.com"},
            "cmek_key": "alpha-cmek",
        },
        "tenant-beta": {
            "tenant_id": "tenant-beta",
            "display_name": "Beta Co",
            "tier": "standard",
            "identity": {"issuer": "https://idp.beta.example.com"},
            "cmek_key": "beta-cmek",
        },
    }
    for tenant_name, tenant_body in tenant_specs.items():
        (root / "tenants" / "custom" / f"{tenant_name}.yaml").write_text(
            yaml.safe_dump(tenant_body)
        )
    return root


class _RecordingMintBackend:
    """In-memory credential broker backend recording requested access-token lifetimes."""

    def __init__(self, clock: list[float]) -> None:
        self._clock = clock
        self.requested_lifetimes: list[int] = []

    def access_token(
        self, *, principal: str, lifetime_seconds: int
    ) -> MintedCredential:
        self.requested_lifetimes.append(lifetime_seconds)
        return MintedCredential(
            kind="access_token",
            token=f"sa-tok-{len(self.requested_lifetimes)}",
            expires_at=self._clock[0] + lifetime_seconds,
            principal=principal,
        )

    def id_token(self, *, principal: str, audience: str) -> MintedCredential:
        return MintedCredential(
            kind="id_token",
            token=f"id-tok-{audience}",
            expires_at=self._clock[0] + 3600,
            principal=principal,
        )


def _cloud_run_verified_caller_header(email: str, audience: str) -> str:
    payload = jwt.utils.base64url_encode(
        json.dumps(
            {
                "iss": "https://accounts.google.com",
                "email": email,
                "email_verified": True,
                "aud": audience,
            }
        ).encode("utf-8")
    ).decode("ascii")
    return f"Bearer eyJhbGciOiJSUzI1NiJ9.{payload}.SIGNATURE_REMOVED_BY_GOOGLE"


# ---------------------------------------------------------------------------------------------
# 1. Layered precedence and guard-branch boundary validation
# ---------------------------------------------------------------------------------------------


def test_default_token_policy_and_env_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifies defaults, environment YAML overlays, Cloud Run env overrides, and tenant
    overrides.
    """
    default_config = pc.load_platform_config("sandbox")
    default_policy = pc.resolve_effective_token_policy(default_config)
    assert default_policy.gateway_token_ttl_seconds == 600
    assert default_policy.dpop_proof_max_age_seconds == 120
    assert default_policy.tenant_sa_token_ttl_seconds == 300
    assert default_policy.tenant_sa_refresh_margin_seconds == 60
    assert default_policy.idp_broker_max_token_lifetime_seconds == 3600
    assert default_policy.idp_direct_max_token_lifetime_seconds == 5400

    config_root = _write_custom_config_tree(
        tmp_path,
        env_overrides={
            "token_policy": {
                "gateway_token_ttl_seconds": 900,
                "tenant_sa_token_ttl_seconds": 240,
            },
            "tiers": {
                "standard": {"max_turns_per_session": 7},
                "enterprise": {"max_turns_per_session": 18},
            },
        },
        tenants={
            "tenant-alpha": {
                "tenant_id": "tenant-alpha",
                "display_name": "Alpha Co",
                "tier": "enterprise",
                "identity": {"issuer": "https://idp.alpha.example.com"},
                "cmek_key": "alpha-cmek",
                "max_turns_per_session": 30,
                "rpm_limit": 240,
                "tpm_limit": 500_000,
                "thinking_budget": 12_000,
            },
            "tenant-beta": {
                "tenant_id": "tenant-beta",
                "display_name": "Beta Co",
                "tier": "standard",
                "identity": {"issuer": "https://idp.beta.example.com"},
                "cmek_key": "beta-cmek",
            },
        },
    )
    custom_config = pc.load_platform_config("custom", root=config_root)
    overlay_policy = pc.resolve_effective_token_policy(custom_config)
    assert overlay_policy.gateway_token_ttl_seconds == 900
    assert overlay_policy.tenant_sa_token_ttl_seconds == 240
    assert overlay_policy.dpop_proof_max_age_seconds == 120

    entries = custom_config.tenant_directory_entries(project_id="custom-proj")
    assert entries["tenant-alpha"]["max_turns_per_session"] == 30
    assert entries["tenant-alpha"]["rpm_limit"] == 240
    assert entries["tenant-alpha"]["tpm_limit"] == 500_000
    assert entries["tenant-alpha"]["thinking_budget"] == 12_000
    assert entries["tenant-beta"]["max_turns_per_session"] == 7

    monkeypatch.setenv("GATEWAY_TOKEN_TTL_SECONDS", "1200")
    monkeypatch.setenv("DPOP_PROOF_MAX_AGE_SECONDS", "90")
    monkeypatch.setenv("TENANT_SA_TOKEN_TTL_SECONDS", "180")
    monkeypatch.setenv("TENANT_SA_REFRESH_MARGIN_SECONDS", "45")
    monkeypatch.setenv("IDP_BROKER_MAX_TOKEN_LIFETIME_SECONDS", "7200")
    monkeypatch.setenv("IDP_DIRECT_MAX_TOKEN_LIFETIME_SECONDS", "10800")
    monkeypatch.setenv("STANDARD_MAX_TURNS_PER_SESSION", "11")
    monkeypatch.setenv("ENTERPRISE_MAX_TURNS_PER_SESSION", "25")

    env_policy = pc.resolve_effective_token_policy(custom_config)
    assert env_policy.gateway_token_ttl_seconds == 1200
    assert env_policy.dpop_proof_max_age_seconds == 90
    assert env_policy.tenant_sa_token_ttl_seconds == 180
    assert env_policy.tenant_sa_refresh_margin_seconds == 45
    assert env_policy.idp_broker_max_token_lifetime_seconds == 7200
    assert env_policy.idp_direct_max_token_lifetime_seconds == 10800

    overridden_entries = custom_config.tenant_directory_entries(
        project_id="custom-proj"
    )
    # Per-tenant explicit YAML still overrides tier env default; Beta inherits tier env override.
    assert overridden_entries["tenant-alpha"]["max_turns_per_session"] == 30
    assert overridden_entries["tenant-beta"]["max_turns_per_session"] == 11

    # Dynamically onboarded tenants also inherit the effective tier call ceiling.
    dynamic_meta = agent_context.register_tenant(
        tenant_id="tenant-gamma",
        display_name="Gamma Co",
        tier=agent_context.SubscriptionTier.ENTERPRISE,
        iss="https://idp.gamma.example.com",
    )
    assert dynamic_meta["max_turns_per_session"] == 25


def test_token_policy_boundary_conditions_and_startup_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Checks exact valid/invalid boundaries so mutating any guard branch fails a test."""
    # Exact valid boundary: dpop == gateway_ttl == 120, sa_ttl - margin == 30, gateway_ttl == idp.
    exact_valid = pc.TokenPolicySettings(
        gateway_token_ttl_seconds=300,
        dpop_proof_max_age_seconds=300,
        tenant_sa_token_ttl_seconds=120,
        tenant_sa_refresh_margin_seconds=90,
        idp_broker_max_token_lifetime_seconds=300,
        idp_direct_max_token_lifetime_seconds=300,
    )
    assert exact_valid.gateway_token_ttl_seconds == 300

    # Off-by-one invalid boundaries.
    with pytest.raises(
        ValidationError, match="dpop_proof_max_age_seconds must not exceed"
    ):
        pc.TokenPolicySettings(
            gateway_token_ttl_seconds=90, dpop_proof_max_age_seconds=91
        )
    with pytest.raises(ValidationError, match="at least 30 seconds"):
        pc.TokenPolicySettings(
            tenant_sa_token_ttl_seconds=120,
            tenant_sa_refresh_margin_seconds=91,
        )
    with pytest.raises(
        ValidationError, match="idp_broker_max_token_lifetime_seconds"
    ):
        pc.TokenPolicySettings(
            gateway_token_ttl_seconds=601,
            idp_broker_max_token_lifetime_seconds=600,
        )
    with pytest.raises(
        ValidationError, match="idp_direct_max_token_lifetime_seconds"
    ):
        pc.TokenPolicySettings(
            gateway_token_ttl_seconds=601,
            idp_direct_max_token_lifetime_seconds=600,
        )

    # Per-tenant max_token_lifetime_seconds must be >= gateway_token_ttl_seconds (YAML and env).
    config_root = _write_custom_config_tree(
        tmp_path,
        tenants={
            "tenant-strict": {
                "tenant_id": "tenant-strict",
                "display_name": "Strict Bank",
                "tier": "enterprise",
                "identity": {
                    "issuer": "https://idp.strict.example.com",
                    "max_token_lifetime_seconds": 900,
                },
                "cmek_key": "strict-cmek",
            }
        },
    )
    strict_config = pc.load_platform_config("custom", root=config_root)
    monkeypatch.setenv("GATEWAY_TOKEN_TTL_SECONDS", "900")
    assert (
        pc.resolve_effective_token_policy(
            strict_config
        ).gateway_token_ttl_seconds
        == 900
    )
    monkeypatch.setenv("GATEWAY_TOKEN_TTL_SECONDS", "901")
    with pytest.raises(
        ValueError, match=r"tenant-strict: identity\.max_token_lifetime_seconds"
    ):
        pc.resolve_effective_token_policy(strict_config)

    # Startup check validate_runtime_environment() fails closed on malformed/out-of-bounds env vars,
    # including TENANT_SA_TOKEN_TTL_SECONDS > 300 (ADR-0014 A1: may only lower the 300s ceiling).
    for env_var_name, bad_value in (
        ("GATEWAY_TOKEN_TTL_SECONDS", "not-an-int"),
        ("GATEWAY_TOKEN_TTL_SECONDS", "3601"),
        ("TENANT_SA_TOKEN_TTL_SECONDS", "59"),
        ("TENANT_SA_TOKEN_TTL_SECONDS", "301"),
        ("TENANT_SA_REFRESH_MARGIN_SECONDS", "271"),
        ("STANDARD_MAX_TURNS_PER_SESSION", "0"),
        ("ENTERPRISE_MAX_TURNS_PER_SESSION", "501"),
    ):
        for reset_var in _POLICY_ENV_VARS:
            monkeypatch.delenv(reset_var, raising=False)
        monkeypatch.setenv(env_var_name, bad_value)
        with pytest.raises((ValueError, ValidationError)):
            runtime_env.validate_runtime_environment()


# ---------------------------------------------------------------------------------------------
# 2. Live HTTP boundary tracing: token TTL, context token, turn ceiling, silent refresh, DPoP
# ---------------------------------------------------------------------------------------------


def test_http_token_exchange_and_whoami_honor_gateway_token_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Traces custom GATEWAY_TOKEN_TTL_SECONDS across /auth/token, /whoami, and ctx+jwt bounds."""
    monkeypatch.setenv("GATEWAY_TOKEN_TTL_SECONDS", "900")
    status = runtime_env.validate_runtime_environment()
    assert status["gateway_token_ttl_seconds"] == 900

    client = TestClient(app)
    caller = SandboxCaller(
        client,
        tenant_id=FINVAULT_TENANT_ID,
        sub="alice@finvault.com",
        role="sre_admin",
    )
    exchange_url = BASE_URL + "/api/v1/auth/token"
    exchange_response = client.post(
        "/api/v1/auth/token",
        json={"subject_token": caller.id_token},
        headers={"DPoP": caller.dpop_proof("POST", exchange_url)},
    )
    assert exchange_response.status_code == 200
    exchange_body = exchange_response.json()
    assert 895 <= exchange_body["expires_in"] <= 900

    caller._access_token = exchange_body["access_token"]
    whoami_url = BASE_URL + "/api/v1/whoami"
    whoami_response = client.get(
        "/api/v1/whoami",
        headers=caller.headers("GET", whoami_url),
    )
    assert whoami_response.status_code == 200
    assert whoami_response.json()["tenant_id"] == FINVAULT_TENANT_ID

    # ADR-0014 Amendment A1: even when gateway_token_ttl_seconds > 600 (e.g., 1800s), irrevocable
    # KMS context tokens stay capped at min(gateway_exp, iat + 600) and re-sign fresh ones as
    # needed; when gateway_token_ttl_seconds < 600 (e.g., 180s), not_after clamps ctx+jwt to 180s.
    monkeypatch.setenv("GATEWAY_TOKEN_TTL_SECONDS", "1800")
    with pytest.raises(
        ValueError, match="max_ttl_seconds must be between 1 and 600"
    ):
        cs.ContextTokenIssuer(cs.LocalTestSigner(), max_ttl_seconds=601)

    base_wall_now = int(time.time())
    fake_now = [float(base_wall_now - 596)]
    local_signer = cs.LocalTestSigner()
    issuer = cs.ContextTokenIssuer(local_signer, clock=lambda: fake_now[0])
    verifier = ct.ContextTokenVerifier(
        local_signer.public_keys, clock=lambda: fake_now[0]
    )
    assert issuer.max_ttl_seconds == ct.CONTEXT_TOKEN_MAX_TTL_SECONDS == 600

    gateway_exp = int(fake_now[0]) + 1800
    envelope = EDGE_VERIFIER.exchange_obo_token(
        verified_idp_claims={
            "iss": "https://accounts.google.com",
            "sub": "alice@finvault.com",
            "tenant_id": FINVAULT_TENANT_ID,
            "user_role": "sre_admin",
            "idp_provider": "google_workspace_oidc",
            "exp": gateway_exp,
            "jti": f"gw-{uuid.uuid4().hex}",
        },
        dpop_proof={"jkt": "jkt-finvault-1", "jti": f"dpop-{uuid.uuid4().hex}"},
        session_id="sess-1800",
        replay_checked=True,
        issue_context_token=False,
    )
    claim_kwargs: dict[str, Any] = {
        "sub": envelope.security.sub,
        "cnf": {"jkt": envelope.security.dpop_jkt},
        "tenant_id": envelope.tenant.tenant_id,
        "tier": str(envelope.tenant.subscription_tier),
        "org_unit": envelope.tenant.org_unit,
        "thinking_budget": envelope.tenant.thinking_token_budget,
        "scopes": list(envelope.tenant.authorized_scopes),
        "cmek_key_name": envelope.tenant.cmek_key_name,
        "user_role": envelope.security.user_role,
        "idp_provider": envelope.security.idp_provider,
        "idp_iss": envelope.security.iss,
        "session_id": envelope.request.session_id,
        "max_delegation_depth": 3,
    }
    first_ctx_token, first_ctx_claims = issuer.issue(
        source_jti=envelope.security.jti,
        not_after=gateway_exp,
        **claim_kwargs,
    )
    assert (
        first_ctx_claims["exp"] - first_ctx_claims["iat"]
        == ct.CONTEXT_TOKEN_MAX_TTL_SECONDS
    )
    verified = verifier.verify(first_ctx_token, audience=ct.AUDIENCE_RUNTIME)
    assert verified["tenant_id"] == FINVAULT_TENANT_ID
    assert issuer.sign_count == 1

    # Still within first 600s window -> cached context token reused (no extra KMS sign).
    fake_now[0] = float(
        base_wall_now - 10
    )  # t + 586s (14s remaining > 5s refresh margin)
    cached_token, _ = issuer.issue(
        source_jti=envelope.security.jti,
        not_after=gateway_exp,
        **claim_kwargs,
    )
    assert cached_token == first_ctx_token
    assert issuer.sign_count == 1

    # Nearing/past 600s while 1800s gateway token is still live -> transparently re-signs a fresh
    # <=600s context token tied to the same gateway src_jti; when remaining gateway lifetime is
    # < 600s, not_after clamps exp strictly below 600s.
    fake_now[0] = float(
        base_wall_now
    )  # t + 596s (4s remaining <= 5s refresh margin)
    second_ctx_token, second_ctx_claims = issuer.issue(
        source_jti=envelope.security.jti,
        not_after=gateway_exp,
        **claim_kwargs,
    )
    assert second_ctx_token != first_ctx_token
    assert second_ctx_claims["jti"] != first_ctx_claims["jti"]
    assert second_ctx_claims["src_jti"] == envelope.security.jti
    assert (
        second_ctx_claims["exp"] - second_ctx_claims["iat"]
        == ct.CONTEXT_TOKEN_MAX_TTL_SECONDS
    )
    assert (
        verifier.verify(second_ctx_token, audience=ct.AUDIENCE_RUNTIME)["jti"]
        == second_ctx_claims["jti"]
    )
    assert issuer.sign_count == 2

    tail_gateway_exp = base_wall_now + 240
    final_ctx_token, final_ctx_claims = issuer.issue(
        source_jti=f"gw-tail-{uuid.uuid4().hex}",
        not_after=tail_gateway_exp,
        **claim_kwargs,
    )
    assert final_ctx_claims["exp"] == tail_gateway_exp
    assert final_ctx_claims["exp"] - final_ctx_claims["iat"] == 240
    assert (
        verifier.verify(final_ctx_token, audience=ct.AUDIENCE_RUNTIME)["exp"]
        == tail_gateway_exp
    )
    assert issuer.sign_count == 3

    # Exact 600 + CLOCK_SKEW_SECONDS passes; +1 fails closed in _check_claim_shapes even with
    # GATEWAY_TOKEN_TTL_SECONDS=1800 set in the environment.
    exact_cap_token, _ = issuer._sign_claims(
        {
            k: v
            for k, v in final_ctx_claims.items()
            if k not in {"iss", "jti", "iat", "exp"}
        },
        kid=local_signer.kid,
        now=int(fake_now[0]),
        exp=int(fake_now[0])
        + ct.CONTEXT_TOKEN_MAX_TTL_SECONDS
        + ct.CLOCK_SKEW_SECONDS,
        jti_prefix="ctx",
    )
    assert verifier.verify(exact_cap_token, audience=ct.AUDIENCE_RUNTIME)[
        "tenant_id"
    ] == (FINVAULT_TENANT_ID)

    overlong_token, _ = issuer._sign_claims(
        {
            k: v
            for k, v in final_ctx_claims.items()
            if k not in {"iss", "jti", "iat", "exp"}
        },
        kid=local_signer.kid,
        now=int(fake_now[0]),
        exp=int(fake_now[0])
        + ct.CONTEXT_TOKEN_MAX_TTL_SECONDS
        + ct.CLOCK_SKEW_SECONDS
        + 1,
        jti_prefix="ctx",
    )
    with pytest.raises(ct.ContextTokenError) as exc_info:
        verifier.verify(overlong_token, audience=ct.AUDIENCE_RUNTIME)
    assert exc_info.value.code == "E_CONTEXT_TOKEN_CLAIMS"

    # Shorter gateway TTL (180s) caps ctx+jwt at gateway token exp (min(gateway_exp, iat + 600)).
    short_token, short_claims = issuer.issue(
        source_jti=f"gw-short-{uuid.uuid4().hex}",
        not_after=int(fake_now[0]) + 180,
        **claim_kwargs,
    )
    assert short_claims["exp"] - short_claims["iat"] == 180
    assert (
        verifier.verify(short_token, audience=ct.AUDIENCE_RUNTIME)["exp"]
        == short_claims["exp"]
    )


def test_http_invoke_agent_turn_ceiling_and_silent_dpop_reexchange(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Proves custom turn ceiling trips 429 on N+1 while same-key re-exchange avoids IdP re-auth."""
    monkeypatch.setenv("STANDARD_MAX_TURNS_PER_SESSION", "2")
    agent_context.reset_dynamic_tenants()
    assert (
        agent_context.TENANT_DIRECTORY[RETAILSTREAM_TENANT_ID][
            "max_turns_per_session"
        ]
        == 2
    )

    client = TestClient(app)
    caller = SandboxCaller(
        client,
        tenant_id=RETAILSTREAM_TENANT_ID,
        sub="maya@retailstream.io",
        role="sre_admin",
    )
    original_id_token = caller.id_token
    first_gateway_token = caller.access_token
    invoke_url = BASE_URL + "/api/v1/invoke-agent"

    for turn_number in (1, 2):
        response = client.post(
            "/api/v1/invoke-agent",
            json={
                "tool_name": "query_telemetry_rls",
                "requested_thinking_tokens": 512,
            },
            headers=caller.headers("POST", invoke_url),
        )
        assert (
            response.status_code == 200
        ), f"turn {turn_number} failed: {response.text}"

    # Turn 3 on the same gateway token exceeds max_turns_per_session=2 -> HTTP 429.
    third_response = client.post(
        "/api/v1/invoke-agent",
        json={
            "tool_name": "query_telemetry_rls",
            "requested_thinking_tokens": 512,
        },
        headers=caller.headers("POST", invoke_url),
    )
    assert third_response.status_code == 429
    third_detail = third_response.json()["detail"]
    assert third_detail["error"] == "E_SESSION_LOOP_CIRCUIT_BREAKER"
    assert third_detail["status"] == "BLOCKED_BY_AGENT_SANDBOX_GOVERNANCE"

    # An attacker who copied the still-valid IdP ID token cannot exchange it with another DPoP key.
    thief = SandboxCaller(
        client,
        tenant_id=RETAILSTREAM_TENANT_ID,
        sub="maya@retailstream.io",
        role="sre_admin",
    )
    thief._id_token = original_id_token
    exchange_url = BASE_URL + "/api/v1/auth/token"
    theft_attempt = client.post(
        "/api/v1/auth/token",
        json={"subject_token": original_id_token},
        headers={"DPoP": thief.dpop_proof("POST", exchange_url)},
    )
    assert theft_attempt.status_code == 401
    assert theft_attempt.json()["detail"] == {
        "error": "E_SUBJECT_TOKEN_INVALID"
    }

    # The legitimate client silently re-exchanges the SAME IdP token (zero user re-login prompt!)
    # using the bound DPoP key, receives a fresh gateway token jti, and continues cleanly.
    caller._access_token = None
    refreshed_gateway_token = caller.access_token
    assert refreshed_gateway_token != first_gateway_token
    assert caller.id_token == original_id_token

    resumed_response = client.post(
        "/api/v1/invoke-agent",
        json={
            "tool_name": "query_telemetry_rls",
            "requested_thinking_tokens": 512,
        },
        headers=caller.headers("POST", invoke_url),
    )
    assert resumed_response.status_code == 200


def test_dpop_proof_freshness_honors_configured_max_age(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tightens DPOP_PROOF_MAX_AGE_SECONDS=45 and verifies HTTP /whoami rejects a 50s-old proof."""
    monkeypatch.setenv("DPOP_PROOF_MAX_AGE_SECONDS", "45")
    client = TestClient(app)
    caller = SandboxCaller(
        client,
        tenant_id=FINVAULT_TENANT_ID,
        sub="alice@finvault.com",
        role="sre_admin",
    )
    gateway_token = caller.access_token
    whoami_url = BASE_URL + "/api/v1/whoami"

    def _proof_with_age(age_seconds: int) -> str:
        public_jwk = agent_context.AsymmetricDPoPProvider.public_key_to_jwk(
            caller._dpop_key.public_key()
        )
        return jwt.encode(
            {
                "htm": "GET",
                "htu": whoami_url,
                "iat": int(time.time()) - age_seconds,
                "jti": f"dpop-age-{age_seconds}-{uuid.uuid4().hex}",
                "ath": gt.access_token_hash(gateway_token),
            },
            caller._dpop_key,
            algorithm="ES256",
            headers={"typ": "dpop+jwt", "alg": "ES256", "jwk": public_jwk},
        )

    valid_response = client.get(
        "/api/v1/whoami",
        headers={
            "Authorization": f"DPoP {gateway_token}",
            "DPoP": _proof_with_age(40),
        },
    )
    assert valid_response.status_code == 200

    # A 50s-old proof would pass the default 120s window, proving the env policy is wired live.
    stale_response = client.get(
        "/api/v1/whoami",
        headers={
            "Authorization": f"DPoP {gateway_token}",
            "DPoP": _proof_with_age(50),
        },
    )
    assert stale_response.status_code == 401
    assert stale_response.json()["detail"] == {"error": "E_DPOP_STALE"}


# ---------------------------------------------------------------------------------------------
# 3. Hop 0 IdP lifetime limits (direct federation + Identity Platform broker + per-tenant override)
# ---------------------------------------------------------------------------------------------


def test_hop0_enforces_env_and_per_tenant_idp_max_lifetime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifies IDP_*_MAX_TOKEN_LIFETIME_SECONDS and per-tenant
    identity.max_token_lifetime_seconds.
    """
    monkeypatch.setenv("IDP_DIRECT_MAX_TOKEN_LIFETIME_SECONDS", "1200")
    auth.reset_hop0_cache()
    client = TestClient(app)

    # Sandbox DevIssuer caps its token TTL to 1200s automatically, so normal callers keep working.
    caller = SandboxCaller(
        client,
        tenant_id=FINVAULT_TENANT_ID,
        sub="alice@finvault.com",
        role="sre_admin",
    )
    unverified = jwt.decode(
        caller.id_token, options={"verify_signature": False}
    )
    assert int(unverified["exp"]) - int(unverified["iat"]) == 1200
    assert caller.access_token

    # An IdP token signed with the real Hop 0 key but lifetime 1201s fails closed at /auth/token.
    wiring = auth.get_hop0()
    assert wiring.dev_issuer is not None
    now = int(time.time())
    overlong_idp_token = jwt.encode(
        {
            "iss": "https://accounts.google.com",
            "aud": "https://agent-gateway.cymbal.internal",
            "sub": "alice@finvault.com",
            "user_role": "sre_admin",
            "iat": now,
            "exp": now + 1201,
            "jti": f"dev-overlong-{uuid.uuid4().hex}",
        },
        wiring.dev_issuer.private_key,
        algorithm="RS256",
        headers={"kid": wiring.dev_issuer.kid},
    )
    exchange_url = BASE_URL + "/api/v1/auth/token"
    rejected_exchange = client.post(
        "/api/v1/auth/token",
        json={"subject_token": overlong_idp_token},
        headers={"DPoP": caller.dpop_proof("POST", exchange_url)},
    )
    assert rejected_exchange.status_code == 401
    assert rejected_exchange.json()["detail"] == {
        "error": "E_SUBJECT_TOKEN_INVALID"
    }

    # Verify per-tenant override in Identity Platform broker mode: exact bound accepted, +1 refused.
    config_root = _write_custom_config_tree(
        tmp_path,
        env_overrides={"identity": {"broker_project_id": "cymbal-gcip-prod"}},
        tenants={
            "tenant-finvault-alpha": {
                "tenant_id": "tenant-finvault-alpha",
                "display_name": "FinVault Bank",
                "tier": "enterprise",
                "identity": {
                    "issuer": "https://securetoken.google.com/cymbal-gcip-prod",
                    "provider": "okta",
                    "gcip_tenant_id": "finvault-gcip",
                    "sign_in_providers": ["saml.okta-finvault"],
                    "role_claim": "cymbal_role",
                    "role_map": dict(hop0.DEFAULT_OKTA_GROUP_MAP),
                    "max_token_lifetime_seconds": 1800,
                },
                "cmek_key": "finvault-alpha-cmek",
            }
        },
    )
    gcip_cfg = pc.load_platform_config("custom", root=config_root)
    monkeypatch.setitem(
        agent_context.TENANT_DIRECTORY[FINVAULT_TENANT_ID],
        "iss",
        "https://securetoken.google.com/cymbal-gcip-prod",
    )
    registry = auth.build_registry(gcip_cfg)
    assert (
        registry.for_gcip_tenant("finvault-gcip").upstream_idp
        == hop0.FederatedIdP.OKTA_ENTERPRISE_OIDC
    )
    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    resolver = hop0.StaticJWKSResolver()
    resolver.add_key(
        issuer="https://securetoken.google.com/cymbal-gcip-prod",
        kid="gcip-1",
        public_key=rsa_key.public_key(),
    )
    gate = hop0.HopZeroFederationGate(registry=registry, resolver=resolver)

    def _mint_gcip(ttl_seconds: int) -> str:
        issued_at = int(time.time())
        return jwt.encode(
            {
                "iss": "https://securetoken.google.com/cymbal-gcip-prod",
                "aud": "cymbal-gcip-prod",
                "sub": "alice-uid",
                "iat": issued_at,
                "exp": issued_at + ttl_seconds,
                "auth_time": issued_at - 2,
                "cymbal_role": "cymbal-sre-admins",
                "firebase": {
                    "tenant": "finvault-gcip",
                    "sign_in_provider": "saml.okta-finvault",
                },
            },
            rsa_key,
            algorithm="RS256",
            headers={"kid": "gcip-1"},
        )

    accepted_claims = gate.verify_and_normalize(_mint_gcip(1800))
    assert accepted_claims["tenant_id"] == FINVAULT_TENANT_ID
    with pytest.raises(PermissionError, match="E_HOP0_TOKEN_LIFETIME_TOO_LONG"):
        gate.verify_and_normalize(_mint_gcip(1801))


# ---------------------------------------------------------------------------------------------
# 4. Tenant SA CredentialBroker, proactive refresh margin, offboarding, and broker_service HTTP
# ---------------------------------------------------------------------------------------------


def test_tenant_sa_broker_and_broker_service_honor_configured_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies broker 300s hard ceiling, TENANT_SA_TOKEN_TTL_SECONDS tightening, and clamp."""
    broker_url = "https://cymbal-credential-broker.example.run.app"
    runtime_sa = "cymbal-pooled-runtime-sa@cymbal-multitenancy-example.iam.gserviceaccount.com"

    # Hard 300s ceiling: both runtime TenantCredentialBroker and broker_service CredentialBroker
    # reject construction above 300s (config may only lower <= 300s per ADR-0014 Amendment A1).
    with pytest.raises(ValueError, match="E_CREDENTIAL_LIFETIME"):
        tc.TenantCredentialBroker(
            project_id="cymbal-multitenancy-example",
            backend=tc.LocalTenantCredentialBackend(),
            lifetime_seconds=301,
        )
    with pytest.raises(
        ValueError, match="E_BROKER_CONFIG: max_access_token_lifetime_seconds"
    ):
        CredentialBroker(
            project_id="cymbal-multitenancy-example",
            allowed_callers=frozenset({runtime_sa}),
            backend=_RecordingMintBackend([time.time()]),
            tenants=lambda: {FINVAULT_TENANT_ID: ()},
            expected_caller_audience=broker_url,
            max_access_token_lifetime_seconds=301,
        )

    monkeypatch.setenv("TENANT_SA_TOKEN_TTL_SECONDS", "180")
    monkeypatch.setenv("TENANT_SA_REFRESH_MARGIN_SECONDS", "45")

    # Start 300s behind wall clock so advancing +135s keeps iat <= PyJWT wall-clock now.
    clock = [float(int(time.time()) - 300)]
    local_backend = tc.LocalTenantCredentialBackend(clock=lambda: clock[0])
    broker = tc.TenantCredentialBroker(
        project_id="cymbal-multitenancy-example",
        backend=local_backend,
        clock=lambda: clock[0],
    )
    assert broker.lifetime_seconds == 180
    assert broker.refresh_margin_seconds == 45

    envelope = EDGE_VERIFIER.exchange_obo_token(
        verified_idp_claims={
            "iss": "https://accounts.google.com",
            "sub": "alice@finvault.com",
            "tenant_id": FINVAULT_TENANT_ID,
            "user_role": "sre_admin",
            "idp_provider": "google_workspace_oidc",
            "exp": int(clock[0]) + 3600,
            "jti": f"gw-{uuid.uuid4().hex}",
        },
        dpop_proof={"jkt": "jkt-1", "jti": f"dpop-{uuid.uuid4().hex}"},
        session_id="sess-cred",
        replay_checked=True,
    )

    first_cred = broker.credential_for(envelope)
    assert first_cred.expires_at - clock[0] == 180
    assert len(local_backend.minted) == 1

    # At t + 134 (1 second before the 45s refresh margin on a 180s token): cache hit.
    clock[0] += 134.0
    assert broker.credential_for(envelope).token == first_cred.token
    assert len(local_backend.minted) == 1

    # At t + 135 (expires_at - margin == clock): proactive refresh mints a fresh 180s token.
    clock[0] += 1.0
    second_cred = broker.credential_for(envelope)
    assert second_cred.token != first_cred.token
    assert second_cred.expires_at - clock[0] == 180
    assert len(local_backend.minted) == 2

    # Wire tc.RemoteBrokerBackend -> live FastAPI broker_service.main.create_app:
    # configure broker_core at its 300s ceiling while runtime env is tightened to 180s so removing
    # the runtime-side `min(int(lifetime_seconds), policy_max_ttl)` clamp in RemoteBrokerBackend
    # directly fails `captured_json_payloads` AND `recording_backend.requested_lifetimes`.
    local_signer = cs.LocalTestSigner()
    ctx_issuer = cs.ContextTokenIssuer(local_signer, clock=lambda: clock[0])
    ctx_verifier = ct.ContextTokenVerifier(
        local_signer.public_keys, clock=lambda: clock[0]
    )
    exchange = ContextTokenExchange(
        issuer=ctx_issuer, verifier=ctx_verifier, clock=lambda: clock[0]
    )
    recording_backend = _RecordingMintBackend(clock)
    broker_core_300 = CredentialBroker(
        project_id="cymbal-multitenancy-example",
        allowed_callers=frozenset({runtime_sa}),
        backend=recording_backend,
        tenants=lambda: {FINVAULT_TENANT_ID: ()},
        verifier=lambda: ctx_verifier,
        expected_caller_audience=broker_url,
        max_access_token_lifetime_seconds=300,
        clock=lambda: clock[0],
    )
    broker_client_300 = TestClient(create_broker_app(broker_core_300))
    captured_json_payloads: list[dict[str, Any]] = []

    def _post_to_broker_300(
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
        timeout: float,
    ) -> Any:
        del timeout
        captured_json_payloads.append(dict(json))
        path = url.removeprefix(broker_url)
        patched_headers = {
            **headers,
            "X-Serverless-Authorization": _cloud_run_verified_caller_header(
                runtime_sa, broker_url
            ),
        }
        return broker_client_300.post(path, headers=patched_headers, json=json)

    internal_ctx_token, _ = ctx_issuer.issue(
        source_jti=f"gw-{uuid.uuid4().hex}",
        not_after=int(clock[0]) + 600,
        sub="alice@finvault.com",
        cnf={"jkt": "jkt-remote"},
        tenant_id=FINVAULT_TENANT_ID,
        tier="enterprise",
        org_unit="regulated-banking-us",
        thinking_budget=8000,
        scopes=list(envelope.tenant.authorized_scopes),
        cmek_key_name=envelope.tenant.cmek_key_name,
        user_role="sre_admin",
        idp_provider="google_workspace_oidc",
        idp_iss="https://accounts.google.com",
        session_id="sess-remote",
        max_delegation_depth=3,
    )
    remote_backend = tc.RemoteBrokerBackend(
        broker_url,
        exchange=exchange,
        id_token_provider=lambda aud: f"placeholder.{aud}.sig",
        http_post=_post_to_broker_300,
    )
    expected_principal = tenant_service_account_email(
        FINVAULT_TENANT_ID, "cymbal-multitenancy-example"
    )

    # Caller requests 300s (which broker_core_300 would allow!), so ONLY RemoteBrokerBackend's
    # runtime-side clamp lowers the outbound HTTP body + minted token to 180s.
    minted_runtime_clamped = remote_backend.mint(
        tenant_id=FINVAULT_TENANT_ID,
        principal=expected_principal,
        lifetime_seconds=300,
        context_token=internal_ctx_token,
    )
    assert captured_json_payloads == [
        {"kind": "access_token", "lifetime_seconds": 180}
    ]
    assert recording_backend.requested_lifetimes == [180]
    assert minted_runtime_clamped.expires_at - clock[0] == 180

    # Caller requesting 30s is clamped upward to the 60s minimum floor.
    remote_backend.mint(
        tenant_id=FINVAULT_TENANT_ID,
        principal=expected_principal,
        lifetime_seconds=30,
        context_token=internal_ctx_token,
    )
    assert captured_json_payloads[-1] == {
        "kind": "access_token",
        "lifetime_seconds": 60,
    }
    assert recording_backend.requested_lifetimes == [180, 60]

    # Broker-side tightening & 300s hard cap: requesting 900s on a 180s-configured broker clamps to
    # 180s; requesting 900s on the 300s broker clamps to 300s; requesting 3601s fails at HTTP 422.
    tightened_backend = _RecordingMintBackend(clock)
    tightened_broker_client = TestClient(
        create_broker_app(
            CredentialBroker(
                project_id="cymbal-multitenancy-example",
                allowed_callers=frozenset({runtime_sa}),
                backend=tightened_backend,
                tenants=lambda: {FINVAULT_TENANT_ID: ()},
                verifier=lambda: ctx_verifier,
                expected_caller_audience=broker_url,
                max_access_token_lifetime_seconds=(
                    pc.resolve_effective_token_policy().tenant_sa_token_ttl_seconds
                ),
                clock=lambda: clock[0],
            )
        )
    )
    tight_broker_token, _ = exchange.exchange(
        internal_ctx_token, audience="broker"
    )
    tightened_response = tightened_broker_client.post(
        tc.BROKER_CREDENTIAL_PATH,
        headers={
            "X-Serverless-Authorization": _cloud_run_verified_caller_header(
                runtime_sa, broker_url
            ),
            tc.BROKER_CONTEXT_TOKEN_HEADER: tight_broker_token,
        },
        json={"kind": "access_token", "lifetime_seconds": 900},
    )
    assert tightened_response.status_code == 200
    assert tightened_backend.requested_lifetimes == [180]
    assert tightened_response.json()["expires_at"] - clock[0] == 180

    ceiling_broker_token, _ = exchange.exchange(
        internal_ctx_token, audience="broker"
    )
    clamped_mint = _post_to_broker_300(
        f"{broker_url}{tc.BROKER_CREDENTIAL_PATH}",
        headers={tc.BROKER_CONTEXT_TOKEN_HEADER: ceiling_broker_token},
        json={"kind": "access_token", "lifetime_seconds": 900},
        timeout=5.0,
    )
    assert clamped_mint.status_code == 200
    assert recording_backend.requested_lifetimes == [180, 60, 300]
    assert clamped_mint.json()["expires_at"] - clock[0] == 300

    rejected_mint = _post_to_broker_300(
        f"{broker_url}{tc.BROKER_CREDENTIAL_PATH}",
        headers={tc.BROKER_CONTEXT_TOKEN_HEADER: ceiling_broker_token},
        json={"kind": "access_token", "lifetime_seconds": 3601},
        timeout=5.0,
    )
    assert rejected_mint.status_code == 422

    # Offboarding immediately evicts cached credentials on the active instance.
    offboard_report = agent_context.offboard_tenant(FINVAULT_TENANT_ID)
    assert offboard_report["removed_from_directory"] is True
    assert offboard_report["evicted_sa_credential"] is True
    with pytest.raises(PermissionError, match="E_TENANT_NOT_ONBOARDED"):
        broker.credential_for(envelope)


# ---------------------------------------------------------------------------------------------
# 5. Terraform variable defaults and recommended preset parity
# ---------------------------------------------------------------------------------------------


def test_terraform_token_and_session_policy_defaults_and_presets_match_schema() -> (
    None
):
    """Asserts Terraform defaults and tfvars presets agree with config/base.yaml and schema
    rules.
    """
    variables_tf = (TERRAFORM_DIR / "variables.tf").read_text()
    iap_gateway_tf = (
        TERRAFORM_DIR / "modules" / "platform_core" / "iap_gateway.tf"
    ).read_text()
    broker_tf = (
        TERRAFORM_DIR / "modules" / "platform_core" / "credential_broker.tf"
    ).read_text()
    tfvars_example = (TERRAFORM_DIR / "terraform.tfvars.example").read_text()

    base_config = pc.load_platform_config("sandbox")
    expected_defaults = {
        "gateway_token_ttl_seconds": base_config.token_policy.gateway_token_ttl_seconds,
        "dpop_proof_max_age_seconds": base_config.token_policy.dpop_proof_max_age_seconds,
        "tenant_sa_token_ttl_seconds": base_config.token_policy.tenant_sa_token_ttl_seconds,
        "tenant_sa_refresh_margin_seconds": (
            base_config.token_policy.tenant_sa_refresh_margin_seconds
        ),
        "idp_broker_max_token_lifetime_seconds": (
            base_config.token_policy.idp_broker_max_token_lifetime_seconds
        ),
        "idp_direct_max_token_lifetime_seconds": (
            base_config.token_policy.idp_direct_max_token_lifetime_seconds
        ),
        "standard_max_turns_per_session": base_config.tiers[
            "standard"
        ].max_turns_per_session,
        "enterprise_max_turns_per_session": base_config.tiers[
            "enterprise"
        ].max_turns_per_session,
    }
    for field_name, default_value in expected_defaults.items():
        pattern = rf"{field_name}\s*=\s*optional\(number,\s*{default_value}\)"
        assert re.search(
            pattern, variables_tf
        ), f"missing/drifted Terraform default: {field_name}"

    for env_name in _POLICY_ENV_VARS:
        assert (
            env_name in iap_gateway_tf
        ), f"{env_name} not wired in terraform/modules/platform_core/iap_gateway.tf"
    assert 'name  = "TENANT_SA_TOKEN_TTL_SECONDS"' in broker_tf

    # Extract all 3 commented preset blocks from terraform.tfvars.example and validate each!
    preset_blocks = re.findall(
        r"# token_and_session_policy = \{\n((?:#   [a-z_]+\s*=\s*\d+\n)+)# \}",
        tfvars_example,
    )
    assert (
        len(preset_blocks) == 3
    ), f"expected 3 presets in tfvars.example, got {len(preset_blocks)}"
    for block in preset_blocks:
        parsed_fields = {
            key: int(val)
            for key, val in re.findall(r"#   ([a-z_]+)\s*=\s*(\d+)", block)
        }
        assert set(parsed_fields) == set(expected_defaults)
        token_fields = {
            k: v
            for k, v in parsed_fields.items()
            if not k.endswith("_max_turns_per_session")
        }
        validated_policy = pc.TokenPolicySettings.model_validate(token_fields)
        assert (
            validated_policy.gateway_token_ttl_seconds
            == parsed_fields["gateway_token_ttl_seconds"]
        )
        for tier_key in (
            "standard_max_turns_per_session",
            "enterprise_max_turns_per_session",
        ):
            pc.TierLimits(
                thinking_budget=4000,
                rpm_limit=30,
                tpm_limit=40_000,
                max_turns_per_session=parsed_fields[tier_key],
            )
