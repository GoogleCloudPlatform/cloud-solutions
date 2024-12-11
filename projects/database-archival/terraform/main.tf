# Copyright 2024 Google LLC
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


terraform {
  required_version = ">= 1.5.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "6.13.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

## Compute Project number from Project Id.
data "google_project" "gcp_project_info" {
  project_id = var.project_id
}

## Enable required APIs.
resource "google_project_service" "enable_required_services" {
  project            = var.project_id
  disable_on_destroy = false
  for_each = toset([
    "cloudresourcemanager.googleapis.com",
    "bigquery.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudfunctions.googleapis.com",
    "composer.googleapis.com",
    "compute.googleapis.com",
    "datastream.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "servicenetworking.googleapis.com",
    "sql-component.googleapis.com",
    "sqladmin.googleapis.com",
    "storage-component.googleapis.com",
    "storage.googleapis.com",
    "vpcaccess.googleapis.com",
  ])
  service = each.key
}

locals {
  gcs_bucket_name = "${var.project_id}-db-archival-bucket"
}

## Create Service Account for the Database Archival tool and assign roles/permissions.
resource "google_service_account" "db_archival_sa" {
  account_id  = var.service_account_name
  project     = var.project_id
  description = "Service Account for Database Archival tool"
  depends_on  = [google_project_service.enable_required_services]
}

## Assign Roles to the SA.
resource "google_project_iam_member" "assign_sa_roles" {
  for_each = toset([
    "roles/bigquery.dataEditor",
    "roles/bigquery.jobUser",
    "roles/cloudfunctions.invoker",
    "roles/cloudsql.client",
    "roles/cloudsql.editor",
    "roles/cloudsql.instanceUser",
    "roles/composer.worker",
    "roles/compute.admin",
    "roles/run.invoker",
    "roles/secretmanager.secretAccessor",
    "roles/storage.objectAdmin",
    "roles/storage.objectCreator",
    "roles/storage.objectUser",
    "roles/storage.objectViewer",
    "roles/logging.logWriter",
  ])
  role    = each.key
  member  = "serviceAccount:${google_service_account.db_archival_sa.email}"
  project = var.project_id
}

## Create VPC network.
resource "google_compute_network" "db_archival_network" {
  depends_on              = [google_project_service.enable_required_services]
  project                 = var.project_id
  name                    = "db-archival-vpc"
  description             = "VPC network for Database Archival workloads"
  auto_create_subnetworks = true
  mtu                     = 1460
  routing_mode            = "REGIONAL"
}


## Create Private Subnetwork for Composer.
locals {
  composer_subnet = "10.8.0.0/28"
}

resource "google_compute_subnetwork" "composer_subnet" {
  name          = "db-archival-composer-subnet"
  ip_cidr_range = local.composer_subnet
  region        = var.region
  project       = var.project_id
  network       = google_compute_network.db_archival_network.id

  private_ip_google_access = true
}

# Private Service Access components to allow connectivity between Datastream and Cloud SQL.
resource "google_compute_global_address" "private_ip_alloc" {
  name          = "private-ip-alloc"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.db_archival_network.id
}
resource "google_service_networking_connection" "private_vpc_connection" {
  depends_on = [
    google_compute_network.db_archival_network,
    google_compute_global_address.private_ip_alloc,
    google_project_service.enable_required_services,
  ]

  network                 = google_compute_network.db_archival_network.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_alloc.name]
}

## Create Firewalls.
locals {
  datastream_subnet_cidr = "10.0.0.0/29"
}
resource "google_compute_firewall" "allow_datastream_to_natvm" {
  depends_on = [
    google_datastream_private_connection.private_connection
  ]
  project = var.project_id
  name    = "allow-datastream-to-natvm"
  network = google_compute_network.db_archival_network.id

  allow {
    protocol = "tcp"
    ports    = ["3306"]
  }
  source_ranges = [local.datastream_subnet_cidr]
  direction     = "INGRESS"
  priority      = 1000
}

resource "google_compute_firewall" "vpc_allow_https" {
  depends_on = [google_compute_network.db_archival_network]

  project     = var.project_id
  name        = "db-archival-vpc-allow-https"
  network     = "projects/${var.project_id}/global/networks/${google_compute_network.db_archival_network.name}"
  description = <<-EOT
Allows SSL connections from any source to any instance
on the network using port 443.
EOT
  priority    = 65534

  allow {
    protocol = "tcp"
    ports    = ["443"]
  }
  source_ranges = ["0.0.0.0/0"]
}

