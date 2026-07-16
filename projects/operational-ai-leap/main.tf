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

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google-beta"
      version = ">= 5.45.2"
    }
    local = {
      source  = "hashicorp/local"
      version = ">= 2.9.0"
    }
    null = {
      source  = "hashicorp/null"
      version = ">= 3.3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.9.0"
    }
    external = {
      source  = "hashicorp/external"
      version = ">= 2.4.0"
    }
    http = {
      source  = "hashicorp/http"
      version = "~> 3.6"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.14"
    }
  }
}

# Detect active project ID via gcloud if not explicitly passed
data "external" "gcloud_project" {
  program = ["sh", "-c", "echo \"{\\\"project\\\": \\\"$(gcloud config get-value project 2>/dev/null)\\\"}\""]
}

# Detect active caller account across key files, gcloud, and metadata server
data "external" "caller_identity" {
  program = ["sh", "-c", <<-EOT
    email=""
    if [ -n "$GOOGLE_APPLICATION_CREDENTIALS" ] && [ -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
      email=$(grep -o '"client_email": *"[^"]*"' "$GOOGLE_APPLICATION_CREDENTIALS" | sed 's/"client_email": *"//;s/"//' | head -n 1)
    fi
    if [ -z "$email" ] && command -v gcloud >/dev/null 2>&1; then
      email=$(gcloud config get-value account 2>/dev/null)
    fi
    if [ -z "$email" ] && command -v curl >/dev/null 2>&1; then
      email=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email 2>/dev/null || true)
    fi
    echo "{\"email\": \"$email\"}"
  EOT
  ]
}

locals {
  gcp_project_id = var.gcp_project_id != "" ? var.gcp_project_id : data.external.gcloud_project.result["project"]
  caller_email   = data.external.caller_identity.result["email"]
  caller_member  = length(regexall("gserviceaccount\\.com$", local.caller_email)) > 0 ? "serviceAccount:${local.caller_email}" : "user:${local.caller_email}"
}

# Configure the Google Cloud provider
provider "google" {
  project = local.gcp_project_id
  region  = var.gcp_region
}

# Get authentication token for the local-exec provisioner
data "google_client_config" "current" {}

# Automatically bootstrap missing CLI dependencies (psql, gcloud) on runner containers
resource "null_resource" "bootstrap_runner" {
  provisioner "local-exec" {
    command = <<-EOT
      export PATH=$PATH:/usr/local/bin:/usr/bin:/bin:/google/google-cloud-sdk/bin:/usr/lib/google-cloud-sdk/bin

      if ! command -v psql >/dev/null 2>&1; then
        echo "Installing postgresql-client on runner..."
        if command -v apt-get >/dev/null 2>&1; then
          apt-get update -qq && apt-get install -y -qq postgresql-client
        elif command -v apk >/dev/null 2>&1; then
          apk add --no-cache postgresql-client
        elif command -v yum >/dev/null 2>&1; then
          yum install -y -q postgresql
        fi
      fi

      if ! command -v gcloud >/dev/null 2>&1; then
        echo "Installing Google Cloud CLI on runner..."
        if command -v apt-get >/dev/null 2>&1; then
          apt-get update -qq && apt-get install -y -qq curl gnupg
          echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list
          curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key --keyring /usr/share/keyrings/cloud.google.gpg add - >/dev/null 2>&1
          apt-get update -qq && apt-get install -y -qq google-cloud-cli
        elif command -v apk >/dev/null 2>&1; then
          apk add --no-cache curl python3 bash
          curl -sSL https://sdk.cloud.google.com | bash
        fi
      fi

      # Ensure gcloud CLI is authenticated with the active service account credentials
      if [ -n "$GOOGLE_APPLICATION_CREDENTIALS" ] && [ -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
        echo "Activating gcloud service account from GOOGLE_APPLICATION_CREDENTIALS..."
        gcloud auth activate-service-account --key-file="$GOOGLE_APPLICATION_CREDENTIALS" --quiet 2>/dev/null || true
      fi

      echo "=== Active Google Cloud CLI Credential & Project ==="
      gcloud auth list
      gcloud config list --format="value(core.account, core.project)" || true
      echo "===================================================="
    EOT
  }
}

# Enable the required Google Cloud APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "aiplatform.googleapis.com",
    "bigquery.googleapis.com",
    "bigquerydatatransfer.googleapis.com",
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "alloydb.googleapis.com",
    "logging.googleapis.com",
    "storage-component.googleapis.com",
    "serviceusage.googleapis.com",
    "networkmanagement.googleapis.com",
    "servicenetworking.googleapis.com",
    "dns.googleapis.com",
    "vpcaccess.googleapis.com",
    "iam.googleapis.com",
    "compute.googleapis.com",
    "networkconnectivity.googleapis.com",
    "notebooks.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudtrace.googleapis.com",
    "monitoring.googleapis.com",
    "iap.googleapis.com"
  ])
  service                    = each.key
  disable_dependent_services = true
}

