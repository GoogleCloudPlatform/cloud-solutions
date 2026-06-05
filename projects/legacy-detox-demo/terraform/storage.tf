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

resource "google_storage_bucket" "detox_bucket" {
  name                        = "${var.project_id}-detox-bucket"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true
}

# We use a static list of files to avoid "inconsistent result" errors from fileset()
# when files are generated during the apply phase.
locals {
  src_artifacts_for_upload = [
    "predict_job.py",
    "run_predict_job.sh",
    "spark_centric_demo.ipynb"
  ]
}

resource "google_storage_bucket_object" "src_files" {
  for_each = toset(local.src_artifacts_for_upload)

  name   = each.value
  bucket = google_storage_bucket.detox_bucket.name
  source = "${path.module}/../src/${each.value}"

  # Ensure files are re-uploaded if content changes
  source_md5hash = filemd5("${path.module}/../src/${each.value}")
}
