/**
 * Copyright 2024 Google LLC
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
 * limitations under the License
 */

/** @fileoverview Provides scaling profiles for the AlloyDB Autoscaler. */

import {
  CPU_HIGH_AVERAGE_UTILIZATION,
  CPU_LOW_AVERAGE_UTILIZATION,
  CPU_HIGH_MAXIMUM_UTILIZATION,
  CPU_LOW_MAXIMUM_UTILIZATION,
  CONNECTIONS_HIGH_UTILIZATION,
} from './rules';

export const DEFAULT_RULESET = {
  cpuHighAverageUtilization: CPU_HIGH_AVERAGE_UTILIZATION,
  cpuLowAverageUtilization: CPU_LOW_AVERAGE_UTILIZATION,
  cpuHighMaximumUtilization: CPU_HIGH_MAXIMUM_UTILIZATION,
  cpuLowMaximumUtilization: CPU_LOW_MAXIMUM_UTILIZATION,
  connectionsHighUtilization: CONNECTIONS_HIGH_UTILIZATION,
};
