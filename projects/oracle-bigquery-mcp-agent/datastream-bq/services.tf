# Declarative Google Cloud API Services activation
resource "google_project_service" "datastream_api" {
  project            = var.project_id
  service            = "datastream.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "bigquery_api" {
  project            = var.project_id
  service            = "bigquery.googleapis.com"
  disable_on_destroy = false
}
