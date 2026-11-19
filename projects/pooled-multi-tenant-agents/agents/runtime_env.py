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

"""Runtime environment contract: the ONE list of environment variables the platform reads.

Terraform (`terraform/iap_gateway.tf`), deploy scripts, and code must agree with this list; the
parity tests in `tests/unit/test_platform_config_contract.py` enforce that. Secrets are not
environment variables in live mode (Secret Manager only, docs/secrets_management.md).
"""

from __future__ import annotations

import os

from agents import platform_config
from agents.platform_config import (
    get_platform_config,
    is_live_mode,
    resolve_project_id,
)

# name -> purpose
RUNTIME_ENV_CONTRACT: dict[str, str] = {
    # Environment selection and mode
    "CYMBAL_ENV": "Platform config environment (config/environments/<env>.yaml); default sandbox",
    "CYMBAL_CONFIG_DIR": "Alternate config directory (enterprise overlays)",
    "CYMBAL_LIVE_GCP": "1 = call live Google Cloud / 3P APIs; unset = local simulation",
    "RUN_LIVE_GCP_TESTS": "1 = enable opt-in live tests",
    "CYMBAL_OFFLINE_CI": "1 = force offline even if live flags are set",
    "CYMBAL_TENANT_SCOPED_CREDENTIALS": (
        "0 = migration escape hatch to the shared identity (ADR-0010)"
    ),
    # Context-token signing (ADR-0014 B2)
    "CONTEXT_SIGNING_KMS_KEY": (
        "Overrides identity.context_signing_kms_key (KMS key or key version)"
    ),
    "CONTEXT_SIGNING_KMS_KEY_VERSION": "Overrides identity.context_signing_kms_key_version",
    # Credential broker (ADR-0014 B4)
    "CREDENTIAL_BROKER_URL": "Runtime: broker service URL; live mode then mints via the broker",
    "BROKER_3LO_VAULT_URL": (
        "Optional override URL for the out-of-process 3LO user consent vault on the broker"
    ),
    "CYMBAL_DIRECT_IMPERSONATION": (
        "Runtime, pre-B4 only: 1 = impersonate tenant SAs directly (live)"
    ),
    "AGENT_RUNTIME_URLS": (
        "Gateway: JSON map agent_id -> agent runtime service URL (ADR-0014 B5); unset = "
        "turns run in process"
    ),
    "RUNTIME_AGENT_ID": "Agent runtime service only: the one catalog agent this service runs (B5)",
    "RUNTIME_ALLOWED_CALLERS": (
        "Agent runtime service only: comma-separated caller principals (the gateway SA)"
    ),
    "RUNTIME_EXPECTED_AUDIENCE": (
        "Agent runtime service only: its own URL (the gateway's ID-token audience)"
    ),
    "CONTEXT_TOKEN_KMS_KEY_VERSION": "Agent runtime service: KMS signing key version "
    "resource name for public-key "
    "verification",
    "CONTEXT_TOKEN_REQUIRE_KMS": "Agent runtime service: 1 = require KMS public-key verification",
    "CONTEXT_TOKEN_BIND_AGENT_ID": (
        "Gateway: 1 = bind the routed agent_id claim into signed context tokens (ADR-0016)"
    ),
    "CONTEXT_TOKEN_REQUIRE_AGENT_ID": (
        "Verifiers (runtime, broker, MCP): 1 = refuse context tokens without a signed "
        "agent_id claim"
    ),
    "BROKER_REQUIRE_AGENT_BINDING": (
        "Broker service: 1 = require caller workload identity to match the token's signed "
        "agent_id binding"
    ),
    "MCP_REQUIRE_AGENT_BINDING": (
        "MCP server: 1 = require caller workload identity to match the token's signed "
        "agent_id binding"
    ),
    "WORKLOAD_IDENTITY_AGENT_PRINCIPAL_CLAIM": (
        "Caller ID-token claim carrying the Agent Identity SPIFFE ID (default sub)"
    ),
    "WORKLOAD_IDENTITY_SA_PRINCIPAL_CLAIM": (
        "Caller ID-token claim carrying the service account email (default email)"
    ),
    "CONTEXT_JWKS_URL": (
        "Agent runtime service only: fetch context public keys from the gateway's internal "
        "JWKS route instead of KMS"
    ),
    "CONTEXT_JWKS_AUDIENCE": (
        "Gateway internal JWKS route / runtime fetcher: ID-token audience (the gateway URL)"
    ),
    "CONTEXT_JWKS_ALLOWED_CALLERS": (
        "Gateway only: principals allowed on /internal/v1/context-jwks (agent services); "
        "unset = route absent"
    ),
    "CYMBAL_KMS_MTLS": "0 = do not use the KMS mTLS endpoint even when "
    "a workload certificate config is "
    "present",
    "GOOGLE_API_CERTIFICATE_CONFIG": (
        "Set by Cloud Run for agent identity (--identity-certificate): Google APIs are "
        "called over mTLS"
    ),
    "BROKER_ALLOWED_CALLERS": "Broker service only: comma-separated caller SA emails (runtime SA)",
    "BROKER_EXPECTED_AUDIENCE": "Broker service only: its own URL (caller ID token aud)",
    "CYMBAL_LOCAL_CONTEXT_SIGNER": "1 = OFFLINE SANDBOX ONLY: per-process local context signer",
    "CYMBAL_LOCAL_SANDBOX": (
        "1 = opt in to sandbox mode (dev issuer, demo endpoints) off a managed runtime; "
        "ignored on Cloud Run / GKE, where the metadata server decides"
    ),
    "K_SERVICE": (
        "Set by Cloud Run services (managed runtime: metadata-only project, no local signer)"
    ),
    "CLOUD_RUN_JOB": "Set by Cloud Run jobs (managed runtime, as above)",
    "KUBERNETES_SERVICE_HOST": "Set by GKE (managed runtime, as above)",
    # Google Cloud placement (non-secret; set by Terraform on Cloud Run)
    "GOOGLE_CLOUD_PROJECT": "Target project (overrides gcp.project_id)",
    "GOOGLE_CLOUD_PROJECT_NUMBER": "Target project number (informational)",
    "GOOGLE_CLOUD_REGION": "Region (overrides gcp.region)",
    "GOOGLE_CLOUD_LOCATION": "Vertex AI location",
    "GOOGLE_GENAI_USE_VERTEXAI": "Use Vertex AI for Gemini",
    "OTEL_EXPORTER_GCP_TRACE_PROJECT_ID": "Cloud Trace export project",
    "SHARED_DIAGNOSTIC_MODEL": "Model for the shared diagnostic agent",
    "FINVAULT_AGENT_ALPHA_MODEL": "Sandbox demo: model for the private FinVault agent",
    "CYMBAL_OAUTH_REDIRECT_URI": "3LO OAuth callback (https://<gateway-url>/oauth2/callback)",
    "OAUTH_3LO_CSRF_SECRET_VERSION": (
        "Pinned Secret Manager version resource name for multi-instance 3LO OAuth state HMAC"
    ),
    "OAUTH_REQUIRE_SHARED_CSRF_KEY": (
        "1 = require pinned OAUTH_3LO_CSRF_SECRET_VERSION for multi-instance OAuth callbacks"
    ),
    "CONTEXT_CACHE_TTL_SECONDS": "Shared prefix cache TTL",
    # Configurable token-expiry and autonomous call-ceiling policy (var.token_and_session_policy)
    "GATEWAY_TOKEN_TTL_SECONDS": "Gateway DPoP session token TTL (60-3600s; ctx+jwt stays <= 600s)",
    "DPOP_PROOF_MAX_AGE_SECONDS": "RFC 9449 DPoP proof freshness window (30-300s)",
    "TENANT_SA_TOKEN_TTL_SECONDS": (
        "Per-tenant Google IAM access-token TTL (60-300s; may only lower 300s cap)"
    ),
    "TENANT_SA_REFRESH_MARGIN_SECONDS": "Proactive tenant SA token refresh lead window (15-270s)",
    "IDP_BROKER_MAX_TOKEN_LIFETIME_SECONDS": (
        "Max Hop 0 IdP token lifetime in Identity Platform mode"
    ),
    "IDP_DIRECT_MAX_TOKEN_LIFETIME_SECONDS": "Max Hop 0 IdP token lifetime in direct OIDC mode",
    "STANDARD_MAX_TURNS_PER_SESSION": (
        "Default max autonomous agent calls per gateway token (standard)"
    ),
    "ENTERPRISE_MAX_TURNS_PER_SESSION": (
        "Default max autonomous agent calls per gateway token (enterprise)"
    ),
    # Resource names (Terraform outputs; default from platform config)
    "DLP_INSPECT_TEMPLATE": "Full Cloud DLP inspect template name",
    "DLP_DEIDENTIFY_TEMPLATE": "Full Cloud DLP de-identify template name",
    "MODEL_ARMOR_TEMPLATE_ID": "Model Armor template ID (not the full path)",
    "KMS_KEYRING_NAME": "Tenant CMEK keyring",
    "FINVAULT_KMS_KEY": "Sandbox demo: FinVault CMEK key name",
    "RETAILSTREAM_KMS_KEY": "Sandbox demo: RetailStream CMEK key name",
    "RUNBOOK_BUCKET_NAME": "Pooled runbook bucket",
    "FIRESTORE_DATABASE": "Firestore memory bank database",
    "MEMORY_BANK_REASONING_ENGINE": (
        "Optional Memory Bank in Gemini parent reasoningEngine resource name"
    ),
    "BIGQUERY_DATASET": "BigQuery analytics dataset",
    "BIGQUERY_OTEL_TABLE": "BigQuery OTel spans table",
    "DATABASE_URL": "PostgreSQL / AlloyDB connection DSN for RLS pool initialization (optional)",
    "ALLOYDB_IAM_AUTH": (
        "1 = authenticate asyncpg to AlloyDB using short-lived Google IAM OAuth2 tokens"
    ),
    "ALLOYDB_TENANT_IAM_AUTH": (
        "1 = authenticate per-tenant asyncpg pools to AlloyDB using brokered ct-* tenant IAM tokens"
    ),
    "FIRESTORE_REVOCATION_STORE": (
        "1 = share control-plane agent suspensions and tenant revocations via Firestore"
    ),
    "REDIS_URL": (
        "Optional Memorystore / Redis URL (redis://host:port/db) for shared DPoP replay and "
        "rate-limit bulkheads"
    ),
    "REDIS_TLS_SECRET_VERSION": (
        "Pinned Secret Manager version holding JSON {url, ca_pem} for AUTH+TLS Memorystore "
        "Redis (preferred over plaintext REDIS_URL)"
    ),
    # Agent Sandbox in Gemini (ADR-0012 / PR-S2; live mode requires AGENT_SANDBOX_REASONING_ENGINE_NAME)
    "AGENT_SANDBOX_REASONING_ENGINE_NAME": (
        "agent runtime in Gemini parent resource name for live sandboxEnvironments; unset fails "
        "closed in live mode"
    ),
    "AGENT_SANDBOX_CODE_TEMPLATE": (
        "Gemini SandboxEnvironmentTemplate ID for python/javascript sandboxes (optional override)"
    ),
    "AGENT_SANDBOX_SHELL_TEMPLATE": (
        "Gemini SandboxEnvironmentTemplate ID for bash sandboxes (optional override)"
    ),
    "AGENT_SANDBOX_LRO_TIMEOUT_SECONDS": (
        "Max seconds to poll agent sandbox in GeminiEnvironments LROs (default 240s in live mode)"
    ),
    # Offline-only connector settings (ignored for secrets in live mode)
    "AZURE_ENTRA_TENANT_ID": "Entra directory ID (non-secret)",
    "AZURE_ENTRA_CLIENT_ID": "Entra app client ID (non-secret)",
    "AZURE_ENTRA_CLIENT_SECRET": "OFFLINE SANDBOX ONLY; live mode reads Secret Manager",
    # Local workstation TLS shims (workstation / sandbox), not used on Cloud Run
    "GOOGLE_API_USE_CLIENT_CERTIFICATE": "Disable corporate client certs for sandbox ADC",
    "CLOUDSDK_CONTEXT_AWARE_USE_CLIENT_CERTIFICATE": "Same, for gcloud",
    "CLOUDSDK_CONTEXT_AWARE_USE_MTLS_FOR_GRPC": "Same, for gRPC",
}


