#!/usr/bin/env python3
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

# pylint: disable=line-too-long,wrong-import-position

"""CLI to validate or deploy Cymbal Pooled Multi-Tenancy to agent runtime in Gemini
(`ReasoningEngine`).

Supports both deployment targets for Workstream 2:
1. Cloud Run v2 (`cymbal-pooled-gateway` — fast edge PEP with raw HTTP header control)
2. agent runtime in Gemini (`ReasoningEngine` — managed `agent_runtime` via `agents-cli` or Vertex
   SDK)

Usage:
  uv run python scripts/deploy_vertex_agent_engine.py --dry-run
  uv run python scripts/deploy_vertex_agent_engine.py \
    --project-id cymbal-multitenancy-example --region
  us-central1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.reasoning_engine_app import (
    run_local_reasoning_engine_smoke_test,
    sanitize_gcp_project_id,
)
from mcp_server.sql_rls_engine_verifier import RelationalSQLRLSVerifier

REQUIRED_REASONING_ENGINE_ROLES = (
    # Least privilege (ADR-0010): no project-wide KMS or Secret Manager roles. Tenant data access
    # goes through per-tenant service accounts the runtime impersonates (TokenCreator on each).
    "roles/aiplatform.user",
    "roles/modelarmor.user",
    "roles/dlp.user",
    "roles/datastore.user",
    "roles/bigquery.jobUser",
    "roles/cloudtrace.agent",
    "roles/monitoring.metricWriter",
    "roles/logging.logWriter",
)


def build_agents_cli_deploy_command(project_id: str, region: str) -> str:
    clean_proj = sanitize_gcp_project_id(project_id)
    sa_email = f"cymbal-pooled-runtime-sa@{clean_proj}.iam.gserviceaccount.com"
    env_vars = ",".join(
        [
            f"GOOGLE_CLOUD_LOCATION={region}",
            "GOOGLE_GENAI_USE_VERTEXAI=true",
            "GOOGLE_API_USE_CLIENT_CERTIFICATE=false",
            "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY=true",
            "OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental",
            # Never export prompt/response content into the shared Cloud Trace: it would expose
            # every
            # tenant's data to anyone with trace read access (isolation invariant I4).
            "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=NO_CONTENT",
            "ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS=false",
            f"OTEL_EXPORTER_GCP_TRACE_PROJECT_ID={clean_proj}",
            f"MODEL_ARMOR_TEMPLATE_ID=projects/{clean_proj}/locations/{region}/templates/cymbal-pooled-inbound-pep",
        ]
    )
    return (
        "GOOGLE_API_USE_CLIENT_CERTIFICATE=false agents-cli deploy \\\n"
        "  --deployment-target agent_runtime \\\n"
        "  --service-name cymbal-pooled-reasoning-engine \\\n"
        f"  --service-account {sa_email} \\\n"
        f"  --project {clean_proj} \\\n"
        f"  --region {region} \\\n"
        f"  --update-env-vars {env_vars}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate or deploy Cymbal Multi-Tenant ReasoningEngine + SQL RLS Verifier."
    )
    parser.add_argument("--project-id", default="cymbal-multitenancy-example")
    parser.add_argument("--region", default="us-central1")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Run local ReasoningEngine 5-Hop smoke test and SQL RLS verification (default: True).",
    )
    args = parser.parse_args()

    clean_proj = sanitize_gcp_project_id(args.project_id)
    re_smoke = run_local_reasoning_engine_smoke_test()
    sql_report = RelationalSQLRLSVerifier().run_verification_suite()

    report = {
        "status": "PASS" if sql_report["status"] == "PASS" else "FAIL",
        "project_id": clean_proj,
        "region": args.region,
        "deployment_targets_supported": [
            "cloud_run_v2 (cymbal-pooled-gateway)",
            "vertex_ai_agent_engine (CymbalMultiTenantReasoningEngineApp)",
        ],
        "required_runtime_sa_roles": list(REQUIRED_REASONING_ENGINE_ROLES),
        "agents_cli_deploy_command": build_agents_cli_deploy_command(
            clean_proj, args.region
        ),
        "reasoning_engine_smoke_test": {
            "sanitized_trace_project_id": re_smoke[
                "sanitized_trace_project_id"
            ],
            "finvault_clamped_budget": re_smoke["finvault"][
                "clamped_thinking_budget"
            ],
            "finvault_rls_rows": re_smoke["finvault"]["rls_incidents_returned"],
            "retailstream_clamped_budget": re_smoke["retailstream"][
                "clamped_thinking_budget"
            ],
            "retailstream_rls_rows": re_smoke["retailstream"][
                "rls_incidents_returned"
            ],
            "retailstream_pre_model_redactions": re_smoke["retailstream"][
                "pre_model_redactions"
            ],
        },
        "relational_sql_rls_verification": sql_report,
    }
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
