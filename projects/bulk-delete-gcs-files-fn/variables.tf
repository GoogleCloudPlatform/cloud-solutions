#
# Copyright 2024 Google LLC
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

## Define variables

variable "project_id" {
  type        = string
  description = "Google Cloud project id to deploy resources"
}

variable "region" {
  type        = string
  description = "Google Cloud Region to use for deploying resources"
}

variable "artifact_registry_name" {
  type        = string
  default     = "gcs-delete-remote-functions"
  description = "Name of the Artifact registry to create remote function's image"
}

variable "bq_dataset" {
  type        = string
  default     = "fns_del"
  description = "Name of the BigQuery dataset to create the remote function"
}

variable "service_name" {
  default     = "bulk-delete-gcs-fn"
  description = "Name of the Cloud Run service running the Delete Remote function"
}
