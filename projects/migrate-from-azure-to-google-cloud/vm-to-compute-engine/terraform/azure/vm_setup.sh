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

# First-boot setup for the source Azure VM: mounts the data disk at /data by
# UUID, stores Docker data on it, runs the ASP.NET Core sample container on
# port 80, records each boot in /data/evidence/boots.log, and disables
# cloud-init for future boots on Compute Engine.

set -o errexit
set -o nounset
set -o pipefail

readonly APP_IMAGE="mcr.microsoft.com/dotnet/samples:aspnetapp-10.0@sha256:aacefb8b6fc1fc743531d518ebd9b3849ae3223f9de3e642ebcc0d3e5921cd66"
readonly DATA_DIR="/data"

# Wait for the LUN 0 data disk symlink and mount it by UUID so fstab still
# works after migrating to Compute Engine.
device=""
for _ in $(seq 1 60); do
  for candidate in /dev/disk/azure/scsi1/lun0 /dev/disk/azure/data/by-lun/0; do
    if [[ -e "${candidate}" ]]; then
      device="$(readlink -f "${candidate}")"
      break 2
    fi
  done
  sleep 5
done
if [[ -z "${device}" ]]; then
  echo "Data disk not found at LUN 0." >&2
  exit 1
fi

if ! blkid "${device}" >/dev/null 2>&1; then
  mkfs.ext4 -L appdata "${device}"
fi
uuid="$(blkid -s UUID -o value "${device}")"
if [[ -z "${uuid}" ]]; then
  echo "Failed to read filesystem UUID for ${device}." >&2
  exit 1
fi
install -d -m 0755 "${DATA_DIR}"
grep -q "^UUID=${uuid} " /etc/fstab || echo "UUID=${uuid} ${DATA_DIR} ext4 defaults,nofail 0 2" >>/etc/fstab
mountpoint -q "${DATA_DIR}" || mount "${DATA_DIR}"

# Store Docker data on /data and require /data to mount before Docker starts.
install -d -m 0755 /etc/docker /etc/systemd/system/docker.service.d
cat >/etc/docker/daemon.json <<EOF
{
  "data-root": "${DATA_DIR}/docker",
  "log-driver": "journald",
  "features": { "containerd-snapshotter": false }
}
EOF
cat >/etc/systemd/system/docker.service.d/data-disk.conf <<EOF
[Unit]
RequiresMountsFor=${DATA_DIR}
EOF
systemctl daemon-reload

# Disable unattended upgrades so test clones and cut-over match the source.
cat >/etc/apt/apt.conf.d/20auto-upgrades <<EOF
APT::Periodic::Update-Package-Lists "0";
APT::Periodic::Unattended-Upgrade "0";
EOF

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install --yes --no-install-recommends \
  -o Dpkg::Options::=--force-confdef \
  -o Dpkg::Options::=--force-confold \
  curl docker.io

docker pull "${APP_IMAGE}"

# The "-" prefix of ExecStartPre lets the unit start when no stale sample-app
# container exists.
cat >/etc/systemd/system/sample-app.service <<EOF
[Unit]
Description=ASP.NET Core sample app
Requires=docker.service
After=docker.service

[Service]
ExecStartPre=-/usr/bin/docker rm --force sample-app
ExecStart=/usr/bin/docker run --rm --name sample-app --hostname %H --publish 80:8080 --cap-drop ALL --security-opt no-new-privileges ${APP_IMAGE}
ExecStop=/usr/bin/docker stop sample-app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Record each boot on /data so boots.log proves Azure then Compute Engine boots.
install -d -m 0755 "${DATA_DIR}/evidence"
cat >/usr/local/sbin/record-boot <<'EOF'
#!/bin/bash
set -o errexit
set -o nounset
set -o pipefail

firmware="BIOS"
[[ -d /sys/firmware/efi ]] && firmware="UEFI"
printf '%s host=%s vendor="%s" product="%s" firmware=%s kernel=%s\n' \
  "$(date --utc +%Y-%m-%dT%H:%M:%SZ)" "$(hostname)" \
  "$(cat /sys/class/dmi/id/sys_vendor)" \
  "$(cat /sys/class/dmi/id/product_name)" \
  "${firmware}" "$(uname -r)" >>/data/evidence/boots.log
if [[ -c /dev/ttyS0 ]]; then
  # Ignore EIO errors when no serial console receiver is attached.
  sed 's/^/record-boot: /' /data/evidence/boots.log >/dev/ttyS0 2>/dev/null || true
fi
EOF
chmod 0755 /usr/local/sbin/record-boot

cat >/etc/systemd/system/record-boot.service <<EOF
[Unit]
Description=Record this boot on the data disk
RequiresMountsFor=${DATA_DIR}
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/record-boot

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now record-boot.service sample-app.service

for _ in $(seq 1 60); do
  curl --fail --silent http://localhost/healthz >/dev/null && break
  sleep 5
done
curl --fail --silent --show-error http://localhost/healthz
echo

touch /etc/cloud/cloud-init.disabled