# Access the project data object
data "google_project" "project" {
  project_id = local.gcp_project_id
}

# Get execution environment IP for network security rules
data "http" "my_ip" {
  url = "https://api.ipify.org?format=json"
}

locals {
  my_ip = jsondecode(data.http.my_ip.response_body).ip
}

# Override the Argolis policies
resource "null_resource" "override_argolis_policies" {
  count      = var.argolis ? 1 : 0
  depends_on = [google_project_service.apis]

  provisioner "local-exec" {
    command = <<-EOT
      # Update org policies
      echo "Updating org policies"
      declare -a policies=("constraints/run.allowedIngress"
        "constraints/iam.allowedPolicyMemberDomains"
        "constraints/compute.vmExternalIpAccess"
      )
      for policy in "$${policies[@]}"; do
        cat <<EOF >new_policy.yaml
      constraint: $policy
      listPolicy:
        allValues: ALLOW
      EOF
        gcloud resource-manager org-policies set-policy new_policy.yaml --project="${local.gcp_project_id}"
      done

      rm new_policy.yaml

      # Wait for policies to apply
      echo "Waiting 90 seconds for Org policies to apply..."
      sleep 90
    EOT
  }
}

# Create a custom VPC
resource "google_compute_network" "demo_vpc" {
  name                    = "demo-vpc"
  auto_create_subnetworks = true
  mtu                     = 1460
  routing_mode            = "REGIONAL"
  depends_on              = [google_project_service.apis]
}

# Create a Cloud Router
resource "google_compute_router" "router" {
  name    = "nat-router"
  network = google_compute_network.demo_vpc.id
  region  = var.gcp_region
}

# Create a Cloud NAT Gateway
resource "google_compute_router_nat" "nat" {
  name                               = "managed-nat-gateway"
  router                             = google_compute_router.router.name
  region                             = google_compute_router.router.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

# Create firewall rule for IAP internal traffic
resource "google_compute_firewall" "iap_internal_communication" {
  name    = "allow-iap-internal"
  network = google_compute_network.demo_vpc.name
  project = local.gcp_project_id

  allow {
    protocol = "all"
  }

  source_ranges = ["35.235.240.0/20"]
  direction     = "INGRESS"
  priority      = 1000 # You can adjust the priority if needed. Lower numbers have higher precedence.
  description   = "Allows internal TCP communication for IAP."
}

# Reserve a private IP range for service networking
resource "google_compute_global_address" "private_ip_alloc" {
  name          = "private-ip-alloc"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.demo_vpc.id
}

# Create a private VPC connection
resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.demo_vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_alloc.name]
}

# Generate a secure random password if one is not provided
resource "random_password" "alloydb_password" {
  length      = 16
  special     = false
  min_upper   = 2
  min_lower   = 2
  min_numeric = 2
}

