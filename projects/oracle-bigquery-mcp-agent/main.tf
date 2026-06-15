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

terraform {
  required_version = ">= 1.3.0"
  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
  }
}

resource "local_file" "tfvars" {
  filename = "${path.module}/terraform.tfvars"
  content  = <<-EOT
# ==============================================================================
# FynanceAI: Automatically Generated global configuration variables
# ==============================================================================
project_id          = "${var.project_id}"
db_password         = "${var.db_password}"
region              = "${var.region}"
zone                = "${var.zone}"
gcs_bucket_name     = "${var.gcs_bucket_name != "" ? var.gcs_bucket_name : "oracle-staging-${var.project_id}"}"
ssh_user            = "${var.ssh_user}"
ssh_key_path        = "${var.ssh_key_path}"
oauth_client_id     = "${var.oauth_client_id}"
oauth_client_secret = "${var.oauth_client_secret}"
edition             = "${var.edition}"
create_vpc          = ${var.create_vpc}
vpc_name            = "${var.vpc_name}"
create_subnetwork   = ${var.create_subnetwork}
subnetwork_name     = "${var.subnetwork_name}"
create_gcs_bucket   = ${var.create_gcs_bucket}
rpm_name            = "${var.rpm_name}"
EOT
}
