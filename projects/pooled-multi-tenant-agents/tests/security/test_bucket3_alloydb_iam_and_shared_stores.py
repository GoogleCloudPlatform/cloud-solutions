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

# pylint: disable=import-outside-toplevel,inconsistent-quotes,line-too-long
# pylint: disable=missing-class-docstring,protected-access,unused-argument

"""Bucket 3 security & infrastructure contract tests.

Covers:
1. AlloyDB IAM OAuth2 authentication (`make_asyncpg_pool_factory(..., iam_auth=True, db_role=...)`)
   and `RLSDatabasePool.update_incident(...)` write RBAC enforcement (offline + live-pool mock).
2. Multi-replica Firestore control-plane revocation store (`FirestoreRevocationStore` +
   `FIRESTORE_REVOCATION_STORE=1`) synchronizing agent suspensions and tenant offboarding across
   gateway, runtime, and credential broker processes.
3. Live mid-turn `AskPro` secondary Vertex AI consultation (`SharedModelRoutingPDP`) with 1-per-turn
   cap and live Gemini 4 Argon invocation seam.
4. Terraform AlloyDB primary instance, IAM DB user, password complexity guard, and Cloud Run Direct
   VPC Egress (`PRIVATE_RANGES_ONLY`) contracts.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import pytest
from agents import context as agent_context
from agents import platform_config
from agents.context import RequestContext, SecurityContext, TenantContext
from agents.context_exchange import get_context_token_exchange
from agents.model_routing import DEFAULT_PRO_MODEL, SharedModelRoutingPDP
from agents.workload_identity import (
    FirestoreRevocationStore,
    clear_tenant_revoked,
    install_revocation_store,
    is_agent_suspended,
    is_tenant_revoked,
    mark_tenant_revoked,
    reset_control_plane_revocations,
    resume_agent,
    suspend_agent,
)
from broker_service.core import BrokerRefused, CredentialBroker
from broker_service.iam_backend import MintedCredential
from mcp_server import db as mcp_db
from mcp_server.db import RLSDatabasePool, make_asyncpg_pool_factory
from tests.helpers.context_token_fakes import _envelope

REPO = Path(__file__).resolve().parents[2]
FINVAULT = "tenant-finvault-alpha"
RETAILSTREAM = "tenant-retailstream-beta"
PROJECT = "cymbal-multitenancy-example"
RUNTIME_SA = f"cymbal-pooled-runtime-sa@{PROJECT}.iam.gserviceaccount.com"
BROKER_URL = "https://cymbal-credential-broker.example.run.app"


def _mint_envelope(
    tenant_id: str = FINVAULT,
    user_sub: str = "alice@finvault.com",
    user_role: str = "sre_admin",
    agent_id: str = "cymbal_shared_diagnostic_agent",
) -> agent_context.ContextEnvelope:
    meta = agent_context.TENANT_DIRECTORY[tenant_id]
    now = int(time.time())
    env = _envelope(tenant_id, user_sub, user_role=user_role)
    if agent_id:
        env = agent_context.EdgeAuthVerifier().bind_routed_agent(env, agent_id)
    ctx_tok = env.context_token
    return agent_context.ContextEnvelope(
        security=SecurityContext(
            iss=str(meta["iss"]),
            sub=user_sub,
            aud="https://agent-gateway.cymbal.internal",
            exp=now + 600,
            jti=f"jti-b3-{tenant_id}-{now}",
            kid="kms-b3",
            dpop_jkt="jkt-b3",
            user_role=user_role,
            idp_provider="google_workspace_oidc",
        ),
        tenant=TenantContext(
            tenant_id=tenant_id,
            subscription_tier=meta["tier"],
            org_unit=str(meta["org_unit"]),
            authorized_scopes=tuple(meta["authorized_scopes"]),
            thinking_token_budget=int(meta["thinking_budget"]),
            cmek_key_name=str(meta["cmek_key_name"]),
        ),
        request=RequestContext(
            trace_id="trace-b3",
            correlation_id="corr-b3",
            session_id=f"sess-b3-{tenant_id}-{now}",
        ),
        context_token=ctx_tok,
        delegation_sig="b3-sig",
    )


class _FakeFirestoreDocSnap:
    def __init__(self, data: dict[str, Any] | None) -> None:
        self._data = data

    @property
    def exists(self) -> bool:
        return self._data is not None

    def to_dict(self) -> dict[str, Any] | None:
        return dict(self._data) if self._data is not None else None


class _FakeFirestoreDocRef:
    def __init__(self, backing: dict[str, dict[str, Any]], doc_id: str) -> None:
        self._backing = backing
        self._doc_id = doc_id

    def set(self, payload: dict[str, Any]) -> None:
        self._backing[self._doc_id] = dict(payload)

    def get(self) -> _FakeFirestoreDocSnap:
        return _FakeFirestoreDocSnap(self._backing.get(self._doc_id))

    def delete(self) -> None:
        self._backing.pop(self._doc_id, None)


class _FakeFirestoreCollection:
    def __init__(self, backing: dict[str, dict[str, Any]]) -> None:
        self._backing = backing

    def document(self, doc_id: str) -> _FakeFirestoreDocRef:
        return _FakeFirestoreDocRef(self._backing, doc_id)


class _FakeFirestoreClient:
    def __init__(self) -> None:
        self.collections: dict[str, dict[str, dict[str, Any]]] = {}

    def collection(self, name: str) -> _FakeFirestoreCollection:
        return _FakeFirestoreCollection(self.collections.setdefault(name, {}))


class _FakeMintBackend:
    def access_token(
        self, *, principal: str, lifetime_seconds: int
    ) -> MintedCredential:
        return MintedCredential(
            kind="access_token",
            token="fake-sa-access-token",
            expires_at=time.time() + lifetime_seconds,
            principal=principal,
        )

    def id_token(self, *, principal: str, audience: str) -> MintedCredential:
        return MintedCredential(
            kind="id_token",
            token="eyJ.fake.id",
            expires_at=time.time() + 3600,
            principal=principal,
        )


def test_firestore_revocation_store_synchronizes_multi_replica_suspensions_and_offboarding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Replica A writes suspension/revocation to Firestore; Replica B enforces immediately."""
    import base64
    import json

    def _caller_bearer() -> str:
        def _b64(obj: dict[str, Any]) -> str:
            return (
                base64.urlsafe_b64encode(json.dumps(obj).encode())
                .rstrip(b"=")
                .decode()
            )

        claims = {
            "iss": "https://accounts.google.com",
            "aud": BROKER_URL,
            "email": RUNTIME_SA,
            "email_verified": True,
            "exp": int(time.time()) + 3600,
        }
        return (
            f"Bearer {_b64({'alg': 'RS256', 'typ': 'JWT'})}.{_b64(claims)}"
            ".SIGNATURE_REMOVED_BY_GOOGLE"
        )

    fake_fs = _FakeFirestoreClient()
    replica_a_store = FirestoreRevocationStore(firestore_client=fake_fs)
    replica_b_store = FirestoreRevocationStore(firestore_client=fake_fs)

    try:
        # Simulate Replica A writing to Firestore, then Replica B reading with empty local RAM!
        install_revocation_store(replica_a_store)
        suspend_agent(
            "finvault_regulatory_escalation_agent", reason="multi_replica_drill"
        )
        mark_tenant_revoked("tenant-ephemeral-delta")

        # Clear in-process RAM dicts to simulate a separate Cloud Run replica (`Replica B`)!
        reset_control_plane_revocations()
        install_revocation_store(replica_b_store)

        assert (
            is_agent_suspended("finvault_regulatory_escalation_agent") is True
        )
        assert is_tenant_revoked("tenant-ephemeral-delta") is True

        # Broker on Replica B blocks pre-minted context tokens via shared Firestore state!
        exchange = get_context_token_exchange()
        fv_env = _mint_envelope(
            FINVAULT,
            agent_id="finvault_regulatory_escalation_agent",
        )
        broker_tok, _ = exchange.exchange(
            fv_env.context_token, audience="broker"
        )
        broker = CredentialBroker(
            project_id=PROJECT,
            allowed_callers=frozenset({RUNTIME_SA}),
            backend=_FakeMintBackend(),
            tenants=lambda: {FINVAULT: ()},
            expected_caller_audience=BROKER_URL,
        )
        with pytest.raises(BrokerRefused, match="E_AGENT_SUSPENDED"):
            broker.mint(
                caller_header=_caller_bearer(),
                context_token=broker_tok,
                kind="access_token",
            )

        assert resume_agent("finvault_regulatory_escalation_agent") is True
        assert (
            is_agent_suspended("finvault_regulatory_escalation_agent") is False
        )
        assert clear_tenant_revoked("tenant-ephemeral-delta") is True
        assert is_tenant_revoked("tenant-ephemeral-delta") is False

        # Verify `build_firestore_client` selects `FirestoreClient(transport="rest")` on Cloud Run
        # Agent Identity (`workload_spiffe_mtls_active() == True`).
        import sys
        import types

        from agents import kms_rest

        captured_gapic: dict[str, Any] = {}

        class _FakeFSClient:
            def __init__(self, *, project: str, database: str) -> None:
                self.project = project
                self.database = database
                self._credentials = "FAKE_SPIFFE_CREDS"
                self._firestore_api_internal: Any = None

        def _fake_gapic_client(**kwargs: Any) -> str:
            captured_gapic.update(kwargs)
            return "REST_MTLS_FIRESTORE_API"

        monkeypatch.setenv("K_SERVICE", "cymbal-agent-shared")
        monkeypatch.setenv(
            "GOOGLE_API_CERTIFICATE_CONFIG",
            "/var/run/secrets/workload-spiffe-credentials/config.json",
        )
        monkeypatch.setitem(
            sys.modules,
            "google.cloud.firestore",
            types.SimpleNamespace(Client=_FakeFSClient),
        )
        monkeypatch.setitem(
            sys.modules,
            "google.cloud.firestore_v1.services.firestore",
            types.SimpleNamespace(
                client=types.SimpleNamespace(
                    FirestoreClient=_fake_gapic_client
                ),
            ),
        )
        import google.cloud

        monkeypatch.setattr(
            google.cloud,
            "firestore",
            sys.modules["google.cloud.firestore"],
            raising=False,
        )
        built_fs = kms_rest.build_firestore_client(
            project_id=PROJECT,
            database="cymbal-memory-bank-prod",
        )
        assert built_fs._firestore_api_internal == "REST_MTLS_FIRESTORE_API"
        assert captured_gapic == {
            "credentials": "FAKE_SPIFFE_CREDS",
            "transport": "rest",
        }
    finally:
        install_revocation_store(None)
        reset_control_plane_revocations()


