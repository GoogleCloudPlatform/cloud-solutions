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

# Remote state (GCS). No bucket is set here on purpose: bucket names are global, so a default
# could point at a bucket you do not own. `terraform init` fails until you name your own bucket
# and prefix (scripts/deploy.sh does this for you):
#
#   terraform -chdir=terraform init -reconfigure \
#     -backend-config="bucket=<project>-tfstate" -backend-config="prefix=<env>"
#
# Create the state bucket once, out of band (uniform access, public access prevention enforced,
# object versioning on); see terraform/README.md. State can hold sensitive values: never commit
# it, and keep bucket access to the operators who run Terraform.
terraform {
  backend "gcs" {}
}
