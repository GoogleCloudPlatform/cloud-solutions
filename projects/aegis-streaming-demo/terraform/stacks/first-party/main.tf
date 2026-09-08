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
# Project Aegis - 1st-Party Stack (Cloud Pub/Sub + Cloud Dataflow)
# =============================================================================

module "stack_first_party" {
  source = "../../modules/stack_first_party"

  project_id  = var.project_id
  region      = var.region
  environment = var.environment
}

module "base_platform" {
  source = "../../modules/base_platform"

  project_id          = var.project_id
  region              = var.region
  zone                = var.zone
  environment         = var.environment
  authorized_invokers = var.authorized_invokers

  stack_type      = "first_party"
  ingestion_type  = "pubsub"
  pipeline_engine = "dataflow"
  pubsub_topic    = module.stack_first_party.pubsub_topic_name
  staging_bucket  = module.stack_first_party.dataflow_staging_bucket
}
