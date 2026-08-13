# Copyright 2026 Google LLC
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

variable "project_id" {
  type        = string
  description = "The Google Cloud Project ID"
}

variable "region" {
  type        = string
  description = "The Google Cloud region to deploy resources in"
  default     = "us-central1"
}

variable "ces_service_agent" {
  type        = string
  description = "The Google Customer Engagement Suite (GECX/CES) Service Agent email to grant access to"
}

variable "image_tag" {
  type        = string
  description = "The tag of the container image to deploy"
  default     = "latest"
}

variable "conversation_profile_id" {
  type        = string
  description = "The Dialogflow Agent Assist Conversation Profile ID resource name"
}


