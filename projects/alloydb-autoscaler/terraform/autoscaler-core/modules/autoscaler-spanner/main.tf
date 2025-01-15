/**
 * Copyright 2024 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

resource "google_spanner_instance" "state_spanner_instance" {
  count = var.terraform_spanner_state ? 1 : 0

  name         = var.spanner_state_name
  config       = "regional-${var.region}"
  display_name = var.spanner_state_name
  project      = var.project_id

  processing_units = var.spanner_state_processing_units
}

resource "google_spanner_database" "state_database" {
  count = var.terraform_spanner_state ? 1 : 0

  instance = var.spanner_state_name
  name     = var.spanner_state_database
  ddl = [
    <<EOT
    CREATE TABLE ${var.spanner_state_table} (
      id STRING(MAX),
      lastScalingTimestamp TIMESTAMP,
      createdOn TIMESTAMP,
      updatedOn TIMESTAMP,
      lastScalingCompleteTimestamp TIMESTAMP,
      scalingOperationId STRING(MAX),
      scalingRequestedSize INT64,
      scalingMethod STRING(MAX),
      scalingPreviousSize INT64,
    ) PRIMARY KEY (id)
    EOT
  ]
  # Must specify project because provider project may be different than var.project_id
  project = var.project_id

  depends_on          = [google_spanner_instance.state_spanner_instance]
  deletion_protection = false
}

# Allows scaler to read/write the state from/in Spanner
resource "google_spanner_instance_iam_member" "spanner_state_user" {
  count = var.terraform_spanner_state ? 1 : 0

  instance = var.spanner_state_name
  role     = "roles/spanner.databaseUser"
  project  = var.project_id
  member   = "serviceAccount:${var.scaler_sa_email}"

  depends_on = [google_spanner_instance.state_spanner_instance]
}
