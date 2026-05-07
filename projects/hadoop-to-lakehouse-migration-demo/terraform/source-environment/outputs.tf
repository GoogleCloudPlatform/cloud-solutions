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

output "cluster_name" {
  value = google_dataproc_cluster.legacy_hadoop.name
}

output "cluster_region" {
  value = google_dataproc_cluster.legacy_hadoop.region
}

output "cluster_zone" {
  value = var.zone
}

output "project_id" {
  value = var.source_project_id
}

output "staging_bucket" {
  value = google_storage_bucket.staging.name
}
