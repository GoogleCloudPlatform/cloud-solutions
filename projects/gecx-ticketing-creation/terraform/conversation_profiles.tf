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

locals {
  all_coach_files = fileset("${path.module}/assets/coaches", "*.json")
  coaches = {
    for f in local.all_coach_files :
    replace(f, ".json", "") => {
      filename = f
      coach_id = replace(f, ".json", "")
      name = lookup(
        jsondecode(file("${path.module}/assets/coaches/${f}")),
        "name",
        lookup(
          jsondecode(file("${path.module}/assets/coaches/${f}")),
          "description",
          replace(f, ".json", "")
        )
      )
    }
  }
}

resource "google_dialogflow_conversation_profile" "coach_profiles" {
  provider     = google-beta
  for_each     = var.conversation_profile_id == "" ? local.coaches : {}
  display_name = "Cymbal Coach - ${each.value.name}"
  location     = "global"
  project      = var.project_id
  lifecycle {
    ignore_changes = [
      human_agent_assistant_config,
    ]
  }
}
