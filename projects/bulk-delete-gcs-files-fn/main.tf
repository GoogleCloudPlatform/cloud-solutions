#
# Copyright 2024 Google LLC
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
#

###################################
##    Creating Cloud Resources   ##
###################################


resource "google_service_account" "run_service_account" {
  account_id = "${var.service_name}-runner"
  project    = var.project_id
}

resource "google_project_iam_member" "grant_role_to_sa" {
  for_each = toset([
    "roles/storage.objectUser",
  ])
  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.run_service_account.email}"
}

resource "google_artifact_registry_repository" "image_registry" {
  format        = "DOCKER"
  repository_id = var.artifact_registry_name
  project       = var.project_id
  location      = var.region
}


## Create Image using Cloud Build and store in artifact registry
resource "random_id" "build_version" {
  byte_length = 8

  keepers = {
    project_id = var.project_id
    region     = var.region
  }
}

resource "null_resource" "build_function_image" {
  depends_on = [google_artifact_registry_repository.image_registry]

  triggers = {
    project_id      = var.project_id
    region          = var.region
    full_image_path = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.image_registry.name}/${var.service_name}:${random_id.build_version.hex}"
  }

  provisioner "local-exec" {
    when    = create
    command = <<EOF
gcloud builds submit \
--project ${var.project_id} \
--region ${var.region} \
--machine-type=e2-highcpu-8 \
--substitutions=_CONTAINER_IMAGE_NAME=${self.triggers.full_image_path}
EOF
  }

  provisioner "local-exec" {
    when    = destroy
    command = <<EOF
gcloud artifacts docker images delete \
${self.triggers.full_image_path} \
--quiet
EOF
  }
}

resource "google_cloud_run_v2_service" "bq_function" {
  location   = var.region
  name       = var.service_name
  project    = var.project_id
  depends_on = [null_resource.build_function_image]

  template {
    service_account       = google_service_account.run_service_account.email
    execution_environment = "EXECUTION_ENVIRONMENT_GEN2"

    containers {
      image = null_resource.build_function_image.triggers.full_image_path
      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "BULK_DEL_FN_VERSION"
        value = "0.1"
      }
    }
  }
}

resource "google_bigquery_connection" "external_bq_fn_connection" {
  project       = var.project_id
  connection_id = "ext-${var.service_name}"
  location      = var.region
  description   = "External transformation function connection"
  cloud_resource {}
}

resource "google_project_iam_binding" "grant_bq_connection_run_invoker_role" {
  project = var.project_id
  role    = "roles/run.invoker"
  members = [
    "serviceAccount:${google_bigquery_connection.external_bq_fn_connection.cloud_resource[0].service_account_id}"
  ]
}

resource "google_bigquery_dataset" "routines_dataset" {
  project    = var.project_id
  location   = var.region
  dataset_id = var.bq_dataset
}

## Create DLP DeId Template

resource "random_id" "random_de_id_template_id_random" {
  byte_length = 8
  prefix      = "bqdlpfn_"
  keepers = {
    project_id = var.project_id
    region     = var.region
  }
}

## Create BigQuery remote functions
resource "random_id" "bq_job_random" {
  byte_length = 8
}

resource "null_resource" "bq_gcs_delete_fn" {
  depends_on = [google_cloud_run_v2_service.bq_function, google_bigquery_connection.external_bq_fn_connection, google_bigquery_dataset.routines_dataset]

  triggers = {
    project_id         = var.project_id
    region             = var.region
    dataset_id         = var.bq_dataset
    cloud_service_name = google_cloud_run_v2_service.bq_function.id
    cloud_run_uri      = google_cloud_run_v2_service.bq_function.uri
  }

  provisioner "local-exec" {
    when    = create
    command = <<EOF
bq query --project_id "${self.triggers.project_id}" \
--use_legacy_sql=false \
"CREATE OR REPLACE FUNCTION ${self.triggers.dataset_id}.gcs_delete(v STRING) RETURNS STRING \
REMOTE WITH CONNECTION \`${self.triggers.project_id}.${self.triggers.region}.${google_bigquery_connection.external_bq_fn_connection.connection_id}\` \
OPTIONS (endpoint = '${self.triggers.cloud_run_uri}', user_defined_context = []);" \
EOF
  }

  provisioner "local-exec" {
    when    = destroy
    command = <<EOF
bq query --project_id "${self.triggers.project_id}" \
--use_legacy_sql=false \
"DROP FUNCTION ${self.triggers.dataset_id}.gcs_delete" \
EOF
  }
}

## Create test Cloud Storage bucket

resource "google_storage_bucket" "sample_bucket" {
  location      = var.region
  name          = "${var.project_id}-bulk-delete-test"
  force_destroy = true
}

## Copy Test file to GCS
resource "google_storage_bucket_object" "sample_file1" {
  bucket = google_storage_bucket.sample_bucket.name
  name   = "file1"
  source = "./LICENCE"
}

output "sample_sql" {
  value = <<EOT
  SELECT `${var.project_id}.${var.bq_dataset}.gcs_delete`('gs://${google_storage_bucket.sample_bucket}/file1')
  EOT
}
