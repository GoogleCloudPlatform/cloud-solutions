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


resource "terraform_data" "inference_server_image" {
  # Trigger a rebuild whenever any source file in src/inference-server changes.
  triggers_replace = [
    sha256(join("", [for f in fileset("${path.module}/../src/inference-server", "*") : filesha256("${path.module}/../src/inference-server/${f}")]))
  ]

  provisioner "local-exec" {
    command = <<EOT
      gcloud builds submit ${path.module}/../src/inference-server \
        --tag ${var.region}-docker.pkg.dev/${data.google_project.legacy_detox_project.project_id}/${google_artifact_registry_repository.legacy_detox_artifact_registry.repository_id}/inference-server:latest \
        --gcs-source-staging-dir gs://${google_storage_bucket.detox_bucket.name}/cloudbuild-staging \
        --project ${data.google_project.legacy_detox_project.project_id}
    EOT
  }

  depends_on = [
    google_artifact_registry_repository.legacy_detox_artifact_registry,
    google_storage_bucket.detox_bucket,
    google_project_iam_member.default_compute_cloudbuild_editor,
    google_storage_bucket_iam_member.default_compute_storage_object_admin,
    google_artifact_registry_repository_iam_member.default_compute_ar_writer
  ]
}

locals {
  inference_server_image_uri = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.legacy_detox_artifact_registry.repository_id}/inference-server:latest"
}
