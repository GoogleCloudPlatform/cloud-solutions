# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

resource "google_vertex_ai_endpoint_with_model_garden_deployment" "timesfm_deployment" {
  location             = var.region
  publisher_model_name = "publishers/google/models/timesfm@timesfm-v2"

  model_config {
    accept_eula = true
  }

  deploy_config {
    dedicated_resources {
      machine_spec {
        machine_type      = "g2-standard-8"
        accelerator_type  = "NVIDIA_L4"
        accelerator_count = 1
      }
      min_replica_count = 1
    }
  }
}
