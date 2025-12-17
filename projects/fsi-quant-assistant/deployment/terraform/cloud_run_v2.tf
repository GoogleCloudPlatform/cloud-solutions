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
  # provider = google-beta

  name                = "toolbox"
  location            = var.region
  deletion_protection = false

  # Using beta IAP for now, will switch to LBs later
  # launch_stage = "BETA"
  # iap_enabled  = false

  # To avoid TF seeing changes in Argolis environment
  scaling {
    manual_instance_count = 0
    min_instance_count    = 0
    max_instance_count    = 20
  }

  template {
    service_account = google_service_account.toolbox-identity.email

    vpc_access {
      network_interfaces {
        network    = google_compute_network.agent_cluster_vpc_network.name
        subnetwork = google_compute_subnetwork.agent_cluster_subnet.name
        tags       = ["mcp-toolbox-for-databases"]
      }
    }

    # Defines the container to be deployed.
    containers {
      image = var.tools_image_url

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
    # Vertex AI SA/ Agent Engine SA
    # Will be force created by google_project_service_identity.vertex_ai_sa though
    # the email is not the primary one.
    "serviceAccount:service-${data.google_project.project.number}@gcp-sa-aiplatform-re.iam.gserviceaccount.com",
  ], var.additional_tools_run_invoker_members)
}

resource "google_cloud_run_v2_service_iam_member" "toolbox_allow_invokers" {
  for_each = toset(local.tools_run_invoker_members)

  project  = google_cloud_run_v2_service.toolbox.project
  location = google_cloud_run_v2_service.toolbox.location
  name     = google_cloud_run_v2_service.toolbox.name
  role     = "roles/run.invoker"

  member = each.key

  depends_on = [google_project_service_identity.vertex_ai_sa]
}

locals {
  order_service_url = var.order_service_image_url != null ? var.order_service_image_url : "${var.region}-docker.pkg.dev/${var.project_id}/finance-bundle/order-service:latest"
}

resource "google_cloud_run_v2_service" "order_service" {
  count               = var.deploy_order_service ? 1 : 0
  name                = "order-service"
  location            = var.region
  deletion_protection = false

  # To avoid TF seeing changes in Argolis environment
  scaling {
    manual_instance_count = 0
    min_instance_count    = 0
    max_instance_count    = 20
  }

  template {
    service_account = google_service_account.order-service.email

    vpc_access {
      network_interfaces {
        network    = google_compute_network.agent_cluster_vpc_network.name
        subnetwork = google_compute_subnetwork.agent_cluster_subnet.name
      }
      egress = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = local.order_service_url

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "REGION"
        value = var.region
      }
      env {
        name  = "ALLOYDB_CLUSTER"
        value = google_alloydb_cluster.default.cluster_id
      }
      env {
        name  = "ALLOYDB_INSTANCE"
        value = google_alloydb_instance.default.instance_id
      }
      env {
        name  = "ALLOYDB_USER"
        value = google_alloydb_user.order_service_iam_user.user_id
      }
      env {
        name  = "ALLOYDB_DATABASE"
        value = var.alloydb_db_name
      }
      env {
        name  = "USE_IAM_AUTH"
        value = "true"
      }
    }
  }

  depends_on = [google_project_service.run_googleapis_com, google_alloydb_instance.default]
}

resource "google_cloud_run_v2_service_iam_member" "order_service_allow_invokers" {
  for_each = var.deploy_order_service ? toset(local.tools_run_invoker_members) : toset([])

  project  = google_cloud_run_v2_service.order_service[0].project
  location = google_cloud_run_v2_service.order_service[0].location
  name     = google_cloud_run_v2_service.order_service[0].name
  role     = "roles/run.invoker"

  member = each.key

  depends_on = [google_project_service_identity.vertex_ai_sa]
}
