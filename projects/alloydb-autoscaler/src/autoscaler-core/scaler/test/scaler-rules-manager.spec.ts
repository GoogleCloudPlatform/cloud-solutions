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

/** @fileoverview Tests scaler-rules-manager. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import pino from 'pino';
import {createLoggerWithMocks} from '../../testing/testing-framework';
import {
  RulesManager,
  Rules,
  RulesProfileMap,
  createSimpleRule,
  MetricOperator,
} from '../scaler-rules-manager';
import {RuleSet} from '../scaler-rules';
import {
  TEST_CUSTOM_RULE_IN,
  TEST_CUSTOM_RULE_OUT,
  TEST_INSTANCE_WITH_DATA,
} from '../../testing/testing-data';
import {AutoscalerScalingDirection} from '../scaling-methods/scaling-direction';

/** Custom Rule profiles for testing. */
const RULE_PROFILES: RulesProfileMap = new Map(
  Object.entries({
    scaleInAndOut: {
      customScaleOut: TEST_CUSTOM_RULE_OUT,
      customScaleIn: TEST_CUSTOM_RULE_IN,
    } as Rules,
  })
);

/** Default Rules for testing. */
const DEFAULT_RULES: Rules = {customRuleIn: TEST_CUSTOM_RULE_IN};

/** Custom Rules for testing. */
const CUSTOM_RULES: RuleSet[] = [TEST_CUSTOM_RULE_OUT];

