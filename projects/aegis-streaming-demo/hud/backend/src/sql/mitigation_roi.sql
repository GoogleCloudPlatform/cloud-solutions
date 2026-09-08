-- Copyright 2026 Google LLC
--
-- Licensed under the Apache License, Version 2.0 (the "License");
-- you may not use this file except in compliance with the License.
-- You may obtain a copy of the License at
--
--     http://www.apache.org/licenses/LICENSE-2.0
--
-- Unless required by applicable law or agreed to in writing, software
-- distributed under the License is distributed on an "AS IS" BASIS,
-- WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-- See the License for the specific language governing permissions and
-- limitations under the License.

SELECT
  asset_id,
  COUNT(*) as mitigation_events,
  SUM(tokens_used) as total_tokens_consumed,
  ROUND(SUM(cost_usd), 6) as total_gemini_cost_usd,
  ROUND(SUM(5000.0), 2) as total_downtime_saved_usd,
  ROUND(SUM(5000.0) / NULLIF(SUM(cost_usd), 0), 1) as roi_multiplier
FROM `{project_id}.{dataset_id}.rca_events`
GROUP BY asset_id
ORDER BY total_downtime_saved_usd DESC
LIMIT 10
