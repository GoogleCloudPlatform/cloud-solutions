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

module "demo_ui" {
  source                   = "./ui"
  project_id               = var.project_id
  project_number           = local.target_project_number
  ui_name                  = var.component
  ui_assets_path           = "${path.module}/assets/${var.component}-ui"
  dialogflow_cx_agent_name = module.dialogflow_cx_demo_agent.agent_name
}
