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
  description = "The Google Cloud Project ID"
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "Google Cloud hosting region for the Looker Core instance"
}

variable "instance_name" {
  type        = string
  default     = "fynanceai-reporting-core"
  description = "The target resource identifier for Looker instance deployment"
}

variable "edition" {
  type        = string
  default     = "LOOKER_CORE_STANDARD"
  description = "Looker core platform pricing tier (e.g., LOOKER_CORE_STANDARD or LOOKER_CORE_ENTERPRISE_ANNUAL)"
}

variable "oauth_client_id" {
  type        = string
  description = "Google Cloud OAuth Web Client ID used to authenticate Looker console users"
  default     = ""
}

variable "oauth_client_secret" {
  type        = string
  sensitive   = true
  description = "Google Cloud OAuth Web Client Secret corresponding to the Web Client ID"
  default     = ""
}
