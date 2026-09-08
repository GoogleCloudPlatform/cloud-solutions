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
  TIMESTAMP_TRUNC(timestamp, MINUTE) as window_minute,
  ROUND(MAX(temperature_c), 2) as peak_temp_c,
  ROUND(MAX(cpu_utilization), 2) as peak_cpu_pct,
  ANY_VALUE(status) as status
FROM `{project_id}.{dataset_id}.telemetry_events`
WHERE temperature_c > 80.0 OR cpu_utilization > 85.0
GROUP BY asset_id, window_minute
ORDER BY peak_temp_c DESC
LIMIT 15
