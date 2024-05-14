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

resource "google_spanner_instance" "main" {
  config       = "regional-${var.spanner_location}"
  name         = "main"
  display_name = "main-instance"
  num_nodes    = 1
}

locals {
  orders_change_stream = "orders_changes"
}

resource "google_spanner_database" "fulfillment" {
  instance                 = google_spanner_instance.main.name
  name                     = "fulfillment"
  version_retention_period = "1d"
  ddl = [
    "CREATE TABLE orders (order_id INT64 NOT NULL, status STRING(10) NOT NULL, description STRING(64) NOT NULL) PRIMARY KEY(order_id)",
    "CREATE CHANGE STREAM ${local.orders_change_stream} FOR orders OPTIONS ( value_capture_type = 'NEW_ROW' )"
  ]
  deletion_protection = false
}

resource "google_spanner_database_iam_member" "dataflow_sa_editor" {
  database = google_spanner_database.fulfillment.name
  instance = google_spanner_instance.main.name
  member   = local.dataflow_sa_principal
  role     = "roles/spanner.databaseUser"
}
