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

data "archive_file" "apparel_search_cf" {
  type = "zip"

  source {
    content  = file("${path.module}/assets/apparel-search-cf/main.py")
    filename = "main.py"
  }

  source {
    content  = file("${path.module}/assets/apparel-search-cf/requirements.txt")
    filename = "requirements.txt"
  }

  source {
    content  = file("${path.module}/assets/apparel-search-cf/utils.py")
    filename = "utils.py"
  }

  source {
    content  = <<-EOT
    [gcp]
    project_id = "${var.project_id}"
    project_number = "${local.target_project_number}"
    apparel_firebase_db = "apparel-db"
    EOT
    filename = "config.toml"
  }

  output_path = "${path.module}/apparel-search-cf.zip"
}


resource "google_storage_bucket" "apparel_search_src_bucket" {
  name                        = "${var.project_id}-apparel-search-source" # Every bucket name must be globally unique
  location                    = "US"
  uniform_bucket_level_access = true
}

resource "google_storage_bucket_object" "apparel_search_src_archive" {
  name   = "apparel-search-src.zip"
  bucket = google_storage_bucket.apparel_search_src_bucket.name
  source = data.archive_file.apparel_search_cf.output_path
}

resource "google_cloudfunctions2_function" "function" {
  location = var.region
  name     = "apparel-search-cf"
  project  = var.project_id

  build_config {
    entry_point = "main"
    runtime     = "python312"
    source {
      storage_source {
        bucket = google_storage_bucket.apparel_search_src_bucket.name
        object = google_storage_bucket_object.apparel_search_src_archive.name
      }
    }
    service_account = "projects/${var.project_id}/serviceAccounts/${local.target_project_number}-compute@developer.gserviceaccount.com"
  }

  service_config {
    available_memory      = "512Mi"
    ingress_settings      = "ALLOW_ALL"
    max_instance_count    = 100
    service_account_email = "${local.target_project_number}-compute@developer.gserviceaccount.com"
  }
}
