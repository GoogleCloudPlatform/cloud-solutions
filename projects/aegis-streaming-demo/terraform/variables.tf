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

variable "project_id" {
  type        = string
  description = "The GCP Project ID where resources will be provisioned. Format pattern: lowercase letters, numbers, and hyphens (e.g. 'my-gcp-project-id')."
}

variable "region" {
  type        = string
  description = "The target GCP region for regional resources. Format pattern: GCP region name (e.g. 'us-central1', 'europe-west1')."
}

variable "zone" {
  type        = string
  description = "The target GCP zone for regional resources. Format pattern: GCP zone name (e.g. 'us-central1-a', 'europe-west1-b')."
}


variable "environment" {
  type        = string
  description = "Deployment environment stage. Format pattern: 'dev', 'staging', or 'prod'."
}

variable "authorized_invokers" {
  type        = list(string)
  description = "List of IAM member principals permitted to invoke Cloud Run services. Expected member format patterns: 'domain:<DOMAIN>', 'user:<EMAIL>', 'group:<EMAIL>', or 'serviceAccount:<EMAIL>' (e.g. 'domain:example.com', 'user:admin@example.com')."
}
