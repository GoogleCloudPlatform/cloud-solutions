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

locals {
  cloud_storage_buckets = {
    input = {
      force_destroy      = false,
      versioning_enabled = true,
    },
    output = {
      force_destroy      = false,
      versioning_enabled = true,
    }
  }
}

resource "google_storage_bucket" "media_cloud_storage_buckets" {
  for_each = local.cloud_storage_buckets

  force_destroy               = each.value.force_destroy
  location                    = var.region
  name                        = join("-", [var.unique_identifier_prefix, each.key])
  project                     = google_project_service.storage_googleapis_com.project
  uniform_bucket_level_access = true

  versioning {
    enabled = each.value.versioning_enabled
  }
}

data "google_storage_project_service_account" "gcs_account" {
  project = google_project_service.storage_googleapis_com.project
}
