/*
 * Copyright 2023 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

SELECT
    `timestamp` AS test_timestamp,
    metric,
    unit,
    value,
    labels,
FROM
    `some-result-project.perfkit.results`
WHERE
    owner = 'cloud-build-success-id'
  AND metric NOT IN ('lscpu',
                     'gcc_version',
                     'glibc_version',
                     'proccpu_mapping',
                     'proccpu',
                     'cpu_vuln',
                     'Write_Min_Latency_time_series',
                     'Write_Max_Latency_time_series',
                     'Read_Max_Latency_time_series',
                     'Read_Min_Latency_time_series')