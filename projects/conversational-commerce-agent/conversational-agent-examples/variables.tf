# Copyright 2024 Google LLC
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
  description = "The ID of the project in which to provision resources."
  type        = string
}

variable "region" {
  default     = "us-central1"
  description = "The region for use"
  type        = string
}

variable "component" {
  default     = "apparel"
  description = "Deploy one of the components: apparel, food and beauty"
  type        = string
  validation {
    condition     = contains(["apparel", "food", "beauty"], var.component)
    error_message = "Component should be one of apparel, food or beauty."
  }
}
