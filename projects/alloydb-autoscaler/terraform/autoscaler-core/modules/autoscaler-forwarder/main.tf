/**
 * Copyright 2024 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

resource "google_service_account" "build_sa" {
  account_id   = "build-sa"
  display_name = "Autoscaler - Cloud Build Builder Service Account"
}

resource "google_project_iam_member" "build_iam" {
  for_each = toset([
    "roles/artifactregistry.writer",
    "roles/logging.logWriter",
    "roles/storage.objectViewer",
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.build_sa.email}"
}

resource "time_sleep" "wait_for_iam" {
  depends_on      = [google_project_iam_member.build_iam]
  create_duration = "90s"
}

resource "google_service_account" "forwarder_sa" {
  account_id   = "forwarder-sa"
  display_name = "Autoscaler - PubSub Forwarder SA"
}

resource "google_pubsub_topic" "forwarder_topic" {
  name = "forwarder-topic"
}

resource "google_pubsub_topic_iam_member" "forwader_pubsub_sub_binding" {
  project = var.project_id
  topic   = google_pubsub_topic.forwarder_topic.name
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.forwarder_sa.email}"
}

resource "google_storage_bucket" "bucket_gcf_source" {
  name                        = "${var.project_id}-gcf-source"
  storage_class               = "REGIONAL"
  location                    = var.region
  force_destroy               = "true"
  uniform_bucket_level_access = var.uniform_bucket_level_access
}

data "archive_file" "local_forwarder_source" {
  type        = "zip"
  source_dir  = abspath("${path.module}/../../../..")
  output_path = "${var.local_output_path}/forwarder.zip"
  excludes = [
    "node_modules",
    "terraform",
    "resources",
    ".github",
    "kubernetes",
    "gke"
  ]
}

resource "google_storage_bucket_object" "gcs_functions_forwarder_source" {
  name   = "forwarder.${data.archive_file.local_forwarder_source.output_md5}.zip"
  bucket = google_storage_bucket.bucket_gcf_source.name
  source = data.archive_file.local_forwarder_source.output_path
}

resource "google_cloudfunctions2_function" "forwarder_function" {
  name     = "tf-forwarder-function"
  project  = var.project_id
  location = var.region

  build_config {
    runtime     = "nodejs${var.nodejs_version}"
    entry_point = var.autoscaler_forwarder_function_name

    source {
      storage_source {
        bucket = google_storage_bucket.bucket_gcf_source.name
        object = google_storage_bucket_object.gcs_functions_forwarder_source.name
      }
    }
    service_account = google_service_account.build_sa.id
  }

  service_config {
    available_memory      = "256M"
    ingress_settings      = "ALLOW_INTERNAL_AND_GCLB"
    service_account_email = google_service_account.forwarder_sa.email
    environment_variables = {
      POLLER_TOPIC = var.target_pubsub_topic
    }
  }

  event_trigger {
    event_type            = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic          = google_pubsub_topic.forwarder_topic.id
    retry_policy          = "RETRY_POLICY_RETRY"
    service_account_email = google_service_account.forwarder_sa.email
  }

  depends_on = [
    time_sleep.wait_for_iam,
    google_pubsub_topic_iam_member.forwader_pubsub_sub_binding
  ]
}

resource "google_cloud_run_service_iam_member" "cloud_run_forwarder_invoker" {
  project  = google_cloudfunctions2_function.forwarder_function.project
  location = google_cloudfunctions2_function.forwarder_function.location
  service  = google_cloudfunctions2_function.forwarder_function.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.forwarder_sa.email}"
}
