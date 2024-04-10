# Copyright 2024 Google LLC
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

# Create an Eventarc trigger, routing Cloud Storage events to Cloud Run as an example of an event source
resource "google_eventarc_trigger" "cloud_storage_object_finalized_event_trigger" {
  name     = "cloud-storage-object-finalized-trigger"
  location = var.region
  project  = data.google_project.project.project_id

  # Capture the "Object finalized" event...
  matching_criteria {
    attribute = "type"
    value     = "google.cloud.storage.object.v1.finalized"
  }
  #  ...in this bucket
  matching_criteria {
    attribute = "bucket"
    value     = module.event_processing_gcs_buckets.buckets_map[local.event_source_gcs_bucket_name].name
  }

  # Send captured events to Cloud Run
  destination {
    cloud_run_service {
      service = google_cloud_run_v2_service.event_processor.name
      region  = google_cloud_run_v2_service.event_processor.location
    }
  }

  service_account = module.service_accounts.service_accounts_map[local.eventarc_service_account_name].email
}
