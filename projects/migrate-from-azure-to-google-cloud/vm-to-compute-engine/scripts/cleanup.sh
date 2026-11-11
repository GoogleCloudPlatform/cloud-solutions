#!/bin/bash
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Tears down Google Cloud and Azure resources created by the VM migration demo,
# including Migrate to Virtual Machines migrations, the Azure source, and any
# leftover Azure snapshot resource group.

set -o errexit
set -o nounset
set -o pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
DEMO_DIR="$(dirname -- "${SCRIPT_DIR}")"
readonly DEMO_DIR

if [[ ! -f "${DEMO_DIR}/temp/demo.env" ]]; then
  echo "Error: ${DEMO_DIR}/temp/demo.env not found." >&2
  exit 1
fi

# shellcheck source=/dev/null
source "${DEMO_DIR}/temp/demo.env"

gcloud auth print-access-token >/dev/null
az account show --subscription "${AZURE_SUBSCRIPTION_ID}" >/dev/null

wait_vmmigration_op() {
  local op_name="$1"
  local op_json
  local failures=0
  while true; do
    if ! op_json="$(curl --silent --fail \
      --header "Authorization: Bearer $(gcloud auth print-access-token)" \
      --header "x-goog-user-project: ${GOOGLE_CLOUD_PROJECT_ID}" \
      "https://vmmigration.googleapis.com/v1/${op_name}")"; then
      failures=$((failures + 1))
      if ((failures >= 6)); then
        echo "Error: Failed to poll VM Migration operation ${op_name}." >&2
        return 1
      fi
      sleep 5
      continue
    fi
    failures=0
    if [[ "$(jq -r '.done // false' <<<"${op_json}")" == "true" ]]; then
      if [[ "$(jq -r 'has("error")' <<<"${op_json}")" == "true" ]]; then
        echo "VM Migration operation failed: $(jq -c '.error' <<<"${op_json}")" >&2
        return 1
      fi
      return 0
    fi
    sleep 5
  done
}

for vm in "vm-demo-app" "vm-demo-clone"; do
  if gcloud compute instances describe "${vm}" --zone="${ZONE}" --project="${GOOGLE_CLOUD_PROJECT_ID}" >/dev/null 2>&1; then
    gcloud compute instances delete "${vm}" --zone="${ZONE}" --project="${GOOGLE_CLOUD_PROJECT_ID}" --delete-disks=all --quiet
  fi
done

vmm_base="https://vmmigration.googleapis.com/v1"
source_path="projects/${GOOGLE_CLOUD_PROJECT_ID}/locations/${REGION}/sources/vm-demo-azure"
m2vm_rg=""
source_json=""

if [[ "$(gcloud services list --enabled --project="${GOOGLE_CLOUD_PROJECT_ID}" --filter="config.name=vmmigration.googleapis.com" --format="value(config.name)")" == "vmmigration.googleapis.com" ]]; then
  source_tmp="$(mktemp)"
  trap 'rm -f "${source_tmp}"' EXIT
  http_code="$(curl --silent --output "${source_tmp}" --write-out '%{http_code}' \
    --header "Authorization: Bearer $(gcloud auth print-access-token)" \
    --header "x-goog-user-project: ${GOOGLE_CLOUD_PROJECT_ID}" \
    "${vmm_base}/${source_path}")"
  if [[ "${http_code}" == "200" ]]; then
    source_json="$(cat "${source_tmp}")"
  elif [[ "${http_code}" != "404" ]]; then
    echo "Error: Failed to query Azure source ${source_path} (HTTP ${http_code}): $(cat "${source_tmp}")" >&2
    exit 1
  fi
fi

