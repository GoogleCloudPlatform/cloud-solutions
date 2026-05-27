# Declarative Google Cloud API Services activation
resource "google_project_service" "dialogflow_api" {
  project            = var.project_id
  service            = "dialogflow.googleapis.com"
  disable_on_destroy = false
}
