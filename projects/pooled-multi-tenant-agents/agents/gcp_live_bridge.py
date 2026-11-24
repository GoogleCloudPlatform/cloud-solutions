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

"""Backward-compatible facade for live GCP and 3P enterprise adapters (`agents.adapters`)."""

from __future__ import annotations

from agents import interceptors
from agents.adapters import (
    _KMS_VERIFY_CACHE,
    _KMS_VERIFY_LOCK,
    DEFAULT_BQ_DATASET,
    DEFAULT_BQ_TABLE,
    DEFAULT_DLP_DEIDENTIFY_TEMPLATE,
    DEFAULT_DLP_INSPECT_TEMPLATE,
    DEFAULT_FIRESTORE_DB,
    DEFAULT_GCP_PROJECT,
    DEFAULT_GCP_REGION,
    DEFAULT_KMS_KEYRING,
    DEFAULT_MODEL_ARMOR_TEMPLATE_ID,
    FINVAULT_KMS_KEY,
    KMS_VERIFY_TTL_SECONDS,
    RETAILSTREAM_KMS_KEY,
    ConnectorSecretUnavailableError,
    LiveADKVertexRunner,
    LiveAtlassianJiraConnector,
    LiveBigQueryOTelSink,
    LiveCloudDLPGuardrail,
    LiveCloudKMSCMEKVerifier,
    LiveFirestoreMemoryBank,
    LiveGCSCMEKRunbookVault,
    LiveGeminiAgentSandboxClient,
    LiveMicrosoftEntraOIDCConnector,
    LiveModelArmorGuardrail,
    LiveServiceNowITOMConnector,
    LiveVertexMemoryBankAdapter,
    _DotEnvHelper,
    _fetch_secret_json,
    _get_live_gemini_sandbox_manager,
    _legacy_adc_headers,
    _tenant_headers,
    _tenant_policy,
    access_tenant_secret,
    clear_kms_verify_cache,
    evict_kms_verify_cache_for_tenant,
    is_live_gcp_enabled,
    load_live_connector_secret,
)
from agents.interceptors import egress_dlp_and_nlc_guardrail
from agents.kms_rest import configure_client_certificate_env
from agents.shared_diagnostic_agent import get_clean_project_id

configure_client_certificate_env()

__all__ = [
    "DEFAULT_BQ_DATASET",
    "DEFAULT_BQ_TABLE",
    "DEFAULT_DLP_DEIDENTIFY_TEMPLATE",
    "DEFAULT_DLP_INSPECT_TEMPLATE",
    "DEFAULT_FIRESTORE_DB",
    "DEFAULT_GCP_PROJECT",
    "DEFAULT_GCP_REGION",
    "DEFAULT_KMS_KEYRING",
    "DEFAULT_MODEL_ARMOR_TEMPLATE_ID",
    "FINVAULT_KMS_KEY",
    "KMS_VERIFY_TTL_SECONDS",
    "RETAILSTREAM_KMS_KEY",
    "_KMS_VERIFY_CACHE",
    "_KMS_VERIFY_LOCK",
    "ConnectorSecretUnavailableError",
    "LiveADKVertexRunner",
    "LiveAtlassianJiraConnector",
    "LiveBigQueryOTelSink",
    "LiveCloudDLPGuardrail",
    "LiveCloudKMSCMEKVerifier",
    "LiveFirestoreMemoryBank",
    "LiveGCSCMEKRunbookVault",
    "LiveGeminiAgentSandboxClient",
    "LiveMicrosoftEntraOIDCConnector",
    "LiveModelArmorGuardrail",
    "LiveServiceNowITOMConnector",
    "LiveVertexMemoryBankAdapter",
    "_DotEnvHelper",
    "_fetch_secret_json",
    "_get_live_gemini_sandbox_manager",
    "_legacy_adc_headers",
    "_tenant_headers",
    "_tenant_policy",
    "access_tenant_secret",
    "clear_kms_verify_cache",
    "egress_dlp_and_nlc_guardrail",
    "evict_kms_verify_cache_for_tenant",
    "get_clean_project_id",
    "interceptors",
    "is_live_gcp_enabled",
    "load_live_connector_secret",
]
