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

/** @fileoverview Validates and further refines suggested size. */

import pino from 'pino';
import {ScalableInstanceWithData} from '../../common/instance-info';
import {AutoscalerScalingDirection} from './scaling-direction';
import {getInstanceLogger} from '../../common/logger';

/** Validates the scaling suggested size and further refines it. */
export interface IScalingSizeValidator {
  /** Validates the scaling suggested size and further refines it. */
  validateSuggestedSize(
    instance: ScalableInstanceWithData,
    suggestedSize: number,
    scalingDirection: AutoscalerScalingDirection
  ): number;
}

/** @inheritdoc */
export class ScalingSizeValidator implements IScalingSizeValidator {
  /**
   * Initializes ScalingSizeValidator.
   *
   * @param absoluteMinSize The lowest number of nodes that it is possible to
   *   have for this product.
   * @param absoluteMaxSize The highest number of nodes that it is possible to
   *   have for this product.
   */
  constructor(
    protected baseLogger: pino.Logger,
    protected absoluteMinSize?: number,
    protected absoluteMaxSize?: number
  ) {}

  /** @inheritdoc */
  validateSuggestedSize(
    instance: ScalableInstanceWithData,
    suggestedSize: number,
    // This variables may be used by derived clasess.
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    scalingDirection: AutoscalerScalingDirection
  ): number {
    const instanceLogger = getInstanceLogger(this.baseLogger, instance);
    if (suggestedSize > instance.scalingConfig.maxSize) {
      instanceLogger.debug({
        message:
          `\tClamping the suggested size of ${suggestedSize} to configured ` +
          `maximum ${instance.scalingConfig.maxSize}`,
      });
      suggestedSize = instance.scalingConfig.maxSize;
    }

    if (suggestedSize < instance.scalingConfig.minSize) {
      instanceLogger.debug({
        message:
          `\tClamping the suggested size of ${suggestedSize} to configured ` +
          `minimum ${instance.scalingConfig.minSize}`,
      });
      suggestedSize = instance.scalingConfig.minSize;
    }

    if (this.absoluteMaxSize && suggestedSize > this.absoluteMaxSize) {
      instanceLogger.debug({
        message:
          `\tClamping the suggested size of ${suggestedSize} to the limit of ` +
          `${this.absoluteMaxSize}`,
      });
      suggestedSize = this.absoluteMaxSize;
    }

    if (this.absoluteMinSize && suggestedSize < this.absoluteMinSize) {
      instanceLogger.debug({
        message:
          `\tClamping the suggested size of ${suggestedSize} to the limit of ` +
          `${this.absoluteMaxSize}`,
      });
      suggestedSize = this.absoluteMinSize;
    }

    return suggestedSize;
  }
}
