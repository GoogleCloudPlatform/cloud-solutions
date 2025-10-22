# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

resource "google_secret_manager_secret" "tools" {
  secret_id = "tools"

  replication {
    auto {}
  }

  depends_on = [google_project_service.secretmanager_googleapis_com]
}

resource "google_secret_manager_secret_version" "tools_version" {
  secret = google_secret_manager_secret.tools.id
  secret_data = templatefile("../../mcp-toolbox/tools.yaml.tftpl", {
    project_id = var.project_id,
  })
}

resource "google_secret_manager_secret" "hugging_face_api_token" {
  secret_id = "hf_api_token"

  replication {
    auto {}
  }

  depends_on = [google_project_service.secretmanager_googleapis_com]
}

resource "google_secret_manager_secret_version" "hugging_face_api_token_version" {
  secret      = google_secret_manager_secret.hugging_face_api_token.id
  secret_data = var.hugging_face_api_token
}
