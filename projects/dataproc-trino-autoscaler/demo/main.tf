#
# Copyright 2023 Google LLC
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

######################################
##    Initializing Cloud Services   ##
######################################

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 4.0.0"
    }
  }

  provider_meta "google" {
    module_name = "cloud-solutions/trino-autoscaler-deploy-v0.1"
  }
}

provider "google" {
  billing_project = var.project_id
  project         = var.project_id
  region          = var.region
  zone            = var.zone
}

###################################
##    Creating Cloud Resources   ##
###################################

resource "google_storage_bucket" "dataproc_staging_bucket" {
  location      = var.region
  name          = coalesce(var.dataproc_staging_gcs_bucket_name, "trino-staging-bucket-${var.project_id}")
  force_destroy = true
}

## Create application JAR using Cloud Build and store in GCS Bucket
resource "random_id" "build_version" {
  byte_length = 8

  keepers = {
    project_id = var.project_id
    region     = var.region
  }
}

resource "null_resource" "build_application_jar" {
  depends_on = [google_storage_bucket.dataproc_staging_bucket]

  triggers = {
    project_id     = var.project_id
    region         = var.region
    jar_folder_url = "${google_storage_bucket.dataproc_staging_bucket.url}/${var.autoscaler_folder}/${random_id.build_version.hex}"
  }

  provisioner "local-exec" {
    when    = create
    command = <<EOF
gcloud builds submit ${path.root}/../ \
--config=${path.root}/../cloudbuild.yaml \
--project ${var.project_id} \
--region ${var.region} \
--machine-type=e2-highcpu-8 \
--substitutions=_JAR_LOCATION=${self.triggers.jar_folder_url}
EOF
  }

  provisioner "local-exec" {
    when    = destroy
    command = "gsutil -m rm -rf ${self.triggers.jar_folder_url}"
  }
}

## Copy Demo config to GCS
resource "google_storage_bucket_object" "sample_config" {
  bucket = google_storage_bucket.dataproc_staging_bucket.name
  name   = "${var.autoscaler_folder}/config/autoscaler_config.textproto"
  source = "./sample_config.textproto"
}

## Generate init action script in GCS
locals {
  dataproc_init_script_content = replace(
    replace(
      file("${path.root}/trino-autoscaler-init.sh"),
      "CONFIG_JAR_FILE_GCS_URI=\"\"",
    "CONFIG_JAR_FILE_GCS_URI=\"${null_resource.build_application_jar.triggers.jar_folder_url}/dataproc-trino-autoscaler-all.jar\""),
    "CONFIG_PROTO_FILE_GCS_URI=\"\"",
    "CONFIG_PROTO_FILE_GCS_URI=\"${google_storage_bucket.dataproc_staging_bucket.url}/${google_storage_bucket_object.sample_config.output_name}\""
  )
}

resource "google_storage_bucket_object" "init_script" {
  bucket  = google_storage_bucket.dataproc_staging_bucket.name
  name    = "${var.autoscaler_folder}/init-script/trino-autoscaler-init.sh"
  content = local.dataproc_init_script_content
}

# Create Dataproc Cluster
resource "google_service_account" "dataproc_service_account" {
  account_id = "${var.dataproc_cluster_name}-runner"
  project    = var.project_id
}

resource "google_project_iam_member" "grant_role_to_sa" {
  for_each = toset([
    "roles/compute.admin",
    "roles/bigquery.dataViewer",
    "roles/bigquery.user",
    "roles/dataproc.editor",
    "roles/dataproc.worker",
    "roles/monitoring.viewer",
    "roles/storage.objectViewer",
  ])
  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.dataproc_service_account.email}"
}

resource "google_dataproc_cluster" "trino_dataproc_cluster" {

  depends_on = [google_storage_bucket.dataproc_staging_bucket]

  name   = var.dataproc_cluster_name
  region = var.region

  cluster_config {

    master_config {
      num_instances = 1
      machine_type  = "n2-standard-4"
    }

    worker_config {
      num_instances = 0
      machine_type  = "n2-standard-2"
    }

    preemptible_worker_config {
      num_instances  = 0
      preemptibility = "PREEMPTIBLE"
    }

    software_config {
      image_version = "2.1-debian11"
      optional_components = [
        "TRINO"
      ]
      override_properties = {
        "dataproc:dataproc.monitoring.stackdriver.enable" = true
      }
    }

    gce_cluster_config {
      zone                   = var.zone
      service_account        = google_service_account.dataproc_service_account.email
      service_account_scopes = ["cloud-platform"]
    }

    # Configure custom init action
    initialization_action {
      script      = "${google_storage_bucket.dataproc_staging_bucket.url}/${google_storage_bucket_object.init_script.output_name}"
      timeout_sec = 500
    }

    staging_bucket = google_storage_bucket.dataproc_staging_bucket.name
  }
}

## Create monitoring dashboard
resource "google_monitoring_dashboard" "dashboard" {
  depends_on     = [google_dataproc_cluster.trino_dataproc_cluster]
  dashboard_json = replace(replace(file("${path.root}/monitoring-dashboard.json"), "{{cluster_name}}", google_dataproc_cluster.trino_dataproc_cluster.name), "{{cluster_region}}", google_dataproc_cluster.trino_dataproc_cluster.region)
}

output "dashboard_url" {
  value = join("", [
    "https://console.cloud.google.com/monitoring/dashboards/builder/",
    regex("([^/]+)$", google_monitoring_dashboard.dashboard.id)[0],
    ";duration=PT30M?project=",
    var.project_id
  ])
}

output "trino-master-ssh-command" {
  value = "gcloud compute ssh --zone '${var.zone}' '${var.dataproc_cluster_name}-m' --project '${var.project_id}'"
}
