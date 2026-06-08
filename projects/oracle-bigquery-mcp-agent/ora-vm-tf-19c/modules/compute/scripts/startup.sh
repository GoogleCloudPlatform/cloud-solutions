#!/bin/bash

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

set -e
echo "=== Starting Google Cloud GCE VM Startup Bootstrap ==="

# Queries the dynamic guest VM metadata instance attributes to retrieve the staging bucket name dynamically, enabling environment portability.
gcs_bucket_name=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/gcs_bucket_name")

# Queries the dynamic guest VM metadata instance attributes to retrieve the Oracle 19c RPM package name dynamically.
rpm_name=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/rpm_name")

# Enables the pre-installed local package manager repo configuration to authorize direct DNF package installs of Google Cloud SRE CLI utilities.
sed -i '/\[google-cloud-sdk\]/,/enabled=/ s/enabled=0/enabled=1/' /etc/yum.repos.d/google-cloud.repo

# Installs the Google Cloud SDK package natively, providing the 'gcloud storage' command required for secure private GCS artifact pulls.
dnf install -y google-cloud-cli

# Copies pre-staged provisioning shell scripts and PL/SQL schema files from GCS to host local execution.
mkdir -p /tmp/oracle_bootstrap
gcloud storage cp gs://"${gcs_bucket_name}"/ora-setup.sh /tmp/oracle_bootstrap/ora-setup.sh
gcloud storage cp gs://"${gcs_bucket_name}"/app_seed.sh /tmp/oracle_bootstrap/app_seed.sh
gcloud storage cp gs://"${gcs_bucket_name}"/app_setup.sql /tmp/oracle_bootstrap/app_setup.sql
gcloud storage cp gs://"${gcs_bucket_name}"/seed_primary.sql /tmp/oracle_bootstrap/seed_primary.sql

# Invokes the primary installer script, passing the staging GCS bucket name and target Oracle RPM filename dynamically.
chmod +x /tmp/oracle_bootstrap/ora-setup.sh
BUCKET="${gcs_bucket_name}" RPM_NAME="${rpm_name}" /tmp/oracle_bootstrap/ora-setup.sh

# Stages database seeding assets in the /tmp directory, matching standard execution paths of SQL*Plus heredocs.
cp /tmp/oracle_bootstrap/seed_primary.sql /tmp/seed_primary.sql
cp /tmp/oracle_bootstrap/app_setup.sql /tmp/app_setup.sql
chown oracle:oinstall /tmp/seed_primary.sql /tmp/app_setup.sql

# Runs the data seeding script strictly under the 'oracle' OS user, ensuring correct file ownership and Oracle environment variables.
echo "Executing Seeding Orchestrator as oracle user..."
chmod +x /tmp/oracle_bootstrap/app_seed.sh
sudo -u oracle bash -c "/tmp/oracle_bootstrap/app_seed.sh"

# Pauses execution to allow dynamic database registration to complete, preventing TNS ORA-12514 connection race conditions on cold boots.
echo "Waiting 45s for dynamic TNS service registration..."
sleep 45

# Writes a completed sentinel record to disk, enabling serverless VPC connector loops to privately poll and verify database readiness.
echo "ORACLE BOOTSTRAP AND DATA SEEDING SUCCESSFULLY COMPLETED!" >/var/log/oracle-bootstrap-completed
