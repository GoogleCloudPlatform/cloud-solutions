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

# Example values only (placeholders). Copy to an untracked *.auto.tfvars for a real tenant.
tenant_project_id = "example-tenant-data-project"
tenant_id         = "tenant-acme-corp"
name_prefix       = "acme-data"
region            = "us-central1"
pooled_project_id = "example-pooled-project"
pooled_network    = "projects/example-pooled-project/global/networks/cymbal-pooled-vpc-prod"
pooled_subnetwork = "projects/example-pooled-project/regions/us-central1/subnetworks/cymbal-pooled-vpc-prod"