locals {
  alloydb_password = var.alloydb_password != "" ? var.alloydb_password : random_password.alloydb_password.result
}

# Create an AlloyDB cluster with PSA
resource "google_alloydb_cluster" "default" {
  cluster_id      = var.alloydb_cluster_id
  location        = var.gcp_region
  deletion_policy = "FORCE"
  project         = local.gcp_project_id
  initial_user {
    password = local.alloydb_password
  }
  continuous_backup_config {
    enabled = false
  }
  automated_backup_policy {
    enabled = false
  }
  network_config {
    network            = google_compute_network.demo_vpc.id
    allocated_ip_range = google_compute_global_address.private_ip_alloc.name
  }
  depends_on = [
    google_project_service.apis,
    google_service_networking_connection.private_vpc_connection
  ]
}

# Create a single-zone AlloyDB instance with PSA
resource "google_alloydb_instance" "primary" {
  depends_on = [
    null_resource.override_argolis_policies,
    google_project_iam_member.project_alloydb_sa_roles
  ]

  cluster           = google_alloydb_cluster.default.name
  instance_id       = var.alloydb_instance_id
  instance_type     = "PRIMARY"
  availability_type = "ZONAL"
  machine_config {
    cpu_count = 2
  }
  database_flags = {
    "google_columnar_engine.enabled"                = "on"
    "google_columnar_engine.enable_vectorized_join" = "on"
    "google_ml_integration.enable_model_support"    = "on"
    "google_ml_integration.enable_ai_query_engine"  = "on"
    "bigquery_fdw.enabled"                          = "on"
    "password.enforce_complexity"                   = "on"
    "password.min_uppercase_letters"                = "1"
    "password.min_numerical_chars"                  = "1"
    "password.min_pass_length"                      = "10"
  }
  client_connection_config {
    ssl_config {
      ssl_mode = "ALLOW_UNENCRYPTED_AND_ENCRYPTED"
    }
  }
  #  Public IP configuration
  network_config {
    enable_public_ip = false
  }

}

# Diagnostic provisioner to log execution environment details after runner CLI bootstrap and AlloyDB readiness
resource "null_resource" "log_execution_environment" {
  depends_on = [
    null_resource.bootstrap_runner,
    google_alloydb_instance.primary
  ]

  triggers = {
    always_run = timestamp()
  }

  provisioner "local-exec" {
    command = <<-EOT
      echo "========================================================================="
      echo "=== TERRAFORM EXECUTION ENVIRONMENT DIAGNOSTICS ==="
      echo "1. HOSTNAME: $(hostname 2>/dev/null || echo 'Unknown')"
      echo "2. OS INFORMATION:"
      if [ -f /etc/os-release ]; then
        cat /etc/os-release | grep -E '^(NAME|VERSION|PRETTY_NAME)=' || true
      else
        uname -a
      fi
      echo "3. TOOL LOCATIONS & VERSIONS:"
      echo "   - terraform path: $(command -v terraform || echo 'NOT FOUND in PATH')"
      terraform --version 2>/dev/null | head -n 1 || echo "   terraform version check failed"
      echo "   - gcloud path: $(command -v gcloud || echo 'NOT FOUND in PATH')"
      gcloud --version 2>/dev/null | head -n 2 || echo "   gcloud version check failed"
      echo "   - psql path: $(command -v psql || echo 'NOT FOUND in PATH')"
      psql --version 2>/dev/null || echo "   psql version check failed"
      echo "   - PATH: $PATH"
      echo "========================================================================="
    EOT
  }
}

# --- START: Section for creating the AlloyDB password secret ---

# Create a secret for the AlloyDB password
resource "google_secret_manager_secret" "alloydb_password" {
  depends_on = [google_project_service.apis]
  secret_id  = "alloydb-password"
  project    = local.gcp_project_id

  replication {
    auto {}
  }
}

# Store the AlloyDB password in Secret Manager
resource "google_secret_manager_secret_version" "alloydb_password_version" {
  secret      = google_secret_manager_secret.alloydb_password.id
  secret_data = local.alloydb_password
}

