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

output "dataproc_cluster_name" {
  value       = google_dataproc_cluster.managed_spark.name
  description = "The name of the Dataproc cluster."
}

output "bucket_name" {
  value       = google_storage_bucket.detox_bucket.name
  description = "The name of the GCS bucket."
}

output "predict_job_gcs_path" {
  value       = "gs://${google_storage_bucket.detox_bucket.name}/predict_job.py"
  description = "The GCS path to the prediction job script."
}

output "project_id" {
  value = var.project_id
}

output "region" {
  value = var.region
}
