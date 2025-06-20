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

locals {
  files = [
    "files/sample_files/ddos.txt",
    "files/sample_files/phising.txt",
    "files/sample_files/sql_injection.txt",
    "files/sample_files/wanna_cry.txt",
    "files/sample_files/zero_day.txt"
  ]
}

resource "google_storage_bucket" "widget_storage" {
  name          = "${var.project_id}-widget-bucket"
  location      = var.region
  force_destroy = true

  uniform_bucket_level_access = true
}

resource "google_storage_bucket_object" "sample_files" {
  for_each     = toset(local.files)
  content_type = "text/plain"
  name         = each.key
  source       = each.key
  bucket       = google_storage_bucket.widget_storage.id
}

resource "google_storage_bucket" "api_source_bucket" {
  name          = "${var.project_id}-api-source-bucket"
  location      = var.region
  force_destroy = true

  uniform_bucket_level_access = true
}


resource "google_storage_bucket" "client_source_bucket" {
  name          = "${var.project_id}-client-source-bucket"
  location      = var.region
  force_destroy = true

  uniform_bucket_level_access = true
}
