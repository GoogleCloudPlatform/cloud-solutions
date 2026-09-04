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

# Project Aegis - Terraform Infrastructure Root Entrypoint
# =========================================================
# Managed Open Source (Apache Kafka & Apache Spark) + Google Cloud Native Integration

locals {
  # Standardized internal resource naming identifiers
  # These defaults are optimized for the reference architecture and rarely need modification.
  bigtable_instance_id        = "aegis-bigtable"
  bigquery_dataset_id         = "analytics"
  artifact_registry_repo_name = "aegis-containers"
}