locals {
  vpc_allowed_tcp_udp_ranges = ["10.8.0.0/28"]
}

resource "google_compute_firewall" "vpc_allow_internal" {
  depends_on = [google_compute_network.db_archival_network]

  project     = var.project_id
  name        = "db-archival-vpc-allow-internal"
  network     = "projects/${var.project_id}/global/networks/${google_compute_network.db_archival_network.name}"
  description = "Allow internal traffic on the default network"
  priority    = 65534
  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }
  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }

  source_ranges = local.vpc_allowed_tcp_udp_ranges
}

resource "google_compute_instance" "nat-vm" {
  depends_on = [
    google_compute_firewall.allow_datastream_to_natvm
  ]
  project      = var.project_id
  name         = "nat-vm"
  machine_type = "e2-micro"
  zone         = "${var.region}-a"

  tags = ["nat-vm-proxy"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-11"
    }
  }

  network_interface {
    network = google_compute_network.db_archival_network.id
  }

  metadata = {
    # gce-container-declaration = module.gce-container.metadata_value
    google-logging-enabled    = "true"
    google-monitoring-enabled = "true"
  }

  metadata_startup_script = <<-EOT
  #! /bin/bash

  export DB_ADDR="${google_sql_database_instance.db-archival_sql_instance.private_ip_address}"
  export DB_PORT=3306

  # Enable the VM to receive packets whose destinations do
  # not match any running process local to the VM
  echo 1 > /proc/sys/net/ipv4/ip_forward

  # Ask the Metadata server for the IP address of the VM nic0
  # network interface:
  md_url_prefix="http://169.254.169.254/computeMetadata/v1/instance"
  vm_nic_ip="$(curl -H "Metadata-Flavor: Google" $md_url_prefix/network-interfaces/0/ip)"

  # Clear any existing iptables NAT table entries (all chains):
  iptables -t nat -F

  # Create a NAT table entry in the prerouting chain, matching
  # any packets with destination database port, changing the destination
  # IP address of the packet to the SQL instance IP address:
  iptables -t nat -A PREROUTING \
      -p tcp --dport $DB_PORT \
      -j DNAT \
      --to-destination $DB_ADDR

  # Create a NAT table entry in the postrouting chain, matching
  # any packets with destination database port, changing the source IP
  # address of the packet to the NAT VM's primary internal IPv4 address:
  iptables -t nat -A POSTROUTING \
      -p tcp --dport $DB_PORT \
      -j SNAT \
      --to-source $vm_nic_ip

  # Save iptables configuration:
  iptables-save
  EOT

  service_account {
    scopes = ["cloud-platform"]
    email  = google_service_account.db_archival_sa.email
  }
}

## Create a Secret in Secret Manager to store the database password.
resource "google_secret_manager_secret" "database_password" {
  depends_on = [google_project_service.enable_required_services]
  secret_id  = "db-archival-db-password"
  project    = var.project_id
  replication {
    user_managed {
      replicas {
        location = var.region
      }
      replicas {
        location = "us-central1"
      }
    }
  }
}

## Add the password as a Secret Version.
resource "google_secret_manager_secret_version" "database_password_version" {
  secret_data = var.database_user_password
  secret      = google_secret_manager_secret.database_password.id
}

## Grant the db_archival_sa service account access to the secret.
resource "google_secret_manager_secret_iam_member" "db_archival_sa_secret_access" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.database_password.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.db_archival_sa.email}"
}

## Create Cloud SQL Instance.
resource "google_sql_database_instance" "db-archival_sql_instance" {
  depends_on = [
    google_service_networking_connection.private_vpc_connection,
    google_project_service.enable_required_services,
    google_secret_manager_secret_version.database_password_version,
  ]
  name             = "private-db-archival-db"
  region           = var.region
  database_version = "MYSQL_8_0"
  settings {
    tier = "db-f1-micro"
    ip_configuration {
      ipv4_enabled                                  = false
      private_network                               = google_compute_network.db_archival_network.self_link
      enable_private_path_for_google_cloud_services = true # Private Service Access flag
    }
    backup_configuration {
      binary_log_enabled = true
      enabled            = true
    }
  }
  root_password       = google_secret_manager_secret_version.database_password_version.secret_data
  deletion_protection = false
}

