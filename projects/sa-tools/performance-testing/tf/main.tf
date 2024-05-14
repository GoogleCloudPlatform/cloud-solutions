
// Provision all necenssary resources for performance testing
// Do not change default values in variables.tf unless you know what you are doing
// To override default values, create a file called terraform.tfvars and put your overrides there

data "google_project" "project" {
  project_id = var.project_id
}

// Enable requires APIs
resource "google_project_service" "required_services" {
  project                    = var.project_id
  disable_on_destroy         = false
  disable_dependent_services = true
  for_each = toset([
    "cloudresourcemanager.googleapis.com",
    "cloudapis.googleapis.com",
    "file.googleapis.com",
    "container.googleapis.com",
    "containerregistry.googleapis.com",
    "compute.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "storage-api.googleapis.com",
    "storage-component.googleapis.com",
    "workflowexecutions.googleapis.com",
    "workflows.googleapis.com",
    "run.googleapis.com",
    "monitoring.googleapis.com",
    "clouddeploy.googleapis.com",
    "cloudbuild.googleapis.com",
    "firestore.googleapis.com",
    "eventarc.googleapis.com",
  ])
  service = each.key

}

// Grant the iam.serviceAccountTokenCreator role to the Pub/Sub service account
resource "google_project_iam_binding" "token_creator_iam" {
  provider = google-beta
  project  = var.project_id
  role     = "roles/iam.serviceAccountTokenCreator"

  members    = ["serviceAccount:service-${data.google_project.project.number}@gcp-sa-pubsub.iam.gserviceaccount.com"]
  depends_on = [google_project_service.required_services]
}

// Provision a service account
resource "google_service_account" "service_account" {
  project      = var.project_id
  account_id   = var.service_account
  display_name = var.service_account
}

// Grant service account with permissions
// 1-Grant service account with Network Admin role
resource "google_project_iam_member" "service_account_network_admin" {
  project = var.project_id
  role    = "roles/compute.networkAdmin"
  member  = "serviceAccount:${google_service_account.service_account.email}"
}
// 2-Grant service account with GKE admin role
resource "google_project_iam_member" "service_account_gke_admin" {
  project = var.project_id
  role    = "roles/container.admin"
  member  = "serviceAccount:${google_service_account.service_account.email}"
}

// 3-Grant service account with Storage Admin role
resource "google_project_iam_member" "service_account_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.service_account.email}"
}
// 4-Grant service account with Cloud Run Admin role
resource "google_project_iam_member" "service_account_cloud_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.service_account.email}"
}
// 5-Grant service account with Workflows Admin role
resource "google_project_iam_member" "service_account_cloud_workflows_admin" {
  project = var.project_id
  role    = "roles/workflows.admin"
  member  = "serviceAccount:${google_service_account.service_account.email}"
}
// 6-Grant service account with Cloud Build Admin role
resource "google_project_iam_member" "service_account_cloud_build_admin" {
  project = var.project_id
  role    = "roles/cloudbuild.builds.editor"
  member  = "serviceAccount:${google_service_account.service_account.email}"
}
// 7-Grant service account with Cloud Monitoring Admin role
resource "google_project_iam_member" "service_account_cloud_monitoring_admin" {
  project = var.project_id
  role    = "roles/monitoring.admin"
  member  = "serviceAccount:${google_service_account.service_account.email}"
}
// 8-Grant service account with Cloud Logging Admin role
resource "google_project_iam_member" "service_account_cloud_logging_admin" {
  project = var.project_id
  role    = "roles/logging.admin"
  member  = "serviceAccount:${google_service_account.service_account.email}"
}
// 9-Grant service account with Firestore Admin role
resource "google_project_iam_member" "service_account_firestore_admin" {
  project = var.project_id
  role    = "roles/datastore.owner"
  member  = "serviceAccount:${google_service_account.service_account.email}"
}
// 10-Grant service account with Project IAM Admin role
resource "google_project_iam_member" "service_account_project_iam_admin" {
  project = var.project_id
  role    = "roles/resourcemanager.projectIamAdmin"
  member  = "serviceAccount:${google_service_account.service_account.email}"
}
// 11-Grant service account with Service Account Admin role
resource "google_project_iam_member" "service_account_service_account_admin" {
  project = var.project_id
  role    = "roles/iam.serviceAccountAdmin"
  member  = "serviceAccount:${google_service_account.service_account.email}"
}
// 12-Grant service account with Artifact Registry Admin role
resource "google_project_iam_member" "service_account_artifact_registry_admin" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.service_account.email}"
}
// 13-Grant service account with service account user role
resource "google_project_iam_member" "service_account_service_account_user" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${google_service_account.service_account.email}"
}
// 14-Grant service account with Pub/Sub Publisher role
resource "google_project_iam_member" "service_account_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.service_account.email}"
}


// Provision bucket to store test results
resource "google_storage_bucket" "pt_archieve_bucket" {
  project                     = var.project_id
  name                        = "${var.project_id}_${var.archieve_bucket}"
  location                    = var.region
  force_destroy               = true
  public_access_prevention    = "enforced"
  uniform_bucket_level_access = true
}
// Provision bucket for Cloud Build
resource "google_storage_bucket" "pt_build_bucket" {
  project                     = var.project_id
  name                        = "${var.project_id}_cloudbuild"
  location                    = var.region
  force_destroy               = true
  public_access_prevention    = "enforced"
  uniform_bucket_level_access = true
}

