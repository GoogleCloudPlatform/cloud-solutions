# Copyright 2024 Google LLC
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

data "archive_file" "agent_playbook" {
  type = "zip"
  dynamic "source" {
    for_each = fileset("${path.module}/assets/agent/", "**/*.json")
    content {
      content  = file("${path.module}/assets/agent/${source.value}")
      filename = source.value
    }
  }
  dynamic "source" {
    for_each = fileset("${path.module}/assets/agent/", "**/*.yaml.tmpl")
    content {
      content  = replace(file("${path.module}/assets/agent/${source.value}"), "_CF_URL_PLACEHOLDER_", google_cloudfunctions2_function.function.service_config[0].uri)
      filename = trimsuffix(source.value, ".tmpl")
    }
  }
  output_path = "${path.module}/agent_playbook.zip"
}

resource "google_storage_bucket" "dialogflowcx_assets_bucket" {
  name                        = "${var.project_id}-dialogflowcx-assets" # Every bucket name must be globally unique
  location                    = "US"
  uniform_bucket_level_access = true
}

resource "google_storage_bucket_object" "agent_playbook_archive" {
  name   = "agent_playbook.zip"
  bucket = google_storage_bucket.dialogflowcx_assets_bucket.name
  source = data.archive_file.agent_playbook.output_path
}


resource "google_dialogflow_cx_agent" "cc_agent" {
  default_language_code = "en"
  display_name          = "Conversational Commerce Agent"
  location              = var.region
  #    name                     = "8224d296-a944-4d8b-9bee-d2a733247a03"
  project                  = var.project_id
  supported_language_codes = []
  time_zone                = "America/Los_Angeles"

  advanced_settings {
    speech_settings {
      endpointer_sensitivity        = 90
      models                        = {}
      no_speech_timeout             = "5s"
      use_timeout_based_endpointing = false
    }
  }
  provisioner "local-exec" {
    command    = <<EOT
    curl -f -X POST \
      -H "X-Goog-User-Project: ${self.project}" \
      --header "Authorization: Bearer $(gcloud auth print-access-token)" \
      --json '{"agentUri": "gs://${google_storage_bucket.dialogflowcx_assets_bucket.name}/${google_storage_bucket_object.agent_playbook_archive.name}"}' \
      https://${self.location}-dialogflow.googleapis.com/v3/${self.id}:restore
EOT
    on_failure = fail
  }
}
