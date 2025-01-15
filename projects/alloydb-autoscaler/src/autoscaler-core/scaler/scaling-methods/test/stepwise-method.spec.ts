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

/** @fileoverview Tests stepwise scaling method. */

import {
  TEST_ENGINE_ANALYSIS,
  TEST_INSTANCE_WITH_DATA,
} from '../../../testing/testing-data';
import {StepwiseScalingMethod} from '../stepwise-method';
import {AutoscalerScalingDirection} from '../scaling-direction';
import {silentLogger} from '../../../testing/testing-framework';

describe('StepwiseScalingMethod', () => {
  describe('calculateSuggestedSize', () => {
    [
      {
        testCaseName: 'out by 3',
        currentSize: 2,
        stepSize: 3,
        scalingDirection: AutoscalerScalingDirection.SCALE_OUT,
        expectedSize: 5,
      },
      {
        testCaseName: 'in by 2',
        currentSize: 10,
        stepSize: 2,
        scalingDirection: AutoscalerScalingDirection.SCALE_IN,
        expectedSize: 8,
      },
      {
        testCaseName: 'no scaling',
        currentSize: 10,
        stepSize: 5,
        scalingDirection: AutoscalerScalingDirection.NONE,
        expectedSize: 10,
      },
    ].forEach(
      ({
        testCaseName,
        currentSize,
        stepSize,
        scalingDirection,
        expectedSize,
      }) => {
        it(`returns expected size value ${testCaseName}`, () => {
          const instance = {
            ...TEST_INSTANCE_WITH_DATA,
            metadata: {
              ...TEST_INSTANCE_WITH_DATA.metadata,
              currentSize: currentSize,
            },
            scalingConfig: {
              ...TEST_INSTANCE_WITH_DATA.scalingConfig,
              stepSize: stepSize,
            },
          };
          const stepwiseMethod = new StepwiseScalingMethod();

          const output = stepwiseMethod.calculateSuggestedSize(
            instance,
            scalingDirection,
            TEST_ENGINE_ANALYSIS,
            silentLogger
          );

          expect(output).toEqual(expectedSize);
        });
      }
    );

    [
      {
        scalingDirection: AutoscalerScalingDirection.SCALE_UP,
        expectedErrorMessage:
          'STEPWISE scaler does not support SCALE_UP. ' +
          'Please choose another scalingMethod',
      },
      {
        scalingDirection: AutoscalerScalingDirection.SCALE_DOWN,
        expectedErrorMessage:
          'STEPWISE scaler does not support SCALE_DOWN. ' +
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
        const stepwiseMethod = new StepwiseScalingMethod();

        expect(() => {
          stepwiseMethod.calculateSuggestedSize(
            instance,
            scalingDirection,
            TEST_ENGINE_ANALYSIS,
            silentLogger
          );
        }).toThrowError(expectedErrorMessage);
      });
    });

    it('throws if stepSize is not configured', () => {
      const instance = {
        ...TEST_INSTANCE_WITH_DATA,
        scalingConfig: {
          ...TEST_INSTANCE_WITH_DATA.scalingConfig,
          stepSize: undefined,
        },
      };
      const stepwiseMethod = new StepwiseScalingMethod();

      expect(() => {
        stepwiseMethod.calculateSuggestedSize(
          instance,
          AutoscalerScalingDirection.SCALE_OUT,
          TEST_ENGINE_ANALYSIS,
          silentLogger
        );
      }).toThrowError(
        'stepSize is not configured but it is required for STEPWISE scaling ' +
          'method'
      );
    });
  });
});
