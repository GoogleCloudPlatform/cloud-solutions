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

"""Turnkey 3rd-Party SaaS Connector & Sample Data Bootstrap CLI (`REQ-PORT-03`).

Allows any engineer or customer cloning this repository to wire their own:
1. **Atlassian Jira Cloud** instance (`--jira-url`, `--jira-email`, `--jira-token`)
2. **ServiceNow PDI / ITOM** instance (`--servicenow-url`, `--servicenow-user`,
   `--servicenow-password`)
3. **Microsoft Azure Entra ID / SharePoint** tenant (`--entra-tenant-id`, `--entra-client-id`,
   `--entra-client-secret`)
4. **Pooled GCS Per-Object CMEK Runbook Vault** (`--seed-gcs-runbooks`)

into their target GCP project's Secret Manager (`cymbal-finvault-jira-credentials`,
`cymbal-retailstream-servicenow-credentials`, `cymbal-retailstream-entra-credentials`) and
optionally auto-seed synthetic test projects/incidents (`--seed-sample-data`) with zero manual UI
clicks.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import urllib.parse

import httpx


def _store_gcp_secret(
    *, project_id: str, secret_id: str, payload: dict[str, str]
) -> None:
    """Idempotently creates a GCP Secret Manager secret and adds a version (no IAM changes)."""
    env = os.environ.copy()
    env["CLOUDSDK_METRICS_ENVIRONMENT"] = "datacloud.antigravity"
    env["CLOUDSDK_BILLING_QUOTA_PROJECT"] = project_id

    subprocess.run(
        [
            "gcloud",
            "secrets",
            "create",
            secret_id,
            "--replication-policy=automatic",
            f"--project={project_id}",
            f"--billing-project={project_id}",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    subprocess.run(
        [
            "gcloud",
            "secrets",
            "versions",
            "add",
            secret_id,
            "--data-file=-",
            f"--project={project_id}",
            f"--billing-project={project_id}",
        ],
        input=json.dumps(payload),
        env=env,
        check=True,
    )
    # Values only. IAM on the secret is owned by Terraform (terraform/modules/tenant), which grants
    # secretAccessor to the owning tenant's service account ONLY. Binding a shared identity here
    # would re-create cross-tenant secret access (deployment audit finding F2).
    print(
        f"[OK] Stored a new version of secret '{secret_id}' in project '{project_id}'."
    )


def setup_jira_connector(
    *,
    project_id: str,
    base_url: str,
    email: str,
    api_token: str,
    project_key: str,
    seed_data: bool,
) -> None:
    base_url = base_url.rstrip("/")
    basic = base64.b64encode(f"{email}:{api_token}".encode()).decode("ascii")
    headers = {
        "Authorization": f"Basic {basic}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    with httpx.Client(headers=headers, timeout=20.0) as client:
        me = client.get(f"{base_url}/rest/api/3/myself")
        me.raise_for_status()
        account_id = me.json()["accountId"]
        print(
            f"[Jira] Authenticated as '{me.json().get('displayName')}' ({account_id})."
        )

        if seed_data:
            projs = (
                client.get(f"{base_url}/rest/api/3/project/search")
                .json()
                .get("values", [])
            )
            keys = {p.get("key") for p in projs}
            if project_key not in keys:
                create_p = client.post(
                    f"{base_url}/rest/api/3/project",
                    json={
                        "key": project_key,
                        "name": "FinVault Regulatory",
                        "projectTypeKey": "software",
                        "projectTemplateKey": (
                            "com.pyxis.greenhopper.jira:gh-simplified-kanban-classic"
                        ),
                        "leadAccountId": account_id,
                        "assigneeType": "PROJECT_LEAD",
                    },
                )
                create_p.raise_for_status()
                print(f"[Jira] Created project '{project_key}' on {base_url}.")

            meta = client.get(
                f"{base_url}/rest/api/3/issue/createmeta?projectKeys={project_key}"
            ).json()
            issue_type_id = "10001"
            for proj in meta.get("projects", []):
                for it in proj.get("issuetypes", []):
                    if not it.get("subtask", False):
                        issue_type_id = str(it["id"])
                        break

            existing = (
                client.post(
                    f"{base_url}/rest/api/3/search/jql",
                    json={
                        "jql": f"project = {project_key}",
                        "fields": ["summary"],
                    },
                )
                .json()
                .get("issues", [])
            )
            if not existing:
                for summary, label in [
                    (
                        (
                            "[SEC-17a-4] FinVault High-Value Wire Settlement Audit & WORM "
                            "Retention Escalation"
                        ),
                        "sec-17a-4",
                    ),
                    (
                        "[FINRA-4511] Cross-Tenant Confused Deputy & 3LO Vault Verification Record",
                        "finra-4511",
                    ),
                ]:
                    client.post(
                        f"{base_url}/rest/api/3/issue",
                        json={
                            "fields": {
                                "project": {"key": project_key},
                                "summary": summary,
                                "issuetype": {"id": issue_type_id},
                                "labels": [label, "tenant-finvault-alpha"],
                            }
                        },
                    ).raise_for_status()
                print(
                    f"[Jira] Seeded 2 regulatory compliance issues in '{project_key}'."
                )

    _store_gcp_secret(
        project_id=project_id,
        secret_id="cymbal-finvault-jira-credentials",
        payload={
            "base_url": base_url,
            "email": email,
            "api_token": api_token,
            "project_key": project_key,
            "tenant_id": "tenant-finvault-alpha",
        },
    )


def setup_servicenow_connector(
    *,
    project_id: str,
    instance_url: str,
    username: str,
    password: str,
    correlation_id: str,
    seed_data: bool,
) -> None:
    instance_url = instance_url.rstrip("/")
    basic = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
    headers = {
        "Authorization": f"Basic {basic}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    inc_number = ""
    with httpx.Client(headers=headers, timeout=25.0) as client:
        q = urllib.parse.quote(f"correlation_id={correlation_id}")
        res = client.get(
            f"{instance_url}/api/now/table/incident?sysparm_query={q}&sysparm_limit=1"
        )
        res.raise_for_status()
        rows = res.json().get("result", [])
        if rows:
            inc_number = str(rows[0].get("number", ""))
            print(
                f"[ServiceNow] Found existing incident '{inc_number}' ({correlation_id})."
            )
        elif seed_data:
            created = client.post(
                f"{instance_url}/api/now/table/incident",
                json={
                    "short_description": (
                        "["
                        f"{correlation_id}"
                        "] RetailStream POS Checkout Redis Connection Pool Starvation"
                    ),
                    "urgency": "1",
                    "impact": "1",
                    "correlation_id": correlation_id,
                },
            )
            created.raise_for_status()
            inc_number = str(created.json().get("result", {}).get("number", ""))
            print(
                f"[ServiceNow] Seeded incident '{inc_number}' ({correlation_id})."
            )

    _store_gcp_secret(
        project_id=project_id,
        secret_id="cymbal-retailstream-servicenow-credentials",
        payload={
            "instance_url": instance_url,
            "username": username,
            "password": password,
            "seeded_incident_number": inc_number,
            "correlation_id": correlation_id,
            "tenant_id": "tenant-retailstream-beta",
        },
    )


def setup_entra_connector(
    *,
    project_id: str,
    entra_tenant_id: str,
    client_id: str,
    client_secret: str,
    sharepoint_site_id: str,
) -> None:
    _store_gcp_secret(
        project_id=project_id,
        secret_id="cymbal-retailstream-entra-credentials",
        payload={
            "entra_tenant_id": entra_tenant_id,
            "issuer": f"https://login.microsoftonline.com/{entra_tenant_id}/v2.0",
            "client_id": client_id,
            "client_secret": client_secret,
            "sharepoint_site_id": sharepoint_site_id,
            "tenant_id": "tenant-retailstream-beta",
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Configure & seed 3rd-party SaaS connectors (Jira, ServiceNow, Azure Entra) in "
            "GCP Secret Manager."
        )
    )
    parser.add_argument(
        "--project-id",
        default=os.getenv(
            "GOOGLE_CLOUD_PROJECT", "cymbal-multitenancy-example"
        ),
        help="Target Google Cloud Project ID",
    )
    parser.add_argument(
        "--seed-sample-data",
        action="store_true",
        default=True,
        help="Automatically create sample FINVAULT Jira project/issues and ServiceNow incident",
    )
    parser.add_argument("--jira-url", default=os.getenv("JIRA_BASE_URL", ""))
    parser.add_argument("--jira-email", default=os.getenv("JIRA_EMAIL", ""))
    parser.add_argument("--jira-token", default=os.getenv("JIRA_API_TOKEN", ""))
    parser.add_argument(
        "--jira-project-key", default=os.getenv("JIRA_PROJECT_KEY", "FINVAULT")
    )

    parser.add_argument(
        "--servicenow-url", default=os.getenv("SERVICENOW_INSTANCE_URL", "")
    )
    parser.add_argument(
        "--servicenow-user", default=os.getenv("SERVICENOW_USERNAME", "admin")
    )
    parser.add_argument(
        "--servicenow-password", default=os.getenv("SERVICENOW_PASSWORD", "")
    )
    parser.add_argument(
        "--servicenow-correlation-id",
        default=os.getenv("SERVICENOW_CORRELATION_ID", "ROA-2026-8812"),
    )

    parser.add_argument(
        "--entra-tenant-id", default=os.getenv("AZURE_ENTRA_TENANT_ID", "")
    )
    parser.add_argument(
        "--entra-client-id", default=os.getenv("AZURE_ENTRA_CLIENT_ID", "")
    )
    parser.add_argument(
        "--entra-client-secret",
        default=os.getenv("AZURE_ENTRA_CLIENT_SECRET", ""),
    )
    parser.add_argument(
        "--sharepoint-site-id", default=os.getenv("SHAREPOINT_SITE_ID", "")
    )

    args = parser.parse_args()

    if args.jira_url and args.jira_email and args.jira_token:
        setup_jira_connector(
            project_id=args.project_id,
            base_url=args.jira_url,
            email=args.jira_email,
            api_token=args.jira_token,
            project_key=args.jira_project_key,
            seed_data=args.seed_sample_data,
        )

    if args.servicenow_url and args.servicenow_password:
        setup_servicenow_connector(
            project_id=args.project_id,
            instance_url=args.servicenow_url,
            username=args.servicenow_user,
            password=args.servicenow_password,
            correlation_id=args.servicenow_correlation_id,
            seed_data=args.seed_sample_data,
        )

    if (
        args.entra_tenant_id
        and args.entra_client_id
        and args.entra_client_secret
    ):
        setup_entra_connector(
            project_id=args.project_id,
            entra_tenant_id=args.entra_tenant_id,
            client_id=args.entra_client_id,
            client_secret=args.entra_client_secret,
            sharepoint_site_id=args.sharepoint_site_id,
        )


if __name__ == "__main__":
    main()
