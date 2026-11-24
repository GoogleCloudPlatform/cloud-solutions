#!/usr/bin/env bash
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

# ============================================================================
# Single deployment entrypoint (one path for our sandbox and customer projects).
#
#   scripts/deploy.sh <env> [--skip-infra] [--skip-image] [--skip-smoke] [--skip-db-bootstrap] [--provision-sandbox] [--auto-approve]
#
#   1. config-check : validates config/environments/<env>.yaml + tenant files (fails fast)
#   2. infra        : terraform apply (owns infra, IAM, the Cloud Run service identity and env),
#                     plus optional Gemini ReasoningEngine provisioning and AlloyDB RLS schema bootstrap
#   3. image        : builds and rolls the gateway image ONLY (no --service-account / gateway
#                     env overrides, so Terraform stays owner of identity and gateway config;
#                     for per-agent services whose `ignore_changes` preserves `functional_type`,
#                     optional AGENT_SANDBOX_* sandbox vars are propagated via `--update-env-vars`)
#   4. smoke        : Tier 3 post-deploy checks (scripts/verify_cloud_run_deployment.py)
#
# Each step is also a make target (config-check, deploy-infra, deploy-image, smoke) so enterprise
# CI/CD can call them individually.
# ============================================================================
set -euo pipefail

ENV_NAME="${1:-}"
if [[ -z "$ENV_NAME" || "$ENV_NAME" == -* ]]; then
  echo "Usage: scripts/deploy.sh <env> [--skip-infra] [--skip-image] [--skip-smoke] [--skip-db-bootstrap] [--provision-sandbox] [--auto-approve]"
  exit 1
fi
shift
SKIP_INFRA=0
SKIP_IMAGE=0
SKIP_SMOKE=0
SKIP_DB_BOOTSTRAP=0
PROVISION_SANDBOX=0
APPROVE=""
for arg in "$@"; do
  case "$arg" in
    --skip-infra) SKIP_INFRA=1 ;;
    --skip-image) SKIP_IMAGE=1 ;;
    --skip-smoke) SKIP_SMOKE=1 ;;
    --skip-db-bootstrap) SKIP_DB_BOOTSTRAP=1 ;;
    --provision-sandbox) PROVISION_SANDBOX=1 ;;
    --auto-approve) APPROVE="-auto-approve" ;;
    *)
      echo "Unknown option: $arg"
      exit 1
      ;;
  esac
done

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"
export CYMBAL_ENV="$ENV_NAME"
export CLOUDSDK_CORE_DISABLE_PROMPTS=1
export CLOUDSDK_METRICS_ENVIRONMENT="${CLOUDSDK_METRICS_ENVIRONMENT:+$CLOUDSDK_METRICS_ENVIRONMENT }datacloud.ai-agent"
SERVICE="cymbal-pooled-gateway"

