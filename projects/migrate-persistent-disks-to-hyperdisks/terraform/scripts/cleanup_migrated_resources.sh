#!/usr/bin/env bash
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

set -o errexit
set -o nounset
set -o pipefail

readonly PROJECT_ID="$1"
readonly ZONE="$2"
readonly NAME_PREFIX="$3"
readonly REGION="${ZONE%-*}"

if [[ ! "${NAME_PREFIX}" =~ ^[a-z][a-z0-9-]{2,20}[a-z0-9]$ ]]; then
  echo "ERROR: Invalid NAME_PREFIX '${NAME_PREFIX}'." >&2
  exit 1
fi

if ! command -v gcloud >/dev/null 2>&1; then
  echo "gcloud CLI not found; skipping out-of-band migration resource cleanup."
  exit 0
fi

INSTANCE_NAMES="$(gcloud compute instances list \
  --quiet \
  --project="${PROJECT_ID}" \
  --zones="${ZONE}" \
  --filter="name ~ ^${NAME_PREFIX}-" \
  --format="value(name)")"

if [[ -n "${INSTANCE_NAMES}" ]]; then
  readarray -t instances <<<"${INSTANCE_NAMES}"
  gcloud compute instances delete "${instances[@]}" \
    --quiet \
    --project="${PROJECT_ID}" \
    --zone="${ZONE}"
fi

ADDRESS_NAMES="$(gcloud compute addresses list \
  --quiet \
  --project="${PROJECT_ID}" \
  --regions="${REGION}" \
  --filter="name ~ ^${NAME_PREFIX}-" \
  --format="value(name)")"

if [[ -n "${ADDRESS_NAMES}" ]]; then
  readarray -t addresses <<<"${ADDRESS_NAMES}"
  gcloud compute addresses delete "${addresses[@]}" \
    --quiet \
    --project="${PROJECT_ID}" \
    --region="${REGION}"
fi

DISK_NAMES="$(gcloud compute disks list \
  --quiet \
  --project="${PROJECT_ID}" \
  --zones="${ZONE}" \
  --filter="name ~ ^${NAME_PREFIX}-" \
  --format="value(name)")"

if [[ -n "${DISK_NAMES}" ]]; then
  readarray -t disks <<<"${DISK_NAMES}"
  gcloud compute disks delete "${disks[@]}" \
    --quiet \
    --project="${PROJECT_ID}" \
    --zone="${ZONE}"
fi

SNAPSHOT_NAMES="$(gcloud compute snapshots list \
  --quiet \
  --project="${PROJECT_ID}" \
  --filter="name ~ ^${NAME_PREFIX}- OR sourceDisk ~ /disks/${NAME_PREFIX}-" \
  --format="value(name)")"

if [[ -n "${SNAPSHOT_NAMES}" ]]; then
  readarray -t snapshots <<<"${SNAPSHOT_NAMES}"
  gcloud compute snapshots delete "${snapshots[@]}" \
    --quiet \
    --project="${PROJECT_ID}"
fi
