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
  COUNT(*) as total_readings,
  ROUND(AVG(cpu_utilization), 2) as avg_cpu_pct,
  ROUND(MAX(cpu_utilization), 2) as max_cpu_pct,
  ROUND(AVG(temperature_c), 2) as avg_temp_c,
  ROUND(MAX(temperature_c), 2) as max_temp_c,
  COUNTIF(status = 'CRITICAL' OR cpu_utilization > 85.0 OR temperature_c > 85.0) as critical_events
FROM `{project_id}.{dataset_id}.telemetry_events`
GROUP BY asset_id
ORDER BY critical_events DESC, max_temp_c DESC
LIMIT 10
