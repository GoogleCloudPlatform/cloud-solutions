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

-- BigQuery Continuous Query 10-Second Tumbling Window Aggregation
-- Aggregates raw IIoT sensor payloads streamed directly from Cloud Pub/Sub
-- (telemetry-raw-bq-sub) into 10-second operational windows for Cloud Bigtable.

SELECT
  asset_id,
  ROUND(AVG(cpu_utilization), 2) AS avg_cpu,
  ROUND(AVG(temperature_c), 2) AS avg_temp,
  ROUND(MAX(temperature_c), 2) AS max_temp,
  ROUND(AVG(pressure_psi), 2) AS avg_pressure,
  ROUND(AVG(memory_utilization_pct), 2) AS avg_memory,
  CASE
    WHEN AVG(temperature_c) > 90.0 OR AVG(cpu_utilization) > 90.0 THEN 'CRITICAL'
    WHEN AVG(temperature_c) > 75.0 OR AVG(cpu_utilization) > 75.0 THEN 'WARNING'
    ELSE 'OK'
  END AS status,
  LOGICAL_OR(COALESCE(is_anomaly, FALSE))
    OR AVG(temperature_c) > 90.0
    OR AVG(cpu_utilization) > 90.0 AS is_anomaly,
  UNIX_MILLIS(MAX(timestamp)) AS ingestion_timestamp_ms,
  FORMAT_TIMESTAMP('%Y-%m-%dT%H:%M:%SZ', MAX(timestamp)) AS window_end
FROM
  `{project_id}.{dataset_id}.telemetry_events`
WHERE
  timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 10 SECOND)
GROUP BY
  asset_id
