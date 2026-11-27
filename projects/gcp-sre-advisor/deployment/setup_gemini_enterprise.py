# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Registers GCP SRE Advisor in Gemini Enterprise with OAuth authorization."""

import os
import subprocess
import time
from typing import Any
from urllib.parse import quote

from deployment.auth import gcloud_cmd, require_project_id, resolve_credentials
from google.auth.transport.requests import AuthorizedSession

DEFAULT_STARTER_PROMPTS = [
    {
        "text": (
            "What applications, workloads, and Google Cloud projects do you "
            "have access to inspect right now?"
        )
    },
    {
        "text": (
            "Audit IAM least privilege, public storage exposure, and alerting "
            "coverage across my application or GCP project."
        )
    },
    {
        "text": (
            "Investigate database replica load, slow queries, and autoscaling "
            "bottlenecks for an active service."
        )
    },
    {
        "text": (
            "Run a full six-pillar Google Cloud Architecture Framework "
            "assessment and prioritize remediations."
        )
    },
]

DEFAULT_PLACEHOLDER = (
    "Name an application, workload, or Google Cloud project and describe the "
    "symptom or audit..."
)


def _encode_oauth_scopes(raw_scopes: str) -> str:
    tokens = [
        tok
        for chunk in (raw_scopes or "").split(",")
        for tok in chunk.split()
        if tok
    ]
    normalized = (
        " ".join(tokens)
        or "https://www.googleapis.com/auth/cloud-platform.read-only"
    )
    return quote(normalized, safe="")


def _post_idempotent(
    session: AuthorizedSession,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    *,
    patch_url_on_conflict: str | None = None,
) -> None:
    resp = session.post(url, headers=headers, json=payload, timeout=20)
    if resp.status_code == 409:
        if patch_url_on_conflict:
            patch_resp = session.patch(
                patch_url_on_conflict, headers=headers, json=payload, timeout=20
            )
            patch_resp.raise_for_status()
        return
    resp.raise_for_status()