if [[ -n "${source_json}" ]]; then
  m2vm_rg="$(jq -r '.azure.resourceGroupId // empty | split("/") | last' <<<"${source_json}")"

  vms_json="$(curl --silent --fail \
    --header "Authorization: Bearer $(gcloud auth print-access-token)" \
    --header "x-goog-user-project: ${GOOGLE_CLOUD_PROJECT_ID}" \
    "${vmm_base}/${source_path}/migratingVms")"

  while IFS=$'\t' read -r vm_name vm_state; do
    [[ -z "${vm_name}" ]] && continue
    if [[ "${vm_state}" == "ACTIVE" || "${vm_state}" == "SYNCING" ]]; then
      pause_op="$(curl --silent --fail --request POST \
        --header "Authorization: Bearer $(gcloud auth print-access-token)" \
        --header "x-goog-user-project: ${GOOGLE_CLOUD_PROJECT_ID}" \
        "${vmm_base}/${vm_name}:pauseMigration" | jq -r '.name // empty')"
      if [[ -n "${pause_op}" ]]; then
        wait_vmmigration_op "${pause_op}"
      fi
    fi
    op_name="$(curl --silent --fail --request DELETE \
      --header "Authorization: Bearer $(gcloud auth print-access-token)" \
      --header "x-goog-user-project: ${GOOGLE_CLOUD_PROJECT_ID}" \
      "${vmm_base}/${vm_name}" | jq -r '.name // empty')"
    if [[ -n "${op_name}" ]]; then
      wait_vmmigration_op "${op_name}"
    fi
  done < <(jq -r '.migratingVms[]? | [.name, (.state // "")] | @tsv' <<<"${vms_json}")

  op_name="$(curl --silent --fail --request DELETE \
    --header "Authorization: Bearer $(gcloud auth print-access-token)" \
    --header "x-goog-user-project: ${GOOGLE_CLOUD_PROJECT_ID}" \
    "${vmm_base}/${source_path}" | jq -r '.name // empty')"
  if [[ -n "${op_name}" ]]; then
    wait_vmmigration_op "${op_name}"
  fi
fi

for output in discovery_client_id m2vm_client_id; do
  # Ignore missing outputs if terraform/azure was already destroyed.
  app_id="$(terraform -chdir="${DEMO_DIR}/terraform/azure" output -raw "${output}" 2>/dev/null || true)"
  if [[ -n "${app_id}" ]]; then
    # Ignore missing app registrations if already deleted outside Terraform.
    while IFS= read -r key_id; do
      [[ -z "${key_id}" ]] && continue
      az ad app credential delete --id "${app_id}" --key-id "${key_id}"
    done < <(az ad app credential list --id "${app_id}" --query "[].keyId" --output tsv 2>/dev/null || true)
  fi
done

# Continue cleanup if Cloud Shell is disabled by organization policy or unreachable.
if ! gcloud cloud-shell ssh --authorize-session --quiet --command="rm -rf ~/vm-demo-mcdc"; then
  echo "Warning: Failed to remove ~/vm-demo-mcdc in Cloud Shell." >&2
fi

if [[ -f "${DEMO_DIR}/terraform/gcp/terraform.tfstate" ]]; then
  terraform -chdir="${DEMO_DIR}/terraform/gcp" destroy -auto-approve
fi

if gcloud compute ssl-certificates describe "vm-demo-lb-cert" --global --project="${GOOGLE_CLOUD_PROJECT_ID}" >/dev/null 2>&1; then
  gcloud compute ssl-certificates delete "vm-demo-lb-cert" --global --project="${GOOGLE_CLOUD_PROJECT_ID}" --quiet
fi

while IFS= read -r snapshot; do
  [[ -z "${snapshot}" ]] && continue
  gcloud compute snapshots delete "${snapshot}" --project="${GOOGLE_CLOUD_PROJECT_ID}" --quiet
done < <(gcloud compute snapshots list --project="${GOOGLE_CLOUD_PROJECT_ID}" --filter="sourceSnapshotSchedulePolicy~resourcePolicies/vm-demo-daily" --format="value(name)")

if gcloud compute resource-policies describe "vm-demo-daily" --region="${REGION}" --project="${GOOGLE_CLOUD_PROJECT_ID}" >/dev/null 2>&1; then
  gcloud compute resource-policies delete "vm-demo-daily" --region="${REGION}" --project="${GOOGLE_CLOUD_PROJECT_ID}" --quiet
fi

if [[ -f "${DEMO_DIR}/terraform/azure/terraform.tfstate" ]]; then
  if ! terraform -chdir="${DEMO_DIR}/terraform/azure" destroy -auto-approve; then
    echo "Waiting 15s for Azure role-assignment deletions to propagate before retrying..."
    sleep 15
    terraform -chdir="${DEMO_DIR}/terraform/azure" destroy -auto-approve
  fi
fi

if [[ -n "${m2vm_rg}" ]]; then
  if [[ "$(az group exists --subscription "${AZURE_SUBSCRIPTION_ID}" --name "${m2vm_rg}")" == "true" ]]; then
    az group delete --subscription "${AZURE_SUBSCRIPTION_ID}" --name "${m2vm_rg}" --yes
  fi
fi
