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

"""Shared runtime configuration, ADC/broker credential headers, and facade hooks for live
adapters.
"""

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

import google.auth
import google.auth.transport.requests
import httpx
from agents.context import ContextEnvelope
from agents.interceptors import egress_dlp_and_nlc_guardrail
from agents.kms_rest import configure_client_certificate_env
from agents.platform_config import get_platform_config, is_live_mode
from agents.shared_diagnostic_agent import get_clean_project_id
from agents.tenant_credentials import (
    TenantIsolationPolicy,
    get_default_broker,
    tenant_scoped_credentials_enabled,
)


def _live_enabled() -> bool:
    """Resolves `is_live_gcp_enabled` via `agents.gcp_live_bridge` when loaded for
    monkeypatching.
    """
    facade = sys.modules.get("agents.gcp_live_bridge")
    hook = getattr(facade, "is_live_gcp_enabled", is_live_gcp_enabled)
    return bool(hook())


def _adc_headers(project_id: str) -> dict[str, str]:
    """Resolves `_legacy_adc_headers` via `agents.gcp_live_bridge` when loaded for
    monkeypatching.
    """
    facade = sys.modules.get("agents.gcp_live_bridge")
    hook = getattr(facade, "_legacy_adc_headers", _legacy_adc_headers)
    return dict(hook(project_id))


def _access_secret(
    *, envelope: ContextEnvelope, project_id: str, secret_id: str
) -> dict[str, str]:
    """Resolves `access_tenant_secret` via `agents.gcp_live_bridge` when loaded for
    monkeypatching.
    """
    facade = sys.modules.get("agents.gcp_live_bridge")
    hook = getattr(facade, "access_tenant_secret", access_tenant_secret)
    return dict(
        hook(envelope=envelope, project_id=project_id, secret_id=secret_id)
    )


def _egress_guardrail(**kwargs: object) -> str:
    """Resolves `egress_dlp_and_nlc_guardrail` via `agents.gcp_live_bridge` when monkeypatched."""
    facade = sys.modules.get("agents.gcp_live_bridge")
    hook = getattr(
        facade, "egress_dlp_and_nlc_guardrail", egress_dlp_and_nlc_guardrail
    )
    return str(hook(**kwargs))


# Disable workstation corporate mTLS client certs locally so SDKs use sandbox ADC cleanly, while
# preserving workload SPIFFE mTLS on Cloud Run Agent Identity (--identity-certificate).
configure_client_certificate_env()

DEFAULT_GCP_PROJECT = get_clean_project_id()


def is_live_gcp_enabled() -> bool:
    """Returns True only when live GCP API calls are explicitly opted into (`CYMBAL_LIVE_GCP=1` or
    `RUN_LIVE_GCP_TESTS=1`).

    Prevents local developer/teammate runs from triggering unsolicited `gcloud` ADC reauth or
    `403 PERMISSION_DENIED` requests against `cymbal-multitenancy-example`.
    """
    return is_live_mode()


# Non-secret settings: environment variable (set by Terraform on Cloud Run) > platform config
# (config/environments/<env>.yaml). No sandbox-specific IDs are hard-coded here.
_CFG = get_platform_config()
DEFAULT_GCP_REGION = os.getenv("GOOGLE_CLOUD_REGION", _CFG.gcp.region)
DEFAULT_FIRESTORE_DB = os.getenv(
    "FIRESTORE_DATABASE", _CFG.gcp.firestore_database
)
DEFAULT_BQ_DATASET = os.getenv("BIGQUERY_DATASET", _CFG.gcp.bigquery_dataset)
DEFAULT_BQ_TABLE = os.getenv("BIGQUERY_OTEL_TABLE", "tenant_otel_spans")
_DLP_PARENT = f"projects/{DEFAULT_GCP_PROJECT}/locations/{DEFAULT_GCP_REGION}"
DEFAULT_DLP_INSPECT_TEMPLATE = os.getenv(
    "DLP_INSPECT_TEMPLATE",
    (
        f"{_DLP_PARENT}/inspectTemplates/{_CFG.gcp.dlp_inspect_template_id}"
        if _CFG.gcp.dlp_inspect_template_id
        else ""
    ),
)
DEFAULT_DLP_DEIDENTIFY_TEMPLATE = os.getenv(
    "DLP_DEIDENTIFY_TEMPLATE",
    (
        f"{_DLP_PARENT}/deidentifyTemplates/{_CFG.gcp.dlp_deidentify_template_id}"
        if _CFG.gcp.dlp_deidentify_template_id
        else ""
    ),
)
DEFAULT_MODEL_ARMOR_TEMPLATE_ID = os.getenv(
    "MODEL_ARMOR_TEMPLATE_ID", _CFG.gcp.model_armor_template_id
)
DEFAULT_KMS_KEYRING = os.getenv("KMS_KEYRING_NAME", _CFG.gcp.kms_keyring)
FINVAULT_KMS_KEY = os.getenv(
    "FINVAULT_KMS_KEY",
    _CFG.kms_key_name("finvault-alpha-cmek", DEFAULT_GCP_PROJECT),
)
RETAILSTREAM_KMS_KEY = os.getenv(
    "RETAILSTREAM_KMS_KEY",
    _CFG.kms_key_name("retailstream-beta-cmek", DEFAULT_GCP_PROJECT),
)


