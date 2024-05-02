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

output "source_cloud_storage_bucket_name" {
  description = "Name of the Cloud Storage bucket used as a source of events"
  value       = module.event_processing_gcs_buckets.buckets_map[local.event_source_gcs_bucket_name].name
}

output "event_processor_cloud_run_service_name" {
  description = "Name of the event processing Cloud Run service"
  value       = google_cloud_run_v2_service.event_processor.name
}

output "event_processing_dead_letter_topic_name" {
  description = "Name of the dead-letter Cloud Pub/Sub topic"
  value       = google_pubsub_topic.event_processing_dead_letter_topic.name
}
