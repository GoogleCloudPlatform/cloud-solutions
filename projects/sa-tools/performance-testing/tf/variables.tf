/**
 * Copyright 2022 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

// This file was automatically generated from a template in ./autogen/main

variable "project_id" {
  type        = string
  description = "The project ID to host Performance Testing in (required)"
}

variable "region" {
  type        = string
  description = "The region to host Performance Testing in "
}

variable "service_account" {
  type        = string
  description = "The account ID to host Performance Testing in"
  default     = "pt-service-account"
}


variable "archieve_bucket" {
  type        = string
  description = "The bucket to achieve all testing result in "
  default     = "pt-results-archive"
}


variable "firestore_collection" {
  type        = string
  description = "The name of collection in Firestore, where all related records to store "
  default     = "pt-transactions"
}


// Image for pt-admin in Cloud Run
variable "pt_admin_image" {
  type        = string
  description = "The image to deploy to Cloud Run"
}