# Grant the Compute SA access to the AlloyDB password secret
resource "google_secret_manager_secret_iam_member" "compute_sa_secret_accessor" {
  project   = local.gcp_project_id
  secret_id = google_secret_manager_secret.alloydb_password.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.compute_service_account
}

# --- END: Section for creating the AlloyDB password secret ---



# --- START: Section for assigning permissions to the AlloyDB service account ---

# Define lists of roles to assign to the default compute service account
locals {
  # Roles to be applied to the GCP project
  alloydb_sa_project_roles = [
    "roles/aiplatform.user",
    "roles/alloydb.serviceAgent", # Required for AlloyDB to create tenant projects and manage resources
    "roles/serviceusage.serviceUsageConsumer",
    "roles/storage.admin",
    "roles/servicenetworking.serviceAgent"
    # Add any other project-wide roles here
  ]
}

# Define the service account name once to keep the code DRY (Don't Repeat Yourself)
locals {
  alloydb_service_account_member = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-alloydb.iam.gserviceaccount.com"
}

# Loop: Create IAM role bindings for the GCP PROJECT
resource "google_project_iam_member" "project_alloydb_sa_roles" {
  depends_on = [google_alloydb_cluster.default]

  # This for_each creates a resource instance for each role in the list
  for_each = toset(local.alloydb_sa_project_roles)

  project = data.google_project.project.id
  role    = each.key # 'each.key' refers to the current role in the loop
  member  = local.alloydb_service_account_member
}

# --- END: Section for assigning permissions to the AlloyDB service account ---

# --- START: Section for creating the database and importing data via Bootstrap VM ---

resource "random_password" "agentspace_user_password" {
  length           = 16
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# Custom least-privilege service account for the Bootstrap VM
resource "google_service_account" "bootstrap_sa" {
  account_id   = "alloydb-bootstrap-sa"
  display_name = "Service Account for AlloyDB Bootstrap VM"
  project      = local.gcp_project_id
}

# Grant bootstrap_sa required roles for database initialization and GCS SQL import
resource "google_project_iam_member" "bootstrap_sa_roles" {
  depends_on = [google_project_service.apis]
  for_each = toset([
    "roles/alloydb.admin",
    "roles/storage.admin",
    "roles/logging.logWriter",
    "roles/bigquery.admin"
  ])

  project = data.google_project.project.id
  role    = each.key
  member  = "serviceAccount:${google_service_account.bootstrap_sa.email}"
}

# Allow caller executing Terraform to attach bootstrap_sa to the VM
resource "google_service_account_iam_member" "bootstrap_sa_user" {
  service_account_id = google_service_account.bootstrap_sa.name
  role               = "roles/iam.serviceAccountUser"
  member             = local.caller_member
}

# Temporary Bootstrap VM to initialize AlloyDB database, install extensions, import data, and create indexes inside private VPC
resource "google_compute_instance" "bootstrap_vm" {
  depends_on = [
    google_alloydb_instance.primary,
    google_project_iam_member.bootstrap_sa_roles,
    google_service_account_iam_member.bootstrap_sa_user
  ]

  name         = "alloydb-bootstrap-vm"
  machine_type = "n1-standard-2"
  zone         = "${var.gcp_region}-b"
  project      = local.gcp_project_id

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 20
    }
  }

  network_interface {
    network    = google_compute_network.demo_vpc.id
    subnetwork = data.google_compute_subnetwork.auto_subnet.id
    access_config {} # ephemeral external IP for downloading OS apt packages during bootstrap
  }

  service_account {
    email  = google_service_account.bootstrap_sa.email
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }

  metadata_startup_script = templatefile("${path.module}/scripts/bootstrap_db.sh.tpl", {
    alloydb_ip               = google_alloydb_instance.primary.ip_address
    alloydb_password         = local.alloydb_password
    alloydb_database         = var.alloydb_database
    alloydb_cluster_id       = var.alloydb_cluster_id
    gcp_region               = var.gcp_region
    gcp_project_id           = local.gcp_project_id
    database_backup_uri      = var.database_backup_uri
    agentspace_user_password = random_password.agentspace_user_password.result
    notebook_bucket          = google_storage_bucket.notebook_bucket.name
  })
}

