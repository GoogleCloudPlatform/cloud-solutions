# Copyright 2024 Google LLC
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

resource "google_cloud_run_v2_service" "event_processor" {
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  location = var.region
  name     = local.cloud_run_event_processing_service_name
  project  = data.google_project.project.project_id

  template {
    containers {
      image = var.cloud_run_service_event_processing_service_container_image_id

      resources {
        limits = {
          cpu    = "2"
          memory = "1024Mi"
        }
      }
    }

    scaling {
      max_instance_count = 2
    }

    service_account = module.service_accounts.service_accounts_map[local.cloud_run_service_account_name].email
  }
}