describe('RulesManager', () => {
  let baseLogger: jasmine.SpyObj<pino.Logger>;
  let instanceLoggerMock: jasmine.SpyObj<pino.Logger>;

  beforeEach(() => {
    baseLogger = createLoggerWithMocks();
    instanceLoggerMock = createLoggerWithMocks();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    baseLogger.child.and.returnValue(instanceLoggerMock as any);
  });

  describe('getRules', () => {
    it('gets default rules if no scaling profile is provided', () => {
      const rulesManager = new RulesManager(
        baseLogger,
        DEFAULT_RULES,
        RULE_PROFILES
      );
      const instance = {
        ...TEST_INSTANCE_WITH_DATA,
        scalingConfig: {
          ...TEST_INSTANCE_WITH_DATA.scalingConfig,
          scalingProfile: undefined,
        },
      };

      const output = rulesManager.getRules(instance);

      expect(output).toEqual(DEFAULT_RULES);
      expect(instanceLoggerMock.info).toHaveBeenCalledWith(
        jasmine.objectContaining({
          message: 'No scaling profile configured. Using default rules:',
        })
      );
    });

    it('gets default rules for CUSTOM profile with no custom rules', () => {
      const rulesManager = new RulesManager(
        baseLogger,
        DEFAULT_RULES,
        RULE_PROFILES
      );
      const instance = {
        ...TEST_INSTANCE_WITH_DATA,
        scalingConfig: {
          ...TEST_INSTANCE_WITH_DATA.scalingConfig,
          scalingProfile: 'CUSTOM',
        },
      };

      const output = rulesManager.getRules(instance);

      expect(output).toEqual(DEFAULT_RULES);
      expect(instanceLoggerMock.info).toHaveBeenCalledWith(
        jasmine.objectContaining({
          message:
            'CUSTOM rule profile was selected, but no scalingRules were ' +
            'passed. Using default rules:',
        })
      );
    });

    it('gets default rules for CUSTOM profile with empty custom rules', () => {
      const rulesManager = new RulesManager(
        baseLogger,
        DEFAULT_RULES,
        RULE_PROFILES
      );
      const instance = {
        ...TEST_INSTANCE_WITH_DATA,
        scalingConfig: {
          ...TEST_INSTANCE_WITH_DATA.scalingConfig,
          scalingProfile: 'CUSTOM',
          scalingRules: [],
        },
      };

      const output = rulesManager.getRules(instance);

      expect(output).toEqual(DEFAULT_RULES);
      expect(instanceLoggerMock.info).toHaveBeenCalledWith(
        jasmine.objectContaining({
          message:
            'CUSTOM rule profile was selected, but no scalingRules were ' +
            'passed. Using default rules:',
        })
      );
    });

    it('gets custom rules for CUSTOM profile', () => {
      const rulesManager = new RulesManager(
        baseLogger,
        DEFAULT_RULES,
        RULE_PROFILES
      );
      const instance = {
        ...TEST_INSTANCE_WITH_DATA,
        scalingConfig: {
          ...TEST_INSTANCE_WITH_DATA.scalingConfig,
          scalingProfile: 'CUSTOM',
          scalingRules: CUSTOM_RULES,
        },
      };

      const output = rulesManager.getRules(instance);

      expect(output).toEqual({customRuleOut: TEST_CUSTOM_RULE_OUT});
      expect(instanceLoggerMock.info).toHaveBeenCalledWith(
        jasmine.objectContaining({
          message: 'Using custom rules:',
        })
      );
    });

    it('gets default rules if no profile rules are provided', () => {
      const rulesManager = new RulesManager(baseLogger, DEFAULT_RULES);
      const instance = {
        ...TEST_INSTANCE_WITH_DATA,
        scalingConfig: {
          ...TEST_INSTANCE_WITH_DATA.scalingConfig,
          scalingProfile: 'PROFILE_NAME',
        },
      };

      const output = rulesManager.getRules(instance);

      expect(output).toEqual(DEFAULT_RULES);
      expect(instanceLoggerMock.info).toHaveBeenCalledWith(
        jasmine.objectContaining({
          message:
            'No profiles exist for this autoscaler. Using default rules:',
        })
      );
    });

    it('gets default rules if predefined profile does not exist', () => {
      const rulesManager = new RulesManager(
        baseLogger,
        DEFAULT_RULES,
        RULE_PROFILES
      );
      const instance = {
        ...TEST_INSTANCE_WITH_DATA,
        scalingConfig: {
          ...TEST_INSTANCE_WITH_DATA.scalingConfig,
          scalingProfile: 'BAD_PROFILE_NAME',
        },
      };

      const output = rulesManager.getRules(instance);

      expect(output).toEqual(DEFAULT_RULES);
      expect(instanceLoggerMock.info).toHaveBeenCalledWith(
        jasmine.objectContaining({
          message:
            'Unknown scaling profile BAD_PROFILE_NAME. Using default rules:',
        })
      );
    });

    it('gets profile rules for predefined profile', () => {
      const rulesManager = new RulesManager(
        baseLogger,
        DEFAULT_RULES,
        RULE_PROFILES
      );
      const instance = {
        ...TEST_INSTANCE_WITH_DATA,
        scalingConfig: {
          ...TEST_INSTANCE_WITH_DATA.scalingConfig,
          scalingProfile: 'scaleInAndOut',
        },
      };

      const output = rulesManager.getRules(instance);

      expect(output).toEqual({
        customScaleOut: TEST_CUSTOM_RULE_OUT,
        customScaleIn: TEST_CUSTOM_RULE_IN,
      });
      expect(instanceLoggerMock.info).toHaveBeenCalledWith(
        jasmine.objectContaining({
          message: 'Using predefined scaling rules for profile scaleInAndOut:',
        })
      );
    });
  });
});

describe('createSimpleRule', () => {
  it('creates expected rule OUT', () => {
    const output = createSimpleRule(
      'customRuleOut',
      AutoscalerScalingDirection.SCALE_OUT,
      'metric_name',
      MetricOperator.GREATER_THAN,
      0.8,
      'high metric name'
    );

    expect(output).toEqual({
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
    });
  });

  it('creates expected rule IN', () => {
    const output = createSimpleRule(
      'customRuleIn',
      AutoscalerScalingDirection.SCALE_IN,
      'metric_name',
      MetricOperator.LESS_THAN,
      0.7,
      'low metric name'
    );

    expect(output).toEqual({
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
    });
  });
});
