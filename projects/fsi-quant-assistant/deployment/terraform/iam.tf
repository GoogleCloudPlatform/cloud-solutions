# Copyright 2025 Google LLC
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

resource "google_service_account" "toolbox-identity" {
  account_id   = "toolbox-identity"
  display_name = "Toolbox Identity"

  lifecycle {
    ignore_changes = [
      description,
      display_name
    ]
  }
}

resource "google_service_account" "adk-agent" {
  account_id   = "adk-agent"
  display_name = "ADK Agent"

  lifecycle {
    ignore_changes = [
      description,
      display_name
    ]
  }
}

resource "google_service_account" "adk-builder" {
  account_id   = "adk-builder"
  display_name = "ADK Cloud Builder"

  lifecycle {
    ignore_changes = [
      description,
      display_name
    ]
  }
}

resource "google_service_account" "gemma-agent" {
  account_id   = "gemma-agent"
  display_name = "Gemma Agent"

  lifecycle {
    ignore_changes = [
      description,
      display_name
    ]
  }
}

resource "google_service_account" "terraform-runner" {
  account_id   = "terraform-runner"
  display_name = "Terraform Runner"

  lifecycle {
    ignore_changes = [
      description,
      display_name
    ]
  }
}

data "google_compute_default_service_account" "default" {
}
