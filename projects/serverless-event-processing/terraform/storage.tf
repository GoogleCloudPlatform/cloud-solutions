# Copyright 2024 Google LLC
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

module "terraform_backend_gcs_buckets" {
  source  = "terraform-google-modules/cloud-storage/google"
  version = "9.1.0"

  location                 = var.region
  names                    = [local.terraform_backend_gcs_bucket_name]
  prefix                   = data.google_project.project.project_id
  project_id               = data.google_project.project.project_id
  public_access_prevention = "enforced"
  randomize_suffix         = true

  force_destroy = {
    (local.terraform_backend_gcs_bucket_name) = true
  }

  versioning = {
    (local.terraform_backend_gcs_bucket_name) = true
  }
}

module "event_processing_gcs_buckets" {
  source  = "terraform-google-modules/cloud-storage/google"
  version = "9.1.0"

  names = [
    local.event_processing_results_gcs_bucket_name,
    local.event_source_gcs_bucket_name
  ]

  location                 = var.region
  prefix                   = data.google_project.project.project_id
  project_id               = data.google_project.project.project_id
  public_access_prevention = "enforced"
  randomize_suffix         = true

  force_destroy = {
    (local.event_processing_results_gcs_bucket_name) = true
    (local.event_source_gcs_bucket_name)             = true
  }

  versioning = {
    (local.event_processing_results_gcs_bucket_name) = true
    (local.event_source_gcs_bucket_name)             = true
  }
}
