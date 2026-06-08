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

# Removed public IP output as VM is private

output "oracle_db_private_ip" {
  value       = module.compute.oracle_db_private_ip
  description = "Internal IP address of the Oracle DB VM Instance"
}

output "gcs_bucket_name" {
  value       = local.bucket_name
  description = "The GCS staging bucket name configured or fetched"
}

output "db_password_secret_id" {
  value       = google_secret_manager_secret.db_password_secret.id
  description = "The resource ID identifier of the database password Secret container"
}

output "oracle_db_zone" {
  value       = var.zone
  description = "The Google Cloud Zone where the Oracle database virtual machine is hosted"
}
