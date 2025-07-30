# Copyright 2025 Google LLC
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

locals {
  config_content = <<-EOT
        [gcp]
        GCP_PROJECT_ID = "${var.project_id}"
        ECOMMERCE_DATASET_ID = "ecommerce_data"
        GCS_BUCKET = "${var.project_id}-widget-bucket"
  EOT
}

resource "local_file" "generate_config_toml" {
  filename = "../api/config.toml"
  content  = join("", [file("../api/config-template.toml"), local.config_content])
}
