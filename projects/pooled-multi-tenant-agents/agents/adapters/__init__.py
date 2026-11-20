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

"""Live Google Cloud and 3P enterprise connector adapters (`agents.adapters`)."""

from __future__ import annotations

from agents.adapters._bridge_runtime import (
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
    RETAILSTREAM_KMS_KEY,
    ConnectorSecretUnavailableError,
    _DotEnvHelper,
    _fetch_secret_json,
    _legacy_adc_headers,
    _tenant_headers,
    _tenant_policy,
    access_tenant_secret,
    is_live_gcp_enabled,
    load_live_connector_secret,
)
from agents.adapters.enterprise_connectors import (
    LiveAtlassianJiraConnector,
    LiveMicrosoftEntraOIDCConnector,
    LiveServiceNowITOMConnector,
)
from agents.adapters.guardrails import (
    LiveCloudDLPGuardrail,
    LiveModelArmorGuardrail,
)
from agents.adapters.kms_cmek import (
    _KMS_VERIFY_CACHE,
    _KMS_VERIFY_LOCK,
    KMS_VERIFY_TTL_SECONDS,
    LiveCloudKMSCMEKVerifier,
    clear_kms_verify_cache,
    evict_kms_verify_cache_for_tenant,
)
from agents.adapters.storage_and_telemetry import (
    LiveBigQueryOTelSink,
    LiveFirestoreMemoryBank,
    LiveGCSCMEKRunbookVault,
    LiveVertexMemoryBankAdapter,
)
from agents.adapters.vertex_runner import (
    LiveADKVertexRunner,
    LiveGeminiAgentSandboxClient,
    _get_live_gemini_sandbox_manager,
)

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
    "evict_kms_verify_cache_for_tenant",
    "is_live_gcp_enabled",
    "load_live_connector_secret",
]
