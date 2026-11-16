# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

variable "project_id" {
  description = "Google Cloud project ID where the Persistent Disk migration testbed is deployed."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "project_id must be a valid Google Cloud project ID between 6 and 30 characters."
  }
}

variable "region" {
  description = "Google Cloud region for networking and snapshot schedule resources."
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "Google Cloud zone for the source Gen2 Compute Engine instance and Persistent Disks."
  type        = string
  default     = "us-central1-a"
}

variable "resource_prefix" {
  description = "Short lowercase prefix prepended to demo resource names."
  type        = string
  default     = "pd-hd-demo"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,14}[a-z0-9]$", var.resource_prefix))
    error_message = "resource_prefix must be 3 to 16 characters of lowercase letters, digits, and hyphens."
  }
}

variable "source_machine_type" {
  description = "Second-generation Compute Engine machine type for the baseline source instance."
  type        = string
  default     = "n2-standard-2"
}

variable "boot_disk_size_gb" {
  description = "Boot Persistent Disk capacity in GiB."
  type        = number
  default     = 20

  validation {
    condition     = var.boot_disk_size_gb >= 10 && floor(var.boot_disk_size_gb) == var.boot_disk_size_gb
    error_message = "boot_disk_size_gb must be an integer of at least 10 GiB."
  }
}

variable "data_disk_size_gb" {
  description = "Attached primary application data Persistent Disk capacity in GiB."
  type        = number
  default     = 100

  validation {
    condition     = var.data_disk_size_gb >= 10 && floor(var.data_disk_size_gb) == var.data_disk_size_gb
    error_message = "data_disk_size_gb must be an integer of at least 10 GiB."
  }
}

variable "wal_disk_size_gb" {
  description = "Attached write-ahead log (pd-ssd) Persistent Disk capacity in GiB on the multi-disk instance."
  type        = number
  default     = 50

  validation {
    condition     = var.wal_disk_size_gb >= 10 && floor(var.wal_disk_size_gb) == var.wal_disk_size_gb
    error_message = "wal_disk_size_gb must be an integer of at least 10 GiB."
  }
}

variable "spool_disk_size_gb" {
  description = "Attached throughput spool (pd-standard) Persistent Disk capacity in GiB on the multi-disk instance."
  type        = number
  default     = 200

  validation {
    condition     = var.spool_disk_size_gb >= 10 && floor(var.spool_disk_size_gb) == var.spool_disk_size_gb
    error_message = "spool_disk_size_gb must be an integer of at least 10 GiB."
  }
}
