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

/** @fileoverview Tests linear scaling method. */

import {MetricValueMap} from '../../../common/instance-info';
import {
  TEST_ENGINE_ANALYSIS,
  TEST_INSTANCE_WITH_DATA,
} from '../../../testing/testing-data';
import {silentLogger} from '../../../testing/testing-framework';
import {LinearScalingMethod} from '../linear-method';
import {AutoscalerScalingDirection} from '../scaling-direction';

// largest, multiple scale in metrics one role, multiple scale in rules

describe('LinearScalingMethod', () => {
  describe('calculateSuggestedSize', () => {
    it('returns current size for direction: NONE', () => {
      const instance = {
        ...TEST_INSTANCE_WITH_DATA,
        metadata: {
          ...TEST_INSTANCE_WITH_DATA.metadata,
          currentSize: 7,
        },
      };
      const linearMethod = new LinearScalingMethod();

      const output = linearMethod.calculateSuggestedSize(
        instance,
        AutoscalerScalingDirection.NONE,
        TEST_ENGINE_ANALYSIS,
        silentLogger
      );

      expect(output).toEqual(7);
    });

    [
      {
        testCaseName: 'by 100%, without limit',
        metricValue: 100,
        metricThreshold: 50,
        expectedSize: 20,
        currentSize: 10,
      },
      {
        testCaseName: 'by 125%, capped by limit',
        scaleOutLimit: 3,
        metricValue: 12.5,
        metricThreshold: 10,
        expectedSize: 23,
        currentSize: 20,
      },
      {
        testCaseName: 'by 125%, scaleOutLimit 0 is ignored',
        scaleOutLimit: 0,
        metricValue: 12.5,
        metricThreshold: 10,
        expectedSize: 25,
        currentSize: 20,
      },
      {
        testCaseName: 'by 75%, will keep currentSize',
        metricValue: 75,
        metricThreshold: 100,
        expectedSize: 10,
        currentSize: 10,
      },
      {
        testCaseName: 'by 50%, will keep currentSize',
        metricValue: 50,
        metricThreshold: 100,
        expectedSize: 5,
        currentSize: 5,
      },
      {
        testCaseName: 'threshold 0 is ignored, returns current size',
        metricValue: 100,
        metricThreshold: 0,
        expectedSize: 10,
        currentSize: 10,
      },
    ].forEach(
      ({
        testCaseName,
        scaleOutLimit,
        metricValue,
        metricThreshold,
        expectedSize,
        currentSize,
      }) => {
        it(`calculates expected OUT size: ${testCaseName}`, () => {
          const instance = {
            ...TEST_INSTANCE_WITH_DATA,
            metadata: {
              ...TEST_INSTANCE_WITH_DATA.metadata,
              currentSize: currentSize,
            },
            scalingConfig: {
              ...TEST_INSTANCE_WITH_DATA.scalingConfig,
              scaleInLimit: 100, // Should be ignored.
              scaleOutLimit: scaleOutLimit,
            },
            metrics: {sampleMetric1: metricValue},
          };
          const engineAnalysis = {
            ...TEST_ENGINE_ANALYSIS,
            matchedConditions: {
              ...TEST_ENGINE_ANALYSIS.matchedConditions,
              [AutoscalerScalingDirection.SCALE_OUT]: [
                {
                  fact: 'sampleMetric1',
                  operator: 'greaterThan',
                  value: metricThreshold,
                  valueResult: metricThreshold,
                  factResult: metricValue,
                  result: true,
                },
              ],
            },
            scalingMetrics: {
              ...TEST_ENGINE_ANALYSIS.scalingMetrics,
              [AutoscalerScalingDirection.SCALE_OUT]: new Set([
                'sampleMetric1',
              ]),
            },
          };
          const linearMethod = new LinearScalingMethod();

          const output = linearMethod.calculateSuggestedSize(
            instance,
            AutoscalerScalingDirection.SCALE_OUT,
            engineAnalysis,
            silentLogger
          );

          expect(output).toEqual(expectedSize);
        });
      }
    );

    [
      {
        testCaseName: 'by 75%, without limit',
        metricValue: 75,
        metricThreshold: 100,
        expectedSize: 8,
        currentSize: 10,
      },
      {
        testCaseName: 'by 50%, capped by limit',
        scaleInLimit: 2,
        metricValue: 50,
        metricThreshold: 100,
        expectedSize: 8,
        currentSize: 10,
      },
      {
        testCaseName: 'by 50%, scaleInLimit 0 is ignored',
        scaleInLimit: 0,
        metricValue: 50,
        metricThreshold: 100,
        expectedSize: 5,
        currentSize: 10,
      },
      {
        testCaseName: 'by 100%, will keep currentSize',
        metricValue: 100,
        metricThreshold: 50,
        expectedSize: 10,
        currentSize: 10,
      },
      {
        testCaseName: 'by 125%, will keep currentSize',
        metricValue: 12.5,
        metricThreshold: 10,
        expectedSize: 10,
        currentSize: 10,
      },
      {
        // Note: this will later be capped to minSize by validator.
        testCaseName: 'to 0%',
        metricValue: 0,
        metricThreshold: 10,
        expectedSize: 0,
        currentSize: 10,
      },
      {
        testCaseName: 'threshold 0 is ignored, returns current size',
        metricValue: 150,
        metricThreshold: 0,
        expectedSize: 9,
        currentSize: 9,
      },
    ].forEach(
      ({
        testCaseName,
        scaleInLimit,
        metricValue,
        metricThreshold,
        expectedSize,
        currentSize,
      }) => {
        it(`calculates expected size IN size: ${testCaseName}`, () => {
          const instance = {
            ...TEST_INSTANCE_WITH_DATA,
            metadata: {
              ...TEST_INSTANCE_WITH_DATA.metadata,
              currentSize: currentSize,
            },
            scalingConfig: {
              ...TEST_INSTANCE_WITH_DATA.scalingConfig,
              scaleInLimit: scaleInLimit,
              scaleOutLimit: 9, // Should be ignored.
            },
            metrics: {sampleMetric1: metricValue},
          };
          const engineAnalysis = {
            ...TEST_ENGINE_ANALYSIS,
            matchedConditions: {
              ...TEST_ENGINE_ANALYSIS.matchedConditions,
              [AutoscalerScalingDirection.SCALE_IN]: [
                {
                  fact: 'sampleMetric1',
                  operator: 'greaterThan',
                  value: metricThreshold,
                  valueResult: metricThreshold,
                  factResult: metricValue,
                  result: true,
                },
              ],
            },
            scalingMetrics: {
              ...TEST_ENGINE_ANALYSIS.scalingMetrics,
              [AutoscalerScalingDirection.SCALE_IN]: new Set(['sampleMetric1']),
            },
          };
          const linearMethod = new LinearScalingMethod();

          const output = linearMethod.calculateSuggestedSize(
            instance,
            AutoscalerScalingDirection.SCALE_IN,
            engineAnalysis,
            silentLogger
          );

          expect(output).toEqual(expectedSize);
        });
      }
    );

    it('returns currentSize if there is no engineAnalysis', () => {
      const instance = {
        ...TEST_INSTANCE_WITH_DATA,
        metadata: {
          ...TEST_INSTANCE_WITH_DATA.metadata,
          currentSize: 3,
        },
      };
      const linearMethod = new LinearScalingMethod();

      const output = linearMethod.calculateSuggestedSize(
        instance,
        AutoscalerScalingDirection.SCALE_OUT,
        null,
        silentLogger
      );

      expect(output).toEqual(3);
    });

    [
      AutoscalerScalingDirection.SCALE_OUT,
      AutoscalerScalingDirection.SCALE_IN,
    ].forEach(direction => {
      it(`returns current size for no matched metrics - ${direction}`, () => {
        const instance = {
          ...TEST_INSTANCE_WITH_DATA,
          metadata: {
            ...TEST_INSTANCE_WITH_DATA.metadata,
            currentSize: 2,
          },
        };
        const engineAnalysis = {
          ...TEST_ENGINE_ANALYSIS,
          matchedConditions: {
            ...TEST_ENGINE_ANALYSIS.matchedConditions,
            [direction]: [
              {
                fact: 'sampleMetric1',
                operator: 'greaterThan',
                value: 40,
                valueResult: 40,
                factResult: 80,
                result: true,
              },
            ],
          },
          scalingMetrics: {
            ...TEST_ENGINE_ANALYSIS.scalingMetrics,
            [direction]: new Set([]), // Empty set.
          },
        };
        const linearMethod = new LinearScalingMethod();

        const output = linearMethod.calculateSuggestedSize(
          instance,
          direction,
          engineAnalysis,
          silentLogger
        );

        expect(output).toEqual(2);
      });
    });

    [
      {
        scalingDirection: AutoscalerScalingDirection.SCALE_UP,
        expectedErrorMessage:
          'LINEAR scaler does not support SCALE_UP. ' +
          'Please choose another scalingMethod',
      },
      {
        scalingDirection: AutoscalerScalingDirection.SCALE_DOWN,
        expectedErrorMessage:
          'LINEAR scaler does not support SCALE_DOWN. ' +
          'Please choose another scalingMethod',
      },
    ].forEach(({scalingDirection, expectedErrorMessage}) => {
      it('throws for unsupported scaling directions', () => {
        const instance = {
          ...TEST_INSTANCE_WITH_DATA,
          scalingConfig: {
            ...TEST_INSTANCE_WITH_DATA.scalingConfig,
            stepSize: 2,
          },
        };
        const linearMethod = new LinearScalingMethod();

        expect(() => {
          linearMethod.calculateSuggestedSize(
            instance,
            scalingDirection,
            TEST_ENGINE_ANALYSIS,
            silentLogger
          );
        }).toThrowError(expectedErrorMessage);
      });
    });

    [
      {
        testCaseName: 'OUT, same metric, two matches, uses largest size',
        scalingDirection: AutoscalerScalingDirection.SCALE_OUT,
        metrics: {sampleMetric1: 10},
        matchedRules: [
          {
            fact: 'sampleMetric1',
            operator: 'greaterThan',
            value: 1,
            valueResult: 1,
            factResult: 10, // 10x
            result: true,
          },
          {
            fact: 'sampleMetric1',
            operator: 'greaterThan',
            value: 1,
            valueResult: 1,
            factResult: 2, // 2x
            result: true,
          },
        ],
        scalingMetrics: ['sampleMetric1'],
        currentSize: 5,
        expectedSize: 50, // 10x over 2x
      },
      {
        testCaseName: 'OUT, different metrics, uses largest size',
        scalingDirection: AutoscalerScalingDirection.SCALE_OUT,
        metrics: {sampleMetric1: 200, sampleMetric2: 150},
        matchedRules: [
          {
            fact: 'sampleMetric1',
            operator: 'greaterThan',
            value: 100,
            valueResult: 100,
            factResult: 200, // 2x
            result: true,
          },
          {
            fact: 'sampleMetric2',
            operator: 'greaterThan',
            value: 100,
            valueResult: 100,
            factResult: 150, // 1.5x
            result: true,
          },
        ],
        scalingMetrics: ['sampleMetric1', 'sampleMetric2'],
        currentSize: 10,
        expectedSize: 20, // 10x over 2x
      },
      {
        testCaseName: 'OUT, uses only metrics in scalingMetrics',
        scalingDirection: AutoscalerScalingDirection.SCALE_OUT,
        metrics: {sampleMetric1: 200, sampleMetric2: 150},
        matchedRules: [
          {
            fact: 'sampleMetric1',
            operator: 'greaterThan',
            value: 100,
            valueResult: 100,
            factResult: 200, // 2x
            result: true,
          },
          {
            fact: 'sampleMetric2',
            operator: 'greaterThan',
            value: 100,
            valueResult: 100,
            factResult: 150, // 1.5x
            result: true,
          },
        ],
        scalingMetrics: ['sampleMetric2'],
        currentSize: 10,
        expectedSize: 15, // Uses only sampleMetric2 from matchedMetrics
      },

      {
        testCaseName: 'IN, same metric, two matches, uses largest size',
        scalingDirection: AutoscalerScalingDirection.SCALE_IN,
        metrics: {sampleMetric1: 50},
        matchedRules: [
          {
            fact: 'sampleMetric1',
            operator: 'greaterThan',
            value: 100,
            valueResult: 100,
            factResult: 50, // 50%
            result: true,
          },
          {
            fact: 'sampleMetric1',
            operator: 'greaterThan',
            value: 200,
            valueResult: 200,
            factResult: 50, // 25%
            result: true,
          },
        ],
        scalingMetrics: ['sampleMetric1'],
        currentSize: 100,
        expectedSize: 50, // 50% over 25%
      },
      {
        testCaseName: 'IN, different metrics, uses largest size',
        scalingDirection: AutoscalerScalingDirection.SCALE_IN,
        metrics: {sampleMetric1: 50, sampleMetric2: 75},
        matchedRules: [
          {
            fact: 'sampleMetric1',
            operator: 'greaterThan',
            value: 100,
            valueResult: 100,
            factResult: 50, // 50%
            result: true,
          },
          {
            fact: 'sampleMetric2',
            operator: 'greaterThan',
            value: 100,
            valueResult: 100,
            factResult: 75, // 75%
            result: true,
          },
        ],
        scalingMetrics: ['sampleMetric1', 'sampleMetric2'],
        currentSize: 10,
        expectedSize: 8, // 75% over 50%
      },
      {
        testCaseName: 'IN, uses only metrics in scalingMetrics',
        scalingDirection: AutoscalerScalingDirection.SCALE_IN,
        metrics: {sampleMetric1: 50, sampleMetric2: 25},
        matchedRules: [
          {
            fact: 'sampleMetric1',
            operator: 'greaterThan',
            value: 100,
            valueResult: 100,
            factResult: 50, // 50%
            result: true,
          },
          {
            fact: 'sampleMetric2',
            operator: 'greaterThan',
            value: 100,
            valueResult: 100,
            factResult: 25, // 25%
            result: true,
          },
        ],
        scalingMetrics: ['sampleMetric2'],
        currentSize: 100,
        expectedSize: 25, // Uses only sampleMetric2 from matchedMetrics
      },
    ].forEach(
      ({
        testCaseName,
        scalingDirection,
        metrics,
        matchedRules,
        scalingMetrics,
        currentSize,
        expectedSize,
      }) => {
        it(`return right size for multiple rules: ${testCaseName}`, () => {
          const instance = {
            ...TEST_INSTANCE_WITH_DATA,
            metadata: {
              ...TEST_INSTANCE_WITH_DATA.metadata,
              currentSize: currentSize,
            },
            metrics: metrics as MetricValueMap,
          };
          const engineAnalysis = {
            ...TEST_ENGINE_ANALYSIS,
            matchedConditions: {
              ...TEST_ENGINE_ANALYSIS.matchedConditions,
              [scalingDirection]: matchedRules,
            },
            scalingMetrics: {
              ...TEST_ENGINE_ANALYSIS.scalingMetrics,
              [scalingDirection]: new Set(scalingMetrics),
            },
          };
          const linearMethod = new LinearScalingMethod();

          const output = linearMethod.calculateSuggestedSize(
            instance,
            scalingDirection,
            engineAnalysis,
            silentLogger
          );

          expect(output).toEqual(expectedSize);
        });
      }
    );
  });
});
