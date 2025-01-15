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

/** @fileoverview Provides scaling methods base definitions. */

import pino from 'pino';
import {ScalableInstanceWithData} from '../../common/instance-info';
import {AutoscalerScalingDirection} from './scaling-direction';
import {RulesEngineAnalysis} from '../scaler-rules-engine';

/** Calculates suggested size based on scaling method rules. */
export interface IScalingMethod {
  /** Name of the scaling method. */
  name: string;

  /** Calculates suggested scaling size. */
  calculateSuggestedSize(
    instance: ScalableInstanceWithData,
    scalingDirection: AutoscalerScalingDirection,
    engineAnalysis: RulesEngineAnalysis | null,
    instanceLogger: pino.Logger
  ): number;
}
