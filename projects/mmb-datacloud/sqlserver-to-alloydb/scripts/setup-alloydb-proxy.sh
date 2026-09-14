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

exec > >(tee -i /var/log/alloydb-proxy-startup.log) 2>&1

echo "Starting AlloyDB database initialization script..."

MD_URL_PREFIX="http://metadata.google.internal/computeMetadata/v1"
ALLOYDB_IP="$(curl -fsSL -H "Metadata-Flavor: Google" "${MD_URL_PREFIX}/instance/attributes/ALLOYDB_IP")"
ALLOYDB_PASSWORD="$(curl -fsSL -H "Metadata-Flavor: Google" "${MD_URL_PREFIX}/instance/attributes/ALLOYDB_PASSWORD")"

echo "Installing postgresql-client to initialize thelook_ecommerce database on AlloyDB..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y postgresql-client

echo "Waiting for AlloyDB at ${ALLOYDB_IP}:5432 to become ready..."
for i in {1..60}; do
  if PGPASSWORD="${ALLOYDB_PASSWORD}" psql -h "${ALLOYDB_IP}" -U postgres -d postgres -c "SELECT 1;" >/dev/null 2>&1; then
    echo "AlloyDB is ready!"
    break
  fi
  echo "Attempt ${i}: AlloyDB not ready yet, sleeping 10s..."
  sleep 10
done

echo "Creating database thelook_ecommerce if it does not exist..."
PGPASSWORD="${ALLOYDB_PASSWORD}" psql -h "${ALLOYDB_IP}" -U postgres -d postgres -tc "SELECT 1 FROM pg_database WHERE datname = 'thelook_ecommerce'" | grep -q 1 ||
  PGPASSWORD="${ALLOYDB_PASSWORD}" psql -h "${ALLOYDB_IP}" -U postgres -d postgres -c "CREATE DATABASE thelook_ecommerce;"

echo "AlloyDB Proxy and database initialization completed successfully."
