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

/** @fileoverview Implements STEPWISE scaling method. */

import pino from 'pino';
import {ScalableInstanceWithData} from '../../common/instance-info';
import {IScalingMethod} from './scaling-method';
import {AutoscalerScalingDirection} from './scaling-direction';
import {RulesEngineAnalysis} from '../scaler-rules-engine';

/** Scales by config stepSize in the requested direction. */
export class StepwiseScalingMethod implements IScalingMethod {
  name: string = 'STEPWISE';

  /** @inheritdoc */
  calculateSuggestedSize(
    instance: ScalableInstanceWithData,
    scalingDirection: AutoscalerScalingDirection,
    // Required by signature, not in use here.
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    engineAnalysis: RulesEngineAnalysis | null,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    instanceLogger: pino.Logger
  ): number {
    const currentSize = instance.metadata.currentSize;
    const stepSize = instance.scalingConfig.stepSize;

    if (!stepSize) {
      throw new Error(
        'stepSize is not configured ' +
          'but it is required for STEPWISE scaling method'
      );
    }

    if (scalingDirection === AutoscalerScalingDirection.SCALE_OUT) {
      return currentSize + stepSize;
    }

    if (scalingDirection === AutoscalerScalingDirection.SCALE_IN) {
      return currentSize - stepSize;
    }

    if (
      scalingDirection === AutoscalerScalingDirection.SCALE_UP ||
      scalingDirection === AutoscalerScalingDirection.SCALE_DOWN
    ) {
      throw new Error(
        `STEPWISE scaler does not support ${scalingDirection}. ` +
          'Please choose another scalingMethod'
      );
    }

    return currentSize;
  }
}
