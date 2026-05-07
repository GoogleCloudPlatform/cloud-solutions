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

-- Translated BigQuery Query demonstrating GoogleSQL idiomatic syntax
WITH exploded_lines AS (
  SELECT
      bus_lines.bus_line_id,
      stop_id
    FROM
      `__PROJECT_ID__.silver-__PROJECT_ID__.default.bus_lines` AS `bus_lines`,
      UNNEST(stops) stop_id
)
SELECT
    s.bus_stop_id,
    s.address,
    count(DISTINCT l.bus_line_id) AS total_lines
  FROM
    exploded_lines AS l
    INNER JOIN `__PROJECT_ID__.silver-__PROJECT_ID__.default.bus_stations` AS s ON l.stop_id = s.bus_stop_id
  GROUP BY 1, 2
ORDER BY
  total_lines DESC;
