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
# Managed Apache Kafka Ingestion Broker Layer (OSS Stack)
# =============================================================================

resource "google_managed_kafka_cluster" "aegis_kafka" {
  provider   = google-beta
  cluster_id = "aegis-kafka-cluster"
  location   = var.region
  project    = var.project_id

  capacity_config {
    vcpu_count   = 3
    memory_bytes = 25769803776 # 24 GiB (3 * 8 GiB)
  }

  gcp_config {
    access_config {
      network_configs {
        subnet = var.subnet_id
      }
    }
  }

  rebalance_config {
    mode = "AUTO_REBALANCE_ON_SCALE_UP"
  }

  labels = {
    environment = var.environment
    component   = "managed-kafka-broker"
  }
}

resource "google_managed_kafka_topic" "telemetry_raw" {
  provider           = google-beta
  topic_id           = "telemetry-raw"
  cluster            = google_managed_kafka_cluster.aegis_kafka.cluster_id
  location           = var.region
  project            = var.project_id
  partition_count    = 6
  replication_factor = 3

  configs = {
    "cleanup.policy" = "delete"
    "retention.ms"   = "86400000" # 24 Hours retention
  }
}
