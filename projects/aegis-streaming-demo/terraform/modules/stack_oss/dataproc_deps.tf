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

# =============================================================================
# Dataproc Standard Spark Cluster PySpark Dependency Staging (OSS Stack)
# =============================================================================

resource "google_storage_bucket" "dataproc_deps" {
  name                        = "${var.project_id}-dataproc-deps"
  location                    = var.region
  project                     = var.project_id
  uniform_bucket_level_access = true
  force_destroy               = true

  labels = {
    environment = var.environment
    component   = "dataproc-dependencies"
  }
}

resource "google_storage_bucket_object" "aegis_etl_py" {
  name   = "dependencies/aegis_etl.py"
  bucket = google_storage_bucket.dataproc_deps.name
  source = "${path.module}/../../../data-ingestion/src/aegis_etl.py"
}

resource "google_storage_bucket_object" "requirements_txt" {
  name   = "dependencies/requirements.txt"
  bucket = google_storage_bucket.dataproc_deps.name
  source = "${path.module}/../../../data-ingestion/requirements.txt"
}

resource "google_storage_bucket_object" "init_spark_deps_sh" {
  name   = "dependencies/init_spark_deps.sh"
  bucket = google_storage_bucket.dataproc_deps.name
  source = "${path.module}/../../../data-ingestion/src/init_spark_deps.sh"
}
