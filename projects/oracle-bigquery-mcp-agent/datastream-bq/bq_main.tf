terraform {
  required_version = ">= 1.3.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.14"
    }

  }
}



# Dynamically queries the compute instance metadata properties to extract the live internal private IP address, preventing static configuration mismatches.
data "google_compute_instance" "oracle_vm" {
  name    = var.oracle_vm_name
  zone    = var.zone
  project = var.project_id
}

# Establishes a private VPC peering link for GCP Datastream, ensuring replication queries route completely privately and securely inside the VPC.
resource "google_datastream_private_connection" "oracle_priv_vpc_conn" {
  display_name          = "Datastream Private Connection"
  private_connection_id = "oracle-priv-vpc-conn"
  location              = var.region
  project               = var.project_id

  vpc_peering_config {
    vpc    = "projects/${var.project_id}/global/networks/${var.vpc_name}"
    subnet = var.datastream_private_ip_range
  }

  depends_on = [
    google_project_service.datastream_api
  ]
}

# Authorizes inbound TCP ingress on Port 1521 strictly from the Datastream private connection IP range, blocking any external DB network scans.
resource "google_compute_firewall" "allow_datastream_to_oracle" {
  name    = "allow-datastream-to-oracle"
  network = var.vpc_name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["1521"]
  }

  source_ranges = [var.datastream_private_ip_range]
  target_tags   = ["oracle-server"]
}

# Declares the BigQuery target dataset to house all replicated database transactions, ensuring geographical alignment with replication pipelines.
resource "google_bigquery_dataset" "oracle_to_bq" {
  dataset_id = "oracle_ledger_sync"
  location   = var.region
  project    = var.project_id
  # WARNING: delete_contents_on_destroy = true is configured for clean teardowns in this demo environment.
  # In production environments, toggle this to false to prevent accidental data loss of historical records!
  delete_contents_on_destroy = true

  depends_on = [
    google_project_service.bigquery_api
  ]
}

# Defines the source connection profile representing the Oracle 19c server, authorizing secure DBA replica credentials.
resource "google_datastream_connection_profile" "source_oracle" {
  display_name          = "Oracle 19c Source Profile"
  connection_profile_id = "ora19c-source-profile"
  location              = var.region
  project               = var.project_id

  oracle_profile {
    hostname         = data.google_compute_instance.oracle_vm.network_interface[0].network_ip
    port             = 1521
    username         = var.oracle_db_user
    password         = var.db_password
    database_service = "ORCLPDB1"
  }

  private_connectivity {
    private_connection = google_datastream_private_connection.oracle_priv_vpc_conn.id
  }
}

# Establishes the target BigQuery connection profile, enabling Datastream to output stream transactions into BigQuery datasets.
resource "google_datastream_connection_profile" "dest_bq" {
  display_name          = "BigQuery Destination Profile"
  connection_profile_id = "bq-dest-profile"
  location              = var.region
  project               = var.project_id
  bigquery_profile {}
}

# Instantiates the streaming Datastream CDC replication pipeline, continuously mirroring transaction logs from Oracle to BigQuery.
resource "google_datastream_stream" "oracle_to_bq_stream" {
  display_name  = "Oracle 19c to BigQuery Ledger Stream"
  stream_id     = "ora19c-to-bq-ledger"
  location      = var.region
  project       = var.project_id
  desired_state = "RUNNING"

  source_config {
    source_connection_profile = google_datastream_connection_profile.source_oracle.id
    oracle_source_config {
      include_objects {
        oracle_schemas {
          schema = var.oracle_schema
        }
      }
    }
  }

  destination_config {
    destination_connection_profile = google_datastream_connection_profile.dest_bq.id
    bigquery_destination_config {
      data_freshness = "15s"
      single_target_dataset {
        dataset_id = google_bigquery_dataset.oracle_to_bq.id
      }
    }
  }

  backfill_all {}

  depends_on = [
    google_datastream_private_connection.oracle_priv_vpc_conn
  ]
}

# Pauses execution to allow asynchronous CDC backfill worker threads to fully mirror baseline database tables to BigQuery.
resource "time_sleep" "wait_for_datastream_backfill" {
  depends_on      = [google_datastream_stream.oracle_to_bq_stream]
  create_duration = "300s"
}

# --- 7. SEMANTIC LAYER: EXECUTIVE VIEW ---
# Builds the consolidated executive ledger reporting view, joining raw replicated transaction tables dynamically.
resource "google_bigquery_table" "vw_executive_ledger" {
  dataset_id          = google_bigquery_dataset.oracle_to_bq.dataset_id
  table_id            = "vw_executive_ledger"
  project             = var.project_id
  deletion_protection = false

  view {
    query = templatefile("${path.module}/templates/vw_executive_ledger.sql.tpl", {
      project_id    = var.project_id
      dataset_id    = google_bigquery_dataset.oracle_to_bq.dataset_id
      oracle_schema = var.oracle_schema
    })
    use_legacy_sql = false
  }

  depends_on = [time_sleep.wait_for_datastream_backfill]
}

# --- 8. PREDICTIVE LAYER: BIGQUERY ML MODEL ---
# Compiles and trains the BigQuery ML spend forecast model natively inside the project.
resource "google_bigquery_job" "compile_ml_model" {
  job_id = "compile_spend_forecast_v2_${md5(templatefile("${path.module}/templates/spend_forecast_model.sql.tpl", {
    project_id = var.project_id
    dataset_id = google_bigquery_dataset.oracle_to_bq.dataset_id
  }))}_${google_bigquery_dataset.oracle_to_bq.creation_time}"
  project  = var.project_id
  location = var.region

  query {
    query = templatefile("${path.module}/templates/spend_forecast_model.sql.tpl", {
      project_id = var.project_id
      dataset_id = google_bigquery_dataset.oracle_to_bq.dataset_id
    })
    use_legacy_sql = false
    # Overriding defaults to empty strings is required for DDL/DML queries (like CREATE MODEL)
    # that do not write results to a destination table, preventing API validation errors.
    create_disposition = ""
    write_disposition  = ""
  }

  depends_on = [google_bigquery_table.vw_executive_ledger]
}

# Pauses execution to allow the BigQuery ML ARIMA model training job to complete in the background.
resource "time_sleep" "wait_for_ml_model" {
  depends_on      = [google_bigquery_job.compile_ml_model]
  create_duration = "30s"
}

# --- 9. PREDICTIVE LAYER: 180-DAY FORECAST VIEW ---
# Builds the predictive spend forecasting view, overlaying actual historical spend with ARIMA_PLUS forecasted values.
resource "google_bigquery_table" "vw_spend_forecast" {
  dataset_id          = google_bigquery_dataset.oracle_to_bq.dataset_id
  table_id            = "vw_spend_forecast"
  project             = var.project_id
  deletion_protection = false

  view {
    query = templatefile("${path.module}/templates/vw_spend_forecast.sql.tpl", {
      project_id = var.project_id
      dataset_id = google_bigquery_dataset.oracle_to_bq.dataset_id
    })
    use_legacy_sql = false
  }

  depends_on = [time_sleep.wait_for_ml_model]
}
