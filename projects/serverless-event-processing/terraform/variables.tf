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

variable "cloud_run_service_event_processing_service_container_image_id" {
  # Source: https://github.com/GoogleCloudPlatform/cloud-run-hello
  default     = "us-docker.pkg.dev/cloudrun/container/hello@sha256:0aa5a17f8cd959c849b5e1c47a365863135c486461cabd0425f39eff0227f461"
  description = "The full ID of the container image of the event processing service to deploy on Cloud Run"
  type        = string
}

variable "project_id" {
  description = "The Google Cloud project ID"
  type        = string
}

variable "provision_event_processing_dead_letter_topic" {
  default     = false
  description = "If set to true, provision a Cloud Pub/Sub topic that you can configure as a dead-letter topic for the Eventarc trigger that routes events. For more information, see https://cloud.google.com/eventarc/docs/retry-events"
  type        = bool
}

variable "region" {
  default     = "europe-west1"
  description = "The default region to provision resources in"
  type        = string
}
