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

resource "local_file" "adk_agent_env" {
  filename = "../../adk-agent/financial_analyst/.agent.env"
  content = templatefile("../../adk-agent/config.tftpl", {
    finnhub_api_key     = var.finnhub_api_key,
    order_service_url   = var.deploy_order_service ? google_cloud_run_v2_service.order_service[0].uri : "http://127.0.0.1:8090"
    tools_url           = google_cloud_run_v2_service.toolbox.uri,
    timesfm_endpoint_id = google_vertex_ai_endpoint_with_model_garden_deployment.timesfm_deployment.id
  })
}
