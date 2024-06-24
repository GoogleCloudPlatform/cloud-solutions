# Copyright 2023 Google LLC
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

resource "google_storage_bucket" "hive_bq_cluster_staging" {
  project                     = data.google_project.project.project_id
  name                        = "${data.google_project.project.project_id}-hivebq-bucket"
  uniform_bucket_level_access = true
  location                    = local.region
  force_destroy               = true
}

resource "google_storage_bucket_object" "init_script" {
  bucket  = google_storage_bucket.hive_bq_cluster_staging.name
  name    = "scripts/initialization-script.sh"
  content = file("../scripts/initialization-script.sh")
}

resource "google_storage_bucket_object" "init_script_requirements" {
  bucket  = google_storage_bucket.hive_bq_cluster_staging.name
  name    = "scripts/initialization-requirements.txt"
  content = file("../scripts/initialization-requirements.txt")
}

resource "google_storage_bucket" "warehouse" {
  project                     = data.google_project.project.project_id
  name                        = "${data.google_project.project.project_id}-warehouse-bucket"
  uniform_bucket_level_access = true
  location                    = local.region
  force_destroy               = true
}
