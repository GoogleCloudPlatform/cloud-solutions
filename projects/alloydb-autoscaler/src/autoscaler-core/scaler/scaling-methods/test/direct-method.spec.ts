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

/** @fileoverview Tests direct scaling method. */

import {
  TEST_ENGINE_ANALYSIS,
  TEST_INSTANCE_WITH_DATA,
} from '../../../testing/testing-data';
import {silentLogger} from '../../../testing/testing-framework';
import {DirectScalingMethod} from '../direct-method';
import {AutoscalerScalingDirection} from '../scaling-direction';

describe('DirectScalingMethod', () => {
  describe('calculateSuggestedSize', () => {
    it('returns instance max size', () => {
      const instance = {
        ...TEST_INSTANCE_WITH_DATA,
        scalingConfig: {
          ...TEST_INSTANCE_WITH_DATA.scalingConfig,
          maxSize: 77,
        },
      };
      const directMethod = new DirectScalingMethod();

      const output = directMethod.calculateSuggestedSize(
        instance,
        AutoscalerScalingDirection.SCALE_OUT,
        TEST_ENGINE_ANALYSIS,
        silentLogger
      );

      expect(output).toEqual(77);
    });
  });
});
