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

variable "project_id" {
  type        = string
  description = "The Google Cloud Project ID where resources will be provisioned."
}

variable "region" {
  type        = string
  description = "The target Google Cloud region for regional resources."
}

variable "zone" {
  type        = string
  description = "The target Google Cloud zone for zonal resources."
}

variable "environment" {
  type        = string
  description = "Deployment environment stage (dev, staging, prod)."
}

variable "authorized_invokers" {
  type        = list(string)
  description = "List of IAM member principals permitted to invoke Cloud Run services."
}

variable "stack_type" {
  type        = string
  description = "Active demonstration stack type: 'oss', 'first_party', or 'low_code'."
  default     = "oss"
}

variable "ingestion_type" {
  type        = string
  description = "Active telemetry ingestion broker type: 'kafka' or 'pubsub'."
  default     = "kafka"
}

variable "pipeline_engine" {
  type        = string
  description = "Active stream processing engine: 'dataproc', 'dataflow', or 'continuous_query'."
  default     = "dataproc"
}

variable "kafka_cluster_id" {
  type        = string
  description = "The ID of the Managed Apache Kafka cluster (when stack uses Kafka)."
  default     = ""
}

variable "kafka_topic_id" {
  type        = string
  description = "The ID of the Managed Apache Kafka topic (when stack uses Kafka)."
  default     = ""
}

variable "kafka_brokers" {
  type        = string
  description = "The bootstrap brokers URI for Managed Apache Kafka."
  default     = ""
}

variable "pubsub_topic" {
  type        = string
  description = "The Google Cloud Pub/Sub topic name for telemetry ingestion (when stack uses Pub/Sub)."
  default     = ""
}

variable "deps_bucket" {
  type        = string
  description = "The Cloud Storage bucket name storing Dataproc streaming job dependencies."
  default     = ""
}

variable "staging_bucket" {
  type        = string
  description = "The Cloud Storage bucket name for GEAP Reasoning Engine staging."
  default     = ""
}

variable "dataproc_cluster_name" {
  type        = string
  description = "The name of the warm Dataproc Enterprise cluster for Spark streaming."
  default     = "aegis-spark-cluster"
}