# Wait for Bootstrap VM to upload completion status flag file to GCS and power off
resource "null_resource" "wait_for_bootstrap" {
  depends_on = [
    google_compute_instance.bootstrap_vm,
    google_storage_bucket.notebook_bucket
  ]

  provisioner "local-exec" {
    command = <<-EOT
      echo "Waiting for Bootstrap VM to finish setup and upload log flag to gs://${google_storage_bucket.notebook_bucket.name}..."
      for i in $(seq 1 150); do
        if gcloud storage ls "gs://${google_storage_bucket.notebook_bucket.name}/bootstrap-completed.txt" >/dev/null 2>&1; then
          echo "Database bootstrap completed successfully! Log summary from GCS:"
          gcloud storage cat "gs://${google_storage_bucket.notebook_bucket.name}/bootstrap-completed.txt" 2>/dev/null | tail -n 25
          # Clean up the temporary bootstrap VM
          gcloud compute instances delete alloydb-bootstrap-vm \
            --zone="${var.gcp_region}-b" \
            --project="${local.gcp_project_id}" \
            --async \
            --quiet 2>/dev/null || true
          exit 0
        fi
        if gcloud storage ls "gs://${google_storage_bucket.notebook_bucket.name}/bootstrap-failed.txt" >/dev/null 2>&1; then
          echo "ERROR: Database bootstrap failed! Error log from gs://${google_storage_bucket.notebook_bucket.name}/bootstrap-failed.txt:" >&2
          gcloud storage cat "gs://${google_storage_bucket.notebook_bucket.name}/bootstrap-failed.txt" 2>/dev/null | tail -n 50 >&2
          exit 1
        fi
        echo "Attempt $i: Waiting for Bootstrap VM to complete database setup..."
        if [ $((i % 3)) -eq 0 ]; then
          status_msg=$(gcloud storage cat "gs://${google_storage_bucket.notebook_bucket.name}/bootstrap-status.txt" 2>/dev/null || echo "VM initializing OS packages...")
          echo "  -> Live VM Progress: $status_msg"
        fi
        sleep 10
      done

      echo "ERROR: Timed out waiting for gs://${google_storage_bucket.notebook_bucket.name}/bootstrap-completed.txt after 25 minutes!" >&2
      exit 1
    EOT
  }
}

# --- END: Section for creating the database and importing data via Bootstrap VM ---

# --- START: Section for assigning permissions to Cloud Build and Compute Service Accounts ---

# Define the service account names once to keep the code DRY
locals {
  compute_service_account    = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
  cloudbuild_service_account = "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com"
}

# Grant the default Compute SA the Storage Admin role so it can upload source to the Cloud Build bucket.
# Also grant it the Cloud Build Editor role to manage builds.
resource "google_project_iam_member" "compute_sa_build_roles" {
  depends_on = [google_project_service.apis]
  for_each = toset([
    "roles/storage.admin",
    "roles/cloudbuild.builds.editor",
    "roles/logging.logWriter",
    "roles/run.admin",
    "roles/artifactregistry.admin",
    "roles/serviceusage.serviceUsageConsumer",
    "roles/bigquery.admin",
    "roles/serviceusage.serviceUsageViewer"
  ])

  project = data.google_project.project.id
  role    = each.key
  member  = local.compute_service_account
}

# Grant the Cloud Build SA the Artifact Registry Writer role so it can push container images.
resource "google_project_iam_member" "cloudbuild_sa_artifact_role" {
  depends_on = [google_project_service.apis]

  project = data.google_project.project.id
  role    = "roles/artifactregistry.writer"
  member  = local.cloudbuild_service_account
}


