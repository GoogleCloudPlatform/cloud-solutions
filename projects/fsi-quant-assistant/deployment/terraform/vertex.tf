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



resource "google_vertex_ai_endpoint" "timesfm_endpoint" {
  name                       = "${var.forecast_model_display_name}-endpoint"
  display_name               = "${var.forecast_model_display_name}-endpoint"
  location                   = var.region
  description                = "Endpoint for TimesFM Forecasting Service"
  dedicated_endpoint_enabled = false
}

output "endpoint_id" {
  value = google_vertex_ai_endpoint.timesfm_endpoint.name
}
