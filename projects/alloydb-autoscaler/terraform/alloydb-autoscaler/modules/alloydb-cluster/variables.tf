/**
 * Copyright 2024 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

variable "project_id" {
  type        = string
  description = "Project ID where the AlloyDB cluster will run"
}

variable "region" {
  type        = string
  description = "The name of the region to run the AlloyDB cluster"
}

variable "network" {
  type        = string
  description = "The VPC network to host the cluster in"
}

variable "alloydb_cluster_name" {
  type        = string
  description = "A unique name for the AlloyDB cluster"
}

variable "alloydb_primary_instance_name" {
  type        = string
  description = "A unique name for the AlloyDB primary instance"
}

variable "alloydb_read_pool_instance_name" {
  type        = string
  description = "A unique name for the AlloyDB read pool instance"
}

variable "alloydb_node_count" {
  type        = number
  description = "Inital number of nodes for the AlloyDB read pool instance"
}

variable "postgres_version" {
  type        = string
  description = "The version of Postgres to use in the AlloyDB cluster"
  default     = "POSTGRES_16"
}

variable "alloydb_username" {
  type        = string
  description = "The initial username for the AlloyDB cluster"
}

variable "alloydb_password" {
  type        = string
  description = "The initial password for the AlloyDB cluster"
}

variable "poller_sa_email" {
  type        = string
  description = "The email of the poller service account"
}

variable "scaler_sa_email" {
  type        = string
  description = "The email of the scaler service account"
}
