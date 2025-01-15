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

/** @fileoverview Provides poller counter definitions. */

import {CounterDefinition} from '../common/counters';

const POLLER_COUNTER_PREFIX = 'poller';

export const POLLER_COUNTER_DEFINITION_MAP: Record<string, CounterDefinition> =
  {
    POLLING_SUCCESS: {
      counterName: `${POLLER_COUNTER_PREFIX}/polling-success`,
      counterDesc: 'The number of Autoscaler polling events that succeeded',
      counterType: 'CUMULATIVE',
    },
    POLLING_FAILED: {
      counterName: `${POLLER_COUNTER_PREFIX}/polling-failed`,
      counterDesc: 'The number of Autoscaler polling events that failed',
      counterType: 'CUMULATIVE',
    },
    REQUESTS_SUCCESS: {
      counterName: `${POLLER_COUNTER_PREFIX}/requests-success`,
      counterDesc:
        'The number of polling request messages handled successfully',
      counterType: 'CUMULATIVE',
    },
    REQUESTS_FAILED: {
      counterName: `${POLLER_COUNTER_PREFIX}/requests-failed`,
      counterDesc: 'The number of polling request messages that failed',
      counterType: 'CUMULATIVE',
    },
  };

export const POLLER_COUNTER_DEFINITIONS: CounterDefinition[] = Object.values(
  POLLER_COUNTER_DEFINITION_MAP
);
