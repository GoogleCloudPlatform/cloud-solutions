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

/** @fileoverview Provides scaling rules for the AlloyDB Autoscaler. */

import {AutoscalerScalingDirection} from '../../../autoscaler-core/scaler/scaling-methods/scaling-direction';

/** Scales OUT if Average CPU utilization is above 80%. */
export const CPU_HIGH_AVERAGE_UTILIZATION = {
  name: 'cpuHighAverageUtilization',
  conditions: {
    all: [
      {
        fact: 'cpuAverageUtilization',
        operator: 'greaterThan',
        value: 0.8,
      },
    ],
  },
  event: {
    type: AutoscalerScalingDirection.SCALE_OUT,
    params: {
      message: 'high average CPU utilization',
      scalingMetrics: ['cpuAverageUtilization'],
    },
  },
};

/**
 * Scales IN if Average CPU utilization is below 75% and it is not limited by
 * the number of connections (70%).
 */
export const CPU_LOW_AVERAGE_UTILIZATION = {
  name: 'cpuLowAverageUtilization',
  conditions: {
    all: [
      {
        fact: 'cpuAverageUtilization',
        operator: 'lessThan',
        value: 0.75,
      },
      {
        fact: 'connectionsUtilization',
        operator: 'lessThan',
        value: 0.7,
      },
    ],
  },
  event: {
    type: AutoscalerScalingDirection.SCALE_IN,
    params: {
      message: 'low average CPU utilization',
      scalingMetrics: ['cpuAverageUtilization'],
    },
  },
};

/**
 * Scales OUT if Maximum CPU utilization is above 75% and the Average CPU
 * utilization is above 70%.
 */
export const CPU_HIGH_MAXIMUM_UTILIZATION = {
  name: 'cpuHighMaximumUtilization',
  conditions: {
    all: [
      {
        fact: 'cpuMaximumUtilization',
        operator: 'greaterThan',
        value: 0.75,
      },
      {
        fact: 'cpuAverageUtilization',
        operator: 'greaterThan',
        value: 0.7,
      },
    ],
  },
  event: {
    type: AutoscalerScalingDirection.SCALE_OUT,
    params: {
      message: 'high maximum CPU utilization',
      scalingMetrics: ['cpuMaximumUtilization'],
    },
  },
};

/**
 * Scales IN if Maximum CPU utilization is below 70%, the Average CPU
 * utilization is below 50% and it is not limited by the number of connections
 * (70%).
 */
export const CPU_LOW_MAXIMUM_UTILIZATION = {
  name: 'cpuLowMaximumUtilization',
  conditions: {
    all: [
      {
        fact: 'cpuMaximumUtilization',
        operator: 'lessThan',
        value: 0.7,
      },
      {
        fact: 'cpuAverageUtilization',
        operator: 'lessThan',
        value: 0.5,
      },
      {
        fact: 'connectionsUtilization',
        operator: 'lessThan',
        value: 0.7,
      },
    ],
  },
  event: {
    type: AutoscalerScalingDirection.SCALE_IN,
    params: {
      message: 'low maximum CPU utilization',
      scalingMetrics: ['cpuMaximumUtilization'],
    },
  },
};

/** Scales OUT if connections utilization is above 80%. */
export const CONNECTIONS_HIGH_UTILIZATION = {
  name: 'connectionsHighUtilization',
  conditions: {
    all: [
      {
        fact: 'connectionsUtilization',
        operator: 'greaterThan',
        value: 0.8,
      },
    ],
  },
  event: {
    type: AutoscalerScalingDirection.SCALE_OUT,
    params: {
      message: 'high connections utilization',
      scalingMetrics: ['connectionsUtilization'],
    },
  },
};
