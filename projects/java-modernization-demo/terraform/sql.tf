# Copyright 2026 Google LLC
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

resource "google_sql_database_instance" "postgres" {
  name             = var.db_instance_name
  database_version = "POSTGRES_17"
  region           = var.region

  settings {
    tier    = "db-f1-micro"
    edition = "ENTERPRISE"
    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.vpc.id
    }
  }

  deletion_protection = false

  depends_on = [
    google_project_service.gcp_services["sqladmin.googleapis.com"],
    google_service_networking_connection.private_vpc_connection
  ]
}

resource "google_sql_database" "databases" {
  for_each = toset(var.db_names)
  name     = each.key
  instance = google_sql_database_instance.postgres.name
}

resource "random_password" "db_password" {
  length           = 16
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "google_sql_user" "users" {
  name     = "dbuser"
  instance = google_sql_database_instance.postgres.name
  password = random_password.db_password.result # For production use Secret Manager

  depends_on = [google_sql_database.databases["employee"]]
}