# ---------------------------------------------------------------------------------------------
# Tenant-scoped credentials (blast-radius containment, ADR-0010)
# ---------------------------------------------------------------------------------------------


def _tenant_policy(project_id: str) -> TenantIsolationPolicy:
    return TenantIsolationPolicy(
        project_id=project_id,
        runbook_bucket=os.getenv(
            "RUNBOOK_BUCKET_NAME", _CFG.runbook_bucket(project_id)
        ),
    )


def _legacy_adc_headers(project_id: str) -> dict[str, str]:
    """Shared-identity ADC headers. Operator tooling and the migration escape hatch only."""
    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    creds.refresh(google.auth.transport.requests.Request())
    return {
        "Authorization": f"Bearer {creds.token}",
        "X-Goog-User-Project": project_id,
    }


def _tenant_headers(
    envelope: ContextEnvelope, project_id: str
) -> dict[str, str]:
    """Headers for the envelope's tenant service account (falls back only if explicitly
    disabled).
    """
    if tenant_scoped_credentials_enabled():
        return get_default_broker(project_id).headers_for(envelope)
    return _adc_headers(project_id)


def _fetch_secret_json(
    *, project_id: str, secret_id: str, headers: dict[str, str]
) -> dict[str, str]:
    url = (
        f"https://secretmanager.googleapis.com/v1/projects/{project_id}"
        f"/secrets/{secret_id}/versions/latest:access"
    )
    resp = httpx.get(url, headers=headers, timeout=15.0)
    resp.raise_for_status()
    return dict(
        json.loads(base64.b64decode(resp.json()["payload"]["data"]).decode())
    )


def access_tenant_secret(
    *, envelope: ContextEnvelope, project_id: str, secret_id: str
) -> dict[str, str]:
    """Reads a tenant-owned secret as that tenant's service account (policy check first)."""
    _tenant_policy(project_id).assert_secret(
        envelope.tenant.tenant_id, secret_id
    )
    return _fetch_secret_json(
        project_id=project_id,
        secret_id=secret_id,
        headers=_tenant_headers(envelope, project_id),
    )


class ConnectorSecretUnavailableError(RuntimeError):
    """Live mode could not read a connector secret; never fall back to simulated data."""


def load_live_connector_secret(
    *, envelope: ContextEnvelope | None, project_id: str, secret_id: str
) -> dict[str, str]:
    """Reads a connector secret in live mode and fails loudly instead of degrading silently.

    With an envelope the read runs as that tenant's service account. `PermissionError` (an
    isolation denial) propagates unchanged; any other failure (network, missing version, bad
    JSON) becomes `E_3P_SECRET_UNAVAILABLE` so callers never mistake an outage for demo data.
    """
    try:
        if envelope is not None:
            return _access_secret(
                envelope=envelope, project_id=project_id, secret_id=secret_id
            )
        return _fetch_secret_json(
            project_id=project_id,
            secret_id=secret_id,
            headers=_adc_headers(project_id),
        )
    except PermissionError:
        raise
    except Exception as exc:
        raise ConnectorSecretUnavailableError(
            f"E_3P_SECRET_UNAVAILABLE: could not read Secret Manager secret '{secret_id}' in "
            f"live mode ({type(exc).__name__}). Refusing to fall back to simulated data."
        ) from exc


class _DotEnvHelper:
    """Helper to read key-value overrides from environment or local untracked `.env` file."""

    @staticmethod
    def get_env_map() -> dict[str, str]:
        values: dict[str, str] = {}
        env_file = str(Path(__file__).resolve().parents[2] / ".env")
        if os.path.exists(env_file):
            with open(env_file, encoding="utf-8") as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        values[k.strip()] = v.strip()
        for k, v in os.environ.items():
            values[k] = v
        return values
