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

# =============================================================================
# Cloud Bigtable Operational Database
# =============================================================================

resource "google_bigtable_instance" "aegis_bigtable" {
  name                = local.bigtable_instance_id
  project             = var.project_id
  deletion_protection = false

  cluster {
    cluster_id   = "${local.bigtable_instance_id}-cluster"
    zone         = var.zone
    num_nodes    = 1
    storage_type = "SSD"
  }

  lifecycle {
    prevent_destroy = false
  }

  depends_on = [google_project_service.enabled_apis]
}

resource "google_bigtable_table" "telemetry_metrics" {
  name                = "telemetry_metrics"
  instance_name       = google_bigtable_instance.aegis_bigtable.name
  project             = var.project_id
  deletion_protection = "UNPROTECTED"

  column_family {
    family = "metrics"
  }
}
