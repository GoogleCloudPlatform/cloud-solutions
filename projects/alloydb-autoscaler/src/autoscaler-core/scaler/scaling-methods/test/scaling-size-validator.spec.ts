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

/** @fileoverview Tests scaling-size-validator. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import {silentLogger} from '../../../testing/testing-framework';
import {ScalingSizeValidator} from '../scaling-size-validator';
import {TEST_INSTANCE_WITH_DATA} from '../../../testing/testing-data';
import {ScalableInstanceWithData} from '../../../common/instance-info';
import {AutoscalerScalingDirection} from '../scaling-direction';

describe('ScalingSizeValidator', () => {
  describe('validateSuggestedSize', () => {
    it('clamps the suggestedSize to config maxSize', () => {
      const instance: ScalableInstanceWithData = {
        ...TEST_INSTANCE_WITH_DATA,
        scalingConfig: {
          ...TEST_INSTANCE_WITH_DATA.scalingConfig,
          maxSize: 10,
        },
      };
      const scalingSizeValidator = new ScalingSizeValidator(silentLogger);

      const output = scalingSizeValidator.validateSuggestedSize(
        instance,
        /** suggestedSize= */ 15,
        AutoscalerScalingDirection.SCALE_OUT
      );

      expect(output).toEqual(10);
    });

    it('clamps the suggestedSize to config minSize', () => {
      const instance: ScalableInstanceWithData = {
        ...TEST_INSTANCE_WITH_DATA,
        scalingConfig: {
          ...TEST_INSTANCE_WITH_DATA.scalingConfig,
          minSize: 5,
        },
      };
      const scalingSizeValidator = new ScalingSizeValidator(silentLogger);

      const output = scalingSizeValidator.validateSuggestedSize(
        instance,
        /** suggestedSize= */ 3,
        AutoscalerScalingDirection.SCALE_IN
      );

      expect(output).toEqual(5);
    });

    it('clamps the suggestedSize to absolute maxSize', () => {
      const instance: ScalableInstanceWithData = {
        ...TEST_INSTANCE_WITH_DATA,
        scalingConfig: {
          ...TEST_INSTANCE_WITH_DATA.scalingConfig,
          maxSize: 100,
        },
      };
      const scalingSizeValidator = new ScalingSizeValidator(
        silentLogger,
        /** absoluteMaxSize= */ 20,
        /** absoluteMinSize= */ 1
      );

      const output = scalingSizeValidator.validateSuggestedSize(
        instance,
        /** suggestedSize= */ 35,
        AutoscalerScalingDirection.SCALE_OUT
      );

      expect(output).toEqual(20);
    });

    it('clamps the suggestedSize to absolute minSize', () => {
      const instance: ScalableInstanceWithData = {
        ...TEST_INSTANCE_WITH_DATA,
        scalingConfig: {
          ...TEST_INSTANCE_WITH_DATA.scalingConfig,
          minSize: 1,
        },
      };
      const scalingSizeValidator = new ScalingSizeValidator(
        silentLogger,
        /** absoluteMinSize= */ 3,
        /** absoluteMaxSize= */ 20
      );

      const output = scalingSizeValidator.validateSuggestedSize(
        instance,
        /** suggestedSize= */ 2,
        AutoscalerScalingDirection.SCALE_IN
      );

      expect(output).toEqual(3);
    });

    it('returns suggestedSize if it was valid: no absolute values', () => {
      const instance: ScalableInstanceWithData = {
        ...TEST_INSTANCE_WITH_DATA,
        scalingConfig: {
          ...TEST_INSTANCE_WITH_DATA.scalingConfig,
          minSize: 1,
          maxSize: 100,
        },
      };
      const scalingSizeValidator = new ScalingSizeValidator(silentLogger);

      const output = scalingSizeValidator.validateSuggestedSize(
        instance,
        /** suggestedSize= */ 7,
        AutoscalerScalingDirection.SCALE_OUT
      );

      expect(output).toEqual(7);
    });

    it('returns suggestedSize if it was valid: with absolute values', () => {
      const instance: ScalableInstanceWithData = {
        ...TEST_INSTANCE_WITH_DATA,
        scalingConfig: {
          ...TEST_INSTANCE_WITH_DATA.scalingConfig,
          minSize: 1,
          maxSize: 100,
        },
      };
      const scalingSizeValidator = new ScalingSizeValidator(
        silentLogger,
        /** absoluteMinSize= */ 3,
        /** absoluteMaxSize= */ 20
      );

      const output = scalingSizeValidator.validateSuggestedSize(
        instance,
        /** suggestedSize= */ 9,
        AutoscalerScalingDirection.SCALE_OUT
      );

      expect(output).toEqual(9);
    });
  });
});
