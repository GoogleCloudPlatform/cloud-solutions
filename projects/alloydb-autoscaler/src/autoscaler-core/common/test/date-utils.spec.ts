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

/** @fileoverview Tests for date-utils. */

import {convertMillisecondsToHumanReadable} from '../date-utils';

describe('date-utils', () => {
  describe('convertMillisecondsToHumanReadable', () => {
    [
      {
        testCaseName: 'negative number',
        inputDuration: -3_000,
        expectedOutput: '0.0 Sec',
      },
      {
        testCaseName: 'zero',
        inputDuration: 0,
        expectedOutput: '0.0 Sec',
      },
      {
        testCaseName: 'seconds',
        inputDuration: 3_599,
        expectedOutput: '3.6 Sec',
      },
      {
        testCaseName: 'minutes',
        inputDuration: 294_123,
        expectedOutput: '4.9 Min',
      },
      {
        testCaseName: 'hours',
        inputDuration: 27_828_444,
        expectedOutput: '7.7 Hrs',
      },
      {
        testCaseName: 'days',
        inputDuration: 86_400_000,
        expectedOutput: '1.0 Days',
      },
    ].forEach(({testCaseName, inputDuration, expectedOutput}) => {
      it(`returns expected string: ${testCaseName}`, () => {
        const output = convertMillisecondsToHumanReadable(inputDuration);

        expect(output).toEqual(expectedOutput);
      });
    });
  });
});
