output "project_id" {
  value = var.project_id
}

output "region" {
  value = var.region
}

output "service_account_email" {
  value = google_service_account.service_account.email
}

output "pt_archieve_bucket" {
  value = google_storage_bucket.pt_archieve_bucket.name
}

output "pt_cloud_build_bucket" {
  value = google_storage_bucket.pt_build_bucket.name
}

output "pt_admin_url" {
  value = google_cloud_run_service.pt_admin_service.status[0].url
}


output "pt_provison_wokflow_name" {
  value = google_workflows_workflow.pt_provision_wf.name
}

output "pt_destroy_workflow_name" {
  value = google_workflows_workflow.pt_destroy_wf.name
}
  