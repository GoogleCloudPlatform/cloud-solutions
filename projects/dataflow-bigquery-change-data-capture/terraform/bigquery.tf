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

resource "google_bigquery_dataset" "spanner_bigquery" {
  dataset_id    = "spanner_to_bigquery"
  friendly_name = "Demo of Spanner to BigQuery replication using CDC"
  location      = var.bigquery_dataset_location
}

resource "google_bigquery_table" "orders" {
  deletion_protection = false
  dataset_id          = google_bigquery_dataset.spanner_bigquery.dataset_id
  table_id            = "order"
  description         = "Replicated orders"
  clustering          = ["order_id"]
  table_constraints {
    primary_key { columns = ["order_id"] }
  }
  schema = <<EOF
[
  {
    "mode": "REQUIRED",
    "name": "order_id",
    "type": "INTEGER"
  },
  {
    "mode": "REQUIRED",
    "name": "status",
    "type": "STRING"
  },
  {
    "mode": "REQUIRED",
    "name": "description",
    "type": "STRING"
  }
]
EOF
}

resource "google_bigquery_table" "sync_point" {
  deletion_protection = false
  dataset_id          = google_bigquery_dataset.spanner_bigquery.dataset_id
  table_id            = "sync_point"
  description         = "Last known completed read from Spanner"
  clustering          = ["table_name"]
  table_constraints {
    primary_key { columns = ["table_name"] }
  }
  schema = <<EOF
[
  {
    "mode": "REQUIRED",
    "name": "table_name",
    "type": "STRING"
  },
  {
    "mode": "REQUIRED",
    "name": "sync_point",
    "type": "TIMESTAMP"
  }
]
EOF
}
resource "google_bigquery_dataset_iam_member" "bigquery_editor_dataflow_sa" {
  dataset_id = google_bigquery_dataset.spanner_bigquery.dataset_id
  member     = local.dataflow_sa_principal
  role       = "roles/bigquery.dataEditor"
}
