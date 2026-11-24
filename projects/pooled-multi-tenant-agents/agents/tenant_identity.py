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

# pylint: disable=inconsistent-quotes,line-too-long

"""Per-tenant service account naming (ADR-0010), dependency-free.

Shared by the runtime (`agents.tenant_credentials`) and the credential broker
(`broker_service`, ADR-0014 B4), which must not import agent or ADK modules.
"""

from __future__ import annotations

import hashlib

TENANT_SA_PREFIX = "ct-"


def tenant_service_account_id(tenant_id: str) -> str:
    """Deterministic service account ID for a tenant.

    Matches Terraform: `"ct-${substr(sha256(tenant_id), 0, 24)}"`. The result is 27 characters,
    starts with a letter, and contains only `[a-z0-9-]`, which satisfies IAM's 6-30 character rule.
    Hashing keeps tenant names out of IAM principals.
    """
    if not tenant_id or tenant_id != tenant_id.strip() or "\x00" in tenant_id:
        raise ValueError(
            "E_INVALID_TENANT_ID: tenant_id must be a non-empty, trimmed string."
        )
    return f"{TENANT_SA_PREFIX}{hashlib.sha256(tenant_id.encode('utf-8')).hexdigest()[:24]}"


def tenant_service_account_email(tenant_id: str, project_id: str) -> str:
    return f"{tenant_service_account_id(tenant_id)}@{project_id}.iam.gserviceaccount.com"
