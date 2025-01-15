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

/** @fileoverview Provides scaling direction definitions. */

import {ScalableInstanceWithData} from '../../common/instance-info';

/**
 * Direction in which scaling is done.
 *
 * In this context,
 * SCALE_UP and SCALE_OUT are synonyms.
 * SCALE_DOWN and SCALE_IN are synonyms.
 */
export enum ScalingDirection {
  SCALE_UP = 'SCALE_UP',
  SCALE_DOWN = 'SCALE_DOWN',
  SCALE_SAME = 'SCALE_SAME',
}

/**
 * Direction in which the autoscaler will scale.
 *
 * In this context,
 * SCALE_UP and SCALE_OUT are different directions.
 * SCALE_DOWN and SCALE_IN are different directions.
 */
export enum AutoscalerScalingDirection {
  SCALE_UP = 'SCALE_UP',
  SCALE_OUT = 'SCALE_OUT',
  SCALE_DOWN = 'SCALE_DOWN',
  SCALE_IN = 'SCALE_IN',
  SCALE_SAME = 'SCALE_SAME',
  NONE = 'NONE',
}

const HORIZONTAL_SCALING = [
  AutoscalerScalingDirection.SCALE_IN,
  AutoscalerScalingDirection.SCALE_OUT,
];

const VERTICAL_SCALING = [
  AutoscalerScalingDirection.SCALE_DOWN,
  AutoscalerScalingDirection.SCALE_UP,
];

/**
 * Gets the scaling direction.
 *
 * Compares instance currentSize vs suggestedSize unless previousSize is
 * provided - in which case previousSize is used.
 */
export const getScalingDirection = (
  instance: ScalableInstanceWithData,
  suggestedSize: number,
  previousSize?: number
): ScalingDirection => {
  previousSize = previousSize ?? instance.metadata.currentSize;
  if (suggestedSize > previousSize) return ScalingDirection.SCALE_UP;
  if (suggestedSize < previousSize) return ScalingDirection.SCALE_DOWN;
  // if (suggestedSize == previousSize)
  return ScalingDirection.SCALE_SAME;
};

/**
 * Gets the AutoscalerDirection equivalent for a ScalingDirection.
 *
 * Since SCALE_UP might be SCALE_UP or SCALE_OUT, it requires an anchor point.
 */
export const convertScalingDirectionToAutoscalerDirection = (
  direction: ScalingDirection,
  originalAutoscalerDirection: AutoscalerScalingDirection
): AutoscalerScalingDirection | null => {
  if (direction === ScalingDirection.SCALE_SAME) {
    return AutoscalerScalingDirection.SCALE_SAME;
  }

  if (direction === ScalingDirection.SCALE_DOWN) {
    if (HORIZONTAL_SCALING.includes(originalAutoscalerDirection)) {
      return AutoscalerScalingDirection.SCALE_IN;
    } else if (VERTICAL_SCALING.includes(originalAutoscalerDirection)) {
      return AutoscalerScalingDirection.SCALE_DOWN;
    } else {
      // Generic, use SCALE_IN as default.
      return AutoscalerScalingDirection.SCALE_IN;
    }
  }

  if (direction === ScalingDirection.SCALE_UP) {
    if (HORIZONTAL_SCALING.includes(originalAutoscalerDirection)) {
      return AutoscalerScalingDirection.SCALE_OUT;
    } else if (VERTICAL_SCALING.includes(originalAutoscalerDirection)) {
      return AutoscalerScalingDirection.SCALE_UP;
    } else {
      // Generic, use SCALE_OUT as default.
      return AutoscalerScalingDirection.SCALE_OUT;
    }
  }

  return null;
};