def setup_gemini_enterprise(
    reasoning_engine_id: str,
    project_id: str | None = None,
    re_location: str | None = None,
    engine_id: str | None = None,
    datastore_id: str | None = None,
) -> dict[str, Any]:
    """Creates or updates the Gemini Enterprise engine and registration."""
    proj = require_project_id(project_id)
    loc = (
        re_location or os.getenv("GOOGLE_CLOUD_LOCATION") or "us-central1"
    ).strip()
    ge_loc = "global"
    eng_id = (
        engine_id or os.getenv("ENGINE_ID") or "gcp-sre-advisor-portal"
    ).strip()
    ds_id = (
        datastore_id or os.getenv("DATASTORE_ID") or "gcp-sre-advisor-kb"
    ).strip()
    oauth_auth_id = os.getenv(
        "DELEGATED_OAUTH_AUTH_ID", "gcp-sre-user-oauth"
    ).strip()
    oauth_client_id = os.getenv("OAUTH_CLIENT_ID", "").strip()
    oauth_client_secret = os.getenv("OAUTH_CLIENT_SECRET", "").strip()
    oauth_scopes = os.getenv(
        "DELEGATED_OAUTH_SCOPES",
        "https://www.googleapis.com/auth/cloud-platform.read-only",
    ).strip()

    project_number = subprocess.check_output(
        gcloud_cmd(
            "projects",
            "describe",
            proj,
            "--format=value(projectNumber)",
            "--quiet",
        ),
        text=True,
    ).strip()

    re_id_clean = reasoning_engine_id.rsplit("/", maxsplit=1)[-1].strip()
    re_path = (
        f"projects/{project_number}/locations/{loc}"
        f"/reasoningEngines/{re_id_clean}"
    )

    de_sa = (
        f"service-{project_number}"
        "@gcp-sa-discoveryengine.iam.gserviceaccount.com"
    )
    for role in ("roles/aiplatform.user", "roles/aiplatform.viewer"):
        subprocess.run(
            gcloud_cmd(
                "projects",
                "add-iam-policy-binding",
                proj,
                f"--member=serviceAccount:{de_sa}",
                f"--role={role}",
                "--quiet",
            ),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )

    creds = resolve_credentials(proj)
    session = AuthorizedSession(creds)
    headers = {
        "Content-Type": "application/json",
        "X-Goog-User-Project": proj,
    }

    ds_url = (
        f"https://discoveryengine.googleapis.com/v1/projects/{proj}"
        f"/locations/{ge_loc}/collections/default_collection"
        f"/dataStores?dataStoreId={ds_id}"
    )
    _post_idempotent(
        session,
        ds_url,
        headers,
        {
            "displayName": "SRE Knowledge Base",
            "industryVertical": "GENERIC",
            "solutionTypes": ["SOLUTION_TYPE_SEARCH", "SOLUTION_TYPE_CHAT"],
            "contentConfig": "NO_CONTENT",
        },
    )

    eng_get_url = (
        f"https://discoveryengine.googleapis.com/v1alpha/projects/{proj}"
        f"/locations/{ge_loc}/collections/default_collection/engines/{eng_id}"
    )
    eng_exists = (
        session.get(eng_get_url, headers=headers, timeout=15).status_code == 200
    )
    if not eng_exists:
        eng_create_url = (
            f"https://discoveryengine.googleapis.com/v1alpha/projects/{proj}"
            f"/locations/{ge_loc}/collections/default_collection"
            f"/engines?engineId={eng_id}"
        )
        _post_idempotent(
            session,
            eng_create_url,
            headers,
            {
                "displayName": "Google Cloud — GCP SRE Advisor",
                "solutionType": "SOLUTION_TYPE_SEARCH",
                "industryVertical": "GENERIC",
                "appType": "APP_TYPE_INTRANET",
                "dataStoreIds": [ds_id],
                "commonConfig": {"companyName": "Cloud SRE Operations"},
                "searchEngineConfig": {
                    "searchTier": "SEARCH_TIER_ENTERPRISE",
                    "searchAddOns": ["SEARCH_ADD_ON_LLM"],
                },
            },
        )
        time.sleep(10)

    agent_body: dict[str, Any] = {
        "displayName": "GCP SRE Advisor",
        "description": (
            "Multi-agent Site Reliability Engineering and Cloud Architecture "
            "advisor structured around the six pillars of the Google Cloud "
            "Architecture Framework using managed MCP servers."
        ),
        "icon": {
            "uri": (
                "https://www.gstatic.com/images/branding/product/2x/"
                "google_cloud_64dp.png"
            ),
        },
        "defaultPinned": True,
        "customPlaceholderText": DEFAULT_PLACEHOLDER,
        "starterPrompts": DEFAULT_STARTER_PROMPTS,
        "adkAgentDefinition": {
            "toolSettings": {
                "toolDescription": (
                    "Live read-only inspection across Operational Excellence, "
                    "Security, Reliability, Performance, Cost Optimization, "
                    "and Sustainability via Google Cloud Managed Remote MCPs."
                )
            },
            "provisionedReasoningEngine": {"reasoningEngine": re_path},
        },
        "sharingConfig": {"scope": "ALL_USERS"},
    }

    if oauth_client_id and oauth_client_secret:
        auth_create_url = (
            f"https://discoveryengine.googleapis.com/v1alpha/projects/{proj}"
            f"/locations/{ge_loc}/authorizations"
            f"?authorizationId={oauth_auth_id}"
        )
        auth_patch_url = (
            f"https://discoveryengine.googleapis.com/v1alpha/projects/{proj}"
            f"/locations/{ge_loc}/authorizations/{oauth_auth_id}"
        )
        encoded_scopes = _encode_oauth_scopes(oauth_scopes)
        _post_idempotent(
            session,
            auth_create_url,
            headers,
            {
                "serverSideOauth2": {
                    "clientId": oauth_client_id,
                    "clientSecret": oauth_client_secret,
                    "authorizationUri": (
                        "https://accounts.google.com/o/oauth2/v2/auth"
                        f"?scope={encoded_scopes}"
                        "&access_type=offline&prompt=consent"
                    ),
                    "tokenUri": "https://oauth2.googleapis.com/token",
                }
            },
            patch_url_on_conflict=auth_patch_url,
        )
        agent_body["authorizationConfig"] = {
            "toolAuthorizations": [
                f"projects/{project_number}/locations/{ge_loc}"
                f"/authorizations/{oauth_auth_id}"
            ]
        }

    agents_base = (
        f"https://discoveryengine.googleapis.com/v1alpha/projects/{proj}"
        f"/locations/{ge_loc}/collections/default_collection/engines/{eng_id}"
        "/assistants/default_assistant/agents"
    )
    list_resp = session.get(agents_base, headers=headers, timeout=15)
    list_resp.raise_for_status()
    existing_list = list_resp.json().get("agents") or []
    existing_agent = next(
        (
            a
            for a in existing_list
            if a.get("adkAgentDefinition", {})
            .get("provisionedReasoningEngine", {})
            .get("reasoningEngine")
            == re_path
            or a.get("displayName") == "GCP SRE Advisor"
        ),
        None,
    )

    if existing_agent:
        agent_name = existing_agent["name"]
        update_mask = (
            "displayName,description,icon,defaultPinned,"
            "customPlaceholderText,starterPrompts,"
            "adkAgentDefinition,sharingConfig"
        )
        if "authorizationConfig" in agent_body:
            update_mask += ",authorizationConfig"
        patch_url = (
            f"https://discoveryengine.googleapis.com/v1alpha/{agent_name}"
            f"?updateMask={update_mask}"
        )
        resp = session.patch(
            patch_url, headers=headers, json=agent_body, timeout=20
        )
        resp.raise_for_status()
        result = resp.json()
    else:
        resp = session.post(
            agents_base, headers=headers, json=agent_body, timeout=20
        )
        resp.raise_for_status()
        result = resp.json()

    dashboard_url = (
        "https://console.cloud.google.com/gemini-enterprise/locations/global"
        f"/engines/{eng_id}/overview/dashboard?project={proj}"
    )
    created_name = result.get("name")
    print(f"Gemini Enterprise agent ready: {created_name}")
    print(f"Console dashboard: {dashboard_url}")
    return result
