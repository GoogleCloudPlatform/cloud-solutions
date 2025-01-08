# Copyright 2025 Google LLC
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

variable "ui_name" {
  description = "The name of the ui"
  type        = string
}

variable "project_id" {
  description = "The project id"
  type        = string
}

variable "project_number" {
  description = "The project number"
  type        = string
}

variable "ui_assets_path" {
  description = "The path to the ui assets"
  type        = string
}

variable "dialogflow_cx_agent_name" {
  description = "The name of the dialogflow agent"
  type        = string
}
