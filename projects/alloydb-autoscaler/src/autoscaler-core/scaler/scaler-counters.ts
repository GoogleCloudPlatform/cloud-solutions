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

/** @fileoverview Provides scaler counter definitions. */

import {CounterDefinition} from '../common/counters';

const SCALER_COUNTER_PREFIX = 'scaler';

export const SCALER_COUNTER_DEFINITION_MAP: Record<string, CounterDefinition> =
  {
    SCALING_SUCCESS: {
      counterName: `${SCALER_COUNTER_PREFIX}/scaling-success`,
      counterDesc: 'The number of Autoscaler scaling events that succeeded',
      counterType: 'CUMULATIVE',
    },
    SCALING_DENIED: {
      counterName: `${SCALER_COUNTER_PREFIX}/scaling-denied`,
      counterDesc: 'The number of Autoscaler scaling events denied',
      counterType: 'CUMULATIVE',
    },
    SCALING_FAILED: {
      counterName: `${SCALER_COUNTER_PREFIX}/scaling-failed`,
      counterDesc: 'The number of Autoscaler scaling events that failed',
      counterType: 'CUMULATIVE',
    },
    SCALING_DURATION: {
      counterName: `${SCALER_COUNTER_PREFIX}/scaling-duration`,
      counterDesc: 'The number of Autoscaler polling events that failed',
      counterType: 'HISTOGRAM',
      counterUnits: 'ms', // Milliseconds.
      // This creates a set of 25 buckets with exponential growth
      // starting at 0s, 22s, 49s, 81s increasing to 7560s ~= 126mins
      // TODO: verify and adjust the bucket values.
      counterHistogramBuckets: [...Array(25).keys()].map(n =>
        Math.floor(60_000 * (2 ** (n / 4) - 1))
      ),
    },
    REQUESTS_SUCCESS: {
      counterName: `${SCALER_COUNTER_PREFIX}/requests-success`,
      counterDesc:
        'The number of scaling request messages handled successfully',
      counterType: 'CUMULATIVE',
    },
    REQUESTS_FAILED: {
      counterName: `${SCALER_COUNTER_PREFIX}/requests-failed`,
      counterDesc: 'The number of scaling request messages that failed',
      counterType: 'CUMULATIVE',
    },
  };

export const SCALER_COUNTER_DEFINITIONS: CounterDefinition[] = Object.values(
  SCALER_COUNTER_DEFINITION_MAP
);
