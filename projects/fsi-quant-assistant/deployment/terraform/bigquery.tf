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

resource "google_bigquery_dataset" "analyst_demo" {
  dataset_id    = "analyst_demo"
  friendly_name = "Analyst Demo Dataset"
  location      = "US"

  depends_on = [google_project_service.bigquery_googleapis_com]
}

resource "google_bigquery_dataset" "iceberg_catalog" {
  dataset_id    = "iceberg_catalog"
  friendly_name = "Iceberg Catalog Dataset"
  location      = "us-central1"

  # WARNING: This allows Terraform to delete all tables inside this dataset
  # to facilitate the location change.
  delete_contents_on_destroy = true

  depends_on = [google_project_service.bigquery_googleapis_com]
}

resource "google_bigquery_table" "watchlist" {
  dataset_id          = google_bigquery_dataset.analyst_demo.dataset_id
  table_id            = "watchlist"
  schema              = file("../bigquery/analyst_demo/table/watchlist.json")
  deletion_protection = false
}

resource "google_bigquery_connection" "iceberg" {
  connection_id = "iceberg"
  location      = "us-central1"
  friendly_name = "Iceberg Connection"
  cloud_resource {}

  depends_on = [google_project_service.bigqueryconnection_googleapis_com]
}

resource "google_bigquery_table" "order_book_snapshot" {
  dataset_id          = google_bigquery_dataset.iceberg_catalog.dataset_id
  table_id            = "order_book_snapshot"
  deletion_protection = false

  biglake_configuration {
    connection_id = google_bigquery_connection.iceberg.name
    storage_uri   = "${google_storage_bucket.iceberg_warehouse.url}/order_book_snapshot/"
    file_format   = "PARQUET"
    table_format  = "ICEBERG"
  }

  schema = file("../bigquery/iceberg_catalog/table/order_book_snapshot.json")

  depends_on = [google_storage_bucket_iam_member.iceberg_connection_access]
}

resource "google_bigquery_table" "money_movement" {
  dataset_id          = google_bigquery_dataset.iceberg_catalog.dataset_id
  table_id            = "money_movement"
  deletion_protection = false

  biglake_configuration {
    connection_id = google_bigquery_connection.iceberg.name
    storage_uri   = "${google_storage_bucket.iceberg_warehouse.url}/money_movement/"
    file_format   = "PARQUET"
    table_format  = "ICEBERG"
  }

  schema = file("../bigquery/iceberg_catalog/table/money_movement.json")

  depends_on = [google_storage_bucket_iam_member.iceberg_connection_access]
}

resource "google_bigquery_table" "trade_tape" {
  dataset_id          = google_bigquery_dataset.iceberg_catalog.dataset_id
  table_id            = "trade_tape"
  deletion_protection = false

  biglake_configuration {
    connection_id = google_bigquery_connection.iceberg.name
    storage_uri   = "${google_storage_bucket.iceberg_warehouse.url}/trade_tape/"
    file_format   = "PARQUET"
    table_format  = "ICEBERG"
  }

  schema = file("../bigquery/iceberg_catalog/table/trade_tape.json")

  depends_on = [google_storage_bucket_iam_member.iceberg_connection_access]
}

resource "null_resource" "alloydb_connection" {
  triggers = {
    project  = var.project_id
    region   = var.region
    conn_id  = "alloydb_conn"
    instance = google_alloydb_instance.default.name
    db_name  = var.alloydb_db_name
    user_id  = google_alloydb_user.bq_connector_user.user_id
    password = google_alloydb_user.bq_connector_user.password
  }

  # https://docs.cloud.google.com/bigquery/docs/connect-to-alloydb#bq
  provisioner "local-exec" {
    command = <<EOT
      bq mk --connection \
        --location=${self.triggers.region} \
        --project_id=${self.triggers.project} \
        --connector_configuration '${jsonencode({
    connector_id = "google-alloydb"
    asset = {
      database              = self.triggers.db_name
      google_cloud_resource = "//alloydb.googleapis.com/${self.triggers.instance}"
    }
    authentication = {
      username_password = {
        username = self.triggers.user_id
        password = {
          plaintext = self.triggers.password
        }
      }
    }
})}' \
        ${self.triggers.conn_id}
    EOT
}

provisioner "local-exec" {
  when    = destroy
  command = <<EOT
      bq rm --connection --force=true \
        --location=${self.triggers.region} \
        --project_id=${self.triggers.project} \
        ${self.triggers.conn_id}
    EOT
}
}

data "external" "alloydb_sa" {
  program = ["bash", "-c", <<EOT
    # 1. Get connection details in JSON format using 'bq'
    #    2>/dev/null silences "Welcome to BigQuery" messages and update warnings
    JSON_DATA=$(bq show --format=json --connection \
      --project_id=${var.project_id} \
      --location=${var.region} \
      ${null_resource.alloydb_connection.triggers.conn_id} 2>/dev/null)

    # 2. Use Python to safely parse the JSON and output the Service Account email
    #    (This avoids needing 'jq' installed on your runner)
    echo "$JSON_DATA" | python3 -c "import sys, json; print(json.dumps({'email': json.load(sys.stdin)['configuration']['authentication']['serviceAccount']}))"
  EOT
  ]

  depends_on = [null_resource.alloydb_connection]
}

resource "google_bigquery_data_transfer_config" "scheduled_trade_tape" {
  display_name   = "trade-tape"
  location       = google_bigquery_dataset.iceberg_catalog.location
  data_source_id = "scheduled_query"
  schedule       = "every 5 minutes"

  params = {
    query = templatefile("../bigquery/iceberg_catalog/queries/copy_trade_tape.sql.tftpl", {
      project_id = var.project_id,
    })
  }

  service_account_name = google_service_account.reporting_service_account.email
}

resource "google_bigquery_data_transfer_config" "scheduled_money_movement" {
  display_name   = "money-movement"
  location       = google_bigquery_dataset.iceberg_catalog.location
  data_source_id = "scheduled_query"
  schedule       = "every 5 minutes"

  params = {
    query = templatefile("../bigquery/iceberg_catalog/queries/copy_money_movement.sql.tftpl", {
      project_id = var.project_id,
    })
  }

  service_account_name = google_service_account.reporting_service_account.email
}

resource "google_bigquery_data_transfer_config" "scheduled_order_book_snapshot" {
  display_name   = "order-book-snapshot"
  location       = google_bigquery_dataset.iceberg_catalog.location
  data_source_id = "scheduled_query"
  schedule       = "every 5 minutes"

  params = {
    query = templatefile("../bigquery/iceberg_catalog/queries/copy_order_book_snapshot.sql.tftpl", {
      project_id = var.project_id,
    })
  }

  service_account_name = google_service_account.reporting_service_account.email
}
