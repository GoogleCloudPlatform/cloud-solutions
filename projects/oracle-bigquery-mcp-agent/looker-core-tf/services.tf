# Declarative Google Cloud API Services activation
resource "google_project_service" "looker_api" {
  project            = var.project_id
  service            = "looker.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "iam_api" {
  project            = var.project_id
  service            = "iam.googleapis.com"
  disable_on_destroy = false
}
