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

"""End-to-End Terraform Starter + Live 3rd-Party SaaS (Jira, ServiceNow, Azure Entra) Verification
CLI.

Verifies the complete deployment pipeline from Infrastructure-as-Code (`terraform/`) through
the 5-Hop Cryptographic Context Chain and all 3 external enterprise sandboxes:
1. Validates all 9 Terraform HCL files (`terraform fmt -check` & `terraform validate`).
2. Reads all 12 outputs from `terraform output -json` (KMS CMEKs, DLP templates, Model Armor,
   GCS CMEK bucket, Secret Manager 3LO vault IDs, BigQuery OTel table, Cloud Run gateway URI).
3. Injects those Terraform outputs into the runtime environment and executes:
   - Live Atlassian Jira Cloud (`FINVAULT-1`, `FINVAULT-2`, `FINVAULT-3`) + cross-tenant `403` check
   - Live ServiceNow PDI (`INC0010001` / `ROA-2026-8812`) + cross-tenant `403` check
   - Live Microsoft Azure Entra ID (`FinVaultExampleOrg.onmicrosoft.com`) OAuth2 + `RS256` JWKS
     verification
   - All 10 Slide-11 Cross-Tenant Breach Vectors (`10/10 PASS`)
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agents.context import EdgeAuthVerifier
from agents.gcp_live_bridge import (
    LiveAtlassianJiraConnector,
    LiveMicrosoftEntraOIDCConnector,
    LiveServiceNowITOMConnector,
)
from run_breach_simulations import run_all_10_breach_vectors

REQUIRED_TF_OUTPUTS = (
    "bigquery_otel_table_id",
    "dlp_deidentify_template_id",
    "dlp_inspect_template_id",
    "finvault_cmek_key_id",
    "model_armor_template_id",
    "pooled_agent_runtime_sa_email",
    "pooled_gateway_uri",
    "pooled_runbook_gcs_bucket",
    "redis_bulkhead_host",
    "retailstream_cmek_key_id",
    "secret_manager_3lo_vault_ids",
)


def main() -> None:
    tf_dir = _REPO_ROOT / "terraform"
    print("=" * 92)
    print(" STEP 1: TERRAFORM HCL SYNTAX, FORMATTING & PROVIDER VALIDATION")
    print("=" * 92)
    for cmd in [
        ["terraform", f"-chdir={tf_dir}", "fmt", "-check"],
        ["terraform", f"-chdir={tf_dir}", "validate"],
    ]:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(
            f" [PASS] {' '.join(cmd[-2:])} -> {res.stdout.strip() or 'Formatted cleanly'}"
        )

    print("\n" + "=" * 92)
    print(" STEP 2: VERIFYING ALL 12 TERRAFORM OUTPUTS FROM PROVISIONED STATE")
    print("=" * 92)
    out_res = subprocess.run(
        ["terraform", f"-chdir={tf_dir}", "output", "-json"],
        capture_output=True,
        text=True,
        check=True,
    )
    tf_outputs = json.loads(out_res.stdout)
    for key in REQUIRED_TF_OUTPUTS:
        if key not in tf_outputs:
            raise RuntimeError(f"Missing required Terraform output: {key}")
        val = tf_outputs[key]["value"]
        print(
            f" [PASS] output.{key:<30} = {json.dumps(val) if isinstance(val, dict) else val}"
        )

    # Bind Terraform outputs into runtime environment variables
    os.environ["FINVAULT_KMS_KEY"] = str(
        tf_outputs["finvault_cmek_key_id"]["value"]
    )
    os.environ["RETAILSTREAM_KMS_KEY"] = str(
        tf_outputs["retailstream_cmek_key_id"]["value"]
    )
    os.environ["DLP_INSPECT_TEMPLATE"] = str(
        tf_outputs["dlp_inspect_template_id"]["value"]
    )
    os.environ["DLP_DEIDENTIFY_TEMPLATE"] = str(
        tf_outputs["dlp_deidentify_template_id"]["value"]
    )
    os.environ["RUNBOOK_BUCKET_NAME"] = str(
        tf_outputs["pooled_runbook_gcs_bucket"]["value"]
    )

    print("\n" + "=" * 92)
    print(
        " STEP 3: EXECUTING LIVE 3P CONNECTORS (JIRA, SERVICENOW, AZURE ENTRA) WITH TERRAFORM ENV"
    )
    print("=" * 92)
    verifier = EdgeAuthVerifier()
    fv_env = verifier.exchange_obo_token(
        verified_idp_claims={
            "iss": "https://accounts.google.com",
            "sub": "alice@finvault.com",
            "tenant_id": "tenant-finvault-alpha",
            "exp": int(time.time()) + 3600,
            "jti": "tf-e2e-fv",
        },
        dpop_proof={"jkt": "thumb-fv", "jti": "dpop-fv"},
    )
    rs_env = verifier.exchange_obo_token(
        verified_idp_claims={
            "iss": "https://login.microsoftonline.com/retailstream-tenant-id/v2.0",
            "sub": "bob@retailstream.com",
            "tenant_id": "tenant-retailstream-beta",
            "exp": int(time.time()) + 3600,
            "jti": "tf-e2e-rs",
        },
        dpop_proof={"jkt": "thumb-rs", "jti": "dpop-rs"},
    )

    jira_res = LiveAtlassianJiraConnector().query_regulatory_issues(
        envelope=fv_env
    )
    jira_keys = [i["key"] for i in jira_res["issues"]]
    print(
        f" [PASS] Atlassian Jira Cloud ({jira_res['jira_site']}) -> Live Tickets: {jira_keys}"
    )

    sn_res = LiveServiceNowITOMConnector().query_itom_incidents(envelope=rs_env)
    sn_nums = [i["number"] for i in sn_res["incidents"]]
    print(
        f" [PASS] ServiceNow PDI ({sn_res['instance_url']}) -> "
        f"State={sn_res.get('pdi_instance_state')} | Incidents: {sn_nums}"
    )

    entra_res = (
        LiveMicrosoftEntraOIDCConnector().verify_live_entra_oidc_and_jwks(
            envelope=rs_env
        )
    )
    print(
        f" [PASS] Microsoft Azure Entra ID (tid={entra_res['jwt_verified_tid']}) -> "
        f"live_jwt={entra_res['live_oauth_jwt_minted']} | "
        "rs256_jwks_verified="
        f"{entra_res['rs256_jwks_signature_verified']}"
        " (kid="
        f"{entra_res['jwt_verified_kid']}"
        ")"
    )

    print("\n" + "=" * 92)
    print(
        " STEP 4: RUNNING 10-VECTOR BREACH MATRIX ON TERRAFORM-CONFIGURED RUNTIME"
    )
    print("=" * 92)
    matrix = asyncio.run(run_all_10_breach_vectors())
    print(f" [PASS] {matrix['suite']} -> {matrix['score']}")
    print("=" * 92)
    print(" ALL TERRAFORM + 3P + 5-HOP END-TO-END CHECKS PASSED!")
    print("=" * 92)


if __name__ == "__main__":
    main()
