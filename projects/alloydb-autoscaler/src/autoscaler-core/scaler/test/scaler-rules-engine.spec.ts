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

/** @fileoverview Tests scaler-method-runner. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import {
  TEST_BASE_RULES,
  TEST_ENGINE_ANALYSIS,
  TEST_INSTANCE_WITH_DATA,
} from '../../testing/testing-data';
import {createSimpleRule, MetricOperator, Rules} from '../scaler-rules-manager';
import {RulesEngine, RulesEngineAnalysis} from '../scaler-rules-engine';
import {silentLogger} from '../../testing/testing-framework';
import {AutoscalerScalingDirection} from '../scaling-methods/scaling-direction';
import {ScalableInstanceWithData} from '../../common/instance-info';

describe('RulesEngine', () => {
  describe('getEngineAnalysis', () => {
    it('returns null if no rules are passed', async () => {
      const rulesEngine = new RulesEngine(silentLogger);

      const output = await rulesEngine.getEngineAnalysis(
        TEST_INSTANCE_WITH_DATA
      );

      expect(output).toBeNull();
    });

    // Condition class is not exported, only its type. As such,
    // jasmine.objectContaining is used to compare matchedConditions to ensure
    // the fields of the returned condition matched what's expected.
    [
      {
        testCaseName: 'no rules triggered',
        instance: {
          ...TEST_INSTANCE_WITH_DATA,
          metrics: {metric_name: 0.7, other_metric: 7},
        } as ScalableInstanceWithData,
        rules: TEST_BASE_RULES as Rules,
        expectedEngineAnalysis: TEST_ENGINE_ANALYSIS as RulesEngineAnalysis,
      },

      {
        testCaseName: 'SCALE_IN rule triggered',
        instance: {
          ...TEST_INSTANCE_WITH_DATA,
          metrics: {metric_name: 0.1, other_metric: 7},
        },
        rules: TEST_BASE_RULES,
        expectedEngineAnalysis: {
          firingRuleCount: {
            ...TEST_ENGINE_ANALYSIS.firingRuleCount,
            [AutoscalerScalingDirection.SCALE_IN]: 1,
          },
          matchedConditions: {
            ...TEST_ENGINE_ANALYSIS.matchedConditions,
            [AutoscalerScalingDirection.SCALE_IN]: [
              jasmine.objectContaining({
                fact: 'metric_name',
                operator: 'lessThan',
                value: 0.7,
                factResult: 0.1,
                valueResult: 0.7,
                result: true,
              }),
            ],
          },
          scalingMetrics: {
            ...TEST_ENGINE_ANALYSIS.scalingMetrics,
            [AutoscalerScalingDirection.SCALE_IN]: new Set(['metric_name']),
          },
        },
      },

      {
        testCaseName: 'SCALE_OUT rule triggered',
        instance: {
          ...TEST_INSTANCE_WITH_DATA,
          metrics: {metric_name: 0.99, other_metric: 7},
        },
        rules: TEST_BASE_RULES,
        expectedEngineAnalysis: {
          firingRuleCount: {
            ...TEST_ENGINE_ANALYSIS.firingRuleCount,
            [AutoscalerScalingDirection.SCALE_OUT]: 1,
          },
          matchedConditions: {
            ...TEST_ENGINE_ANALYSIS.matchedConditions,
            [AutoscalerScalingDirection.SCALE_OUT]: [
              jasmine.objectContaining({
                fact: 'metric_name',
                operator: 'greaterThan',
                value: 0.8,
                factResult: 0.99,
                valueResult: 0.8,
                result: true,
              }),
            ],
          },
          scalingMetrics: {
            ...TEST_ENGINE_ANALYSIS.scalingMetrics,
            [AutoscalerScalingDirection.SCALE_OUT]: new Set(['metric_name']),
          },
        },
      },

      {
        testCaseName: 'SCALE_IN and SCALE_OUT rules triggered',
        instance: {
          ...TEST_INSTANCE_WITH_DATA,
          metrics: {metric_name: 0.5, other_metric: 7},
        },
        rules: {
          firedInRule: createSimpleRule(
            'firedInRule',
            AutoscalerScalingDirection.SCALE_IN,
            'metric_name',
            MetricOperator.LESS_THAN,
            1,
            'scale in'
          ),
          firedOutRule: createSimpleRule(
            'firedOutRule',
            AutoscalerScalingDirection.SCALE_OUT,
            'metric_name',
            MetricOperator.GREATER_THAN,
            0,
            'scale out'
          ),
        },
        expectedEngineAnalysis: {
          firingRuleCount: {
            ...TEST_ENGINE_ANALYSIS.firingRuleCount,
            [AutoscalerScalingDirection.SCALE_OUT]: 1,
            [AutoscalerScalingDirection.SCALE_IN]: 1,
          },
          matchedConditions: {
            ...TEST_ENGINE_ANALYSIS.matchedConditions,
            [AutoscalerScalingDirection.SCALE_OUT]: [
              jasmine.objectContaining({
                fact: 'metric_name',
                operator: 'greaterThan',
                value: 0,
                factResult: 0.5,
                valueResult: 0,
                result: true,
              }),
            ],
            [AutoscalerScalingDirection.SCALE_IN]: [
              jasmine.objectContaining({
                fact: 'metric_name',
                operator: 'lessThan',
                value: 1,
                factResult: 0.5,
                valueResult: 1,
                result: true,
              }),
            ],
          },
          scalingMetrics: {
            ...TEST_ENGINE_ANALYSIS.scalingMetrics,
            [AutoscalerScalingDirection.SCALE_OUT]: new Set(['metric_name']),
            [AutoscalerScalingDirection.SCALE_IN]: new Set(['metric_name']),
          },
        },
      },

      {
        testCaseName: 'multiple SCALE_IN rules triggered',
        instance: {
          ...TEST_INSTANCE_WITH_DATA,
          metrics: {metric_name: 0.1, other_metric: 7},
        },
        rules: {
          ...TEST_BASE_RULES,
          otherRule: createSimpleRule(
            'otherRule',
            AutoscalerScalingDirection.SCALE_IN,
            'other_metric',
            MetricOperator.GREATER_THAN,
            1,
            'other scale IN rule'
          ),
        },
        expectedEngineAnalysis: {
          firingRuleCount: {
            ...TEST_ENGINE_ANALYSIS.firingRuleCount,
            [AutoscalerScalingDirection.SCALE_IN]: 2,
          },
          matchedConditions: {
            ...TEST_ENGINE_ANALYSIS.matchedConditions,
            [AutoscalerScalingDirection.SCALE_IN]: [
              jasmine.objectContaining({
                fact: 'metric_name',
                operator: 'lessThan',
                value: 0.7,
                factResult: 0.1,
                valueResult: 0.7,
                result: true,
              }),
              jasmine.objectContaining({
                fact: 'other_metric',
                operator: 'greaterThan',
                value: 1,
                factResult: 7,
                valueResult: 1,
                result: true,
              }),
            ],
          },
          scalingMetrics: {
            ...TEST_ENGINE_ANALYSIS.scalingMetrics,
            [AutoscalerScalingDirection.SCALE_IN]: new Set([
              'metric_name',
              'other_metric',
            ]),
          },
        },
      },

      {
        testCaseName: 'mutliple SCALE_OUT rules triggered',
        instance: {
          ...TEST_INSTANCE_WITH_DATA,
          metrics: {metric_name: 0.99, other_metric: 7},
        },
        rules: {
          ...TEST_BASE_RULES,
          otherRule: createSimpleRule(
            'otherRule',
            AutoscalerScalingDirection.SCALE_OUT,
            'other_metric',
            MetricOperator.LESS_THAN,
            10,
            'other scale OUT rule'
          ),
        },
        expectedEngineAnalysis: {
          firingRuleCount: {
            ...TEST_ENGINE_ANALYSIS.firingRuleCount,
            [AutoscalerScalingDirection.SCALE_OUT]: 2,
          },
          matchedConditions: {
            ...TEST_ENGINE_ANALYSIS.matchedConditions,
            [AutoscalerScalingDirection.SCALE_OUT]: [
              jasmine.objectContaining({
                fact: 'metric_name',
                operator: 'greaterThan',
                value: 0.8,
                factResult: 0.99,
                valueResult: 0.8,
                result: true,
              }),
              jasmine.objectContaining({
                fact: 'other_metric',
                operator: 'lessThan',
                value: 10,
                factResult: 7,
                valueResult: 10,
                result: true,
              }),
            ],
          },
          scalingMetrics: {
            ...TEST_ENGINE_ANALYSIS.scalingMetrics,
            [AutoscalerScalingDirection.SCALE_OUT]: new Set([
              'metric_name',
              'other_metric',
            ]),
          },
        },
      },
    ].forEach(({testCaseName, instance, rules, expectedEngineAnalysis}) => {
      it(`returns expected engine analysis: ${testCaseName}`, async () => {
        const rulesEngine = new RulesEngine(silentLogger);

        const output = await rulesEngine.getEngineAnalysis(instance, rules);

        expect(output).toEqual(expectedEngineAnalysis);
      });
    });
  });
});
