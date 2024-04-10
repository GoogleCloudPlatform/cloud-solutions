# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

locals {
  _template_backend          = "${path.module}/templates/backend.tf.tpl"
  _template_terraform_tfvars = "${path.module}/templates/terraform.tfvars.tpl"

  cloud_run_event_processing_service_name = "event-processor"

  event_processing_results_gcs_bucket_name = "event-processing-results"
  event_source_gcs_bucket_name             = "event-source" # Cloud Storage bucket to use as an event source, as an example
  terraform_backend_gcs_bucket_name        = "terraform-backend"

  backend = templatefile(local._template_backend, {
    bucket = module.terraform_backend_gcs_buckets.name
  })

  terraform_tfvars = templatefile(local._template_terraform_tfvars, {
    project_id = var.project_id
  })

  cloud_run_service_account_name = "cloud-run-sa"
  cloud_run_service_account_names = [
    local.cloud_run_service_account_name
  ]
  list_cloud_run_service_account_iam_emails = [for service_account in local.cloud_run_service_account_names : "serviceAccount:${module.service_accounts.service_accounts_map[service_account].email}"]

  eventarc_service_account_name = "eventarc-sa"
  eventarc_service_account_names = [
    local.eventarc_service_account_name
  ]
  list_eventarc_service_account_iam_emails = [for service_account in local.eventarc_service_account_names : "serviceAccount:${module.service_accounts.service_accounts_map[service_account].email}"]

  service_account_names = concat(
    local.cloud_run_service_account_names,
    local.eventarc_service_account_names
  )
}

data "google_project" "project" {
  project_id = var.project_id

  depends_on = [
    module.project-services
  ]
}
