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

# Example values only (placeholders). Copy to an untracked *.auto.tfvars for a real silo.
project_id              = "example-silo-project"
project_number          = "123456789012"
region                  = "us-central1"
platform_environment    = "acme" # config/environments/acme.yaml (see docs/customer_deployment.md)
gateway_container_image = "us-central1-docker.pkg.dev/example-silo-project/cloud-run-source-deploy/cymbal-pooled-gateway"

tenant = {
  tenant_id  = "tenant-acme-corp"
  cmek_key   = "tenant-acme-corp-cmek"
  secret_ids = []
}