echo "==> [1/4] Validating platform config for '$ENV_NAME'"
uv run --frozen python scripts/config_check.py --env "$ENV_NAME" --for-deploy >/dev/null
GATEWAY_SIGNING_SECRET=""
read -r PROJECT_ID REGION GATEWAY_SIGNING_SECRET < <(uv run --frozen python -c "
from agents.platform_config import load_platform_config
c = load_platform_config('$ENV_NAME'); print(c.gcp.project_id, c.gcp.region, c.identity.gateway_signing_secret or '')")
echo "    project=$PROJECT_ID region=$REGION"

# Propagate optional Agent Sandbox in Gemini settings to agent_runtime services, which use
# Terraform lifecycle.ignore_changes on env to protect Cloud Run functional_type.
_resolve_tfvars_value() {
  local tf_key="$1"
  local kind="$2"
  local default_val="${3:-}"
  local tf_dir="${DEPLOY_TF_DIR:-terraform}"
  local -a tf_files=()
  [[ -f "$tf_dir/terraform.tfvars" ]] && tf_files+=("$tf_dir/terraform.tfvars")
  shopt -s nullglob
  for f in "$tf_dir"/*.auto.tfvars; do
    tf_files+=("$f")
  done
  shopt -u nullglob
  [[ -f "$tf_dir/$ENV_NAME.tfvars" ]] && tf_files+=("$tf_dir/$ENV_NAME.tfvars")
  if ((${#tf_files[@]} == 0)); then
    printf '%s' "$default_val"
    return
  fi
  python3 - "$tf_key" "$kind" "$default_val" ${tf_files[@]+"${tf_files[@]}"} <<'PYEOF'
import re
import sys
from pathlib import Path

key, kind, default_val = sys.argv[1], sys.argv[2], sys.argv[3]
resolved = default_val
if kind == "bool":
    pat = re.compile(rf"^\s*{re.escape(key)}\s*=\s*(true|false)\b", re.MULTILINE)
else:
    pat = re.compile(rf'^\s*{re.escape(key)}\s*=\s*"([^"]*)"', re.MULTILINE)
for path_str in sys.argv[4:]:
    try:
        text = Path(path_str).read_text(encoding="utf-8")
    except OSError:
        continue
    for match in pat.finditer(text):
        resolved = match.group(1)
print(resolved)
PYEOF
}

_resolve_sandbox_var() {
  local env_key="$1"
  local tf_key="$2"
  local val="${!env_key:-}"
  if [[ -z "$val" ]]; then
    val="$(_resolve_tfvars_value "$tf_key" "string" "")"
  fi
  printf '%s' "$val"
}

AGENT_SANDBOX_REASONING_ENGINE_NAME_VAL="$(_resolve_sandbox_var AGENT_SANDBOX_REASONING_ENGINE_NAME agent_sandbox_reasoning_engine_name)"
AGENT_SANDBOX_CODE_TEMPLATE_VAL="$(_resolve_sandbox_var AGENT_SANDBOX_CODE_TEMPLATE agent_sandbox_code_template)"
AGENT_SANDBOX_SHELL_TEMPLATE_VAL="$(_resolve_sandbox_var AGENT_SANDBOX_SHELL_TEMPLATE agent_sandbox_shell_template)"

# Propagate shell env AGENT_SANDBOX_* overrides into `terraform apply` so `cymbal_pooled_gateway`
# stays in lockstep with `agent_runtime` services.
AGENT_SANDBOX_TF_VAR_ARGS=()
[[ -n "${AGENT_SANDBOX_REASONING_ENGINE_NAME:-}" ]] && AGENT_SANDBOX_TF_VAR_ARGS+=(-var="agent_sandbox_reasoning_engine_name=${AGENT_SANDBOX_REASONING_ENGINE_NAME}")
[[ -n "${AGENT_SANDBOX_CODE_TEMPLATE:-}" ]] && AGENT_SANDBOX_TF_VAR_ARGS+=(-var="agent_sandbox_code_template=${AGENT_SANDBOX_CODE_TEMPLATE}")
[[ -n "${AGENT_SANDBOX_SHELL_TEMPLATE:-}" ]] && AGENT_SANDBOX_TF_VAR_ARGS+=(-var="agent_sandbox_shell_template=${AGENT_SANDBOX_SHELL_TEMPLATE}")

AGENT_SANDBOX_ENV_PAIRS=()
AGENT_SANDBOX_REMOVE_KEYS=()
if [[ -n "$AGENT_SANDBOX_REASONING_ENGINE_NAME_VAL" ]]; then
  AGENT_SANDBOX_ENV_PAIRS+=("AGENT_SANDBOX_REASONING_ENGINE_NAME=${AGENT_SANDBOX_REASONING_ENGINE_NAME_VAL}")
else
  AGENT_SANDBOX_REMOVE_KEYS+=("AGENT_SANDBOX_REASONING_ENGINE_NAME")
fi
if [[ -n "$AGENT_SANDBOX_CODE_TEMPLATE_VAL" ]]; then
  AGENT_SANDBOX_ENV_PAIRS+=("AGENT_SANDBOX_CODE_TEMPLATE=${AGENT_SANDBOX_CODE_TEMPLATE_VAL}")
else
  AGENT_SANDBOX_REMOVE_KEYS+=("AGENT_SANDBOX_CODE_TEMPLATE")
fi
if [[ -n "$AGENT_SANDBOX_SHELL_TEMPLATE_VAL" ]]; then
  AGENT_SANDBOX_ENV_PAIRS+=("AGENT_SANDBOX_SHELL_TEMPLATE=${AGENT_SANDBOX_SHELL_TEMPLATE_VAL}")
else
  AGENT_SANDBOX_REMOVE_KEYS+=("AGENT_SANDBOX_SHELL_TEMPLATE")
fi
AGENT_SANDBOX_UPDATE_ENV_CSV="$(
  IFS=,
  echo "${AGENT_SANDBOX_ENV_PAIRS[*]-}"
)"
AGENT_SANDBOX_REMOVE_ENV_CSV="$(
  IFS=,
  echo "${AGENT_SANDBOX_REMOVE_KEYS[*]-}"
)"

_resolve_enable_live_mode() {
  if [[ -n "${TF_VAR_enable_live_mode:-}" ]]; then
    [[ "${TF_VAR_enable_live_mode}" == "true" || "${TF_VAR_enable_live_mode}" == "1" ]] && printf '1' || printf '0'
    return
  fi
  local tf_live
  tf_live="$(_resolve_tfvars_value enable_live_mode bool true)"
  [[ "$tf_live" == "true" ]] && printf '1' || printf '0'
}

_resolve_enable_agent_runtimes() {
  if [[ -n "${TF_VAR_enable_agent_runtimes:-}" ]]; then
    printf '%s' "${TF_VAR_enable_agent_runtimes}"
    return
  fi
  _resolve_tfvars_value enable_agent_runtimes bool false
}

_resolve_enable_alloydb_primary() {
  local tf_cluster tf_primary
  tf_cluster="${TF_VAR_enable_alloydb_cluster:-$(_resolve_tfvars_value enable_alloydb_cluster bool true)}"
  tf_primary="${TF_VAR_enable_alloydb_primary_instance:-$(_resolve_tfvars_value enable_alloydb_primary_instance bool false)}"
  [[ "$tf_cluster" == "true" && "$tf_primary" == "true" ]] && printf '1' || printf '0'
}

_resolve_alloydb_public_ip() {
  local tf_public
  tf_public="${TF_VAR_alloydb_enable_public_ip:-$(_resolve_tfvars_value alloydb_enable_public_ip bool false)}"
  [[ "$tf_public" == "true" || "$tf_public" == "1" ]] && printf '1' || printf '0'
}

AGENT_LIVE_GCP_FLAG="$(_resolve_enable_live_mode)"
ENABLE_AGENT_RUNTIMES_FLAG="$(_resolve_enable_agent_runtimes)"
ENABLE_ALLOYDB_PRIMARY_FLAG="$(_resolve_enable_alloydb_primary)"
ALLOYDB_PUBLIC_IP_FLAG="$(_resolve_alloydb_public_ip)"

_sync_agent_runtime_live_wiring() {
  # Synchronizes live GCP env vars + Direct VPC Egress onto disaggregated agent runtimes
  # (`lifecycle.ignore_changes` prevents Terraform from mutating Cloud Run `functional_type`).
  if [[ "$ENABLE_AGENT_RUNTIMES_FLAG" != "true" ]]; then
    return
  fi
  local tf_out_json gw_env_json
  tf_out_json="$(terraform -chdir=terraform output -json 2>/dev/null || true)"
  gw_env_json="$(gcloud run services describe "$SERVICE" --region="$REGION" --project="$PROJECT_ID" --format='json(spec.template.spec.containers[0].env)' 2>/dev/null || true)"
  local sync_update_csv="" sync_remove_csv="" sync_vpc_name=""
  eval "$(
    TF_OUT_JSON="$tf_out_json" \
      GW_ENV_JSON="$gw_env_json" \
      LIVE_FLAG="$AGENT_LIVE_GCP_FLAG" \
      MB_ENGINE="$AGENT_SANDBOX_REASONING_ENGINE_NAME_VAL" \
      AGENT_SANDBOX_UPD="$AGENT_SANDBOX_UPDATE_ENV_CSV" \
      AGENT_SANDBOX_REM="$AGENT_SANDBOX_REMOVE_ENV_CSV" \
      python3 - <<'PYEOF'
import json
import os
import shlex

raw = os.environ.get("TF_OUT_JSON", "").strip()
try:
    outputs = json.loads(raw) if raw else {}
except ValueError:
    outputs = {}
if not isinstance(outputs, dict):
    outputs = {}

gw_raw = os.environ.get("GW_ENV_JSON", "").strip()
try:
    gw_doc = json.loads(gw_raw) if gw_raw else {}
except ValueError:
    gw_doc = {}
gw_env: dict[str, str] = {}
if isinstance(gw_doc, dict):
    containers = (
        gw_doc.get("spec", {})
        .get("template", {})
        .get("spec", {})
        .get("containers", [])
    )
    if isinstance(containers, list) and containers and isinstance(containers[0], dict):
        for item in containers[0].get("env", []) or []:
            if isinstance(item, dict) and item.get("name"):
                gw_env[str(item["name"])] = str(item.get("value") or "").strip()


def out_val(key: str) -> str:
    entry = outputs.get(key)
    if isinstance(entry, dict) and entry.get("value") is not None:
        return str(entry["value"]).strip()
    return ""


live = os.environ.get("LIVE_FLAG", "0") == "1"
mb_engine = os.environ.get("MB_ENGINE", "").strip()
sandbox_upd = os.environ.get("AGENT_SANDBOX_UPD", "").strip()
sandbox_rem = os.environ.get("AGENT_SANDBOX_REM", "").strip()

upd: dict[str, str] = {"CYMBAL_LIVE_GCP": "1" if live else "0"}
rem: list[str] = [k for k in sandbox_rem.split(",") if k]

if sandbox_upd:
    for item in sandbox_upd.split(","):
        if "=" in item:
            k, v = item.split("=", 1)
            upd[k] = v

if mb_engine:
    upd["MEMORY_BANK_REASONING_ENGINE"] = mb_engine
else:
    rem.append("MEMORY_BANK_REASONING_ENGINE")

mapping = {
    "MODEL_ARMOR_TEMPLATE_ID": out_val("model_armor_template_short_id"),
    "DLP_INSPECT_TEMPLATE": out_val("dlp_inspect_template_id"),
    "DLP_DEIDENTIFY_TEMPLATE": out_val("dlp_deidentify_template_id"),
    "KMS_KEYRING_NAME": out_val("tenant_key_ring_name"),
    "RUNBOOK_BUCKET_NAME": out_val("pooled_runbook_gcs_bucket"),
    "BIGQUERY_DATASET": out_val("analytics_dataset_id"),
    "FIRESTORE_DATABASE": out_val("firestore_database_name"),
}
for env_k, env_v in mapping.items():
    if env_v:
        upd[env_k] = env_v

vpc_name = ""
if live:
    upd["FIRESTORE_REVOCATION_STORE"] = "1"
    redis_tls_secret = gw_env.get("REDIS_TLS_SECRET_VERSION", "")
    redis_url = gw_env.get("REDIS_URL", "") or out_val("redis_bulkhead_url")
    if redis_tls_secret:
        upd["REDIS_TLS_SECRET_VERSION"] = redis_tls_secret
        rem.append("REDIS_URL")
    elif redis_url:
        upd["REDIS_URL"] = redis_url
        rem.append("REDIS_TLS_SECRET_VERSION")
    alloy_ip = out_val("alloydb_primary_ip_address")
    if alloy_ip:
        upd["DATABASE_URL"] = f"postgresql://{alloy_ip}:5432/postgres"
        upd["ALLOYDB_TENANT_IAM_AUTH"] = "1"
    vpc_name = out_val("pooled_vpc_name")
else:
    rem.extend(
        [
            "FIRESTORE_REVOCATION_STORE",
            "REDIS_URL",
            "REDIS_TLS_SECRET_VERSION",
            "DATABASE_URL",
            "ALLOYDB_TENANT_IAM_AUTH",
        ]
    )

rem_clean = [k for k in dict.fromkeys(rem) if k not in upd]
upd_csv = ",".join(f"{k}={v}" for k, v in upd.items())
rem_csv = ",".join(rem_clean)

print(f"sync_update_csv={shlex.quote(upd_csv)}")
print(f"sync_remove_csv={shlex.quote(rem_csv)}")
print(f"sync_vpc_name={shlex.quote(vpc_name)}")
PYEOF
  )"
  for DISAGG_SVC in cymbal-agent-shared cymbal-agent-finvault-alpha; do
    if gcloud run services describe "$DISAGG_SVC" --region="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
      local -a sync_args=()
      [[ -n "$sync_remove_csv" ]] && sync_args+=(--remove-env-vars="$sync_remove_csv")
      [[ -n "$sync_update_csv" ]] && sync_args+=(--update-env-vars="$sync_update_csv")
      if [[ -n "$sync_vpc_name" ]]; then
        sync_args+=(--network="$sync_vpc_name" --subnet="$sync_vpc_name" --vpc-egress=private-ranges-only)
      fi
      gcloud alpha run services update "$DISAGG_SVC" --region="$REGION" --project="$PROJECT_ID" --quiet ${sync_args[@]+"${sync_args[@]}"}
    fi
  done
}

_run_alloydb_rls_bootstrap() {
  local scope="${1:-all}"
  local tf_out_json state_uri=""
  tf_out_json="$(terraform -chdir=terraform output -json 2>/dev/null || true)"
  ALLOYDB_URI=""
  TENANT_DB_USERS=""
  eval "$(
    TF_OUT_JSON="$tf_out_json" SCOPE="$scope" python3 - <<'PYEOF'
import json, os, shlex

raw = os.environ.get("TF_OUT_JSON", "").strip()
scope = os.environ.get("SCOPE", "all")
try:
    outputs = json.loads(raw) if raw else {}
except ValueError:
    outputs = {}
if not isinstance(outputs, dict):
    outputs = {}
uri = str((outputs.get("alloydb_primary_instance_uri") or {}).get("value") or "").strip()
users: list[str] = []
if scope != "runtime-only":
    sa_map = (outputs.get("tenant_service_accounts") or {}).get("value") or {}
    users = [
        str(email).removesuffix(".gserviceaccount.com")
        for email in sa_map.values()
        if str(email).strip()
    ]
print(f"ALLOYDB_URI={shlex.quote(uri)}")
print(f"TENANT_DB_USERS={shlex.quote(' '.join(users))}")
PYEOF
  )"
  if [[ -z "$ALLOYDB_URI" ]]; then
    state_uri="$(terraform -chdir=terraform state show -no-color 'module.platform_core.google_alloydb_instance.pooled_rls_primary[0]' 2>/dev/null | sed -n 's/^[[:space:]]*name[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' | head -n1 || true)"
    ALLOYDB_URI="$state_uri"
  fi
  if [[ -z "$ALLOYDB_URI" ]]; then
    return
  fi
  echo "==> Bootstrapping AlloyDB PostgreSQL RLS & IAM database roles..."
  if ! command -v alloydb-auth-proxy >/dev/null 2>&1 && [[ ! -x "$HOME/.local/bin/alloydb-auth-proxy" ]]; then
    local proxy_build=""
    case "$(uname -s)/$(uname -m)" in
      Linux/x86_64) proxy_build="linux.amd64" ;;
      Linux/aarch64 | Linux/arm64) proxy_build="linux.arm64" ;;
      Darwin/arm64) proxy_build="darwin.arm64" ;;
      Darwin/x86_64) proxy_build="darwin.amd64" ;;
    esac
    if [[ -z "$proxy_build" ]]; then
      echo "ERROR: alloydb-auth-proxy is not installed and there is no prebuilt binary for" >&2
      echo "       $(uname -s)/$(uname -m). Install it and put it on PATH, then re-run:" >&2
      echo "       https://cloud.google.com/alloydb/docs/auth-proxy/connect#install" >&2
      exit 1
    fi
    mkdir -p "$HOME/.local/bin"
    curl -fsSL -o "$HOME/.local/bin/alloydb-auth-proxy" \
      "https://storage.googleapis.com/alloydb-auth-proxy/v1.11.1/alloydb-auth-proxy.${proxy_build}"
    chmod +x "$HOME/.local/bin/alloydb-auth-proxy"
  fi
  local db_admin_user
  db_admin_user="$(gcloud config get-value account 2>/dev/null || true)"
  if [[ -z "$db_admin_user" ]]; then
    echo "    WARNING: Unable to resolve active gcloud account for AlloyDB RLS bootstrap; skipping."
    return
  fi
  local -a grant_args=(--grant-iam-user "cymbal-pooled-runtime-sa@${PROJECT_ID}.iam")
  local db_user
  for db_user in $TENANT_DB_USERS; do
    grant_args+=(--grant-iam-user "$db_user")
  done
  local -a ip_args=()
  if [[ "$ALLOYDB_PUBLIC_IP_FLAG" != "1" ]]; then
    # alloydb_enable_public_ip = false (the default): the instance has only its private VPC address.
    ip_args+=(--private-ip)
    echo "    AlloyDB public IP is off: connecting the Auth Proxy to the private VPC address."
    echo "    This machine must be able to reach the VPC. If it cannot, either run deploy.sh from"
    echo "    inside the VPC, set alloydb_enable_public_ip = true in terraform/${ENV_NAME}.tfvars"
    echo "    (see terraform/terraform.tfvars.example for what that exposes), or pass --skip-db-bootstrap."
  fi
  uv run --frozen python scripts/bootstrap_alloydb_rls.py \
    --instance-uri "$ALLOYDB_URI" \
    --db-user "$db_admin_user" \
    --iam-auth \
    ${ip_args[@]+"${ip_args[@]}"} \
    ${grant_args[@]+"${grant_args[@]}"}
}

if [[ "$SKIP_INFRA" == 0 ]]; then
  echo "==> [2/4] Bootstrapping core GCP APIs & running terraform apply"
  gcloud services enable \
    serviceusage.googleapis.com \
    cloudresourcemanager.googleapis.com \
    iam.googleapis.com \
    cloudkms.googleapis.com \
    storage.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    aiplatform.googleapis.com \
    --project="$PROJECT_ID" --quiet
  gcloud artifacts repositories describe cloud-run-source-deploy --location="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1 ||
    gcloud artifacts repositories create cloud-run-source-deploy --repository-format=docker --location="$REGION" --project="$PROJECT_ID" --quiet
  gcloud storage buckets describe "gs://run-sources-${PROJECT_ID}-${REGION}" --project="$PROJECT_ID" >/dev/null 2>&1 ||
    gcloud storage buckets create "gs://run-sources-${PROJECT_ID}-${REGION}" --location="$REGION" --project="$PROJECT_ID" --uniform-bucket-level-access --public-access-prevention --quiet
  # State lives per project and per environment (terraform/backend.tf). Always pass both values
  # so one environment's apply can never read or write another environment's state.
  TF_STATE_BUCKET="${TF_STATE_BUCKET:-${PROJECT_ID}-tfstate}"
  if ! gcloud storage buckets describe "gs://${TF_STATE_BUCKET}" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "    Creating Terraform remote state bucket gs://${TF_STATE_BUCKET} (versioning + PAP enabled)..."
    gcloud storage buckets create "gs://${TF_STATE_BUCKET}" --location="$REGION" --project="$PROJECT_ID" --uniform-bucket-level-access --public-access-prevention --quiet
    gcloud storage buckets update "gs://${TF_STATE_BUCKET}" --versioning --quiet >/dev/null 2>&1 || true
  fi
  terraform -chdir=terraform init -input=false -reconfigure \
    -backend-config="bucket=$TF_STATE_BUCKET" -backend-config="prefix=$ENV_NAME" >/dev/null
  # Environment inputs (e.g. terraform/sandbox.tfvars) are required for adopted environments:
  # without them the defaults would plan to remove resources that the environment enables.
  TF_VAR_FILE_ARGS=()
  SIGNING_SECRET_TF_VAR_ARGS=()
  if [[ -f "terraform/$ENV_NAME.tfvars" ]]; then
    TF_VAR_FILE_ARGS=(-var-file="$ENV_NAME.tfvars")
  else
    # No per-environment tfvars. Every Terraform call below already passes project_id, region and
    # platform_environment from the platform config, so Terraform targets the configured project;
    # all other inputs keep their Terraform defaults. If the environment configures a pinned
    # gateway_signing_secret, enable platform_signing_shells so fresh projects get the secret shell
    # and IAM binding before the gateway boots.
    if [[ -n "${GATEWAY_SIGNING_SECRET:-}" ]]; then
      SIGNING_SECRET_TF_VAR_ARGS=(-var="enable_platform_signing_secrets=true")
    fi
    echo "    INFO: terraform/$ENV_NAME.tfvars not found; using project_id=$PROJECT_ID region=$REGION"
    echo "          platform_environment=$ENV_NAME from config/environments/$ENV_NAME.yaml and Terraform"
    echo "          defaults for everything else. Copy terraform/terraform.tfvars.example to"
    echo "          terraform/$ENV_NAME.tfvars to enable live mode, AlloyDB, Redis or agent runtimes."
  fi
  # Ensure cymbal-build-sa, KMS signing key, and signing secret shells exist before building or bootstrapping services
  terraform -chdir=terraform apply -auto-approve ${TF_VAR_FILE_ARGS[@]+"${TF_VAR_FILE_ARGS[@]}"} \
    ${SIGNING_SECRET_TF_VAR_ARGS[@]+"${SIGNING_SECRET_TF_VAR_ARGS[@]}"} \
    -target="module.platform_core.google_project_service.bootstrap_apis" \
    -target="module.platform_core.google_project_service.enabled_apis" \
    -target="module.platform_core.google_service_account.cymbal_build" \
    -target="module.platform_core.google_project_iam_member.build_log_writer" \
    -target="module.platform_core.google_artifact_registry_repository_iam_member.build_ar_writer" \
    -target="module.platform_core.google_storage_bucket_iam_member.build_source_viewer" \
    -target="module.platform_core.google_storage_bucket_iam_member.build_source_creator" \
    -target="module.platform_core.google_kms_key_ring.platform" \
    -target="module.platform_core.google_kms_crypto_key.context_signing" \
    -target="module.platform_core.google_secret_manager_secret.platform_signing_shells" \
    -var="project_id=$PROJECT_ID" \
    -var="region=$REGION" \
    -var="platform_environment=$ENV_NAME" >/dev/null 2>&1 || true
  if [[ -n "${GATEWAY_SIGNING_SECRET:-}" ]]; then
    SIGNING_SECRET_NAME="${GATEWAY_SIGNING_SECRET%%/versions/*}"
    SIGNING_SECRET_VERSION="${GATEWAY_SIGNING_SECRET#*/versions/}"
    [[ "$SIGNING_SECRET_VERSION" == "$GATEWAY_SIGNING_SECRET" ]] && SIGNING_SECRET_VERSION="1"
    if [[ "$SIGNING_SECRET_VERSION" == "1" ]] &&
      gcloud secrets describe "$SIGNING_SECRET_NAME" --project="$PROJECT_ID" >/dev/null 2>&1 &&
      ! gcloud secrets versions describe 1 --secret="$SIGNING_SECRET_NAME" --project="$PROJECT_ID" >/dev/null 2>&1; then
      echo "    Seeding initial EC P-256 signing key version 1 for secret '$SIGNING_SECRET_NAME' (in-memory)..."
      openssl ecparam -name prime256v1 -genkey -noout 2>/dev/null |
        openssl pkcs8 -topk8 -nocrypt 2>/dev/null |
        gcloud secrets versions add "$SIGNING_SECRET_NAME" --project="$PROJECT_ID" --data-file=- --quiet >/dev/null
    fi
  fi
  GW_READY_STATUS="$(gcloud run services describe "$SERVICE" --region="$REGION" --project="$PROJECT_ID" --format='value(status.conditions[0].status)' 2>/dev/null || true)"
  GW_STATE_INFO="$(terraform -chdir=terraform state show -no-color "module.platform_core.google_cloud_run_v2_service.cymbal_pooled_gateway" 2>/dev/null || true)"
  if [[ "$GW_READY_STATUS" == "False" ]] && { [[ -z "$GW_STATE_INFO" ]] || [[ "$GW_STATE_INFO" == *"(tainted)"* ]]; }; then
    echo "    Cleaning up failed gateway service ($SERVICE Ready=False) before rebuild..."
    terraform -chdir=terraform state rm "module.platform_core.google_cloud_run_v2_service.cymbal_pooled_gateway" >/dev/null 2>&1 || true
    gcloud run services delete "$SERVICE" --region="$REGION" --project="$PROJECT_ID" --quiet >/dev/null 2>&1 || true
  fi
  EXISTING_IMAGE="$(gcloud run services describe "$SERVICE" --region="$REGION" --project="$PROJECT_ID" --format='value(spec.template.spec.containers[0].image)' 2>/dev/null || true)"
  if [[ "$SKIP_IMAGE" == 0 ]]; then
    if [[ -n "$EXISTING_IMAGE" && "$EXISTING_IMAGE" != *"cloudrun/container/hello"* ]]; then
      echo "    Pre-building application image with latest config before disaggregated service apply..."
      BUILD_ARGS=()
      if gcloud iam service-accounts describe "cymbal-build-sa@${PROJECT_ID}.iam.gserviceaccount.com" --project="$PROJECT_ID" >/dev/null 2>&1; then
        BUILD_ARGS+=(--build-service-account="projects/${PROJECT_ID}/serviceAccounts/cymbal-build-sa@${PROJECT_ID}.iam.gserviceaccount.com")
      fi
      gcloud run deploy "$SERVICE" --source=. --region="$REGION" --project="$PROJECT_ID" --quiet ${BUILD_ARGS[@]+"${BUILD_ARGS[@]}"}
      EXISTING_IMAGE="$(gcloud run services describe "$SERVICE" --region="$REGION" --project="$PROJECT_ID" --format='value(spec.template.spec.containers[0].image)' 2>/dev/null || true)"
      SKIP_IMAGE=1
    else
      echo "    Fresh project detected ($SERVICE absent or placeholder); pre-building bootstrap image via Cloud Build..."
      BOOTSTRAP_TAG="${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/${SERVICE}:bootstrap"
      CB_CFG="$(mktemp /tmp/cloudbuild-bootstrap-XXXXXX.yaml)"
      cat >"$CB_CFG" <<YAML
steps:
  - name: gcr.io/cloud-builders/docker
    args: ['build', '-t', '${BOOTSTRAP_TAG}', '.']
images:
  - '${BOOTSTRAP_TAG}'
options:
  logging: CLOUD_LOGGING_ONLY
YAML
      CB_ARGS=(
        --config="$CB_CFG"
        --gcs-source-staging-dir="gs://run-sources-${PROJECT_ID}-${REGION}/source"
        --region="$REGION"
        --project="$PROJECT_ID"
        --quiet
      )
      if gcloud iam service-accounts describe "cymbal-build-sa@${PROJECT_ID}.iam.gserviceaccount.com" --project="$PROJECT_ID" >/dev/null 2>&1; then
        CB_ARGS+=(--service-account="projects/${PROJECT_ID}/serviceAccounts/cymbal-build-sa@${PROJECT_ID}.iam.gserviceaccount.com")
      fi
      CB_OK=0
      for attempt in 1 2 3; do
        if gcloud builds submit . ${CB_ARGS[@]+"${CB_ARGS[@]}"}; then
          CB_OK=1
          break
        fi
        if [[ "$attempt" -lt 3 ]]; then
          echo "    Cloud Build bootstrap attempt ${attempt} failed (fresh IAM propagation); retrying in 10s..."
          sleep 10
        fi
      done
      rm -f "$CB_CFG"
      if [[ "$CB_OK" != 1 ]]; then
        echo "ERROR: Cloud Build bootstrap image build failed." >&2
        exit 1
      fi
      EXISTING_IMAGE="$BOOTSTRAP_TAG"
      SKIP_IMAGE=1
    fi
  fi
  # Clean up any tainted/failed Cloud Run services before updating active disaggregated services
  for DISAGG_SVC in cymbal-credential-broker cymbal-agent-shared cymbal-agent-finvault-alpha; do
    READY_STATUS="$(gcloud run services describe "$DISAGG_SVC" --region="$REGION" --project="$PROJECT_ID" --format='value(status.conditions[0].status)' 2>/dev/null || true)"
    if [[ "$READY_STATUS" == "False" ]]; then
      gcloud run services delete "$DISAGG_SVC" --region="$REGION" --project="$PROJECT_ID" --quiet >/dev/null 2>&1 || true
    fi
  done
  IMAGE_VAR_ARGS=()
  if [[ -n "$EXISTING_IMAGE" && "$EXISTING_IMAGE" != *"cloudrun/container/hello"* ]]; then
    IMAGE_VAR_ARGS=(-var="gateway_container_image=$EXISTING_IMAGE" -var="broker_container_image=$EXISTING_IMAGE")
    for DISAGG_SVC in cymbal-credential-broker cymbal-agent-shared cymbal-agent-finvault-alpha; do
      if gcloud run services describe "$DISAGG_SVC" --region="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
        ENV_UPDATE_ARGS=()
        if [[ "$DISAGG_SVC" != "cymbal-credential-broker" ]]; then
          [[ -n "$AGENT_SANDBOX_REMOVE_ENV_CSV" ]] && ENV_UPDATE_ARGS+=(--remove-env-vars="$AGENT_SANDBOX_REMOVE_ENV_CSV")
          [[ -n "$AGENT_SANDBOX_UPDATE_ENV_CSV" ]] && ENV_UPDATE_ARGS+=(--update-env-vars="$AGENT_SANDBOX_UPDATE_ENV_CSV")
        fi
        gcloud alpha run services update "$DISAGG_SVC" --image="$EXISTING_IMAGE" --region="$REGION" --project="$PROJECT_ID" --quiet ${ENV_UPDATE_ARGS[@]+"${ENV_UPDATE_ARGS[@]}"}
      fi
    done
  fi
  # Bootstrap per-agent Cloud Run services with native Cloud Run Agent Identity (--identity-type=agent-identity)
  if [[ "$ENABLE_AGENT_RUNTIMES_FLAG" == "true" && -n "$EXISTING_IMAGE" && "$EXISTING_IMAGE" != *"cloudrun/container/hello"* ]]; then
    PROJECT_NUM="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
    GATEWAY_SA_EMAIL="cymbal-pooled-runtime-sa@${PROJECT_ID}.iam.gserviceaccount.com"
    BROKER_URL="https://cymbal-credential-broker-${PROJECT_NUM}.${REGION}.run.app"
    CONTEXT_KEY_VERSION="projects/${PROJECT_ID}/locations/${REGION}/keyRings/cymbal-platform-kr/cryptoKeys/ws2-context-signing/cryptoKeyVersions/1"
    for PAIR in "shared:cymbal-agent-shared:cymbal_shared_diagnostic_agent" "finvault-alpha:cymbal-agent-finvault-alpha:finvault_regulatory_escalation_agent"; do
      TF_KEY="${PAIR%%:*}"
      REST="${PAIR#*:}"
      AGENT_SVC="${REST%%:*}"
      AGENT_ID="${REST#*:}"
      AGENT_URL="https://${AGENT_SVC}-${PROJECT_NUM}.${REGION}.run.app"
      CUR_ID_TYPE="$(gcloud alpha run services describe "$AGENT_SVC" --region="$REGION" --project="$PROJECT_ID" --format='value(spec.template.metadata.annotations."run.googleapis.com/identity-type")' 2>/dev/null || true)"
      if [[ "$CUR_ID_TYPE" != "agent-identity" ]]; then
        echo "    Bootstrapping $AGENT_SVC with Cloud Run Agent Identity (--identity-type=agent-identity --functional-type=agent --identity-certificate)..."
        terraform -chdir=terraform state rm "module.agent_runtime[\"${TF_KEY}\"].google_cloud_run_v2_service.agent_runtime" >/dev/null 2>&1 || true
        gcloud run services delete "$AGENT_SVC" --region="$REGION" --project="$PROJECT_ID" --quiet >/dev/null 2>&1 || true
        RUNTIME_ENV_CSV="CYMBAL_ENV=${ENV_NAME},CYMBAL_LIVE_GCP=${AGENT_LIVE_GCP_FLAG},GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_REGION=${REGION},GOOGLE_CLOUD_LOCATION=${REGION},GOOGLE_GENAI_USE_VERTEXAI=true,RUNTIME_AGENT_ID=${AGENT_ID},RUNTIME_ALLOWED_CALLERS=${GATEWAY_SA_EMAIL},RUNTIME_EXPECTED_AUDIENCE=${AGENT_URL},CREDENTIAL_BROKER_URL=${BROKER_URL},CONTEXT_SIGNING_KMS_KEY=${CONTEXT_KEY_VERSION},CONTEXT_TOKEN_KMS_KEY_VERSION=${CONTEXT_KEY_VERSION},CONTEXT_TOKEN_REQUIRE_KMS=1,CONTEXT_TOKEN_REQUIRE_AGENT_ID=1"
        [[ -n "$AGENT_SANDBOX_UPDATE_ENV_CSV" ]] && RUNTIME_ENV_CSV="${RUNTIME_ENV_CSV},${AGENT_SANDBOX_UPDATE_ENV_CSV}"
        gcloud alpha run deploy "$AGENT_SVC" \
          --image="$EXISTING_IMAGE" --region="$REGION" --project="$PROJECT_ID" --quiet \
          --identity-type=agent-identity --functional-type=agent --identity-certificate \
          --no-allow-unauthenticated --ingress=all --max-instances=1 --cpu-boost \
          --command=uvicorn \
          --args=runtime_service.main:create_app,--factory,--host,0.0.0.0,--port,8080 \
          --set-env-vars="$RUNTIME_ENV_CSV"
      fi
      if ! terraform -chdir=terraform state show "module.agent_runtime[\"${TF_KEY}\"].google_cloud_run_v2_service.agent_runtime" >/dev/null 2>&1; then
        terraform -chdir=terraform import ${TF_VAR_FILE_ARGS[@]+"${TF_VAR_FILE_ARGS[@]}"} ${SIGNING_SECRET_TF_VAR_ARGS[@]+"${SIGNING_SECRET_TF_VAR_ARGS[@]}"} ${IMAGE_VAR_ARGS[@]+"${IMAGE_VAR_ARGS[@]}"} ${AGENT_SANDBOX_TF_VAR_ARGS[@]+"${AGENT_SANDBOX_TF_VAR_ARGS[@]}"} \
          -var="project_id=$PROJECT_ID" -var="region=$REGION" -var="platform_environment=$ENV_NAME" \
          "module.agent_runtime[\"${TF_KEY}\"].google_cloud_run_v2_service.agent_runtime" \
          "projects/${PROJECT_ID}/locations/${REGION}/services/${AGENT_SVC}"
      fi
    done
  fi
  # Pre-provision AlloyDB + bootstrap `cymbal_mcp_app` role/FORCE RLS before creating `cymbal_pooled_gateway`,
  # because `_gateway_lifespan` fails closed at startup if `cymbal_mcp_app` does not exist yet.
  if [[ "$AGENT_LIVE_GCP_FLAG" == "1" && "$SKIP_DB_BOOTSTRAP" == 0 && "$ENABLE_ALLOYDB_PRIMARY_FLAG" == "1" ]]; then
    echo "==> Pre-provisioning AlloyDB primary instance & bootstrapping RLS schema before gateway apply..."
    terraform -chdir=terraform apply $APPROVE ${TF_VAR_FILE_ARGS[@]+"${TF_VAR_FILE_ARGS[@]}"} \
      -target="module.platform_core.google_compute_network.pooled_vpc" \
      -target="module.platform_core.google_compute_global_address.alloydb_psa_range" \
      -target="module.platform_core.google_service_networking_connection.alloydb_psa_connection" \
      -target="module.platform_core.google_alloydb_cluster.pooled_rls_cluster" \
      -target="module.platform_core.google_alloydb_instance.pooled_rls_primary" \
      -target="module.platform_core.google_service_account.pooled_agent_runtime" \
      -target="module.platform_core.google_alloydb_user.runtime_iam_db_user" \
      -target="module.platform_core.google_alloydb_user.operator_iam_admins" \
      -target="module.platform_core.google_project_iam_member.operator_alloydb_client" \
      -target="module.platform_core.google_project_iam_member.operator_alloydb_db_user" \
      -var="project_id=$PROJECT_ID" \
      -var="region=$REGION" \
      -var="platform_environment=$ENV_NAME"
    _run_alloydb_rls_bootstrap runtime-only
  fi
  terraform -chdir=terraform apply $APPROVE ${TF_VAR_FILE_ARGS[@]+"${TF_VAR_FILE_ARGS[@]}"} ${SIGNING_SECRET_TF_VAR_ARGS[@]+"${SIGNING_SECRET_TF_VAR_ARGS[@]}"} ${IMAGE_VAR_ARGS[@]+"${IMAGE_VAR_ARGS[@]}"} ${AGENT_SANDBOX_TF_VAR_ARGS[@]+"${AGENT_SANDBOX_TF_VAR_ARGS[@]}"} \
    -var="project_id=$PROJECT_ID" \
    -var="region=$REGION" \
    -var="platform_environment=$ENV_NAME"
  _sync_agent_runtime_live_wiring
  if [[ "$PROVISION_SANDBOX" == 1 && -z "$AGENT_SANDBOX_REASONING_ENGINE_NAME_VAL" ]]; then
    echo "==> Provisioning agent runtime in Gemini for per-session sandboxes & Memory Bank..."
    AGENT_SANDBOX_JSON="$(uv run --frozen python scripts/provision_gemini_agent_sandbox.py --live --use-gcloud-auth --project-id "$PROJECT_ID" --location "$REGION")"
    AGENT_SANDBOX_REASONING_ENGINE_NAME_VAL="$(
      python3 - "$AGENT_SANDBOX_JSON" <<'PYEOF'
import json, sys
print(json.loads(sys.argv[1]).get("agent_sandbox_reasoning_engine_name", ""))
PYEOF
    )"
    if [[ -n "$AGENT_SANDBOX_REASONING_ENGINE_NAME_VAL" ]]; then
      echo "    Provisioned Gemini ReasoningEngine: $AGENT_SANDBOX_REASONING_ENGINE_NAME_VAL"
      AGENT_SANDBOX_TF_VAR_ARGS+=(-var="agent_sandbox_reasoning_engine_name=${AGENT_SANDBOX_REASONING_ENGINE_NAME_VAL}")
      AGENT_SANDBOX_UPDATE_ENV_CSV="${AGENT_SANDBOX_UPDATE_ENV_CSV:+${AGENT_SANDBOX_UPDATE_ENV_CSV},}AGENT_SANDBOX_REASONING_ENGINE_NAME=${AGENT_SANDBOX_REASONING_ENGINE_NAME_VAL}"
      AGENT_SANDBOX_REMOVE_ENV_CSV="$(
        python3 - "$AGENT_SANDBOX_REMOVE_ENV_CSV" <<'PYEOF'
