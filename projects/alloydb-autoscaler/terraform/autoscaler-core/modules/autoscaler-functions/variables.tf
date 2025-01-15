/*
 * Copyright 2024 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "nodejs_version" {
  type = string
}

variable "local_output_path" {
  type    = string
  default = "build"
}

variable "uniform_bucket_level_access" {
  type    = bool
  default = true
}

variable "poller_sa_email" {
  type = string
}

variable "scaler_sa_email" {
  type = string
}
variable "build_sa_id" {
  type = string
  // projects/{{project}}/serviceAccounts/{{email}}
}

variable "forwarder_sa_emails" {
  type = list(string)
  // Example ["serviceAccount:forwarder_sa@app-project.iam.gserviceaccount.com"]
  default = []
}

variable "autoscaler_poller_function_name" {
  type        = string
  description = "Name of the Autoscaler Poller entrypoint function"
}

variable "autoscaler_scaler_function_name" {
  type        = string
  description = "Name of the Autoscaler Scaler entrypoint function"
}
