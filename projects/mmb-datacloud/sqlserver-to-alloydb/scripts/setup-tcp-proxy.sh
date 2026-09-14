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

set -euo pipefail

exec > >(tee -i /var/log/tcp-proxy-startup.log) 2>&1

echo "Starting TCP Proxy setup script..."

MD_URL_PREFIX="http://metadata.google.internal/computeMetadata/v1"
SQL_SERVER_IP="$(curl -fsSL -H "Metadata-Flavor: Google" "${MD_URL_PREFIX}/instance/attributes/SQL_SERVER_IP")"
VM_NIC_IP="$(curl -fsSL -H "Metadata-Flavor: Google" "${MD_URL_PREFIX}/instance/network-interfaces/0/ip")"

echo "Configuring IP forwarding and iptables NAT..."

echo 1 >/proc/sys/net/ipv4/ip_forward
sysctl -w net.ipv4.ip_forward=1

iptables -t nat -F

# Forward TCP 1433 to Cloud SQL for SQL Server (in vpc-1 PSA)
echo "Forwarding TCP 1433 -> ${SQL_SERVER_IP}:1433"
iptables -t nat -A PREROUTING \
  -p tcp --dport 1433 \
  -j DNAT \
  --to-destination "${SQL_SERVER_IP}:1433"

iptables -t nat -A POSTROUTING \
  -p tcp -d "${SQL_SERVER_IP}" --dport 1433 \
  -j SNAT \
  --to-source "${VM_NIC_IP}"

# Ensure Database Migration Service (DMS) Service Agent (P4SA) is provisioned
PROJECT_ID="$(curl -fsSL -H "Metadata-Flavor: Google" "${MD_URL_PREFIX}/project/project-id")"
ACCESS_TOKEN="$(curl -fsSL -H "Metadata-Flavor: Google" "${MD_URL_PREFIX}/instance/service-accounts/default/token" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')"
if [ -n "${PROJECT_ID}" ] && [ -n "${ACCESS_TOKEN}" ]; then
  echo "Ensuring DMS Service Identity (P4SA) exists for project ${PROJECT_ID}..."
  # Best-effort initialization; ignore errors if the identity already exists or lacks permission.
  curl -fsSL -X POST \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "Content-Type: application/json" \
    "https://serviceusage.googleapis.com/v1beta1/projects/${PROJECT_ID}/services/datamigration.googleapis.com:generateServiceIdentity" >/dev/null || true
fi

echo "TCP Proxy setup completed successfully."