import sys
print(",".join(k for k in sys.argv[1].split(",") if k and k != "AGENT_SANDBOX_REASONING_ENGINE_NAME"))
PYEOF
      )"
      terraform -chdir=terraform apply $APPROVE ${TF_VAR_FILE_ARGS[@]+"${TF_VAR_FILE_ARGS[@]}"} ${SIGNING_SECRET_TF_VAR_ARGS[@]+"${SIGNING_SECRET_TF_VAR_ARGS[@]}"} ${IMAGE_VAR_ARGS[@]+"${IMAGE_VAR_ARGS[@]}"} ${AGENT_SANDBOX_TF_VAR_ARGS[@]+"${AGENT_SANDBOX_TF_VAR_ARGS[@]}"} \
        -var="project_id=$PROJECT_ID" \
        -var="region=$REGION" \
        -var="platform_environment=$ENV_NAME"
      _sync_agent_runtime_live_wiring
    fi
  fi
  if [[ "$AGENT_LIVE_GCP_FLAG" == "1" && "$SKIP_DB_BOOTSTRAP" == 0 ]]; then
    _run_alloydb_rls_bootstrap
  fi
  echo "==> Verifying Cloud KMS context-signing key readiness (if caller holds signerVerifier)"
  uv run --frozen python scripts/preflight_context_signing.py ||
    echo "    NOTE: To run preflight locally, impersonate cymbal-pooled-runtime-sa@${PROJECT_ID}.iam.gserviceaccount.com or grant your user roles/cloudkms.signerVerifier on ws2-context-signing."
