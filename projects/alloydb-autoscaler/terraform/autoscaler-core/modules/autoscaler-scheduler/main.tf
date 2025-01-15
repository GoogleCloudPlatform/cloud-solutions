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

resource "google_app_engine_application" "app" {
  project     = var.project_id
  location_id = var.location == "us-central1" ? "us-central" : var.location
}

resource "google_cloud_scheduler_job" "poller_job" {
  name        = "poll-instance-metrics"
  description = "Poll metrics for the configured instances"
  schedule    = var.schedule
  time_zone   = var.time_zone

  pubsub_target {
    topic_name = var.pubsub_topic
    data       = base64encode(var.json_config)
  }

  retry_config {
    retry_count          = 0
    max_backoff_duration = "3600s"
    max_retry_duration   = "0s"
    max_doublings        = 5
    min_backoff_duration = "5s"
  }

  depends_on = [google_app_engine_application.app]

  /**
   * Uncomment this stanza if you would prefer to manage the Cloud Scheduler
   * configuration manually following its initial creation, i.e. using the
   * Google Cloud Web Console, the gcloud CLI, or any other non-Terraform
   * mechanism. Without this change, the Terraform configuration will remain
   * the source of truth, and any direct modifications to the Cloud Scheduler
   * configuration will be reset on the next Terraform run. Please see the
   * following link for more details:
   *
   * https://developer.hashicorp.com/terraform/language/meta-arguments/lifecycle#ignore_changes
   */
  /*
  lifecycle {
    ignore_changes = [pubsub_target[0].data]
  }
  */
}
