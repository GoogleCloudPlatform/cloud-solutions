/**
 * Copyright 2026 Google LLC
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

provider "google" {
  project = local.project_id
  region  = local.region
}

provider "nsxt" {
  host                 = data.terraform_remote_state.source.outputs.nsx_fqdn
  username             = data.google_vmwareengine_nsx_credentials.this.username
  password             = data.google_vmwareengine_nsx_credentials.this.password
  allow_unverified_ssl = true
}

provider "vsphere" {
  vsphere_server       = data.terraform_remote_state.source.outputs.vcenter_fqdn
  user                 = data.google_vmwareengine_vcenter_credentials.this.username
  password             = data.google_vmwareengine_vcenter_credentials.this.password
  allow_unverified_ssl = true
}
