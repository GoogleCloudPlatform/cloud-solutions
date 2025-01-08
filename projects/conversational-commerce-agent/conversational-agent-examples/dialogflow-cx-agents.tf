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

module "dialogflow_cx_apparel_agent" {
  source            = "./dialogflow-cx-agent"
  agent_name        = "apparel_search"
  agent_assets      = "${path.module}/assets/apparel-agent"
  project_id        = var.project_id
  region            = var.region
  cloudfunction_uri = google_cloudfunctions2_function.function.service_config[0].uri
}

module "dialogflow_cx_food_agent" {
  source            = "./dialogflow-cx-agent"
  agent_name        = "food"
  agent_assets      = "${path.module}/assets/food-agent"
  project_id        = var.project_id
  region            = var.region
  cloudfunction_uri = google_cloudfunctions2_function.function.service_config[0].uri
}

module "dialogflow_cx_beauty_agent" {
  source            = "./dialogflow-cx-agent"
  agent_name        = "beauty"
  agent_assets      = "${path.module}/assets/beauty-agent"
  project_id        = var.project_id
  region            = var.region
  cloudfunction_uri = google_cloudfunctions2_function.function.service_config[0].uri
}
