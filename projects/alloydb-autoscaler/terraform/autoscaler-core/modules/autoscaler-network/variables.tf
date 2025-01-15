/**
 * Copyright 2024 Google LLC
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

variable "autoscaler_library_name" {
  type = string
}

variable "project_id" {
  type        = string
  description = "Project ID where the cluster will run"
}

variable "region" {
  type        = string
  description = "The name of the region to create the network"
}

variable "ip_range" {
  type        = string
  description = "The range for the network"
}