else
  echo "==> [2/4] skipped (infra)"
fi

if [[ "$SKIP_IMAGE" == 0 ]]; then
  echo "==> [3/4] Building and rolling the gateway image (identity and env stay owned by Terraform)"
  BUILD_ARGS=()
  if gcloud iam service-accounts describe "cymbal-build-sa@${PROJECT_ID}.iam.gserviceaccount.com" --project="$PROJECT_ID" >/dev/null 2>&1; then
    BUILD_ARGS+=(--build-service-account="projects/${PROJECT_ID}/serviceAccounts/cymbal-build-sa@${PROJECT_ID}.iam.gserviceaccount.com")
  fi
  gcloud run deploy "$SERVICE" --source=. --region="$REGION" --project="$PROJECT_ID" --quiet ${BUILD_ARGS[@]+"${BUILD_ARGS[@]}"}
  BUILT_IMAGE="$(gcloud run services describe "$SERVICE" --region="$REGION" --project="$PROJECT_ID" --format='value(spec.template.spec.containers[0].image)')"
  for DISAGG_SVC in cymbal-credential-broker cymbal-agent-shared cymbal-agent-finvault-alpha; do
    if gcloud run services describe "$DISAGG_SVC" --region="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
      echo "    Rolling built image ($BUILT_IMAGE) to disaggregated service: $DISAGG_SVC"
      ENV_UPDATE_ARGS=()
      if [[ "$DISAGG_SVC" != "cymbal-credential-broker" ]]; then
        [[ -n "$AGENT_SANDBOX_REMOVE_ENV_CSV" ]] && ENV_UPDATE_ARGS+=(--remove-env-vars="$AGENT_SANDBOX_REMOVE_ENV_CSV")
        [[ -n "$AGENT_SANDBOX_UPDATE_ENV_CSV" ]] && ENV_UPDATE_ARGS+=(--update-env-vars="$AGENT_SANDBOX_UPDATE_ENV_CSV")
      fi
      gcloud alpha run services update "$DISAGG_SVC" --image="$BUILT_IMAGE" --region="$REGION" --project="$PROJECT_ID" --quiet ${ENV_UPDATE_ARGS[@]+"${ENV_UPDATE_ARGS[@]}"}
    fi
  done
else
  echo "==> [3/4] skipped (image)"
fi

if [[ "$SKIP_SMOKE" == 0 ]]; then
  echo "==> [4/4] Tier 3 smoke checks"
  uv run --frozen python scripts/verify_cloud_run_deployment.py --env "$ENV_NAME"
else
  echo "==> [4/4] skipped (smoke)"
fi
echo "==> Deploy of '$ENV_NAME' complete."
