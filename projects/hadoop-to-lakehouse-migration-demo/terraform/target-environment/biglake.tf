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

# Create BigLake Iceberg Catalog using native Terraform resource
resource "google_biglake_iceberg_catalog" "silver_catalog" {
  name             = google_storage_bucket.silver.name
  project          = data.google_project.target_project.project_id
  primary_location = var.region
  catalog_type     = "CATALOG_TYPE_GCS_BUCKET"
  credential_mode  = "CREDENTIAL_MODE_END_USER"

  depends_on = [
    google_storage_bucket.silver
  ]
}

resource "google_project_iam_member" "dataproc_biglake_editor" {
  project = data.google_project.target_project.project_id
  role    = "roles/biglake.editor"
  member  = "serviceAccount:${google_service_account.dataproc_sa.email}"
}
