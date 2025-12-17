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
    project_id       = var.project_id,
    region           = var.region
    alloydb_cluster  = google_alloydb_cluster.default.cluster_id
    alloydb_instance = google_alloydb_instance.default.instance_id,
    alloydb_database = "postgres",
    alloydb_user     = google_alloydb_user.toolbox_iam_user.user_id
  })
}

data "google_secret_manager_regional_secret_version_access" "gitlab_api_token_secret" {
  count      = var.deploy_cloud_build_triggers ? 1 : 0
  secret     = "cloudbuild-gitlab-1762979946127-api-access-token"
  location   = var.region
  depends_on = [google_project_service.secretmanager_googleapis_com]
}

data "google_secret_manager_regional_secret_version_access" "gitlab_read_token_secret" {
  count      = var.deploy_cloud_build_triggers ? 1 : 0
  secret     = "cloudbuild-gitlab-1762979946127-read-api-access-token"
  location   = var.region
  depends_on = [google_project_service.secretmanager_googleapis_com]
}

data "google_secret_manager_regional_secret_version_access" "gitlab_webhook_secret" {
  count      = var.deploy_cloud_build_triggers ? 1 : 0
  secret     = "cloudbuild-gitlab-1762979946127-webhook-secret"
  location   = var.region
  depends_on = [google_project_service.secretmanager_googleapis_com]
}

resource "google_secret_manager_regional_secret_iam_member" "gitlab_api_token_secret-secretAccessor" {
  count     = var.deploy_cloud_build_triggers ? 1 : 0
  secret_id = data.google_secret_manager_regional_secret_version_access.gitlab_api_token_secret[0].name
  role      = "roles/secretmanager.secretAccessor"
  member    = local.cloudbuild_service_account

  lifecycle {
    ignore_changes = [
      secret_id
    ]
  }

  depends_on = [google_project_service.secretmanager_googleapis_com]
}

resource "google_secret_manager_regional_secret_iam_member" "gitlab_read_token_secret-secretAccessor" {
  count     = var.deploy_cloud_build_triggers ? 1 : 0
  secret_id = data.google_secret_manager_regional_secret_version_access.gitlab_read_token_secret[0].name
  role      = "roles/secretmanager.secretAccessor"
  member    = local.cloudbuild_service_account

  lifecycle {
    ignore_changes = [
      secret_id
    ]
  }

  depends_on = [google_project_service.secretmanager_googleapis_com]
}

resource "google_secret_manager_regional_secret_iam_member" "gitlab_webhook_secret-secretAccessor" {
  count     = var.deploy_cloud_build_triggers ? 1 : 0
  secret_id = data.google_secret_manager_regional_secret_version_access.gitlab_webhook_secret[0].name
  role      = "roles/secretmanager.secretAccessor"
  member    = local.cloudbuild_service_account

  lifecycle {
    ignore_changes = [
      secret_id
    ]
  }

  depends_on = [google_project_service.secretmanager_googleapis_com]
}
