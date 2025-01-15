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
 * limitations under the License.
 */

/** @fileoverview Provides common data for testing. */

import {
  ScalableInstance,
  ScalableInstanceWithData,
} from '../common/instance-info';
import {RuleSet} from '../scaler/scaler-rules';
import {RulesEngineAnalysis} from '../scaler/scaler-rules-engine';
import {Rules} from '../scaler/scaler-rules-manager';
import {AutoscalerScalingDirection} from '../scaler/scaling-methods/scaling-direction';
import {StateData} from '../scaler/state-stores/state';

/** A ScaleableInstance for testing. */
export const TEST_INSTANCE: ScalableInstance = Object.freeze({
  info: Object.freeze({
    projectId: 'project-123',
    regionId: 'us-central1',
    resourcePath: 'projects/project-123/locations/us-central1',
  }),
  scalingConfig: Object.freeze({
    minSize: 1,
    maxSize: 10,
    scalingMethod: 'DIRECT',
    scaleInCoolingMinutes: 15,
    scaleOutCoolingMinutes: 5,
  }),
  stateConfig: Object.freeze({}),
});

/** A ScaleableInstance with data for testing. */
export const TEST_INSTANCE_WITH_DATA: ScalableInstanceWithData = Object.freeze({
  ...TEST_INSTANCE,
  metadata: Object.freeze({currentSize: 7}),
  metrics: Object.freeze({}),
});

/** A StateData for testing. */
export const TEST_STATE_DATA: StateData = {
  scalingOperationId: 'id-123',
  scalingRequestedSize: 5,
  scalingPreviousSize: 3,
  scalingMethod: 'DIRECT',
  createdOn: 1e6,
  updatedOn: 2e6,
  lastScalingTimestamp: 3e6,
  lastScalingCompleteTimestamp: 4e6,
};

/** A cancelled Scale operation for testing. */
export const TEST_OPERATION_CANCELLED = Object.freeze({
  done: false,
  name: 'cancelledOperation',
  metadata: Object.freeze({
    '@type': 'OperationMetadata',
    createTime: '2024-01-01T00:00:00Z',
    endTime: '2024-01-01T00:01:00Z',
    requestedCancellation: true,
  }),
});

/** A running Scale operation for testing. */
export const TEST_OPERATION_RUNNING = Object.freeze({
  done: false,
  name: 'runningOperation',
  metadata: Object.freeze({
    '@type': 'OperationMetadata',
    createTime: '2024-01-01T00:00:00Z',
    endTime: '2024-01-01T00:01:00Z',
  }),
});

/** A failed Scale operation for testing. */
export const TEST_OPERATION_FAILED = Object.freeze({
  done: true,
  name: 'failedOperation',
  metadata: Object.freeze({
    '@type': 'OperationMetadata',
    createTime: '2024-01-01T00:00:00Z',
    endTime: '2024-01-01T00:01:00Z',
  }),
  error: Object.freeze({
    message: 'Unexpected error',
  }),
});

/** A successful Scale operation for testing. */
export const TEST_OPERATION_SUCCESSFUL = Object.freeze({
  done: true,
  name: 'successfulOperation',
  metadata: Object.freeze({
    '@type': 'OperationMetadata',
    createTime: '2024-01-01T00:00:00Z',
    endTime: '2024-01-01T00:01:00Z',
  }),
});

/** A successful Scale operation, without end time, for testing. */
export const TEST_OPERATION_SUCCESSFUL_WITHOUT_END_TIME = Object.freeze({
  done: true,
  name: 'successfulOperation',
  metadata: Object.freeze({
    '@type': 'OperationMetadata',
    createTime: '2024-01-01T00:00:00Z',
  }),
});

/** A sample RuleSet for Scaling IN. */
export const TEST_CUSTOM_RULE_IN: RuleSet = {
  name: 'customRuleIn',
  conditions: {
    all: [
      {
        fact: 'metric_name',
        operator: 'lessThan',
        value: 0.7,
      },
    ],
  },
  event: {
    type: AutoscalerScalingDirection.SCALE_IN,
    params: {
      message: 'low metric name',
      scalingMetrics: ['metric_name'],
    },
  },
  priority: 1,
};

/** A sample RuleSet for Scaling OUT. */
export const TEST_CUSTOM_RULE_OUT: RuleSet = {
  name: 'customRuleOut',
  conditions: {
    all: [
      {
        fact: 'metric_name',
        operator: 'greaterThan',
        value: 0.8,
      },
    ],
  },
  event: {
    type: AutoscalerScalingDirection.SCALE_OUT,
    params: {
      message: 'high metric name',
      scalingMetrics: ['metric_name'],
    },
  },
  priority: 1,
};

/** A sample Rules object with one rule of each kind. */
export const TEST_BASE_RULES: Rules = {
  customRuleIn: TEST_CUSTOM_RULE_IN,
  customRuleOut: TEST_CUSTOM_RULE_OUT,
};

/** Empty (default) engine analysis. */
export const TEST_ENGINE_ANALYSIS: RulesEngineAnalysis = Object.freeze({
  firingRuleCount: Object.freeze({
    [AutoscalerScalingDirection.SCALE_UP]: 0,
    [AutoscalerScalingDirection.SCALE_DOWN]: 0,
    [AutoscalerScalingDirection.SCALE_OUT]: 0,
    [AutoscalerScalingDirection.SCALE_IN]: 0,
    [AutoscalerScalingDirection.SCALE_SAME]: 0,
    [AutoscalerScalingDirection.NONE]: 0,
  }),
  matchedConditions: Object.freeze({
    [AutoscalerScalingDirection.SCALE_UP]: [],
    [AutoscalerScalingDirection.SCALE_DOWN]: [],
    [AutoscalerScalingDirection.SCALE_OUT]: [],
    [AutoscalerScalingDirection.SCALE_IN]: [],
    [AutoscalerScalingDirection.SCALE_SAME]: [],
    [AutoscalerScalingDirection.NONE]: [],
  }),
  scalingMetrics: Object.freeze({
    [AutoscalerScalingDirection.SCALE_UP]: new Set() as Set<string>,
    [AutoscalerScalingDirection.SCALE_DOWN]: new Set() as Set<string>,
    [AutoscalerScalingDirection.SCALE_OUT]: new Set() as Set<string>,
    [AutoscalerScalingDirection.SCALE_IN]: new Set() as Set<string>,
    [AutoscalerScalingDirection.SCALE_SAME]: new Set() as Set<string>,
    [AutoscalerScalingDirection.NONE]: new Set() as Set<string>,
  }),
});