def test_alloydb_iam_pool_factory_and_rls_update_incident_write_rbac(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`make_asyncpg_pool_factory(iam_auth=True)` uses IAM tokens + SSL + write RBAC."""
    captured_create_pool: dict[str, Any] = {}
    executed_init_sql: list[str] = []

    class _FakeConn:
        async def execute(self, sql: str, *args: Any) -> None:
            executed_init_sql.append(sql)

    async def _fake_create_pool(**kwargs: Any) -> str:
        captured_create_pool.update(kwargs)
        if kwargs.get("init") is not None:
            await kwargs["init"](_FakeConn())
        return "FAKE_ASYNCPG_POOL"

    import types

    fake_asyncpg = types.SimpleNamespace(create_pool=_fake_create_pool)
    monkeypatch.setitem(__import__("sys").modules, "asyncpg", fake_asyncpg)

    # 1. Private VPC IP gets `ssl='require'`, `password=resolve_gcp_iam_db_token`, and `SET ROLE`.
    factory = make_asyncpg_pool_factory(
        "postgresql://cymbal-pooled-runtime-sa%40proj.iam@10.28.0.5:5432/postgres",
        iam_auth=True,
        db_role="cymbal_mcp_app",
    )
    pool_res = asyncio.run(factory())
    assert pool_res == "FAKE_ASYNCPG_POOL"
    assert captured_create_pool["password"] is mcp_db.resolve_gcp_iam_db_token
    assert captured_create_pool["ssl"] == "require"
    assert executed_init_sql == ['SET ROLE "cymbal_mcp_app";']

    # Unsafe db_role is rejected before connection creation.
    with pytest.raises(ValueError, match="Invalid PostgreSQL db_role"):
        make_asyncpg_pool_factory(
            "postgresql://127.0.0.1:5432/postgres",
            db_role="cymbal_mcp_app; DROP TABLE tenant_incidents;",
        )

    # 2. Offline `RLSDatabasePool.update_incident` mirrors `tenant_incidents_write_rbac_policy`.
    rls_pool = RLSDatabasePool()
    # Read-only analyst cannot mutate incidents -> None!
    denied_role = asyncio.run(
        rls_pool.update_incident(
            tenant_id=FINVAULT,
            incident_id="INC-FV-1001",
            user_role="read_only_analyst",
            agent_id="cymbal_shared_diagnostic_agent",
            summary="Analyst tamper attempt",
        )
    )
    assert denied_role is None

    # Cross-tenant SRE admin cannot mutate FinVault incident -> None!
    denied_cross_tenant = asyncio.run(
        rls_pool.update_incident(
            tenant_id=RETAILSTREAM,
            incident_id="INC-FV-1001",
            user_role="sre_admin",
            agent_id="cymbal_shared_diagnostic_agent",
            summary="Cross-tenant tamper attempt",
        )
    )
    assert denied_cross_tenant is None

    # Authorized FinVault SRE admin on `cymbal_shared_diagnostic_agent` updates cleanly!
    allowed = asyncio.run(
        rls_pool.update_incident(
            tenant_id=FINVAULT,
            incident_id="INC-FV-1001",
            user_role="sre_admin",
            agent_id="cymbal_shared_diagnostic_agent",
            summary="Wire settlement pool scaled to 64; latency normalized",
        )
    )
    assert allowed is not None
    assert allowed["tenant_id"] == FINVAULT
    assert "scaled to 64" in allowed["summary"]


def test_live_askpro_advisor_consultation_invokes_gemini_4_argon_and_caps_at_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`SharedModelRoutingPDP.escalate_to_advisor` invokes live advisor and caps at 1/turn."""
    fv_env = _mint_envelope(FINVAULT)
    advisor_calls: list[dict[str, str]] = []

    def _fake_live_advisor(**kwargs: str) -> str:
        advisor_calls.append(kwargs)
        return "Root cause confirmed: secondary connection pool saturation on shard 4."

    pdp = SharedModelRoutingPDP(live_advisor_fn=_fake_live_advisor)
    receipt = pdp.escalate_to_advisor(
        envelope=fv_env,
        trace_id="trace-askpro-live-1",
        escalation_reason="complex_synthesis",
        compact_evidence_digest="p99=4810ms, active_conns=64/64",
    )
    assert receipt["status"] == "ASKPRO_ADVISOR_COMPLETED"
    assert receipt["advisor_model"] == DEFAULT_PRO_MODEL
    assert receipt["live_vertex_call"] is True
    assert "secondary connection pool saturation" in receipt["advisor_guidance"]
    assert len(advisor_calls) == 1
    assert advisor_calls[0]["advisor_model"] == "gemini-4-carbon"

    # Second escalation on the same `(tenant_id, trace_id)` is blocked with 429!
    with pytest.raises(
        PermissionError, match="E_ASKPRO_CONSULTATION_CAP_EXCEEDED"
    ):
        pdp.escalate_to_advisor(
            envelope=fv_env,
            trace_id="trace-askpro-live-1",
            escalation_reason="ambiguous_evidence",
            compact_evidence_digest="retry",
        )
    assert platform_config.is_live_mode() is False


def test_terraform_alloydb_primary_iam_auth_and_direct_vpc_egress_contracts() -> (
    None
):
    """Verifies Terraform AlloyDB primary instance, IAM DB user, and Direct VPC Egress."""
    alloydb_tf = (
        REPO / "terraform" / "modules" / "platform_core" / "alloydb.tf"
    ).read_text(encoding="utf-8")
    gateway_tf = (
        REPO / "terraform" / "modules" / "platform_core" / "iap_gateway.tf"
    ).read_text(encoding="utf-8")
    alloydb_code = "\n".join(
        line
        for line in alloydb_tf.splitlines()
        if not line.lstrip().startswith("#")
    )
    assert (
        'resource "google_alloydb_instance" "pooled_rls_primary"'
        in alloydb_code
    )
    assert 'availability_type = "ZONAL"' in alloydb_code
    assert '"alloydb.iam_authentication"  = "on"' in alloydb_code
    assert '"password.enforce_complexity" = "on"' in alloydb_code
    assert "authorized_external_networks" not in alloydb_code
    assert (
        'resource "google_alloydb_user" "runtime_iam_db_user"' in alloydb_code
    )
    assert 'user_type      = "ALLOYDB_IAM_USER"' in alloydb_code
    assert 'egress = "PRIVATE_RANGES_ONLY"' in gateway_tf
    assert "ALLOYDB_IAM_AUTH" in gateway_tf
    assert "FIRESTORE_REVOCATION_STORE" in gateway_tf


def test_per_tenant_brokered_alloydb_iam_pool_factory_enforces_envelope_and_ct_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`make_tenant_iam_pool_factory` authenticates per-tenant pools as `ct-*@<project>.iam`."""
    import types

    from agents.context import _ACTIVE_TENANT_ENVELOPE
    from agents.tenant_credentials import (
        LocalTenantCredentialBackend,
        TenantCredentialBroker,
        set_default_broker,
    )
    from agents.tenant_identity import tenant_service_account_id

    created_pools: list[dict[str, Any]] = []
    executed_init_sql: list[str] = []

    class _FakeConn:
        async def execute(self, sql: str, *args: Any) -> None:
            executed_init_sql.append(sql)

    async def _fake_create_pool(**kwargs: Any) -> str:
        pwd_val = (
            kwargs["password"]()
            if callable(kwargs.get("password"))
            else kwargs.get("password")
        )
        created_pools.append({**kwargs, "resolved_password": pwd_val})
        if kwargs.get("init") is not None:
            await kwargs["init"](_FakeConn())
        return f"POOL_FOR_{kwargs.get('user')}"

    monkeypatch.setitem(
        __import__("sys").modules,
        "asyncpg",
        types.SimpleNamespace(create_pool=_fake_create_pool),
    )
    local_backend = LocalTenantCredentialBackend()
    set_default_broker(
        TenantCredentialBroker(project_id=PROJECT, backend=local_backend)
    )
    fv_env = _mint_envelope(FINVAULT)
    clear_tok = _ACTIVE_TENANT_ENVELOPE.set(None)
    try:
        factory = mcp_db.make_tenant_iam_pool_factory(
            "postgresql://10.65.3.2:5432/postgres",
            project_id=PROJECT,
            db_role="cymbal_mcp_app",
        )
        # Fail closed when `_ACTIVE_TENANT_ENVELOPE` is unset!
        with pytest.raises(
            PermissionError, match="E_ALLOYDB_TENANT_ENVELOPE_MISMATCH"
        ):
            asyncio.run(factory(FINVAULT))

        tok = _ACTIVE_TENANT_ENVELOPE.set(fv_env)
        try:
            # Fail closed on cross-tenant mismatch between active envelope and requested pool!
            with pytest.raises(
                PermissionError, match="E_ALLOYDB_TENANT_ENVELOPE_MISMATCH"
            ):
                asyncio.run(factory(RETAILSTREAM))

            pool_handle = asyncio.run(factory(FINVAULT))
            expected_user = (
                f"{tenant_service_account_id(FINVAULT)}@{PROJECT}.iam"
            )
            assert pool_handle == f"POOL_FOR_{expected_user}"
            assert created_pools[-1]["user"] == expected_user
            assert created_pools[-1]["ssl"] == "require"
            assert str(created_pools[-1]["resolved_password"]).startswith(
                f"local-{tenant_service_account_id(FINVAULT)}-"
            )
            assert executed_init_sql == ['SET ROLE "cymbal_mcp_app";']
        finally:
            _ACTIVE_TENANT_ENVELOPE.reset(tok)
    finally:
        _ACTIVE_TENANT_ENVELOPE.reset(clear_tok)
        set_default_broker(None)


def test_servicenow_reclaimed_pdi_dns_fallback_preserves_secret_manager_and_non_pdi_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reclaimed `*.service-now.com` PDI falls back deterministically while non-PDI re-raises."""
    import httpx
    from agents.gcp_live_bridge import LiveServiceNowITOMConnector

    rs_env = _mint_envelope(RETAILSTREAM, user_sub="bob@retailstream.com")
    fv_env = _mint_envelope(FINVAULT)
    conn = LiveServiceNowITOMConnector(project_id=PROJECT)

    # Cross-tenant call is still rejected with 403 before any network/Secret Manager lookup!
    with pytest.raises(PermissionError, match="403 Forbidden"):
        conn.query_itom_incidents(envelope=fv_env)

    def _raise_connect_error(*args: Any, **kwargs: Any) -> Any:
        raise httpx.ConnectError("[Errno -2] Name or service not known")

    monkeypatch.setattr(httpx, "get", _raise_connect_error)
    monkeypatch.setattr(httpx, "post", _raise_connect_error)

    # 1. Reclaimed ServiceNow PDI returns deterministic fallback + DLP redaction:
    monkeypatch.setattr(
        conn,
        "_load_secret_config",
        lambda _env: {
            "instance_url": "https://retailstream-snow-dev2.service-now.com",
            "username": "admin",
            "password": "secret",
        },
    )
    read_res = conn.query_itom_incidents(envelope=rs_env)
    assert (
        read_res["pdi_instance_state"]
        == "RECLAIMED_PDI_DNS_FALLBACK_AT_DEVELOPER_SERVICENOW_COM"
    )
    assert read_res["incidents"][0]["number"] == "INC0010001"

    write_res = conn.create_live_itom_incident(
        envelope=rs_env,
        short_description="Checkout latency spike for cardholder SSN 123-45-6789",
    )
    assert (
        write_res["pdi_instance_state"]
        == "RECLAIMED_PDI_DNS_FALLBACK_AT_DEVELOPER_SERVICENOW_COM"
    )
    assert "123-45-6789" not in write_res["dlp_redacted_description"]

    # 2. Non-PDI enterprise host (`servicenow.corp.internal`) still fails closed on ConnectError!
    monkeypatch.setattr(
        conn,
        "_load_secret_config",
        lambda _env: {
            "instance_url": "https://servicenow.corp.internal",
            "username": "admin",
            "password": "secret",
        },
    )
    with pytest.raises(httpx.ConnectError):
        conn.query_itom_incidents(envelope=rs_env)
