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

resource "google_storage_bucket" "ui_src_bucket" {
  name                        = "${var.project_id}-${var.ui_name}-ui" # Every bucket name must be globally unique
  location                    = "US"
  uniform_bucket_level_access = true
}

resource "google_storage_bucket_object" "ui_index" {
  name    = "static/index.html"
  bucket  = google_storage_bucket.ui_src_bucket.name
  content = replace(replace(file("${var.ui_assets_path}/static/index.html.tmpl"), "_AGENT_ID_", var.dialogflow_cx_agent_name), "_PROJECT_ID_", var.project_id)
}

resource "google_storage_bucket_object" "ui_static_fiels" {
  for_each = fileset("${var.ui_assets_path}/static", "**/*")
  name     = "static/${each.key}"
  bucket   = google_storage_bucket.ui_src_bucket.name
  source   = "${var.ui_assets_path}/static/${each.key}"
}

resource "google_secret_manager_secret" "nginx_config" {
  secret_id = "${var.ui_name}_nginx_config"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "nginx_config_data" {
  secret = google_secret_manager_secret.nginx_config.id

  secret_data = <<-EOT
    server {
        listen 8080;
        server_name _;
        gzip on;

        location / {
            root   /data/static;
            index  index.html index.htm;
        }
    }
    EOT
}

resource "google_secret_manager_secret_iam_member" "secret-access" {
  secret_id  = google_secret_manager_secret.nginx_config.id
  role       = "roles/secretmanager.secretAccessor"
  member     = "serviceAccount:${var.project_number}-compute@developer.gserviceaccount.com"
  depends_on = [google_secret_manager_secret.nginx_config]
}

resource "google_cloud_run_v2_service" "ui_static" {
  name                = replace("${var.ui_name}-ui-static", "_", "-")
  location            = "us-central1"
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_ALL"

  template {
    containers {
      image = "nginx:latest"
      volume_mounts {
        name       = "nginx_config"
        mount_path = "/etc/nginx/conf.d/"
      }
      volume_mounts {
        name       = "bucket"
        mount_path = "/data"
      }
    }
    volumes {
      name = "nginx_config"
      secret {
        secret       = google_secret_manager_secret.nginx_config.secret_id
        default_mode = 292 # 0444
        items {
          version = "latest"
          path    = "default.conf"
        }
      }
    }
    volumes {
      name = "bucket"
      gcs {
        bucket    = google_storage_bucket.ui_src_bucket.name
        read_only = true
      }
    }
  }
  depends_on = [google_secret_manager_secret.nginx_config,
    google_storage_bucket.ui_src_bucket,
    google_secret_manager_secret_version.nginx_config_data
  ]
}

resource "google_cloud_run_service_iam_binding" "allow_public" {
  location = google_cloud_run_v2_service.ui_static.location
  service  = google_cloud_run_v2_service.ui_static.name
  role     = "roles/run.invoker"
  members = [
    "allUsers"
  ]
}
