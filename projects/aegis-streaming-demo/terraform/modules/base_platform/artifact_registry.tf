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
      for f in fileset("${path.module}/../../../telemetry-simulator", "**") :
      filesha256("${path.module}/../../../telemetry-simulator/${f}")
      if !can(regex("(__pycache__|\\.pyc$|\\.git/|/tests/)", f))
    ]))
  }

  provisioner "local-exec" {
    command = "bash ${path.module}/scripts/build_container_image.sh"
    environment = {
      PROJECT_ID = var.project_id
      IMAGE_TAG  = "${var.region}-docker.pkg.dev/${var.project_id}/${local.artifact_registry_repo_name}/telemetry-simulator:latest"
      SOURCE_DIR = "${path.module}/../../../telemetry-simulator"
    }
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
      for f in fileset("${path.module}/../../../hud/backend", "**") :
      filesha256("${path.module}/../../../hud/backend/${f}")
      if !can(regex("(__pycache__|\\.pyc$|\\.git/|/tests/)", f))
    ]))
  }

  provisioner "local-exec" {
    command = "bash ${path.module}/scripts/build_container_image.sh"
    environment = {
      PROJECT_ID = var.project_id
      IMAGE_TAG  = "${var.region}-docker.pkg.dev/${var.project_id}/${local.artifact_registry_repo_name}/hud-backend:latest"
      SOURCE_DIR = "${path.module}/../../../hud/backend"
    }
  }

  depends_on = [
    google_artifact_registry_repository.aegis_containers,
    google_project_iam_member.cloudbuild_builder_roles
  ]
}

resource "null_resource" "build_hud_frontend" {
  triggers = {
    repo_id = google_artifact_registry_repository.aegis_containers.id
    source_hash = sha256(join("", [
      for f in fileset("${path.module}/../../../hud/frontend", "**") :
      filesha256("${path.module}/../../../hud/frontend/${f}")
      if !can(regex("(__pycache__|\\.pyc$|\\.git/|\\.next/|node_modules/)", f))
    ]))
  }

  provisioner "local-exec" {
    command = "bash ${path.module}/scripts/build_container_image.sh"
    environment = {
      PROJECT_ID = var.project_id
      IMAGE_TAG  = "${var.region}-docker.pkg.dev/${var.project_id}/${local.artifact_registry_repo_name}/hud-frontend:latest"
      SOURCE_DIR = "${path.module}/../../../hud/frontend"
    }
  }

  depends_on = [
    google_artifact_registry_repository.aegis_containers,
    google_project_iam_member.cloudbuild_builder_roles
  ]
}

resource "null_resource" "build_dataflow_pipeline" {
  count = var.pipeline_engine == "dataflow" ? 1 : 0

  triggers = {
    repo_id = google_artifact_registry_repository.aegis_containers.id
    source_hash = sha256(join("", [
      for f in fileset("${path.module}/../../../pipelines/firstparty-dataflow", "**") :
      filesha256("${path.module}/../../../pipelines/firstparty-dataflow/${f}")
      if !can(regex("(__pycache__|\\.pyc$|\\.git/|/tests/)", f))
    ]))
  }

  provisioner "local-exec" {
    command = "bash ${path.module}/scripts/build_container_image.sh"
    environment = {
      PROJECT_ID = var.project_id
      IMAGE_TAG  = "${var.region}-docker.pkg.dev/${var.project_id}/${local.artifact_registry_repo_name}/dataflow-pipeline:latest"
      SOURCE_DIR = "${path.module}/../../../pipelines/firstparty-dataflow"
    }
  }

  depends_on = [
    google_artifact_registry_repository.aegis_containers,
    google_project_iam_member.cloudbuild_builder_roles
  ]
}

resource "google_storage_bucket_object" "dataflow_template_spec" {
  count  = var.pipeline_engine == "dataflow" && var.staging_bucket != "" ? 1 : 0
  name   = "templates/aegis_dataflow_template.json"
  bucket = var.staging_bucket
  content = jsonencode({
    image = "${var.region}-docker.pkg.dev/${var.project_id}/${local.artifact_registry_repo_name}/dataflow-pipeline:latest"
    sdk_info = {
      language = "PYTHON"
    }
  })
  content_type = "application/json"

  depends_on = [
    null_resource.build_dataflow_pipeline
  ]
}

resource "null_resource" "redeploy_dataflow_pipeline" {
  count = var.pipeline_engine == "dataflow" && var.staging_bucket != "" ? 1 : 0

  triggers = {
    source_hash = null_resource.build_dataflow_pipeline[0].triggers.source_hash
    template_id = google_storage_bucket_object.dataflow_template_spec[0].id
  }

  provisioner "local-exec" {
    command = "bash ${path.module}/scripts/redeploy_dataflow_job.sh"
    environment = {
      PROJECT_ID     = var.project_id
      REGION         = var.region
      STAGING_BUCKET = var.staging_bucket
    }
  }

  depends_on = [
    google_storage_bucket_object.dataflow_template_spec,
    google_compute_subnetwork.aegis_subnet,
    google_service_account.aegis_sa,
    google_bigtable_table.telemetry_metrics,
    google_bigquery_table.telemetry_events
  ]
}
