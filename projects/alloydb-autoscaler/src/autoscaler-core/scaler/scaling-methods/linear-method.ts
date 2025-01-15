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

/** @fileoverview Implements LINEAR scaling method. */

import pino from 'pino';
import {ScalableInstanceWithData} from '../../common/instance-info';
import {IScalingMethod} from './scaling-method';
import {AutoscalerScalingDirection} from './scaling-direction';
import {RulesEngineAnalysis} from '../scaler-rules-engine';

/** Internal representation of a matched metric for scaling. */
type ScalingMetric = {
  name: string;
  value: number;
  threshold: number;
};

/** Scales in linear proportionality to the resources used. */
export class LinearScalingMethod implements IScalingMethod {
  name: string = 'LINEAR';

  /** @inheritdoc */
  calculateSuggestedSize(
    instance: ScalableInstanceWithData,
    scalingDirection: AutoscalerScalingDirection,
    engineAnalysis: RulesEngineAnalysis | null,
    instanceLogger: pino.Logger
  ): number {
    const currentSize = instance.metadata.currentSize;

    if (!engineAnalysis) return currentSize;

    if (scalingDirection === AutoscalerScalingDirection.NONE) {
      return currentSize;
    }

    if (
      scalingDirection === AutoscalerScalingDirection.SCALE_UP ||
      scalingDirection === AutoscalerScalingDirection.SCALE_DOWN
    ) {
      throw new Error(
        `LINEAR scaler does not support ${scalingDirection}. ` +
          'Please choose another scalingMethod'
      );
    }

    const scalingMetrics = this.getMetricsForScaling(
      scalingDirection,
      engineAnalysis,
      instanceLogger
    );

    const suggestedSize = this.calculateSuggestedSizedForScalingMetrics(
      instance,
      scalingDirection,
      scalingMetrics
    );
    return suggestedSize;
  }

  /** Gets the metrics for scaling based on direction. */
  private getMetricsForScaling(
    scalingDirection: AutoscalerScalingDirection,
    engineAnalysis: RulesEngineAnalysis | null,
    instanceLogger: pino.Logger
  ): ScalingMetric[] {
    if (!engineAnalysis) return [];

    const matchedConditions =
      engineAnalysis.matchedConditions[scalingDirection];
    if (!matchedConditions) return [];

    const scalingMetrics = engineAnalysis.scalingMetrics[scalingDirection];
    if (!scalingMetrics) return [];

    return matchedConditions
      .filter(matchedCondition => {
        const metricName = matchedCondition.fact;
        return scalingMetrics.has(metricName);
      })
      .map(matchedCondition => {
        return {
          name: matchedCondition.fact,
          value: matchedCondition.factResult,
          threshold: matchedCondition.value,
        } as ScalingMetric;
      })
      .filter(scalingMetric => {
        // This should not happen since the rules engine won't be able to
        // trigger this rule if the metric (fact) is not defined. Adding for
        // safety nonetheless.
        if (scalingMetric.value === null || scalingMetric.value === undefined) {
          instanceLogger.error({
            message:
              'Unable to use this metric for linear scaling. ' +
              `No value for metric ${scalingMetric.name} on the cluster. ` +
              'Consider removing this metric from scalingMetrics or adding a ' +
              'value to the condition for the fact with this name.',
          });
          return false;
        }

        // This should not happen since the rules engine won't be able to
        // trigger this rule if there is not threshold (condition.value).
        if (typeof scalingMetric.threshold !== 'number') {
          instanceLogger.error({
            message:
              'Unable to use this metric for linear scaling. ' +
              `No numeric threshold value for ${scalingMetric.name}. ` +
              'Consider removing this metric from scalingMetrics or adding a ' +
              'numeric value to the condition for the fact with this name. ' +
              'If a value is already added, ensure it is a number (numeric ' +
              'type).',
          });
          return false;
        }

        if (scalingMetric.threshold === 0) {
          instanceLogger.error({
            message:
              'Unable to use this metric for linear scaling. ' +
              `The threshold value for ${scalingMetric.name} is 0. Linear ` +
              'scaling uses threshold value as part of the cross ' +
              'multiplication to calculate the size and it is not possible ' +
              'to divide by 0. Consider removing this metric from ' +
              'scalingMetrics or adding a value other than 0 to the ' +
              'condition for the fact with this name.',
          });
          return false;
        }

        return true;
      });
  }

  /** Calculates suggested size using linear calculation for matched metrics. */
  private calculateSuggestedSizedForScalingMetrics(
    instance: ScalableInstanceWithData,
    scalingDirection: AutoscalerScalingDirection,
    scalingMetrics: ScalingMetric[]
  ): number {
    let suggestedSize = null;

    for (const scalingMetric of scalingMetrics) {
      // This should not happen as this check is done on getMetricsForScaling
      // and an error message is logged. However, this helps type inference.
      if (!scalingMetric.threshold) continue;
      const metricSuggestedSize = this.calculateSizeForScalingMetric(
        instance,
        scalingMetric
      );
      suggestedSize = Math.max(suggestedSize || 0, metricSuggestedSize);
    }

    return this.applyLimitsToSuggestedSize(
      instance,
      scalingDirection,
      suggestedSize
    );
  }

  /** Linear scaling calculation for one metric. */
  private calculateSizeForScalingMetric(
    instance: ScalableInstanceWithData,
    scalingMetric: ScalingMetric
  ): number {
    const currentSize = instance.metadata.currentSize;
    return Math.ceil(
      currentSize * (scalingMetric.value / scalingMetric.threshold)
    );
  }

  /** Limits scaling by configured scaling limits. */
  private applyLimitsToSuggestedSize(
    instance: ScalableInstanceWithData,
    scalingDirection: AutoscalerScalingDirection,
    suggestedSize: number | null
  ): number {
    const currentSize = instance.metadata.currentSize;
    if (suggestedSize === null) suggestedSize = currentSize;

    if (scalingDirection === AutoscalerScalingDirection.SCALE_IN) {
      const scaleInLimit = instance.scalingConfig.scaleInLimit;
      if (scaleInLimit) {
        suggestedSize = Math.max(suggestedSize, currentSize - scaleInLimit);
      }

      if (suggestedSize < currentSize) return suggestedSize;
      return currentSize;
    }

    if (scalingDirection === AutoscalerScalingDirection.SCALE_OUT) {
      const scaleOutLimit = instance.scalingConfig.scaleOutLimit;
      if (scaleOutLimit) {
        suggestedSize = Math.min(suggestedSize, currentSize + scaleOutLimit);
      }

      if (suggestedSize > currentSize) return suggestedSize;
      return currentSize;
    }

    return currentSize;
  }
}
