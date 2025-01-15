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

variable "autoscaler_repository_id" {
  type        = string
  description = "Image registry for the OSS Autoscaler"
  default     = "oss-autoscaler"
}

variable "project_id" {
  description = "Project ID where the cluster will run"
}

variable "region" {
  description = "The name of the region to run the cluster"
}

variable "name" {
  description = "A unique name for the resource"
}

variable "network" {
  description = "The name of the network to use"
}

variable "subnetwork" {
  description = "The name of the subnet to use"
}

variable "ip_range_master" {
  description = "The range for the private master"
}

variable "ip_range_pods" {
  description = "The secondary range for the pods"
}

variable "ip_range_services" {
  description = "The secondary range for the services"
}

variable "namespace" {
  description = "The namespace to use for the services"
  default     = "oss-autoscaler"
}

variable "poller_sa_email" {
  type = string
}

variable "scaler_sa_email" {
  type = string
}

variable "machine_type" {
  description = "Type of node to use to run the cluster"
  default     = "e2-standard-2"
}

variable "minimum_node_pool_instances" {
  type        = number
  description = "Number of node-pool instances to have active"
  default     = 1
}

variable "maximum_node_pool_instances" {
  type        = number
  description = "Maximum number of node-pool instances to scale to"
  default     = 3
}

variable "release_channel" {
  type        = string
  description = "(Beta) The release channel of this cluster. Accepted values are `UNSPECIFIED`, `RAPID`, `REGULAR` and `STABLE`. Defaults to `UNSPECIFIED`."
  default     = "STABLE"
}

variable "otel_collector_sa_name" {
  type        = string
  description = "The name of the service account and workload identity to be created and used by the OpenTelemetry Collector workload"
  default     = "otel-collector-sa"
}

variable "unified_components" {
  description = "Whether Poller and Scaler are unified"
  type        = bool
  default     = true
}
