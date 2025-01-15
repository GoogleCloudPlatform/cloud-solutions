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

/** @fileoverview Implements DIRECT scaling method. */

import pino from 'pino';
import {ScalableInstanceWithData} from '../../common/instance-info';
import {IScalingMethod} from './scaling-method';
import {AutoscalerScalingDirection} from './scaling-direction';
import {RulesEngineAnalysis} from '../scaler-rules-engine';

/** Scales directly to maxSize regardless of the rules. */
export class DirectScalingMethod implements IScalingMethod {
  name: string = 'DIRECT';

  constructor() {}

  /** @inheritdoc */
  calculateSuggestedSize(
    instance: ScalableInstanceWithData,
    // Required by signature, not in use here.
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    scalingDirection: AutoscalerScalingDirection,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    engineAnalysis: RulesEngineAnalysis | null,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    instanceLogger: pino.Logger
  ): number {
    if (!instance.scalingConfig.maxSize) {
      throw new Error(
        'maxSize must be configured when using DIRECT scaling method'
      );
    }
    return instance.scalingConfig.maxSize;
  }
}
