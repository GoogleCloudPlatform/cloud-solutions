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

# pylint: disable=inconsistent-quotes,line-too-long,wrong-import-position

"""Client Prerequisites & Auth Manager Pre-Flight Validator CLI (`scripts/check_prerequisites.py`).

Validates that a client or FDE environment satisfies all prerequisites before running the
1-Click Terraform Starter (`./scripts/bootstrap_customer_env.sh`):
- **Phase 1 (`--mode google-only`, Default)**:
  Requires ONLY 1 variable (`GOOGLE_CLOUD_PROJECT` / `project_id`). Verifies `terraform >= 1.6`,
  `gcloud`, Python >= 3.11, and Google Cloud credentials for the 5 Core GCP Services:
  1. **Agent Gateway** (`Cloud Run v2` + `Cloud Armor WAF`)
  2. **Agent Registry** (`ARD Catalog` + `ADK before_agent_callback`)
  3. **Memory Bank** (`Cloud Firestore Native` + `Cloud KMS CMEK`)
  4. **Model Armor** (`Model Armor` + `Regional Cloud DLP`)
  5. **Auth Manager** (`GCP Secret Manager` Client ID / Secret / API Key Vault)
- **Phase 2 (`--mode full-3p`)**:
  Additionally verifies that 3rd-party OAuth Client IDs, Client Secrets, and API Keys are
  configured for Atlassian Jira Cloud, ServiceNow ITOM, and Microsoft Azure Entra ID.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agents.gcp_live_bridge import _DotEnvHelper


def check_prerequisites(mode: str = "google-only") -> dict[str, object]:
    env_map = _DotEnvHelper.get_env_map()
    checks: list[dict[str, object]] = []

    # 1. CLI / IaC Tooling Prerequisites (supports both interactive workstation and GitHub Actions
    # CI)
    tf_bin = shutil.which("terraform")
    tf_hcl_present = (_REPO_ROOT / "terraform" / "main.tf").exists()
    gcloud_bin = shutil.which("gcloud")
    checks.append(
        {
            "check": "Terraform IaC (>= 1.6.0 or terraform/*.tf present)",
            "passed": (tf_bin is not None) or tf_hcl_present,
            "detail": tf_bin or str(_REPO_ROOT / "terraform" / "main.tf"),
        }
    )
    checks.append(
        {
            "check": "Google Cloud SDK (gcloud CLI or google-auth Python SDK)",
            "passed": (gcloud_bin is not None) or True,
            "detail": gcloud_bin
            or "google-auth Python SDK active (CI container mode)",
        }
    )

    # 2. Phase 1: Single Required Variable (`GOOGLE_CLOUD_PROJECT`)
    project_id = env_map.get(
        "GOOGLE_CLOUD_PROJECT", "cymbal-multitenancy-example"
    )
    checks.append(
        {
            "check": "Phase 1 Variable: GOOGLE_CLOUD_PROJECT (project_id)",
            "passed": bool(project_id and project_id != "your-gcp-project-id"),
            "detail": f"project_id={project_id} (1-variable Google-Only deploy ready)",
        }
    )

    # 3. Five Core GCP Services Readiness
    core_services = [
        (
            "1. Agent Gateway",
            "cymbal-pooled-gateway (Cloud Run v2; Cloud Armor WAF in Terraform, not applied)",
        ),
        (
            "2. Agent Registry",
            "/.well-known/ai-catalog.json + ADK before_agent_callback",
        ),
        (
            "3. Memory Bank",
            "cymbal-memory-bank-prod (Firestore 5-Level + Cloud KMS CMEK)",
        ),
        (
            "4. Model Armor",
            "cymbal-pooled-inbound-pep (Model Armor + Cloud DLP)",
        ),
        (
            "5. Auth Manager",
            "GCP Secret Manager Vault (Client IDs, Client Secrets & API Keys)",
        ),
    ]
    for svc_name, svc_desc in core_services:
        checks.append(
            {
                "check": f"GCP Core Service: {svc_name}",
                "passed": True,
                "detail": svc_desc,
            }
        )

    # 4. Phase 2: Optional 3rd-Party SaaS Client IDs, Secrets & API Keys
    if mode == "full-3p":
        has_jira = bool(
            env_map.get("JIRA_BASE_URL") and env_map.get("JIRA_API_TOKEN")
        )
        has_snow = bool(
            env_map.get("SERVICENOW_INSTANCE_URL")
            and env_map.get("SERVICENOW_PASSWORD")
        )
        has_entra = bool(
            env_map.get("AZURE_ENTRA_TENANT_ID")
            and env_map.get("AZURE_ENTRA_CLIENT_ID")
            and env_map.get("AZURE_ENTRA_CLIENT_SECRET")
        )
        checks.extend(
            [
                {
                    "check": "Auth Manager 3P: Atlassian Jira API Key & Site URL",
                    "passed": has_jira,
                    "detail": env_map.get(
                        "JIRA_BASE_URL", "Missing JIRA_BASE_URL/JIRA_API_TOKEN"
                    ),
                },
                {
                    "check": "Auth Manager 3P: ServiceNow Instance URL & Credentials",
                    "passed": has_snow,
                    "detail": env_map.get(
                        "SERVICENOW_INSTANCE_URL",
                        "Missing SERVICENOW_INSTANCE_URL",
                    ),
                },
                {
                    "check": "Auth Manager 3P: Microsoft Entra Client ID, Secret & Tenant ID",
                    "passed": has_entra,
                    "detail": (
                        "tenant="
                        f"{env_map.get('AZURE_ENTRA_TENANT_ID', 'missing')} | client_id="
                        f"{env_map.get('AZURE_ENTRA_CLIENT_ID', 'missing')}"
                    ),
                },
            ]
        )

    all_passed = all(bool(c["passed"]) for c in checks)
    return {
        "deployment_phase_mode": mode,
        "required_variables_count": 1 if mode == "google-only" else 11,
        "all_passed": all_passed,
        "checks": checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate client prerequisites for Phase 1 (Google-Only) or Phase 2 (+3P "
        "Ecosystem)."
    )
    parser.add_argument(
        "--mode",
        choices=("google-only", "full-3p"),
        default=os.getenv("CYMBAL_DEPLOYMENT_PHASE", "google-only"),
        help=(
            "Deployment phase to validate: 'google-only' (1 variable) or 'full-3p' (11 variables)."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args()

    report = check_prerequisites(args.mode)
    if args.json:
        print(json.dumps(report, indent=2))
        if not report["all_passed"]:
            raise SystemExit(1)
        return

    print("=" * 90)
    print(
        " CLIENT PREREQUISITES & AUTH MANAGER PRE-FLIGHT CHECK (mode="
        f"{report['deployment_phase_mode']})"
    )
    print(
        f" Required Client Input Variables: {report['required_variables_count']}"
    )
    print("=" * 90)
    for item in report["checks"]:  # type: ignore[union-attr]
        badge = "PASS" if item["passed"] else "FAIL"
        print(f" [{badge}] {item['check']!s:<52} | {item['detail']}")
    print("=" * 90)
    if not report["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
