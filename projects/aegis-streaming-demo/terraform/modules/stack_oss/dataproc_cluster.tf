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
# Warm Dataproc Standard Cluster (Vectorized Spark Reader) & Auto-Start Streaming Job
# =============================================================================

resource "google_dataproc_cluster" "aegis_spark_cluster" {
  name    = var.dataproc_cluster_name
  region  = var.region
  project = var.project_id

  labels = {
    environment = var.environment
    component   = "spark-streaming-cluster"
  }

  cluster_config {
    staging_bucket = google_storage_bucket.dataproc_deps.name
    cluster_tier   = "CLUSTER_TIER_STANDARD"

    gce_cluster_config {
      subnetwork             = var.subnet_id
      internal_ip_only       = true
      service_account        = var.service_account_email
      service_account_scopes = ["https://www.googleapis.com/auth/cloud-platform"]

      shielded_instance_config {
        enable_secure_boot          = true
        enable_vtpm                 = true
        enable_integrity_monitoring = true
      }
    }

    master_config {
      num_instances = 1
      machine_type  = "n2-standard-4"

      disk_config {
        boot_disk_type    = "pd-balanced"
        boot_disk_size_gb = 50
      }
    }

    # -------------------------------------------------------------------------
    # Cluster & Spark Shuffle Partition Scaling Guidance:
    # -------------------------------------------------------------------------
    # In Spark Structured Streaming, stateful operations (such as `groupBy` on
    # a 10s tumbling window) commit state-store delta files to Cloud Storage for
    # every shuffle partition on every micro-batch. Leaving `spark.sql.shuffle.partitions`
    # at the Spark default (200) causes 200 Cloud Storage state commits per batch,
    # creating severe micro-batch latency on compact clusters.
    #
    # When scaling `worker_config` up or down, scale `spark.sql.shuffle.partitions`
    # proportionally (`num_instances * vcpus_per_worker`):
    #   - 2x e2-standard-2 workers (4 vCPUs total)  -> shuffle.partitions = 4
    #   - 2x n2-standard-4 workers (8 vCPUs total)  -> shuffle.partitions = 8
    #   - 4x n2-standard-4 workers (16 vCPUs total) -> shuffle.partitions = 16
    # -------------------------------------------------------------------------
    worker_config {
      num_instances = 2
      machine_type  = "n2-standard-4"

      disk_config {
        boot_disk_type    = "pd-balanced"
        boot_disk_size_gb = 50
      }
    }

    software_config {
      image_version = "2.2-debian12"
      override_properties = {
        "dataproc:pip.packages"                          = "google-cloud-bigtable==2.47.0"
        "spark:spark.sql.execution.vectorized.enabled"   = "true"
        "spark:spark.sql.parquet.enableVectorizedReader" = "true"
        "spark:spark.sql.shuffle.partitions"             = "8"
        "spark:spark.scheduler.mode"                     = "FAIR"
        "spark:spark.dataproc.lineage.enabled"           = "true"
        "spark:spark.sql.session.timeZone"               = "UTC"
      }
    }

    initialization_action {
      script      = "gs://${google_storage_bucket.dataproc_deps.name}/${google_storage_bucket_object.init_spark_deps_sh.name}"
      timeout_sec = 600
    }
  }

  lifecycle {
    ignore_changes = [
      cluster_config[0].gce_cluster_config[0].service_account_scopes,
      cluster_config[0].gce_cluster_config[0].subnetwork,
      cluster_config[0].software_config[0].image_version,
      cluster_config[0].endpoint_config,
      cluster_config[0].preemptible_worker_config,
    ]
  }
}

resource "null_resource" "start_initial_spark_job" {
  triggers = {
    cluster_id        = google_dataproc_cluster.aegis_spark_cluster.id
    etl_md5           = google_storage_bucket_object.aegis_etl_py.md5hash
    kafka_topic       = google_managed_kafka_topic.telemetry_raw.id
    submit_script_md5 = filesha256("${path.module}/scripts/submit_initial_spark_job.sh")
  }

  provisioner "local-exec" {
    command = "bash ${path.module}/scripts/submit_initial_spark_job.sh"
    environment = {
      PROJECT_ID              = var.project_id
      REGION                  = var.region
      CLUSTER_NAME            = google_dataproc_cluster.aegis_spark_cluster.name
      DEPS_BUCKET             = google_storage_bucket.dataproc_deps.name
      KAFKA_BOOTSTRAP_SERVERS = "bootstrap.${google_managed_kafka_cluster.aegis_kafka.cluster_id}.${var.region}.managedkafka.${var.project_id}.cloud.goog:9092"
      KAFKA_TOPIC             = google_managed_kafka_topic.telemetry_raw.topic_id
      BIGTABLE_INSTANCE_ID    = var.bigtable_instance_id
      BIGQUERY_DATASET_ID     = var.bigquery_dataset_id
    }
  }

  depends_on = [
    google_dataproc_cluster.aegis_spark_cluster,
    google_storage_bucket_object.aegis_etl_py,
    google_managed_kafka_topic.telemetry_raw,
  ]
}
