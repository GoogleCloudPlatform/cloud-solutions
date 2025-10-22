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

resource "google_cloud_run_v2_service" "toolbox" {
  count = var.deploy_mcp_toolbox_for_databases_to_cloud_run ? 1 : 0

  name                = "toolbox"
  location            = var.region
  deletion_protection = false

  template {
    service_account = google_service_account.toolbox-identity.email

    # Defines the container to be deployed.
    containers {
      image = var.tools_images_url

      # Corresponds to: --args="..."
      args = [
        "--tools-file=/app/tools.yaml",
        "--address=0.0.0.0",
        "--port=8080",
        "--ui",
        "--log-level=debug"
      ]

      # This section mounts the volume defined below into the container.
      # This is the second part of handling the --set-secrets flag.
      volume_mounts {
        name       = "tools-secret-volume"
        mount_path = "/app" # The file path inside the container
      }
    }

    # This section defines the volume that will be mounted.
    # Corresponds to: --set-secrets "/app/tools.yaml=tools:latest"
    volumes {
      name = "tools-secret-volume"
      secret {
        secret = google_secret_manager_secret.tools.secret_id # The name of the secret in Secret Manager
        items {
          path    = "tools.yaml" # The filename for the secret data
          version = "latest"     # The version of the secret
        }
      }
    }
  }

  depends_on = [google_project_service.run_googleapis_com]
}

locals {
  tools_run_invoker_members = concat([
    "serviceAccount:${google_service_account.adk-agent.email}"
  ], var.additional_tools_run_invoker_members)
}

resource "google_cloud_run_v2_service_iam_member" "allow_invokers" {
  # for_each iterates over every item in the set.
  # This creates a separate resource instance for each member.
  # for_each = toset(local.tools_run_invoker_members)
  for_each = var.deploy_mcp_toolbox_for_databases_to_cloud_run ? toset(local.tools_run_invoker_members) : []

  project  = google_cloud_run_v2_service.toolbox[0].project
  location = google_cloud_run_v2_service.toolbox[0].location
  name     = google_cloud_run_v2_service.toolbox[0].name
  role     = "roles/run.invoker"

  # 'each.key' holds the value of the current item in the loop
  member = each.key
}