# --- END: Section for assigning permissions to Cloud Build and Compute Service Accounts ---


# --- START: Section for deploying the Demo App to Cloud Run ---

# Create an Artifact Registry repository to store the demo app container image
resource "google_artifact_registry_repository" "demo_app_repo" {
  depends_on = [google_project_service.apis]

  location      = var.gcp_region
  repository_id = var.demo_app_repo_name
  description   = "Docker repository for the Cymbal Shops demo application."
  format        = "DOCKER"
}

# Data source to get the auto-created subnetwork in the demo VPC for the specified region.
# This is needed to attach the Cloud Run service to the VPC.
data "google_compute_subnetwork" "auto_subnet" {
  depends_on = [google_compute_network.demo_vpc]
  name       = google_compute_network.demo_vpc.name
  region     = var.gcp_region
}

# This null_resource builds the Docker image for the demo app using Cloud Build,
# tags it, and pushes it to the Artifact Registry.
resource "null_resource" "build_and_push_image" {
  depends_on = [
    google_artifact_registry_repository.demo_app_repo,
    google_storage_bucket.notebook_bucket,
    google_project_iam_member.compute_sa_build_roles,
    google_project_iam_member.cloudbuild_sa_artifact_role,
    null_resource.bootstrap_runner
  ]

  # This provisioner will only run if the source code or Dockerfile changes.
  triggers = {
    api_source_hash      = filesha256("./demo_app/api/index.ts")
    ui_source_hash       = filesha256("./demo_app/ui/src/app/app.component.html")
    ui_results_ts_hash   = filesha256("./demo_app/ui/src/app/products/results/product-results.component.ts")
    ui_image_sel_ts_hash = filesha256("./demo_app/ui/src/app/common/image-selector/image-selector.component.ts")
    dockerfile_hash      = filesha256("./demo_app/Dockerfile")
    cloudbuild_yaml_hash = filesha256("./demo_app/cloudbuild.yaml")

    # Force the build to run every time during deployment
    always_run = timestamp()
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e
      echo "Submitting build to Google Cloud Build and waiting for completion..."
      gcloud builds submit ./demo_app \
        --config=./demo_app/cloudbuild.yaml \
        --project=${local.gcp_project_id} \
        --gcs-source-staging-dir=gs://${google_storage_bucket.notebook_bucket.name}/cloudbuild-source \
        --substitutions=_REGION=${var.gcp_region},_REPO_NAME=${google_artifact_registry_repository.demo_app_repo.repository_id},_IMAGE_NAME=${var.demo_app_image_name}

      echo "Cloud Build finished. Image should be available in Artifact Registry."
    EOT
  }
}


# Deploy the demo application to Cloud Run
resource "google_cloud_run_v2_service" "demo_app" {
  depends_on = [
    google_compute_network.demo_vpc,
    null_resource.build_and_push_image,
    null_resource.wait_for_bootstrap,
    google_secret_manager_secret_iam_member.compute_sa_secret_accessor
  ]

  name     = var.demo_app_name
  location = var.gcp_region
  project  = local.gcp_project_id

  deletion_protection = false

  template {
    containers {
      image = "${var.gcp_region}-docker.pkg.dev/${local.gcp_project_id}/${google_artifact_registry_repository.demo_app_repo.repository_id}/${var.demo_app_image_name}:latest"
      ports {
        container_port = 8080
      }
      env {
        name  = "PGHOST"
        value = google_alloydb_instance.primary.ip_address
      }
      env {
        name  = "PGPORT"
        value = "5432"
      }
      env {
        name  = "PGDATABASE"
        value = var.alloydb_database
      }
      env {
        name  = "PGUSER"
        value = "postgres"
      }
      env {
        name = "PGPASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.alloydb_password.secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "PROJECT_ID"
        value = local.gcp_project_id
      }
      env {
        name  = "REGION"
        value = var.gcp_region
      }
      env {
        name  = "BUILD_TRIGGER"
        value = null_resource.build_and_push_image.id
      }
    }

    vpc_access {
      network_interfaces {
        network    = google_compute_network.demo_vpc.id
        subnetwork = data.google_compute_subnetwork.auto_subnet.id
      }
      egress = "PRIVATE_RANGES_ONLY"
    }
  }
}