// Provision a artifact registry for Docker images
resource "google_artifact_registry_repository" "pt_repository" {
  project       = var.project_id
  provider      = google-beta
  location      = "asia"
  repository_id = "${var.project_id}-pt-images"
  format        = "DOCKER"
}

// Provision a firestore database with a collection
resource "random_string" "random_suffix" {
  length  = 16
  special = false
  upper   = false
}

// Provision a firestore collection
# resource "google_firestore_database" "database" {
#   project                     = var.project_id
#   name                        = "(default)"
#   location_id                 = "nam5"
#   type                        = "FIRESTORE_NATIVE"
#   concurrency_mode            = "OPTIMISTIC"
#   app_engine_integration_mode = "DISABLED"

#   depends_on = [google_project_service.required_services]
# }

resource "google_firestore_document" "doc" {
  project     = var.project_id
  collection  = var.firestore_collection
  document_id = "doc-${random_string.random_suffix.id}"
  fields      = "{\"something\":{\"mapValue\":{\"fields\":{\"akey\":{\"stringValue\":\"avalue\"}}}}}"
}

// Provision a Cloud Run service with specified service account
resource "google_cloud_run_service" "pt_admin_service" {
  provider = google-beta
  project  = var.project_id
  name     = "pt-admin-run"
  location = var.region

  template {
    spec {
      service_account_name  = google_service_account.service_account.email
      container_concurrency = 10
      containers {
        image = var.pt_admin_image
        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "LOCATION"
          value = var.region
        }
        env {
          name  = "ARCHIEVE_BUCKET"
          value = "${var.project_id}_${var.archieve_bucket}"
        }
        env {
          name  = "TARGET_PRINCIPAL"
          value = google_service_account.service_account.email
        }
        startup_probe {
          http_get {
            path = "/healthz"
          }
          initial_delay_seconds = 10
          timeout_seconds       = 1
          period_seconds        = 3
          failure_threshold     = 3
        }
        ports {
          container_port = 9080
        }
        resources {
          limits = {
            cpu    = "2"
            memory = "4Gi"
          }
        }

      }
    }
    metadata {
      annotations = {
        "autoscaling.knative.dev/maxScale"         = "100"
        "autoscaling.knative.dev/minScale"         = "1"
        "run.googleapis.com/cpu-throttling"        = false
        "run.googleapis.com/execution-environment" = "gen2"
      }
    }
  }
  traffic {
    percent         = 100
    latest_revision = true
  }
  depends_on = [
    google_service_account.service_account,
  ]
}

// Provision pubsub topics
resource "google_pubsub_topic" "pt_provision_topic" {
  project = var.project_id
  name    = "pt-provision-wf"
}
resource "google_pubsub_topic" "pt_destroy_topic" {
  project = var.project_id
  name    = "pt-destroy-wf"
}

// Provision a workflow to run provision infrastructure and run tests
resource "google_workflows_workflow" "pt_provision_wf" {
  project         = var.project_id
  region          = var.region
  name            = "pt-provision-wf"
  service_account = google_service_account.service_account.id
  description     = "Provision all related resources for PtTask"

  source_contents = templatefile("${path.module}/../pt-admin/workflows/provision.yaml", {})
  depends_on = [
    google_service_account.service_account,
  ]
}

// Provision eventarc trigger to run provision workflow
resource "google_eventarc_trigger" "pt_provision_trigger" {
  project  = var.project_id
  location = var.region
  name     = "pt-provision-trigger"
  matching_criteria {
    attribute = "type"
    value     = "google.cloud.pubsub.topic.v1.messagePublished"
  }
  transport {
    pubsub {
      topic = google_pubsub_topic.pt_provision_topic.id
    }
  }
  destination {
    workflow = google_workflows_workflow.pt_provision_wf.name
  }
  service_account = google_service_account.service_account.email
  depends_on = [
    google_workflows_workflow.pt_provision_wf
  ]
}

// Provision a workflow to destroy infrastructure
resource "google_workflows_workflow" "pt_destroy_wf" {
  project         = var.project_id
  region          = var.region
  name            = "pt-destroy-wf"
  service_account = google_service_account.service_account.id
  description     = "Destroy some of related resources for PtTask, excepted VPC, Subnet, SA, etc"

  source_contents = templatefile("${path.module}/../pt-admin/workflows/destroy.yaml", {})
  depends_on = [
    google_service_account.service_account,
  ]
}

// Provision eventarc trigger to run destroy workflow
resource "google_eventarc_trigger" "pt_destroy_trigger" {
  project  = var.project_id
  location = var.region
  name     = "pt-destroy-trigger"
  matching_criteria {
    attribute = "type"
    value     = "google.cloud.pubsub.topic.v1.messagePublished"
  }
  transport {
    pubsub {
      topic = google_pubsub_topic.pt_destroy_topic.id
    }
  }
  destination {
    workflow = google_workflows_workflow.pt_destroy_wf.name
  }
  service_account = google_service_account.service_account.email
  depends_on = [
    google_workflows_workflow.pt_destroy_wf
  ]
}
