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

resource "google_pubsub_topic" "downstream_topic" {
  name = "downstream-topic"

  depends_on = [google_pubsub_schema.scaler_downstream_pubsub_schema]

  schema_settings {
    schema   = google_pubsub_schema.scaler_downstream_pubsub_schema.id
    encoding = "JSON"
  }

  lifecycle {
    replace_triggered_by = [google_pubsub_schema.scaler_downstream_pubsub_schema]
  }
}

resource "google_pubsub_topic_iam_member" "scaler_downstream_pub_iam" {
  project = var.project_id
  topic   = google_pubsub_topic.downstream_topic.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${var.scaler_sa_email}"
}

resource "google_pubsub_schema" "scaler_downstream_pubsub_schema" {
  name       = "downstream-schema"
  type       = "PROTOCOL_BUFFER"
  definition = file("${path.module}/../../../../${var.path_to_downstream_proto}")
}

resource "google_project_iam_member" "metrics_publisher_iam_poller" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${var.poller_sa_email}"
}

resource "google_project_iam_member" "metrics_publisher_iam_scaler" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${var.scaler_sa_email}"
}

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