# Allow unauthenticated (public) access to the Cloud Run service
resource "google_cloud_run_v2_service_iam_member" "allow_public_access" {
  project  = google_cloud_run_v2_service.demo_app.project
  location = google_cloud_run_v2_service.demo_app.location
  name     = google_cloud_run_v2_service.demo_app.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# --- END: Section for deploying the Demo App to Cloud Run ---

# --- START: Section for Colab Enterprise setup ---
# Create Vertex AI Service Identity to ensure the service account exists
resource "google_project_service_identity" "vertex_ai_sa" {
  project    = local.gcp_project_id
  service    = "aiplatform.googleapis.com"
  depends_on = [google_project_service.apis]
}

# Grant Vertex AI Service Agent Network User role so it can use the VPC subnet
resource "google_project_iam_member" "vertex_ai_sa_network_role" {
  project = data.google_project.project.id
  role    = "roles/compute.networkUser"
  member  = "serviceAccount:${google_project_service_identity.vertex_ai_sa.email}"
}

# Create Colab Enterprise Runtime Template configured for the demo VPC
resource "google_colab_runtime_template" "colab_template" {
  depends_on = [
    google_project_service.apis,
    google_project_iam_member.vertex_ai_sa_network_role,
    google_service_networking_connection.private_vpc_connection
  ]

  name         = "stylesearch-colab-template"
  display_name = "Cymbal Shops Colab Template"
  location     = var.gcp_region
  project      = local.gcp_project_id

  machine_spec {
    machine_type = "n1-standard-2"
  }

  network_spec {
    enable_internet_access = true
    network                = google_compute_network.demo_vpc.id
    subnetwork             = data.google_compute_subnetwork.auto_subnet.id
  }
}
# --- END: Section for Colab Enterprise setup ---

# --- START: Section for BigQuery Dataset Copy ---

# Create BigQuery Data Transfer Service Identity to ensure its service agent exists
resource "google_project_service_identity" "bq_transfer_sa" {
  project    = local.gcp_project_id
  service    = "bigquerydatatransfer.googleapis.com"
  depends_on = [google_project_service.apis]
}

# Wait for BigQuery Data Transfer Service Agent IAM propagation across global Google IAM servers
resource "time_sleep" "wait_for_bq_transfer_sa_propagation" {
  depends_on      = [google_project_service_identity.bq_transfer_sa]
  create_duration = "45s"
}

# Grant BQ Data Transfer Service Agent both token creation roles required for service account impersonation during data transfers
resource "google_service_account_iam_member" "bq_transfer_impersonation" {
  for_each = toset([
    "roles/iam.serviceAccountTokenCreator",
    "roles/iam.serviceAccountShortTermTokenMinter"
  ])

  service_account_id = google_service_account.bootstrap_sa.name
  role               = each.key
  member             = "serviceAccount:${google_project_service_identity.bq_transfer_sa.email}"
  depends_on         = [time_sleep.wait_for_bq_transfer_sa_propagation]
}

# Explicit project-level token creator and minter binding for the BigQuery Data Transfer Service agent
resource "google_project_iam_member" "bq_transfer_project_token_creator" {
  for_each = toset([
    "roles/iam.serviceAccountTokenCreator",
    "roles/iam.serviceAccountShortTermTokenMinter"
  ])

  project    = local.gcp_project_id
  role       = each.key
  member     = "serviceAccount:${google_project_service_identity.bq_transfer_sa.email}"
  depends_on = [time_sleep.wait_for_bq_transfer_sa_propagation]
}

# Explicit CLI enforcement step to guarantee DTS service agent token creator and minter binding before schedule triggers
resource "null_resource" "verify_bq_transfer_iam" {
  depends_on = [
    google_service_account_iam_member.bq_transfer_impersonation,
    google_project_iam_member.bq_transfer_project_token_creator,
    null_resource.bootstrap_runner
  ]

  provisioner "local-exec" {
    command = <<-EOT
      echo "Verifying IAM Service Account Token Creator and ShortTermTokenMinter bindings for BigQuery Data Transfer Service..."
      gcloud iam service-accounts add-iam-policy-binding ${google_service_account.bootstrap_sa.email} \
        --member="serviceAccount:${google_project_service_identity.bq_transfer_sa.email}" \
        --role="roles/iam.serviceAccountTokenCreator" \
        --project="${local.gcp_project_id}" \
        --quiet || true
      gcloud iam service-accounts add-iam-policy-binding ${google_service_account.bootstrap_sa.email} \
        --member="serviceAccount:${google_project_service_identity.bq_transfer_sa.email}" \
        --role="roles/iam.serviceAccountShortTermTokenMinter" \
        --project="${local.gcp_project_id}" \
        --quiet || true
      echo "Sleeping 45s to allow global IAM token creation policy propagation before triggering BigQuery Data Transfer..."
      sleep 45
    EOT
  }
}

# Create the local BigQuery dataset to receive the copy
resource "google_bigquery_dataset" "thelook_ecommerce" {
  depends_on                 = [google_project_service.apis]
  dataset_id                 = "thelook_ecommerce"
  friendly_name              = "TheLook eCommerce"
  description                = "Copy of the public thelook_ecommerce dataset"
  location                   = "US" # Must match source dataset location
  project                    = local.gcp_project_id
  delete_contents_on_destroy = true
}

# Configure BigQuery Data Transfer Service to copy the public dataset
resource "google_bigquery_data_transfer_config" "thelook_copy" {
  depends_on = [
    google_project_service.apis,
    google_bigquery_dataset.thelook_ecommerce,
    google_service_account_iam_member.bq_transfer_impersonation,
    google_project_iam_member.bq_transfer_project_token_creator,
    null_resource.verify_bq_transfer_iam
  ]

  display_name           = "thelook-ecommerce-copy"
  location               = "US"
  data_source_id         = "cross_region_copy"
  destination_dataset_id = google_bigquery_dataset.thelook_ecommerce.dataset_id
  project                = local.gcp_project_id
  service_account_name   = google_service_account.bootstrap_sa.email

  params = {
    source_project_id           = "bigquery-public-data"
    source_dataset_id           = "thelook_ecommerce"
    overwrite_destination_table = "true"
  }

  # Schedule it to run daily (it will trigger the first run immediately on creation)
  schedule = "every 24 hours"
}

# --- END: Section for BigQuery Dataset Copy ---

# --- START: Section for Colab Notebook GCS Upload ---

# Create a GCS bucket to store the notebook
resource "google_storage_bucket" "notebook_bucket" {
  name                        = local.gcp_project_id
  location                    = var.gcp_region
  force_destroy               = true
  uniform_bucket_level_access = true

  # Ensure the APIs are enabled first
  depends_on = [google_project_service.apis]
}

# Upload the notebook to the GCS bucket
resource "google_storage_bucket_object" "notebook_upload" {
  name   = "operational-ai-leap.ipynb"
  bucket = google_storage_bucket.notebook_bucket.name
  source = "./operational-ai-leap.ipynb"
}

# Upload the Korean notebook to the GCS bucket
resource "google_storage_bucket_object" "notebook_upload_ko" {
  name   = "operational-ai-leap-ko.ipynb"
  bucket = google_storage_bucket.notebook_bucket.name
  source = "./operational-ai-leap-ko.ipynb"
}

# --- END: Section for Colab Notebook GCS Upload ---
