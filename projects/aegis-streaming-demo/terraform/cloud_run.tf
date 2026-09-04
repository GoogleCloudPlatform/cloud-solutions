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
# Cloud Run Microservices Deployment & IAM Access Bindings
# =============================================================================

# Telemetry Simulator Service (Headless Synthetic IIoT Generator & Kafka Streamer)
resource "google_cloud_run_v2_service" "telemetry_simulator" {
  name     = "telemetry-simulator"
  location = var.region
  project  = var.project_id

  template {
    service_account                  = google_service_account.aegis_sa.email
    max_instance_request_concurrency = 250

    scaling {
      min_instance_count = 1
      max_instance_count = 5
    }

    vpc_access {
      network_interfaces {
        network    = google_compute_network.aegis_vpc.id
        subnetwork = google_compute_subnetwork.aegis_subnet.id
      }
      egress = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${local.artifact_registry_repo_name}/telemetry-simulator:latest"

      resources {
        limits = {
          cpu    = "1000m"
          memory = "1024Mi"
        }
      }

      env {
        name  = "GCP_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GCP_REGION"
        value = var.region
      }
      env {
        name  = "KAFKA_BROKERS"
        value = "bootstrap.${google_managed_kafka_cluster.aegis_kafka.cluster_id}.${var.region}.managedkafka.${var.project_id}.cloud.goog:9092"
      }
      env {
        name  = "KAFKA_TOPIC"
        value = google_managed_kafka_topic.telemetry_raw.topic_id
      }
      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "SERVICE_ACCOUNT"
        value = google_service_account.aegis_sa.email
      }
      env {
        name  = "BUILD_REVISION"
        value = null_resource.build_telemetry_simulator.triggers.source_hash
      }
    }
  }

  depends_on = [
    null_resource.build_telemetry_simulator
  ]
}

# Backend Cloud Run Service (FastAPI SSE & Operations API)
resource "google_cloud_run_v2_service" "hud_backend" {
  name     = "hud-backend"
  location = var.region
  project  = var.project_id

  template {
    service_account                  = google_service_account.aegis_sa.email
    max_instance_request_concurrency = 250

    scaling {
      min_instance_count = 1
      max_instance_count = 5
    }

    vpc_access {
      network_interfaces {
        network    = google_compute_network.aegis_vpc.id
        subnetwork = google_compute_subnetwork.aegis_subnet.id
      }
      egress = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${local.artifact_registry_repo_name}/hud-backend:latest"

      resources {
        limits = {
          cpu    = "1000m"
          memory = "1024Mi"
        }
      }

      env {
        name  = "GCP_PROJECT"
        value = var.project_id
      }
      env {
        name  = "BIGTABLE_INSTANCE_ID"
        value = local.bigtable_instance_id
      }
      env {
        name  = "BIGQUERY_DATASET_ID"
        value = local.bigquery_dataset_id
      }
      env {
        name  = "AGENT_SERVICE_URL"
        value = data.external.geap_agent.result["resource_name"]
      }
      env {
        name  = "SIMULATOR_SERVICE_URL"
        value = google_cloud_run_v2_service.telemetry_simulator.uri
      }
      env {
        name  = "KAFKA_BROKERS"
        value = "bootstrap.${google_managed_kafka_cluster.aegis_kafka.cluster_id}.${var.region}.managedkafka.${var.project_id}.cloud.goog:9092"
      }
      env {
        name  = "KAFKA_TOPIC"
        value = google_managed_kafka_topic.telemetry_raw.topic_id
      }
      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "GCP_REGION"
        value = var.region
      }
      env {
        name  = "DEPS_BUCKET"
        value = "${var.project_id}-dataproc-deps"
      }
      env {
        name  = "SERVICE_ACCOUNT"
        value = google_service_account.aegis_sa.email
      }
      env {
        name  = "SUBNETWORK_URI"
        value = google_compute_subnetwork.aegis_subnet.id
      }
      env {
        name  = "BUILD_REVISION"
        value = null_resource.build_hud_backend.triggers.source_hash
      }
    }
  }

  depends_on = [
    null_resource.build_hud_backend,
    null_resource.deploy_geap_agent,
    google_cloud_run_v2_service.telemetry_simulator
  ]
}

# Frontend Cloud Run Service (Next.js Dashboard)
resource "google_cloud_run_v2_service" "hud_frontend" {
  name     = "hud-frontend"
  location = var.region
  project  = var.project_id
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account                  = google_service_account.aegis_sa.email
    max_instance_request_concurrency = 250

    scaling {
      min_instance_count = 1
      max_instance_count = 5
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${local.artifact_registry_repo_name}/hud-frontend:latest"

      resources {
        limits = {
          cpu    = "1000m"
          memory = "1024Mi"
        }
      }

      env {
        name  = "BACKEND_API_URL"
        value = google_cloud_run_v2_service.hud_backend.uri
      }
      env {
        name  = "NEXT_PUBLIC_HUD_BACKEND_URL"
        value = google_cloud_run_v2_service.hud_backend.uri
      }
      env {
        name  = "GCP_PROJECT"
        value = var.project_id
      }
      env {
        name  = "NEXT_PUBLIC_GCP_PROJECT"
        value = var.project_id
      }
      env {
        name  = "NEXT_PUBLIC_GCP_REGION"
        value = var.region
      }
      env {
        name  = "NEXT_PUBLIC_KAFKA_CLUSTER"
        value = google_managed_kafka_cluster.aegis_kafka.cluster_id
      }
      env {
        name  = "NEXT_PUBLIC_KAFKA_TOPIC"
        value = google_managed_kafka_topic.telemetry_raw.topic_id
      }
      env {
        name  = "NEXT_PUBLIC_BIGTABLE_INSTANCE"
        value = local.bigtable_instance_id
      }
      env {
        name  = "NEXT_PUBLIC_BIGQUERY_DATASET"
        value = local.bigquery_dataset_id
      }
      env {
        name  = "NEXT_PUBLIC_GEAP_AGENT_ID"
        value = data.external.geap_agent.result["agent_id"]
      }
      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "BUILD_REVISION"
        value = null_resource.build_hud_frontend.triggers.source_hash
      }
    }
  }

  depends_on = [
    null_resource.build_hud_frontend,
    google_cloud_run_v2_service.hud_backend
  ]
}

# IAM Access Bindings for Cloud Run Services
# Explicitly grants run.invoker to aegis-sa and authorized corporate domain callers

resource "google_cloud_run_v2_service_iam_member" "telemetry_simulator_invoker" {
  for_each = toset(concat(["allUsers"], var.authorized_invokers))

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.telemetry_simulator.name
  role     = "roles/run.invoker"
  member   = each.value
}

resource "google_cloud_run_v2_service_iam_member" "telemetry_simulator_sa_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.telemetry_simulator.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.aegis_sa.email}"
}

resource "google_cloud_run_v2_service_iam_member" "hud_backend_invoker" {
  for_each = toset(concat(["allUsers"], var.authorized_invokers))

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.hud_backend.name
  role     = "roles/run.invoker"
  member   = each.value
}

resource "google_cloud_run_v2_service_iam_member" "hud_backend_sa_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.hud_backend.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.aegis_sa.email}"
}

resource "google_cloud_run_v2_service_iam_member" "hud_frontend_invoker" {
  for_each = toset(concat(["allUsers"], var.authorized_invokers))

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.hud_frontend.name
  role     = "roles/run.invoker"
  member   = each.value
}

resource "google_cloud_run_v2_service_iam_member" "hud_frontend_sa_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.hud_frontend.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.aegis_sa.email}"
}
