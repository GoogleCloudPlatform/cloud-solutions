# Copyright 2025 Google LLC
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

resource "google_pubsub_topic" "media_transcoding_demo" {
  name    = join("-", [var.unique_identifier_prefix, "media-transcoding-demo"])
  project = google_project_service.pubsub_googleapis_com.project
}

data "google_storage_project_service_account" "gcs_account" {
  project = data.google_project.default.project_id
}

resource "google_pubsub_topic_iam_binding" "gcs_account_pubsub_binding" {
  project = google_project_service.iam_googleapis_com.project
  role    = "roles/pubsub.publisher"
  topic   = google_pubsub_topic.media_transcoding_demo.name

  members = [
    "serviceAccount:${data.google_storage_project_service_account.gcs_account.email_address}",
  ]
}

resource "google_storage_notification" "input_bucket_notification" {
  bucket         = var.cloud_storage_media_input_bucket_name
  event_types    = ["OBJECT_FINALIZE"]
  payload_format = "JSON_API_V1"
  topic          = google_pubsub_topic.media_transcoding_demo.id

  depends_on = [google_pubsub_topic_iam_binding.gcs_account_pubsub_binding]
}

resource "google_pubsub_subscription" "media_transcoding_demo" {
  name    = join("-", [var.unique_identifier_prefix, "media-transcoding-demo"])
  project = google_project_service.pubsub_googleapis_com.project
  topic   = google_pubsub_topic.media_transcoding_demo.id
}
