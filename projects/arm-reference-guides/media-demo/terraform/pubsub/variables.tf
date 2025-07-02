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

variable "cloud_storage_media_input_bucket_name" {
  description = "Name of the media input Cloud Storage bucket"
  type        = string
}

variable "cloud_storage_service_account_email" {
  description = "Email of the Cloud Storage service account"
  type        = string
}

variable "region" {
  description = "Region where to create the storage buckets"
  type        = string
}

variable "project_id" {
  description = "The GCP project where to create resources"
  type        = string
}

variable "unique_identifier_prefix" {
  description = "Unique resource name prefix"
  type        = string
}