resource "google_sql_database" "database_name" {
  name     = "db_archival_demo"
  instance = google_sql_database_instance.db-archival_sql_instance.name
}

resource "google_sql_user" "db_archival_user" {
  depends_on = [google_sql_database_instance.db-archival_sql_instance]
  name       = var.database_user_name
  instance   = google_sql_database_instance.db-archival_sql_instance.name
  password   = var.database_user_password
}

## Create a BigQuery dataset.
resource "google_bigquery_dataset" "db_archival_bq_dataset" {
  dataset_id                 = "db_archival_bq_dataset"
  location                   = var.region
  delete_contents_on_destroy = true
}

## Give the Database Archival service account access to the BigQuery dataset.
resource "google_bigquery_dataset_access" "db_archival_sa_access_dataeditor" {
  dataset_id = google_bigquery_dataset.db_archival_bq_dataset.dataset_id
  for_each = toset([
    "roles/bigquery.admin",
  ])
  role          = each.key
  user_by_email = google_service_account.db_archival_sa.email
}

## Create GCS placeholder.
resource "google_storage_bucket" "db-archival-main-bucket" {
  name = local.gcs_bucket_name

  project  = var.project_id
  location = var.region

  force_destroy               = true
  public_access_prevention    = "enforced"
  uniform_bucket_level_access = true

  depends_on = [google_project_service.enable_required_services]
}

resource "google_storage_bucket_object" "upload_sample_data" {
  depends_on = [
    data.archive_file.local_source,
    google_storage_bucket.db-archival-main-bucket,
  ]
  content_type = "application/zip"
  name         = "mysql_sqldump.sql.gz"
  bucket       = google_storage_bucket.db-archival-main-bucket.name
  source       = abspath("../demo/mysql_sqldump.sql.gz")
}

locals {
  fqdn_database_name = "${var.project_id}:${var.region}:${google_sql_database_instance.db-archival_sql_instance.name}"
}

## Token replace sample_config.json file.
resource "null_resource" "replace_config_file" {
  depends_on = [
    google_sql_database_instance.db-archival_sql_instance,
    google_storage_bucket.db-archival-main-bucket,
    google_sql_database.database_name,
  ]

  provisioner "local-exec" {
    command = <<-EOT
      sed -r -e "s/\\$\{REGION\}/${var.region}/g" \
      -e "s/\\$\{PROJECT_ID\}/${var.project_id}/g" \
      -e "s/\\$\{BIGQUERY_DATASET\}/${google_bigquery_dataset.db_archival_bq_dataset.dataset_id}/g" \
      -e "s/\\$\{CLOUD_SQL_INSTANCE_NAME\}/${local.fqdn_database_name}/g" \
      -e "s/\\$\{CLOUD_SQL_DATABASE_NAME\}/${google_sql_database.database_name.name}/g" \
      -e "s/\\$\{CLOUD_SQL_USER_NAME\}/${var.database_user_name}/g" \
      -e "s:\\$\{CLOUD_SQL_PASSWORD_SECRET\}:${google_secret_manager_secret_version.database_password_version.name}:g" \
      ../demo/sample_config.json > temp/config.json
    EOT
  }
}

resource "google_storage_bucket_object" "upload_config_file" {
  depends_on = [
    google_storage_bucket.db-archival-main-bucket,
    null_resource.replace_config_file
  ]
  source       = abspath("../terraform/temp/config.json")
  name         = "config.json" # target subfolder and rename at the same time
  bucket       = google_storage_bucket.db-archival-main-bucket.name
  content_type = "application/json"
}

## Assign SA of SQL instance permission for bucket access
resource "google_project_iam_member" "assign_db_sa_roles" {
  depends_on = [google_sql_database_instance.db-archival_sql_instance]
  for_each = toset([
    "roles/cloudsql.client",
    "roles/storage.admin",
  ])
  role    = each.key
  member  = "serviceAccount:${google_sql_database_instance.db-archival_sql_instance.service_account_email_address}"
  project = var.project_id
}

