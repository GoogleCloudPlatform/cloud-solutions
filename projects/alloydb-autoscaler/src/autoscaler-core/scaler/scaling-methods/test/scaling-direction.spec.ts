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

/** @fileoverview Tests scaling-direction. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import {
  getScalingDirection,
  convertScalingDirectionToAutoscalerDirection,
  ScalingDirection,
  AutoscalerScalingDirection,
} from '../scaling-direction';
import {TEST_INSTANCE_WITH_DATA} from '../../../testing/testing-data';

describe('getScalingDirection', () => {
  [
    {
      testCaseName: 'UP, no previous size',
      currentSize: 3,
      suggestedSize: 5,
      previousSize: undefined,
      expectedDirection: ScalingDirection.SCALE_UP,
    },
    {
      testCaseName: 'DOWN, no previous size',
      currentSize: 7,
      suggestedSize: 2,
      previousSize: undefined,
      expectedDirection: ScalingDirection.SCALE_DOWN,
    },
    {
      testCaseName: 'SAME, no previous size',
      currentSize: 4,
      suggestedSize: 4,
      previousSize: undefined,
      expectedDirection: ScalingDirection.SCALE_SAME,
    },
    {
      testCaseName: 'UP, no previous size',
      currentSize: 10,
      suggestedSize: 5,
      previousSize: 4,
      expectedDirection: ScalingDirection.SCALE_UP,
    },
    {
      testCaseName: 'DOWN, no previous size',
      currentSize: 1,
      suggestedSize: 2,
      previousSize: 4,
      expectedDirection: ScalingDirection.SCALE_DOWN,
    },
    {
      testCaseName: 'SAME, no previous size',
      currentSize: 10,
      suggestedSize: 4,
      previousSize: 4,
      expectedDirection: ScalingDirection.SCALE_SAME,
    },
    {
      testCaseName: 'previous size is zero',
      currentSize: 10,
      suggestedSize: 3,
      previousSize: 0,
      expectedDirection: ScalingDirection.SCALE_UP,
    },
  ].forEach(
    ({
      testCaseName,
      currentSize,
      suggestedSize,
      previousSize,
      expectedDirection,
    }) => {
      it(`returns expected direction ${testCaseName}`, () => {
        const instance = {
          ...TEST_INSTANCE_WITH_DATA,
          metadata: Object.freeze({currentSize: currentSize}),
        };

        const output = getScalingDirection(
          instance,
          suggestedSize,
          previousSize
        );

        expect(output).toEqual(expectedDirection);
      });
    }
  );
});

describe('convertScalingDirectionToAutoscalerDirection', () => {
  [
    {
      inputDirection: ScalingDirection.SCALE_DOWN,
      inputAutoscalerDirection: AutoscalerScalingDirection.NONE,
      expectedOutput: AutoscalerScalingDirection.SCALE_IN,
    },
    {
      inputDirection: ScalingDirection.SCALE_DOWN,
      inputAutoscalerDirection: AutoscalerScalingDirection.SCALE_DOWN,
      expectedOutput: AutoscalerScalingDirection.SCALE_DOWN,
    },
    {
      inputDirection: ScalingDirection.SCALE_DOWN,
      inputAutoscalerDirection: AutoscalerScalingDirection.SCALE_IN,
      expectedOutput: AutoscalerScalingDirection.SCALE_IN,
    },
    {
      inputDirection: ScalingDirection.SCALE_DOWN,
      inputAutoscalerDirection: AutoscalerScalingDirection.SCALE_OUT,
      expectedOutput: AutoscalerScalingDirection.SCALE_IN,
    },
    {
      inputDirection: ScalingDirection.SCALE_DOWN,
      inputAutoscalerDirection: AutoscalerScalingDirection.SCALE_SAME,
      expectedOutput: AutoscalerScalingDirection.SCALE_IN,
    },
    {
      inputDirection: ScalingDirection.SCALE_DOWN,
      inputAutoscalerDirection: AutoscalerScalingDirection.SCALE_UP,
      expectedOutput: AutoscalerScalingDirection.SCALE_DOWN,
    },
    {
      inputDirection: ScalingDirection.SCALE_SAME,
      inputAutoscalerDirection: AutoscalerScalingDirection.NONE,
      expectedOutput: AutoscalerScalingDirection.SCALE_SAME,
    },
    {
      inputDirection: ScalingDirection.SCALE_SAME,
      inputAutoscalerDirection: AutoscalerScalingDirection.SCALE_DOWN,
      expectedOutput: AutoscalerScalingDirection.SCALE_SAME,
    },
    {
      inputDirection: ScalingDirection.SCALE_SAME,
      inputAutoscalerDirection: AutoscalerScalingDirection.SCALE_IN,
      expectedOutput: AutoscalerScalingDirection.SCALE_SAME,
    },
    {
      inputDirection: ScalingDirection.SCALE_SAME,
      inputAutoscalerDirection: AutoscalerScalingDirection.SCALE_OUT,
      expectedOutput: AutoscalerScalingDirection.SCALE_SAME,
    },
    {
      inputDirection: ScalingDirection.SCALE_SAME,
      inputAutoscalerDirection: AutoscalerScalingDirection.SCALE_SAME,
      expectedOutput: AutoscalerScalingDirection.SCALE_SAME,
    },
    {
      inputDirection: ScalingDirection.SCALE_SAME,
      inputAutoscalerDirection: AutoscalerScalingDirection.SCALE_UP,
      expectedOutput: AutoscalerScalingDirection.SCALE_SAME,
    },
    {
      inputDirection: ScalingDirection.SCALE_UP,
      inputAutoscalerDirection: AutoscalerScalingDirection.NONE,
      expectedOutput: AutoscalerScalingDirection.SCALE_OUT,
    },
    {
      inputDirection: ScalingDirection.SCALE_UP,
      inputAutoscalerDirection: AutoscalerScalingDirection.SCALE_DOWN,
      expectedOutput: AutoscalerScalingDirection.SCALE_UP,
    },
    {
      inputDirection: ScalingDirection.SCALE_UP,
      inputAutoscalerDirection: AutoscalerScalingDirection.SCALE_IN,
      expectedOutput: AutoscalerScalingDirection.SCALE_OUT,
    },
    {
      inputDirection: ScalingDirection.SCALE_UP,
      inputAutoscalerDirection: AutoscalerScalingDirection.SCALE_OUT,
      expectedOutput: AutoscalerScalingDirection.SCALE_OUT,
    },
    {
      inputDirection: ScalingDirection.SCALE_UP,
      inputAutoscalerDirection: AutoscalerScalingDirection.SCALE_SAME,
      expectedOutput: AutoscalerScalingDirection.SCALE_OUT,
    },
    {
      inputDirection: ScalingDirection.SCALE_UP,
      inputAutoscalerDirection: AutoscalerScalingDirection.SCALE_UP,
      expectedOutput: AutoscalerScalingDirection.SCALE_UP,
    },
  ].forEach(({inputDirection, inputAutoscalerDirection, expectedOutput}) => {
    const testCaseName =
      'converts to expected direction ' +
      `(${inputDirection}, ${inputAutoscalerDirection})`;
    it(testCaseName, () => {
      const output = convertScalingDirectionToAutoscalerDirection(
        inputDirection,
        inputAutoscalerDirection
      );

      expect(output).toEqual(expectedOutput);
    });
  });
});
