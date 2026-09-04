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
# Artifact Registry Container Repository & Cloud Build Triggers
# =============================================================================

resource "google_artifact_registry_repository" "aegis_containers" {
  location      = var.region
  repository_id = local.artifact_registry_repo_name
  description   = "Docker container repository for Aegis streaming microservices"
  format        = "DOCKER"
  project       = var.project_id

  depends_on = [google_project_service.enabled_apis]
}



# Local execution provisioners to build & push container images during apply

resource "null_resource" "build_telemetry_simulator" {
  triggers = {
    repo_id = google_artifact_registry_repository.aegis_containers.id
    source_hash = sha256(join("", [
      for f in fileset("${path.module}/../telemetry-simulator", "**") :
      filesha256("${path.module}/../telemetry-simulator/${f}")
      if !can(regex("(__pycache__|\\.pyc$|\\.git/)", f))
    ]))
  }

  provisioner "local-exec" {
    command = <<EOT
      gcloud builds submit --project=${var.project_id} \
        --tag=${var.region}-docker.pkg.dev/${var.project_id}/${local.artifact_registry_repo_name}/telemetry-simulator:latest \
        ${path.module}/../telemetry-simulator
    EOT
  }

  depends_on = [
    google_artifact_registry_repository.aegis_containers,
    google_project_iam_member.cloudbuild_builder_roles
  ]
}

resource "null_resource" "build_hud_backend" {
  triggers = {
    repo_id = google_artifact_registry_repository.aegis_containers.id
    source_hash = sha256(join("", [
      for f in fileset("${path.module}/../hud/backend", "**") :
      filesha256("${path.module}/../hud/backend/${f}")
      if !can(regex("(__pycache__|\\.pyc$|\\.git/)", f))
    ]))
  }

  provisioner "local-exec" {
    command = <<EOT
      gcloud builds submit --project=${var.project_id} \
        --tag=${var.region}-docker.pkg.dev/${var.project_id}/${local.artifact_registry_repo_name}/hud-backend:latest \
        ${path.module}/../hud/backend
    EOT
  }

  depends_on = [
    google_artifact_registry_repository.aegis_containers,
    google_project_iam_member.cloudbuild_builder_roles,
    null_resource.build_telemetry_simulator
  ]
}

resource "null_resource" "build_hud_frontend" {
  triggers = {
    repo_id = google_artifact_registry_repository.aegis_containers.id
    source_hash = sha256(join("", [
      for f in fileset("${path.module}/../hud/frontend", "**") :
      filesha256("${path.module}/../hud/frontend/${f}")
      if !can(regex("(node_modules/|\\.next/|__pycache__|\\.pyc$|\\.git/)", f))
    ]))
  }

  provisioner "local-exec" {
    command = <<EOT
      gcloud builds submit --project=${var.project_id} \
        --config=${path.module}/../hud/frontend/cloudbuild.yaml \
        --substitutions=_IMAGE_TAG=${var.region}-docker.pkg.dev/${var.project_id}/${local.artifact_registry_repo_name}/hud-frontend:latest,_NEXT_PUBLIC_GCP_PROJECT=${var.project_id},_NEXT_PUBLIC_GCP_REGION=${var.region},_NEXT_PUBLIC_KAFKA_CLUSTER=${google_managed_kafka_cluster.aegis_kafka.cluster_id},_NEXT_PUBLIC_KAFKA_TOPIC=${google_managed_kafka_topic.telemetry_raw.topic_id},_NEXT_PUBLIC_BIGTABLE_INSTANCE=${local.bigtable_instance_id},_NEXT_PUBLIC_BIGQUERY_DATASET=${local.bigquery_dataset_id},_NEXT_PUBLIC_GEAP_AGENT_ID=${data.external.geap_agent.result["agent_id"]} \
        ${path.module}/../hud/frontend
    EOT
  }

  depends_on = [
    google_artifact_registry_repository.aegis_containers,
    google_project_iam_member.cloudbuild_builder_roles,
    null_resource.build_hud_backend,
    data.external.geap_agent
  ]
}