## Ingest sample data into the database.
resource "null_resource" "ingest_sample_data" {
  depends_on = [
    google_sql_database_instance.db-archival_sql_instance,
    google_project_iam_member.assign_db_sa_roles,
    google_storage_bucket_object.upload_sample_data,
    google_project_service.enable_required_services,
  ]

  provisioner "local-exec" {
    command = <<-EOT
      gcloud sql import sql ${google_sql_database_instance.db-archival_sql_instance.name} \
      gs://${google_storage_bucket.db-archival-main-bucket.name}/mysql_sqldump.sql.gz \
      --database=${google_sql_database.database_name.name} \
      --quiet
    EOT
  }
}

## Create Cloud Function (pruning_function).
locals {
  files_to_copy = {
    "../src/database_archival/common/" : "database_archival/",
    "../src/database_archival/pruning_function/" : "database_archival/",
    "../src/database_archival/pruning_function/main.py" : "main.py",
    "../src/database_archival/pruning_function/requirements.in" : "requirements.txt"
  }
  # Create a temporary directory to store copied files
  temp_dir           = "${path.module}/temp"
  cf_zip_output_path = "${path.module}/output"
}

# Create the temporary directory if it doesn't exist
resource "null_resource" "create_dirs" {
  for_each = { "dummy" : 1 } # Workaround for using file functions with null_resource

  provisioner "local-exec" {
    command = <<-EOF
      mkdir -p ${abspath(local.temp_dir)}/database_archival/common
      mkdir -p ${abspath(local.temp_dir)}/database_archival/pruning_function
      mkdir -p ${abspath(local.cf_zip_output_path)}
      EOF
  }
}

## Copy files locally
resource "null_resource" "copy_files_locally" {
  for_each = local.files_to_copy

  depends_on = [null_resource.create_dirs]

  provisioner "local-exec" {
    command = "cp -r ${abspath(each.key)} ${local.temp_dir}/${each.value}"
  }
}

data "archive_file" "local_source" {
  depends_on  = [null_resource.copy_files_locally]
  type        = "zip"
  source_dir  = abspath("${abspath(local.temp_dir)}")
  output_path = "${local.cf_zip_output_path}/db_archival.zip"
  excludes = [".git", ".github", ".DS_Store", ".vscode",
    "kubernetes", "node_modules", "resources", "terraform"
  ]
}

resource "google_storage_bucket_object" "db_archival_source_code_bucket" {
  depends_on = [
    data.archive_file.local_source,
    google_storage_bucket.db-archival-main-bucket
  ]
  content_type = "application/zip"
  name         = "db_archival.zip"
  bucket       = google_storage_bucket.db-archival-main-bucket.name
  source       = "${local.cf_zip_output_path}/db_archival.zip"
}

# IAM entry for all users to invoke the function.
resource "google_cloudfunctions2_function_iam_member" "invoker" {
  project        = google_cloudfunctions2_function.prune_function.project
  location       = google_cloudfunctions2_function.prune_function.location
  cloud_function = google_cloudfunctions2_function.prune_function.name

  role   = "roles/cloudfunctions.invoker"
  member = "serviceAccount:${google_service_account.db_archival_sa.email}"
}

## Serverless VPC connector to allow access to Cloud SQL - Cloud Function.
locals {
  vpc_connector_cidr = "10.8.1.0/28"
}
resource "google_vpc_access_connector" "vpc_connector" {
  depends_on = [
    google_compute_network.db_archival_network,
  ]
  name          = "db-archival-vpc-connector"
  region        = var.region
  project       = var.project_id
  network       = google_compute_network.db_archival_network.name
  ip_cidr_range = local.vpc_connector_cidr
  min_instances = 2
  max_instances = 5
}

resource "google_cloudfunctions2_function" "prune_function" {
  depends_on = [
    google_vpc_access_connector.vpc_connector,
    google_project_service.enable_required_services,
    google_service_account.db_archival_sa,
    google_storage_bucket_object.db_archival_source_code_bucket,
    google_storage_bucket.db-archival-main-bucket
  ]
  name     = "prune-data"
  project  = var.project_id
  location = var.region

  build_config {
    runtime         = "python39"
    entry_point     = "request_handler"
    service_account = "projects/${var.project_id}/serviceAccounts/${google_service_account.db_archival_sa.email}"

    source {
      storage_source {
        bucket = google_storage_bucket.db-archival-main-bucket.name
        object = google_storage_bucket_object.db_archival_source_code_bucket.name
      }
    }
  }

  service_config {
    max_instance_count    = 100
    available_memory      = "2048M"
    timeout_seconds       = 3600
    ingress_settings      = "ALLOW_ALL"
    service_account_email = google_service_account.db_archival_sa.email
    vpc_connector         = google_vpc_access_connector.vpc_connector.name
  }
}

