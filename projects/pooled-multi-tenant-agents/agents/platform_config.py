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

# pylint: disable=broad-exception-caught,import-outside-toplevel,line-too-long
# pylint: disable=missing-class-docstring

"""Layered, schema-validated platform configuration (single source of truth for tenants).

Merge order: `config/base.yaml` -> `config/environments/<env>.yaml` ->
`config/<tenants_dir>/*.yaml`.
The environment is selected by `CYMBAL_ENV` (default `sandbox`). Unknown fields are rejected so a
typo in an enterprise config fails `make config-check` instead of silently falling back to a
default.

This module deliberately imports nothing from `agents.*` so every other module can depend on it.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

CONFIG_ROOT = Path(
    os.getenv(
        "CYMBAL_CONFIG_DIR", Path(__file__).resolve().parent.parent / "config"
    )
)
DEFAULT_ENVIRONMENT = "sandbox"
PLACEHOLDER_PROJECT_IDS = frozenset(
    {"", "your-gcp-project-id", "your-project-id"}
)
_TENANT_ID_RE = re.compile(r"^[a-z][a-z0-9-]{2,62}$")
# Set by managed Google runtimes (Cloud Run services and jobs, GKE). `app.auth` trusts only the
# metadata server there; the local context signer is refused there.
MANAGED_RUNTIME_ENV = ("K_SERVICE", "CLOUD_RUN_JOB", "KUBERNETES_SERVICE_HOST")
# Explicit opt-in for sandbox mode (dev issuer, demo and simulation endpoints) when the process is
# NOT on a managed runtime. Off a managed runtime nothing proves where the process runs, so a bare
# `uvicorn app.main:app` (or the container image on a plain VM) must not mint synthetic tokens.
LOCAL_SANDBOX_ENV = "CYMBAL_LOCAL_SANDBOX"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TierLimits(_Strict):
    thinking_budget: int = Field(gt=0)
    rpm_limit: int = Field(gt=0)
    tpm_limit: int = Field(gt=0)
    max_turns_per_session: int = Field(gt=0, le=500)


class TokenPolicySettings(_Strict):
    """Configurable token-expiry and proactive-refresh bounds across Hops 0 to 5.

    Separates customer session length (`gateway_token_ttl_seconds`, up to `3600` s) from irrevocable
    downstream credentials (ADR-0014 Amendment A1): Cloud KMS context tokens stay capped at
    `min(gateway_ttl, 600)` s, and broker-minted tenant SA access tokens stay capped at `<= 300` s
    (`tenant_sa_token_ttl_seconds` may only tighten the `300` s ceiling).
    """

    gateway_token_ttl_seconds: int = Field(default=600, ge=60, le=3600)
    dpop_proof_max_age_seconds: int = Field(default=120, ge=30, le=300)
    tenant_sa_token_ttl_seconds: int = Field(default=300, ge=60, le=300)
    tenant_sa_refresh_margin_seconds: int = Field(default=60, ge=15, le=270)
    idp_broker_max_token_lifetime_seconds: int = Field(
        default=3600, ge=300, le=28800
    )
    idp_direct_max_token_lifetime_seconds: int = Field(
        default=5400, ge=300, le=28800
    )

    @model_validator(mode="after")
    def _validate_cross_token_bounds(self) -> TokenPolicySettings:
        if self.dpop_proof_max_age_seconds > self.gateway_token_ttl_seconds:
            raise ValueError(
                "token_policy.dpop_proof_max_age_seconds must not exceed gateway_token_ttl_seconds"
            )
        if (
            self.tenant_sa_token_ttl_seconds
            - self.tenant_sa_refresh_margin_seconds
            < 30
        ):
            raise ValueError(
                "token_policy.tenant_sa_token_ttl_seconds must exceed "
                "tenant_sa_refresh_margin_seconds by at least 30 seconds"
            )
        shortest_idp_cap = min(
            self.idp_broker_max_token_lifetime_seconds,
            self.idp_direct_max_token_lifetime_seconds,
        )
        if self.gateway_token_ttl_seconds > shortest_idp_cap:
            raise ValueError(
                "token_policy.gateway_token_ttl_seconds must not exceed "
                "idp_broker_max_token_lifetime_seconds or "
                "idp_direct_max_token_lifetime_seconds"
            )
        return self


class GcpSettings(_Strict):
    project_id: str = ""
    project_number: str | None = None
    region: str = "us-central1"
    kms_keyring: str = "cymbal-tenant-kr-prod"
    runbook_bucket: str = "{project_id}-runbooks"
    bigquery_dataset: str = "cymbal_agent_analytics"
    firestore_database: str = "cymbal-memory-bank-prod"
    model_armor_template_id: str = "cymbal-pooled-inbound-pep"
    dlp_inspect_template_id: str | None = None
    dlp_deidentify_template_id: str | None = None


_MODEL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._@-]{2,95}$")


class ModelSettings(_Strict):
    """Declarative multi-model routing catalog for Gemini 4, Claude, and Gemma tiers."""

    default_shared_model: str = "gemini-4-hydrogen"
    default_executor_model: str = "gemini-4-hydrogen"
    default_frontier_model: str = "gemini-4-carbon"
    fallback_frontier_model: str = "gemini-4-argon"
    fallback_fast_model: str = "gemini-3.8-flash"
    private_regulatory_model: str = "claude-3-7-sonnet@20250219"
    sovereign_open_weight_model: str = "gemma-3-27b-it"
    eval_judge_model: str = "gemini-4-hydrogen"
    standard_allowed_models: tuple[str, ...] = (
        "gemini-4-hydrogen",
        "gemini-4-carbon",
        "gemini-4-argon",
        "gemini-3.8-flash",
    )
    enterprise_allowed_models: tuple[str, ...] = (
        "gemini-4-hydrogen",
        "gemini-4-carbon",
        "gemini-4-argon",
        "gemini-3.8-flash",
        "claude-3-7-sonnet@20250219",
    )

    @field_validator(
        "default_shared_model",
        "default_executor_model",
        "default_frontier_model",
        "fallback_frontier_model",
        "fallback_fast_model",
        "private_regulatory_model",
        "sovereign_open_weight_model",
        "eval_judge_model",
    )
    @classmethod
    def _valid_model_id(cls, v: str) -> str:
        cleaned = v.strip()
        if not _MODEL_ID_RE.fullmatch(cleaned):
            raise ValueError(f"Invalid model identifier: {v!r}")
        return cleaned

    @field_validator("standard_allowed_models", "enterprise_allowed_models")
    @classmethod
    def _valid_allowed_list(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if not v:
            raise ValueError("Allowed model tuple must not be empty")
        cleaned = tuple(item.strip() for item in v)
        for item in cleaned:
            if not _MODEL_ID_RE.fullmatch(item):
                raise ValueError(
                    f"Invalid model identifier in allowed list: {item!r}"
                )
        return cleaned

    @model_validator(mode="after")
    def _defaults_in_allowed_sets(self) -> ModelSettings:
        std_set = set(self.standard_allowed_models)
        ent_set = set(self.enterprise_allowed_models)
        for required in (
            self.default_shared_model,
            self.default_executor_model,
            self.default_frontier_model,
        ):
            if required not in std_set:
                raise ValueError(
                    f"models.{required!r} must appear in models.standard_allowed_models"
                )
            if required not in ent_set:
                raise ValueError(
                    f"models.{required!r} must appear in models.enterprise_allowed_models"
                )
        if self.private_regulatory_model not in ent_set:
            raise ValueError(
                "models.private_regulatory_model must appear in models.enterprise_allowed_models"
            )
        return self


IdPProvider = Literal["google", "entra", "okta", "ping"]
_PINNED_SECRET_RE = re.compile(r"^[A-Za-z0-9_-]{1,255}/versions/[1-9][0-9]*$")
_KMS_CRYPTO_KEY_RE = re.compile(
    r"^projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/locations/[a-z0-9-]+/keyRings/[A-Za-z0-9_-]{1,63}"
    r"/cryptoKeys/[A-Za-z0-9_-]{1,63}$"
)


class TenantIdentity(_Strict):
    """How a tenant's users sign in (Hop 0). Direct federation by default; set `gcip_tenant_id`
    to sign in through the environment's Google Identity Platform broker instead.
    """

    issuer: str
    provider: IdPProvider = "google"
    audience: str | None = None  # defaults to identity.gateway_audience
    directory_id: str | None = (
        None  # Entra tenant ID (`tid`); required for provider=entra
    )
    role_claim: str | None = (
        None  # token claim carrying the user's role or groups
    )
    role_map: dict[str, str] | None = (
        None  # IdP group/app-role name -> platform role
    )
    gcip_tenant_id: str | None = None  # Identity Platform tenant (broker mode)
    sign_in_providers: tuple[
        str, ...
    ] = ()  # allowed `firebase.sign_in_provider` values
    max_token_lifetime_seconds: int | None = Field(
        default=None, ge=300, le=28800
    )

    @field_validator("issuer")
    @classmethod
    def _https(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("identity.issuer must be an https:// URL")
        return v

    @model_validator(mode="after")
    def _provider_fields(self) -> TenantIdentity:
        if self.provider == "entra" and not self.directory_id:
            raise ValueError(
                "identity.directory_id is required for provider 'entra'"
            )
        if self.gcip_tenant_id and not self.sign_in_providers:
            raise ValueError(
                "identity.sign_in_providers is required with gcip_tenant_id"
            )
        return self


class IdentitySettings(_Strict):
    """Environment-wide Hop 0 settings."""

    gateway_audience: str = "https://agent-gateway.cymbal.internal"
    broker_project_id: str | None = (
        None  # Google Identity Platform project (broker mode)
    )
    # SANDBOX ONLY: an in-process issuer that mints synthetic users' tokens for the demo UI,
    # scripts and CI. Allowed only when environment == "sandbox" and data is synthetic.
    dev_issuer: bool = False
    # Canonical public origin of the gateway (e.g. https://agents.example.com). Used as the DPoP
    # `htu` origin so forwarding headers cannot redirect proofs; required for customer data.
    public_origin: str | None = None
    # Secret Manager secret holding the gateway token signing key (EC P-256 PKCS#8 PEM), as
    # `<secret-id>/versions/<n>`: a pinned version so every instance signs with the same key.
    # Required for customer data; synthetic sandboxes may use an ephemeral per-process key.
    gateway_signing_secret: str | None = None
    # Optional previous Secret Manager secret version accepted for verification during signing-key
    # rotation overlap (`(active_kid, previous_kid, next_kid)` ring).
    gateway_previous_signing_secret: str | None = None
    # Optional next Secret Manager secret version pre-staged as verify-only during Step 1 of a
    # multi-instance rolling deploy before switching `gateway_signing_secret` to that version.
    gateway_next_signing_secret: str | None = None
    # Cloud KMS key that signs context tokens (ADR-0014 D1): an asymmetric EC_SIGN_P256_SHA256
    # key, `projects/<p>/locations/<l>/keyRings/<r>/cryptoKeys/<k>`, signing with
    # `context_signing_kms_key_version`. The `CONTEXT_SIGNING_KMS_KEY` (and `_VERSION`) env vars
    # override both. Required for customer data; without any key the gateway refuses to start
    # (tests and explicitly-flagged offline sandbox runs use a per-process local key instead).
    context_signing_kms_key: str | None = None
    context_signing_kms_key_version: int = Field(default=1, ge=1)

    @field_validator("context_signing_kms_key")
    @classmethod
    def _kms_key_name(cls, v: str | None) -> str | None:
        if v is not None and not _KMS_CRYPTO_KEY_RE.match(v):
            raise ValueError(
                "identity.context_signing_kms_key must be "
                "'projects/<p>/locations/<l>/keyRings/<r>/cryptoKeys/<k>'"
            )
        return v

    @field_validator(
        "gateway_signing_secret",
        "gateway_previous_signing_secret",
        "gateway_next_signing_secret",
    )
    @classmethod
    def _pinned_secret_version(cls, v: str | None) -> str | None:
        if v is not None and not _PINNED_SECRET_RE.match(v):
            raise ValueError(
                "gateway signing secret must be '<secret-id>/versions/<number>' (pinned, "
                "so all instances use one key)"
            )
        return v

    @model_validator(mode="after")
    def _rotation_ring_valid(self) -> IdentitySettings:
        if (
            self.gateway_previous_signing_secret is not None
            or self.gateway_next_signing_secret is not None
        ) and self.gateway_signing_secret is None:
            raise ValueError(
                "identity.gateway_previous_signing_secret and identity.gateway_next_signing_secret "
                "require identity.gateway_signing_secret to be set"
            )
        configured_versions = [
            secret
            for secret in (
                self.gateway_signing_secret,
                self.gateway_previous_signing_secret,
                self.gateway_next_signing_secret,
            )
            if secret is not None
        ]
        if len(configured_versions) != len(set(configured_versions)):
            raise ValueError(
                "identity.gateway_signing_secret, gateway_previous_signing_secret, and "
                "gateway_next_signing_secret must be distinct secret versions"
            )
        return self


# Reserved names: "global" is the platform-wide memory namespace and `cymbal-platform-global` is
# the platform key. A tenant claiming either could read or forge GLOBAL memory.
RESERVED_TENANT_IDS = frozenset({"global"})
RESERVED_KMS_KEY_IDS = frozenset({"cymbal-platform-global"})
# Platform capabilities are granted by role only (agents.context.ROLE_PLATFORM_SCOPES), never by
# tenant entitlements; otherwise a role-less token defaulting to `*` could inherit them.
PLATFORM_SCOPES = frozenset({"memory:tenant.write"})


def _reject_platform_scopes(scopes: tuple[str, ...] | None, where: str) -> None:
    leaked = sorted(set(scopes or ()) & PLATFORM_SCOPES)
    if leaked:
        raise ValueError(
            f"{where} may not list platform scopes {leaked}; they are granted by role"
        )


def _is_plain_https_url(url: str) -> bool:
    from urllib.parse import urlsplit

    parts = urlsplit(url)
    return bool(
        parts.scheme == "https"
        and parts.hostname
        and not parts.username
        and not parts.password
        and not parts.fragment
        and len(url) <= 512
    )


_GCP_PROJECT_ID_RE = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
TopologyPattern = Literal["pool", "silo", "hybrid"]
# Fields each pattern needs. Fields of another pattern are rejected, so a half-edited config
# (e.g. pattern switched back to pool with a silo URL left behind) fails instead of being ignored.
TOPOLOGY_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "pool": (),
    "silo": ("runtime_url", "project_id", "audience"),
    "hybrid": ("data_endpoint", "data_project_id", "mcp_audience"),
}
_TOPOLOGY_URL_FIELDS = (
    "runtime_url",
    "audience",
    "data_endpoint",
    "mcp_audience",
)
_TOPOLOGY_PROJECT_FIELDS = ("project_id", "data_project_id")


class TenantTopology(_Strict):
    """Where a tenant's runtime and data run (consumed by `agents.topology_router`).

    - `pool` (default): the shared runtime and data plane, in process.
    - `silo`: the tenant's own runtime (`runtime_url`) in its own project; requests are forwarded
      with a context token whose audience is `audience`.
    - `hybrid`: the shared runtime; data and MCP calls go to the tenant's Private Service Connect
      endpoint (`data_endpoint`) with a context token whose audience is `mcp_audience`.
    """

    pattern: TopologyPattern = "pool"
    runtime_url: str | None = None
    project_id: str | None = None
    audience: str | None = None
    data_endpoint: str | None = None
    data_project_id: str | None = None
    mcp_audience: str | None = None

    @model_validator(mode="after")
    def _pattern_fields(self) -> TenantTopology:
        required = TOPOLOGY_REQUIRED_FIELDS[self.pattern]
        missing = [f for f in required if not getattr(self, f)]
        if missing:
            raise ValueError(
                f"topology.pattern={self.pattern} requires {missing}"
            )
        foreign = sorted(
            f
            for fields in TOPOLOGY_REQUIRED_FIELDS.values()
            for f in fields
            if f not in required and getattr(self, f) is not None
        )
        if foreign:
            raise ValueError(
                f"topology.pattern={self.pattern} does not allow {foreign}"
            )
        for name in _TOPOLOGY_URL_FIELDS:
            value = getattr(self, name)
            if value is not None and not _is_plain_https_url(value):
                raise ValueError(
                    f"topology.{name} must be a plain https URL: {value!r}"
                )
        for name in _TOPOLOGY_PROJECT_FIELDS:
            value = getattr(self, name)
            if value is not None and not _GCP_PROJECT_ID_RE.match(value):
                raise ValueError(
                    f"topology.{name} is not a valid project ID: {value!r}"
                )
        return self

    def endpoints(self) -> tuple[str, ...]:
        """URLs and audiences this tenant owns (no other tenant may reuse them)."""
        return tuple(
            v
            for f in _TOPOLOGY_URL_FIELDS
            if (v := getattr(self, f)) is not None
        )

    def projects(self) -> tuple[str, ...]:
        return tuple(
            v
            for f in _TOPOLOGY_PROJECT_FIELDS
            if (v := getattr(self, f)) is not None
        )


class TenantSpec(_Strict):
    tenant_id: str
    display_name: str
    tier: Literal["enterprise", "standard"]
    identity: TenantIdentity
    cmek_key: str
    org_unit: str = "pooled-saas-tenant"
    authorized_scopes: tuple[str, ...] | None = None
    bigquery_row_policy_id: str | None = None
    # Secret Manager secret IDs this tenant owns (3LO connector credentials). Only this tenant's
    # service account may read them; a secret listed for two tenants is rejected.
    secret_ids: tuple[str, ...] = ()
    # Customer-hosted (Hop 5 BYO) MCP servers registered for this tenant: the only audiences the
    # gateway's token exchange will issue external tokens for (ADR-0014 D3). HTTPS URLs.
    external_mcp_audiences: tuple[str, ...] = ()
    # Audiences the credential broker may mint Google ID tokens for, for this tenant (ADR-0014 D2,
    # kind `id_token`, e.g. a model router URL). Empty = no ID tokens for this tenant.
    broker_id_token_audiences: tuple[str, ...] = ()
    # Pool (default), silo or hybrid. See `TenantTopology` and `agents.topology_router`.
    topology: TenantTopology = TenantTopology()
    # Optional per-tenant quota and autonomous call-ceiling overrides over `tiers.<tier>`.
    thinking_budget: int | None = Field(default=None, gt=0)
    rpm_limit: int | None = Field(default=None, gt=0)
    tpm_limit: int | None = Field(default=None, gt=0)
    max_turns_per_session: int | None = Field(default=None, gt=0, le=500)

    @field_validator("external_mcp_audiences", "broker_id_token_audiences")
    @classmethod
    def _external_mcp_urls(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        for url in v:
            if not _is_plain_https_url(url):
                raise ValueError(
                    f"audience entries must be plain https URLs: {url!r}"
                )
        if len(set(v)) != len(v):
            raise ValueError("audience list has duplicates")
        return v

    @model_validator(mode="after")
    def _topology_not_external_mcp(self) -> TenantSpec:
        # A silo/PSC audience must not double as an external MCP audience: the gateway exchange
        # would then mint tokens a silo accepts.
        overlap = sorted(
            set(self.topology.endpoints()) & set(self.external_mcp_audiences)
        )
        if overlap:
            raise ValueError(
                f"topology endpoints/audiences overlap external_mcp_audiences: {overlap}"
            )
        return self

    def row_policy_id(self) -> str:
        """BigQuery row access policy ID for this tenant (Terraform and runtime agree on it)."""
        return self.bigquery_row_policy_id or "rap_" + self.tenant_id.replace(
            "-", "_"
        )

    @field_validator("tenant_id")
    @classmethod
    def _tenant_id(cls, v: str) -> str:
        if not _TENANT_ID_RE.match(v):
            raise ValueError(
                "tenant_id must be lowercase letters, digits, and hyphens (3-63 chars)"
            )
        if v in RESERVED_TENANT_IDS:
            raise ValueError(
                f"tenant_id '{v}' is reserved for platform-wide memory"
            )
        return v

    @field_validator("authorized_scopes")
    @classmethod
    def _no_platform_scopes(
        cls, v: tuple[str, ...] | None
    ) -> tuple[str, ...] | None:
        _reject_platform_scopes(v, "authorized_scopes")
        return v

    @field_validator("cmek_key")
    @classmethod
    def _cmek_key(cls, v: str) -> str:
        if v in RESERVED_KMS_KEY_IDS:
            raise ValueError(f"cmek_key '{v}' is reserved for the platform")
        return v


class AgentIdentityBinding(_Strict):
    """Expected workload principal of one agent in this environment, and what it may do
    (ADR-0016). `workload_principal` is a Cloud Run Agent Identity principal
    (`principal://agents.global.org-<ORG_ID>.system.id.goog/...`) or a service-account email.
    """

    workload_principal: str
    allowed_purposes: tuple[str, ...] = ()

    @field_validator("workload_principal")
    @classmethod
    def _principal_shape(cls, v: str) -> str:
        from agents.workload_identity import normalize_principal

        candidate = v.strip()
        if "{" in candidate or "}" in candidate:
            probe = (
                candidate.replace("{org_id}", "1")
                .replace("{project_number}", "1")
                .replace("{region}", "us-central1")
            )
            if (
                "{" in probe
                or "}" in probe
                or normalize_principal(probe) is None
            ):
                raise ValueError(
                    "workload_principal template must resolve to an Agent Identity principal or "
                    "SA email"
                )
            return candidate
        principal = normalize_principal(candidate)
        if principal is None:
            raise ValueError(
                "workload_principal must be an Agent Identity principal or SA email"
            )
        return principal.value

    @field_validator("allowed_purposes")
    @classmethod
    def _purpose_shape(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        from agents.workload_identity import PURPOSE_RE

        bad = [p for p in v if not PURPOSE_RE.fullmatch(p)]
        if bad:
            raise ValueError(
                f"allowed_purposes must look like 'broker:<kind>' or 'mcp:<tool>': {bad}"
            )
        return v


class AgentIdentitySettings(_Strict):
    """Agent-level authorization (ADR-0016). `org_id` pins the issuer of Cloud Run Agent Identity
    tokens (the org's agent STS pool); without it no agent-identity caller is accepted.
    `bindings` (keyed by `agent_id`) is empty by default: enforcement is off until the flags are
    set, and then an unbound agent is refused."""

    org_id: str | None = None
    bindings: dict[str, AgentIdentityBinding] = {}

    @field_validator("org_id")
    @classmethod
    def _org_digits(cls, v: str | None) -> str | None:
        from agents.workload_identity import ORG_ID_RE

        if v is not None and not ORG_ID_RE.fullmatch(v):
            raise ValueError(
                "agent_identity.org_id must be the numeric organization id"
            )
        return v

    @model_validator(mode="after")
    def _bound_agents_in_org(self) -> AgentIdentitySettings:
        from agents.workload_identity import principal_org

        for agent_id, spec in self.bindings.items():
            raw_principal = spec.workload_principal
            if "{org_id}" in raw_principal:
                if not self.org_id:
                    raise ValueError(
                        f"agent_identity.bindings[{agent_id!r}]: {{org_id}} placeholder requires "
                        "agent_identity.org_id"
                    )
                raw_principal = raw_principal.replace("{org_id}", self.org_id)
            probe = raw_principal.replace("{project_number}", "1").replace(
                "{region}", "us-central1"
            )
            org = principal_org(probe)
            if org is not None and org != self.org_id:
                raise ValueError(
                    f"agent_identity.bindings[{agent_id!r}]: principal is not in org_id's "
                    "agent trust domain"
                )
        return self

    @field_validator("bindings")
    @classmethod
    def _agent_ids(
        cls, v: dict[str, AgentIdentityBinding]
    ) -> dict[str, AgentIdentityBinding]:
        from agents.workload_identity import AGENT_ID_RE

        bad = [k for k in v if not AGENT_ID_RE.fullmatch(k)]
        if bad:
            raise ValueError(
                f"agent_identity.bindings has malformed agent ids: {bad}"
            )
        return v


class PlatformConfig(_Strict):
    schema_version: Literal[1]
    environment: str
    data_classification: Literal["synthetic", "customer"]
    tenants_dir: str
    gcp: GcpSettings
    tiers: dict[Literal["enterprise", "standard"], TierLimits]
    default_scopes: tuple[str, ...]
    models: ModelSettings = ModelSettings()
    identity: IdentitySettings = IdentitySettings()
    token_policy: TokenPolicySettings = TokenPolicySettings()
    agent_identity: AgentIdentitySettings = AgentIdentitySettings()
    tenants: tuple[TenantSpec, ...]

    @field_validator("default_scopes")
    @classmethod
    def _no_platform_default_scopes(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        _reject_platform_scopes(v, "default_scopes")
        return v

    @model_validator(mode="after")
    def _identity_rules(self) -> PlatformConfig:
        if self.identity.dev_issuer and not (
            self.environment == "sandbox"
            and self.data_classification == "synthetic"
        ):
            raise ValueError(
                "identity.dev_issuer is allowed only in the 'sandbox' environment with synthetic "
                "data; it lets anyone mint user tokens"
            )
        broker_issuer = (
            f"https://securetoken.google.com/{self.identity.broker_project_id}"
            if self.identity.broker_project_id
            else None
        )
        if self.data_classification != "synthetic":
            origin = self.identity.public_origin or ""
            if (
                not origin.startswith("https://")
                or origin.rstrip("/").count("/") != 2
            ):
                raise ValueError(
                    "identity.public_origin (https://host, no path) is required for customer data"
                )
            if not self.identity.gateway_signing_secret:
                raise ValueError(
                    "identity.gateway_signing_secret (Secret Manager ID) is required for customer "
                    "data; instances must share one signing key"
                )
            if not self.identity.context_signing_kms_key:
                raise ValueError(
                    "identity.context_signing_kms_key (Cloud KMS EC_SIGN_P256_SHA256 key) is "
                    "required for customer data; there is no built-in context-signing key"
                )
            for t in self.tenants:
                ident = t.identity
                if not ident.gcip_tenant_id and ident.provider == "google":
                    raise ValueError(
                        f"{t.tenant_id}: direct 'google' federation trusts every Google account; "
                        "use the Identity Platform broker (gcip_tenant_id) for customer data"
                    )
                if not ident.role_map:
                    raise ValueError(
                        f"{t.tenant_id}: identity.role_map is required for customer data (no "
                        "default group names may grant platform roles)"
                    )
                if not ident.gcip_tenant_id and not ident.audience:
                    raise ValueError(
                        f"{t.tenant_id}: identity.audience is required for customer data (the "
                        "shared gateway_audience is guessable)"
                    )
        for t in self.tenants:
            if t.identity.gcip_tenant_id:
                if broker_issuer is None:
                    raise ValueError(
                        f"{t.tenant_id}: gcip_tenant_id needs identity.broker_project_id"
                    )
                if t.identity.issuer != broker_issuer:
                    raise ValueError(
                        f"{t.tenant_id}: broker tenants must use issuer {broker_issuer}"
                    )
            if (
                t.identity.max_token_lifetime_seconds is not None
                and self.token_policy.gateway_token_ttl_seconds
                > t.identity.max_token_lifetime_seconds
            ):
                raise ValueError(
                    f"{t.tenant_id}: identity.max_token_lifetime_seconds "
                    f"({t.identity.max_token_lifetime_seconds}s) must be >= "
                    f"token_policy.gateway_token_ttl_seconds "
                    f"({self.token_policy.gateway_token_ttl_seconds}s)"
                )
        return self

    @model_validator(mode="after")
    def _unique_tenants(self) -> PlatformConfig:
        ids = [t.tenant_id for t in self.tenants]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate tenant_id(s): {dupes}")
        keys = [t.cmek_key for t in self.tenants]
        shared = sorted({k for k in keys if keys.count(k) > 1})
        if shared:
            raise ValueError(
                f"cmek_key shared by multiple tenants (blast radius > 1): {shared}"
            )
        secrets = [s for t in self.tenants for s in t.secret_ids]
        shared_secrets = sorted({s for s in secrets if secrets.count(s) > 1})
        if shared_secrets:
            raise ValueError(
                f"secret_ids shared by multiple tenants (blast radius > 1): {shared_secrets}"
            )
        # A silo/PSC endpoint or token audience belongs to exactly one tenant, otherwise one
        # tenant's forwarded token would be accepted by another tenant's silo.
        endpoints = [
            e for t in self.tenants for e in set(t.topology.endpoints())
        ]
        shared_endpoints = {e for e in endpoints if endpoints.count(e) > 1}
        for t in self.tenants:
            shared_endpoints |= set(t.topology.endpoints()) & {
                a
                for o in self.tenants
                if o is not t
                for a in o.external_mcp_audiences
            }
        if shared_endpoints:
            raise ValueError(
                "topology endpoints/audiences shared by multiple tenants: "
                f"{sorted(shared_endpoints)}"
            )
        projects = [p for t in self.tenants for p in set(t.topology.projects())]
        shared_projects = sorted({p for p in projects if projects.count(p) > 1})
        if shared_projects:
            raise ValueError(
                f"topology projects shared by multiple tenants: {shared_projects}"
            )
        if self.gcp.project_id and self.gcp.project_id in projects:
            raise ValueError(
                f"topology project {self.gcp.project_id!r} is the pooled project; a silo or "
                "hybrid data plane must live in its own project"
            )
        return self

    # -- derived values ---------------------------------------------------------------------

    def project_id(self) -> str:
        return self.gcp.project_id

    def kms_key_name(self, cmek_key: str, project_id: str | None = None) -> str:
        return (
            f"projects/{project_id or self.gcp.project_id}/locations/{self.gcp.region}/"
            f"keyRings/{self.gcp.kms_keyring}/cryptoKeys/{cmek_key}"
        )

    def runbook_bucket(self, project_id: str | None = None) -> str:
        return self.gcp.runbook_bucket.format(
            project_id=project_id or self.gcp.project_id
        )

    def tenant_directory_entries(
        self, project_id: str | None = None
    ) -> dict[str, dict[str, Any]]:
        """Plain dicts in the legacy `TENANT_DIRECTORY` shape (tier left as a string)."""
        out: dict[str, dict[str, Any]] = {}
        for t in self.tenants:
            limits = resolve_effective_tier_limits(self, t.tier)
            thinking_budget = (
                t.thinking_budget
                if t.thinking_budget is not None
                else limits.thinking_budget
            )
            rpm_limit = (
                t.rpm_limit if t.rpm_limit is not None else limits.rpm_limit
            )
            tpm_limit = (
                t.tpm_limit if t.tpm_limit is not None else limits.tpm_limit
            )
            max_turns_per_session = (
                t.max_turns_per_session
                if t.max_turns_per_session is not None
                else limits.max_turns_per_session
            )
            out[t.tenant_id] = {
                "display_name": t.display_name,
                "tier": t.tier,
                "iss": t.identity.issuer,
                "org_unit": t.org_unit,
                "thinking_budget": thinking_budget,
                "rpm_limit": rpm_limit,
                "tpm_limit": tpm_limit,
                "max_turns_per_session": max_turns_per_session,
                "cmek_key_name": self.kms_key_name(t.cmek_key, project_id),
                "authorized_scopes": tuple(
                    t.authorized_scopes or self.default_scopes
                ),
                "secret_ids": tuple(t.secret_ids),
                "external_mcp_audiences": tuple(t.external_mcp_audiences),
                "topology": t.topology.model_dump(exclude_none=True),
            }
        return out


def _deep_merge(
    base: dict[str, Any], overlay: dict[str, Any]
) -> dict[str, Any]:
    merged = dict(base)
    for k, v in overlay.items():
        merged[k] = (
            _deep_merge(merged[k], v)
            if isinstance(v, dict) and isinstance(merged.get(k), dict)
            else v
        )
    return merged


def _read_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise TypeError(f"{path}: top level must be a mapping")
    return data


def available_environments(root: Path = CONFIG_ROOT) -> list[str]:
    return sorted(
        p.name.removesuffix(".yaml")
        for p in (root / "environments").glob("*.yaml")
    )


def load_platform_config(
    environment: str | None = None, root: Path = CONFIG_ROOT
) -> PlatformConfig:
    env = environment or os.getenv("CYMBAL_ENV", DEFAULT_ENVIRONMENT)
    env_file = root / "environments" / f"{env}.yaml"
    if not env_file.exists():
        raise FileNotFoundError(
            f"E_CONFIG_ENV_NOT_FOUND: {env_file} (available: {available_environments(root)})"
        )
    merged = _deep_merge(_read_yaml(root / "base.yaml"), _read_yaml(env_file))
    tenants_dir = root / str(merged.get("tenants_dir", ""))
    tenant_files = (
        sorted(tenants_dir.glob("*.yaml")) if tenants_dir.is_dir() else []
    )
    tenants = []
    for f in tenant_files:
        data = _read_yaml(f)
        if data.get("tenant_id") != f.stem:
            raise ValueError(
                f"{f}: tenant_id must match the file name ('{f.stem}')"
            )
        tenants.append(data)
    merged["tenants"] = tenants
    return PlatformConfig.model_validate(merged)


def get_platform_config(environment: str | None = None) -> PlatformConfig:
    """Resolves `CYMBAL_ENV` on every call; only the parsed config per environment is cached."""
    return _cached_platform_config(
        environment or os.getenv("CYMBAL_ENV", DEFAULT_ENVIRONMENT)
    )


@lru_cache(maxsize=8)
def _cached_platform_config(environment: str) -> PlatformConfig:
    return load_platform_config(environment)


def _parse_optional_env_int(raw_value: str | None, env_name: str) -> int | None:
    """Parses an optional base-10 integer environment variable override.

    Args:
        raw_value: Raw environment variable value from `os.getenv`.
        env_name: Environment variable name for structured error reporting.

    Returns:
        Parsed integer when set to a non-empty value, else `None`.

    Raises:
        ValueError: If `raw_value` is non-empty and not a valid base-10 integer.
    """
    if raw_value is None:
        return None
    stripped_value = raw_value.strip()
    if not stripped_value:
        return None
    try:
        return int(stripped_value, 10)
    except ValueError as exc:
        raise ValueError(
            f"E_CONFIG_INVALID_ENV_INT: {env_name} must be a base-10 integer, got {raw_value!r}"
        ) from exc


def resolve_effective_token_policy(
    config: PlatformConfig | None = None,
) -> TokenPolicySettings:
    """Resolves active token lifetimes from layered config plus Terraform/Cloud Run env overrides.

    Precedence: explicit environment variable > `config/environments/<env>.yaml` >
    `config/base.yaml`.

    Args:
        config: Optional pre-loaded `PlatformConfig`; loads active environment config when omitted.

    Returns:
        Validated `TokenPolicySettings` enforcing all per-field and cross-token bounds.

    Raises:
        ValueError: If any environment override is non-numeric or violates cross-token bounds.
    """
    active_config = config if config is not None else get_platform_config()
    env_overrides = {
        "gateway_token_ttl_seconds": _parse_optional_env_int(
            os.getenv("GATEWAY_TOKEN_TTL_SECONDS"), "GATEWAY_TOKEN_TTL_SECONDS"
        ),
        "dpop_proof_max_age_seconds": _parse_optional_env_int(
            os.getenv("DPOP_PROOF_MAX_AGE_SECONDS"),
            "DPOP_PROOF_MAX_AGE_SECONDS",
        ),
        "tenant_sa_token_ttl_seconds": _parse_optional_env_int(
            os.getenv("TENANT_SA_TOKEN_TTL_SECONDS"),
            "TENANT_SA_TOKEN_TTL_SECONDS",
        ),
        "tenant_sa_refresh_margin_seconds": _parse_optional_env_int(
            os.getenv("TENANT_SA_REFRESH_MARGIN_SECONDS"),
            "TENANT_SA_REFRESH_MARGIN_SECONDS",
        ),
        "idp_broker_max_token_lifetime_seconds": _parse_optional_env_int(
            os.getenv("IDP_BROKER_MAX_TOKEN_LIFETIME_SECONDS"),
            "IDP_BROKER_MAX_TOKEN_LIFETIME_SECONDS",
        ),
        "idp_direct_max_token_lifetime_seconds": _parse_optional_env_int(
            os.getenv("IDP_DIRECT_MAX_TOKEN_LIFETIME_SECONDS"),
            "IDP_DIRECT_MAX_TOKEN_LIFETIME_SECONDS",
        ),
    }
    if all(override is None for override in env_overrides.values()):
        return active_config.token_policy
    merged_policy = active_config.token_policy.model_dump()
    for field_name, override_value in env_overrides.items():
        if override_value is not None:
            merged_policy[field_name] = override_value
    resolved_policy = TokenPolicySettings.model_validate(merged_policy)
    for tenant in active_config.tenants:
        tenant_max_lifetime = tenant.identity.max_token_lifetime_seconds
        if (
            tenant_max_lifetime is not None
            and resolved_policy.gateway_token_ttl_seconds > tenant_max_lifetime
        ):
            raise ValueError(
                f"{tenant.tenant_id}: identity.max_token_lifetime_seconds "
                f"({tenant_max_lifetime}s) must be >= effective gateway_token_ttl_seconds "
                f"({resolved_policy.gateway_token_ttl_seconds}s)"
            )
    return resolved_policy


def resolve_effective_tier_limits(
    config: PlatformConfig, tier_name: Literal["enterprise", "standard"]
) -> TierLimits:
    """Resolves tier quotas with optional Terraform/Cloud Run session call-ceiling override.

    Args:
        config: Loaded `PlatformConfig` holding base tier definitions.
        tier_name: Subscription tier (`"enterprise"` or `"standard"`).

    Returns:
        Validated `TierLimits` for `tier_name`.

    Raises:
        ValueError: If the tier's call-ceiling environment override is invalid or out of range.
    """
    base_limits = config.tiers[tier_name]
    if tier_name == "enterprise":
        turns_override = _parse_optional_env_int(
            os.getenv("ENTERPRISE_MAX_TURNS_PER_SESSION"),
            "ENTERPRISE_MAX_TURNS_PER_SESSION",
        )
    else:
        turns_override = _parse_optional_env_int(
            os.getenv("STANDARD_MAX_TURNS_PER_SESSION"),
            "STANDARD_MAX_TURNS_PER_SESSION",
        )
    if turns_override is None:
        return base_limits
    merged_limits = base_limits.model_dump()
    merged_limits["max_turns_per_session"] = turns_override
    return TierLimits.model_validate(merged_limits)


def is_live_mode() -> bool:
    if os.getenv("CYMBAL_OFFLINE_CI") == "1":
        return False
    return (
        os.getenv("CYMBAL_LIVE_GCP") == "1"
        or os.getenv("RUN_LIVE_GCP_TESTS") == "1"
    )


def resolve_project_number(cfg: PlatformConfig | None = None) -> str | None:
    """Resolves the active numeric GCP project number without hardcoded fallbacks.

    Order: `GOOGLE_CLOUD_PROJECT_NUMBER` env var -> matching `cfg.gcp.project_number` ->
    managed-runtime metadata server (`numeric-project-id`), or `None` if unavailable.
    """
    env_num = os.getenv("GOOGLE_CLOUD_PROJECT_NUMBER", "").strip()
    if env_num.isdigit():
        return env_num
    active_cfg = cfg if cfg is not None else get_platform_config()
    env_project = (os.getenv("GOOGLE_CLOUD_PROJECT") or "").strip()
    cfg_num = getattr(getattr(active_cfg, "gcp", None), "project_number", None)
    if (
        isinstance(cfg_num, str)
        and cfg_num.isdigit()
        and (
            not env_project
            or env_project in {active_cfg.gcp.project_id, cfg_num}
        )
    ):
        return cfg_num
    if any(os.getenv(k) for k in MANAGED_RUNTIME_ENV):
        return _fetch_metadata_project_number()
    return None


@lru_cache(maxsize=1)
def _fetch_metadata_project_number() -> str | None:
    try:
        import httpx

        resp = httpx.get(
            "http://metadata.google.internal/computeMetadata/v1/project/numeric-project-id",
            headers={"Metadata-Flavor": "Google"},
            timeout=2.0,
        )
        if resp.status_code == 200:
            candidate = resp.text.strip()
            if candidate.isdigit():
                return candidate
    except Exception:
        return None
    return None


def resolve_project_id(raw_project_id: str | None = None) -> str:
    """Project precedence: explicit arg > GOOGLE_CLOUD_PROJECT > environment config.

    A numeric project number is translated to the configured project ID when it matches. In live
    mode an unset or placeholder project raises instead of silently targeting another project.
    """
    cfg = get_platform_config()
    pid = (
        raw_project_id
        or os.getenv("GOOGLE_CLOUD_PROJECT")
        or cfg.gcp.project_id
        or ""
    ).strip()
    if (
        pid.isdigit()
        and cfg.gcp.project_number
        and pid == cfg.gcp.project_number
    ):
        pid = cfg.gcp.project_id
    if pid in PLACEHOLDER_PROJECT_IDS:
        if is_live_mode():
            raise RuntimeError(
                "E_PROJECT_NOT_CONFIGURED: set GOOGLE_CLOUD_PROJECT or gcp.project_id in "
                f"config/environments/{cfg.environment}.yaml before running in live mode."
            )
        return cfg.gcp.project_id or "local-sandbox"
    return pid
