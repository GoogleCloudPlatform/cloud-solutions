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

readonly METADATA_DISKS_URL="http://metadata.google.internal/computeMetadata/v1/instance/disks/?recursive=true"

initialize_data_disk() {
  local device_name="$1"
  local mount_point="$2"
  local fs_label="$3"
  local device_symlink="/dev/disk/by-id/google-${device_name}"
  local seed_marker="${mount_point}/.dataset-initialized"
  local checksum_file="${mount_point}/checksums.sha256"
  local disk_uuid=""

  # Wait up to 60 seconds for udev to create the persistent Google disk symlink.
  # This symlink resolves to /dev/sd* on Gen2 SCSI instances and /dev/nvme*n* on
  # Gen4 NVMe instances without hardcoding bus-specific device names.
  for _ in $(seq 1 30); do
    if [[ -b "${device_symlink}" ]]; then
      break
    fi
    udevadm settle || true # Ignore transient udevadm errors while devices attach.
    sleep 2
  done

  if [[ ! -b "${device_symlink}" ]]; then
    echo "ERROR: Expected block device symlink ${device_symlink} not found." >&2
    exit 1
  fi

  # Format the volume only when blkid detects no existing filesystem signature
  # so subsequent boots (including first boot after Hyperdisk snapshot restore)
  # never overwrite existing data.
  if ! blkid -p -u filesystem "${device_symlink}" >/dev/null 2>&1; then
    mkfs.ext4 -m 0 -E lazy_itable_init=0,lazy_journal_init=0,discard -L "${fs_label}" "${device_symlink}"
    udevadm trigger
    udevadm settle
  fi

  disk_uuid="$(blkid -s UUID -o value "${device_symlink}")"
  if [[ -z "${disk_uuid}" ]]; then
    echo "ERROR: Unable to read filesystem UUID from ${device_symlink}." >&2
    exit 1
  fi

  mkdir -p "${mount_point}"

  # Persist a UUID-based fstab entry with nofail so Gen4 NVMe boots never block
  # on legacy /dev/sd* paths.
  if ! grep -q "UUID=${disk_uuid}" /etc/fstab; then
    echo "UUID=${disk_uuid} ${mount_point} ext4 defaults,discard,nofail 0 2" >>/etc/fstab
  fi

  if ! findmnt -rn -M "${mount_point}" >/dev/null 2>&1; then
    mount "${mount_point}"
  fi

  # Seed a persistent sample dataset once on initial provisioning so pre- and
  # post-cutover SHA-256 verification can confirm block-level integrity.
  if [[ ! -f "${seed_marker}" ]]; then
    mkdir -p "${mount_point}/records"
    for index in 01 02 03; do
      dd if=/dev/urandom of="${mount_point}/records/chunk-${index}.bin" bs=1M count=8 status=none
    done
    cat <<EOF >"${mount_point}/records/metadata.json"
{
  "dataset": "pd-to-hyperdisk-demo",
  "device_name": "${device_name}",
  "mount_point": "${mount_point}",
  "filesystem_uuid": "${disk_uuid}"
}
EOF
    (
      pushd "${mount_point}" >/dev/null
      sha256sum \
        records/chunk-01.bin \
        records/chunk-02.bin \
        records/chunk-03.bin \
        records/metadata.json >"${checksum_file}"
      popd >/dev/null
    )
    date -u +"%Y-%m-%dT%H:%M:%SZ" >"${seed_marker}"
    sync
  fi
}

ATTACHED_DISKS_JSON="$(curl --fail -sS --retry 5 --retry-delay 2 --retry-all-errors -H "Metadata-Flavor: Google" "${METADATA_DISKS_URL}")"

initialize_data_disk "app-data" "/mnt/app-data" "app-data"

if grep -Eq '"deviceName":[[:space:]]*"db-wal"' <<<"${ATTACHED_DISKS_JSON}"; then
  initialize_data_disk "db-wal" "/mnt/db-wal" "db-wal"
fi

if grep -Eq '"deviceName":[[:space:]]*"analytics-spool"' <<<"${ATTACHED_DISKS_JSON}"; then
  initialize_data_disk "analytics-spool" "/mnt/analytics-spool" "analytics-spool"
fi
