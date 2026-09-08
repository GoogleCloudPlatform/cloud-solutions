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

# =============================================================================
# Project Aegis - Low-Code Stack (Cloud Pub/Sub + BigQuery Continuous Queries)
# =============================================================================

module "base_platform" {
  source = "../../modules/base_platform"

  project_id          = var.project_id
  region              = var.region
  zone                = var.zone
  environment         = var.environment
  authorized_invokers = var.authorized_invokers

  stack_type      = "low_code"
  ingestion_type  = "pubsub"
  pipeline_engine = "continuous_query"
  pubsub_topic    = module.stack_low_code.pubsub_topic_name
}

module "stack_low_code" {
  source = "../../modules/stack_low_code"

  project_id          = var.project_id
  environment         = var.environment
  bigquery_dataset_id = module.base_platform.bigquery_dataset_id
  telemetry_table_id  = module.base_platform.telemetry_table_id
}