def validate_runtime_environment() -> dict[str, object]:
    """Fail-closed startup check. Raises in live mode when the deployment is misconfigured."""
    cfg = get_platform_config()
    # Fail closed on invalid token-expiry or session-turn overrides in every mode (including
    # startup).
    token_policy = platform_config.resolve_effective_token_policy(cfg)
    standard_limits = platform_config.resolve_effective_tier_limits(
        cfg, "standard"
    )
    enterprise_limits = platform_config.resolve_effective_tier_limits(
        cfg, "enterprise"
    )
    project_id = (
        resolve_project_id()
    )  # raises E_PROJECT_NOT_CONFIGURED in live mode
    problems: list[str] = []
    if not cfg.tenants:
        problems.append(f"no tenants found in config/{cfg.tenants_dir}")
    if is_live_mode():
        if not (
            os.getenv("DLP_INSPECT_TEMPLATE") or cfg.gcp.dlp_inspect_template_id
        ):
            problems.append("DLP inspect template not configured")
        if not (
            os.getenv("DLP_DEIDENTIFY_TEMPLATE")
            or cfg.gcp.dlp_deidentify_template_id
        ):
            problems.append("DLP de-identify template not configured")
        if os.getenv("CYMBAL_TENANT_SCOPED_CREDENTIALS", "1") == "0":
            problems.append(
                "CYMBAL_TENANT_SCOPED_CREDENTIALS=0 restores the shared identity and is not "
                "allowed in live mode"
            )
    if problems and is_live_mode():
        raise RuntimeError("E_RUNTIME_MISCONFIGURED: " + "; ".join(problems))
    return {
        "environment": cfg.environment,
        "data_classification": cfg.data_classification,
        "project_id": project_id,
        "live_mode": is_live_mode(),
        "tenants": [t.tenant_id for t in cfg.tenants],
        "gateway_token_ttl_seconds": token_policy.gateway_token_ttl_seconds,
        "standard_max_turns_per_session": standard_limits.max_turns_per_session,
        "enterprise_max_turns_per_session": enterprise_limits.max_turns_per_session,
        "warnings": problems,
    }