## Configure Composer's DAG.
resource "google_composer_environment" "db_archival_composer" {
  provider = google-beta
  depends_on = [
    google_storage_bucket.db-archival-main-bucket,
    google_compute_subnetwork.composer_subnet,
    google_service_account.db_archival_sa,
    google_cloudfunctions2_function.prune_function,
  ]
  timeouts {
    create = "120m"
    update = "120m"
    delete = "120m"
  }
  name    = "db-archival-composer-env"
  project = var.project_id
  region  = var.region

  config {
    enable_private_environment = true
    node_config {
      network         = google_compute_network.db_archival_network.id
      subnetwork      = google_compute_subnetwork.composer_subnet.id
      service_account = google_service_account.db_archival_sa.email
    }
    software_config {
      image_version = "composer-3-airflow-2"
      env_variables = {
        DATA_ARCHIVAL_CONFIG_PATH        = "gs://${google_storage_bucket.db-archival-main-bucket.name}/config.json"
        CLOUD_FUNCTION_URL_DATA_DELETION = google_cloudfunctions2_function.prune_function.service_config[0].uri
      }
    }
  }
}

# Upload DAGs and common files to the Composer GCS bucket.
resource "google_storage_bucket_object" "upload_dags_files" {
  for_each = fileset(abspath("../src/database_archival"), "**/*.py")
  source   = abspath("../src/database_archival/${each.key}")
  name     = "dags/database_archival/${each.value}"
  bucket = replace(replace(
    google_composer_environment.db_archival_composer.config.0.dag_gcs_prefix
  , "gs://", ""), "/dags", "")
  content_type = "text/x-python"

  depends_on = [google_composer_environment.db_archival_composer]
}

## Set up Datastream.
resource "google_datastream_private_connection" "private_connection" {
  display_name          = "Datastream private connection"
  location              = var.region
  private_connection_id = "datastream-db-archival-private-connection"

  labels = {
    key = "value"
  }
  vpc_peering_config {
    vpc    = google_compute_network.db_archival_network.id
    subnet = local.datastream_subnet_cidr
  }
}

resource "google_datastream_connection_profile" "source_connection_profile" {
  depends_on = [
    google_datastream_private_connection.private_connection,
    google_project_service.enable_required_services,
  ]
  display_name          = "source-connection-profile"
  location              = var.region
  connection_profile_id = "db-archival-source-connection-profile"

  mysql_profile {
    hostname = google_compute_instance.nat-vm.network_interface[0].network_ip
    port     = 3306
    username = google_sql_user.db_archival_user.name
    password = google_sql_user.db_archival_user.password
  }

  private_connectivity {
    private_connection = google_datastream_private_connection.private_connection.id
  }
}

resource "google_datastream_connection_profile" "destination_connection_profile" {
  depends_on            = [google_project_service.enable_required_services]
  display_name          = "destination-connection-profile"
  location              = var.region
  connection_profile_id = "db-archival-destination-connection-profile"

  bigquery_profile {}
}

resource "google_datastream_stream" "db-archival-datastream" {
  depends_on = [
    google_bigquery_dataset.db_archival_bq_dataset,
    google_sql_database_instance.db-archival_sql_instance,
  ]
  stream_id     = "db-archival-datastream"
  location      = var.region
  display_name  = "db-archival-datastream"
  desired_state = "RUNNING"

  source_config {
    source_connection_profile = google_datastream_connection_profile.source_connection_profile.id
    mysql_source_config {
      include_objects {
        mysql_databases {
          database = google_sql_database.database_name.name
          mysql_tables {
            table = "User"
          }
          mysql_tables {
            table = "Transaction"
          }
        }

      }
    }
  }
  destination_config {
    destination_connection_profile = google_datastream_connection_profile.destination_connection_profile.id
    bigquery_destination_config {
      single_target_dataset {
        dataset_id = "projects/${var.project_id}/datasets/${google_bigquery_dataset.db_archival_bq_dataset.dataset_id}"
      }
    }
  }

  backfill_all {
  }
}
