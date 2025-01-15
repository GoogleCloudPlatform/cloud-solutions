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

/** @fileoverview Chooses and runs scaling methods. */

import pino from 'pino';
import {
  getUnitsText,
  ScalableInstanceWithData,
} from '../../common/instance-info';
import {IScalingMethod} from './scaling-method';
import {Rules} from '../scaler-rules-manager';
import {getInstanceLogger} from '../../common/logger';
import {
  AutoscalerScalingDirection,
  getScalingDirection,
  convertScalingDirectionToAutoscalerDirection,
} from './scaling-direction';
import {IScalingSizeValidator} from './scaling-size-validator';
import {IRulesEngine, RulesEngineAnalysis} from '../scaler-rules-engine';
import {DirectScalingMethod} from './direct-method';
import {StepwiseScalingMethod} from './stepwise-method';
import {LinearScalingMethod} from './linear-method';

/** Map of method names to it scaling method implementation. */
export type ScalingMethodMap = Map<string, IScalingMethod>;

/** Chooses and runs scaling methods. */
export interface IScalingMethodRunner {
  /** Gets suggested size using the chosen scaling method. */
  getSuggestedSize(
    instance: ScalableInstanceWithData,
    rules: Rules
  ): Promise<number>;
}

/** Default and recommended scaling methods. */
export const DEFAULT_SCALING_METHODS: ScalingMethodMap = new Map([
  ['DIRECT', new DirectScalingMethod()],
  ['STEPWISE', new StepwiseScalingMethod()],
  ['LINEAR', new LinearScalingMethod()],
]);

/** @inheritdoc */
export class ScalingMethodRunner implements IScalingMethodRunner {
  constructor(
    protected baseLogger: pino.Logger,
    protected rulesEngine: IRulesEngine,
    protected scalingSizeValidator: IScalingSizeValidator,
    protected defaultScalingMethod: IScalingMethod,
    protected scalingMethods: ScalingMethodMap = DEFAULT_SCALING_METHODS
  ) {}

  /** @inheritdoc */
  async getSuggestedSize(
    instance: ScalableInstanceWithData,
    rules: Rules
  ): Promise<number> {
    const instanceLogger = getInstanceLogger(this.baseLogger, instance);

    instanceLogger.debug({
      message:
        `---- ${instance.info.resourcePath}: ` +
        `${instance.scalingConfig.scalingMethod} size suggestions----`,
    });
    instanceLogger.debug({
      message:
        `\tMin=${instance.scalingConfig.minSize}, ` +
        `Current=${instance.metadata.currentSize}, ` +
        `Max=${instance.scalingConfig.maxSize}${getUnitsText(instance)}`,
    });

    const engineAnalysis = await this.rulesEngine.getEngineAnalysis(
      instance,
      rules
    );

    const scalingDirection = this.calculateScalingDirection(engineAnalysis);
    instanceLogger.debug({
      message: `\tScaling direction: ${scalingDirection}`,
    });

    return this.calculateSuggestedSize(
      instance,
      scalingDirection,
      engineAnalysis,
      instanceLogger
    );
  }

  /**
   * Calculates the suggestedSize by delegating to the scaling method.
   *
   * Validates and restrics its value with the validator.
   */
  protected calculateSuggestedSize(
    instance: ScalableInstanceWithData,
    scalingDirection: AutoscalerScalingDirection,
    engineAnalysis: RulesEngineAnalysis | null,
    instanceLogger: pino.Logger
  ): number {
    const scalingMethod = this.chooseScalingMethod(instance);
    const suggestedSize = scalingMethod.calculateSuggestedSize(
      instance,
      scalingDirection,
      engineAnalysis,
      instanceLogger
    );
    const initialSuggestionMessage = this.getScalingSuggestionMessage(
      instance,
      suggestedSize,
      scalingDirection
    );
    instanceLogger.debug({
      message: `\tInitial scaling suggestion: ${initialSuggestionMessage}`,
    });

    const finalSuggestedSize = this.scalingSizeValidator.validateSuggestedSize(
      instance,
      suggestedSize,
      scalingDirection
    );
    const finalSuggestionMessage = this.getScalingSuggestionMessage(
      instance,
      finalSuggestedSize,
      scalingDirection
    );
    instanceLogger.debug({
      message: `\tFinal scaling suggestion: ${finalSuggestionMessage}`,
    });

    return finalSuggestedSize;
  }

  /** Calculates in which direction to scale based on the rules analysis. */
  protected calculateScalingDirection(
    engineAnalysis: RulesEngineAnalysis | null
  ): AutoscalerScalingDirection {
    // TODO: take a decision to prioritize UP vs OUT, IN vs DOWN.

    // If there is no analysis, prioritize scaling out.
    if (!engineAnalysis) return AutoscalerScalingDirection.SCALE_OUT;

    const firingRuleCount = engineAnalysis.firingRuleCount;

    if (firingRuleCount[AutoscalerScalingDirection.SCALE_OUT] > 0) {
      return AutoscalerScalingDirection.SCALE_OUT;
    }

    if (firingRuleCount[AutoscalerScalingDirection.SCALE_UP] > 0) {
      return AutoscalerScalingDirection.SCALE_UP;
    }

    if (firingRuleCount[AutoscalerScalingDirection.SCALE_IN] > 0) {
      return AutoscalerScalingDirection.SCALE_IN;
    }

    if (firingRuleCount[AutoscalerScalingDirection.SCALE_DOWN] > 0) {
      return AutoscalerScalingDirection.SCALE_DOWN;
    }

    return AutoscalerScalingDirection.NONE;
  }

  /** Gets a message to log based on the initial suggested size. */
  protected getScalingSuggestionMessage(
    instance: ScalableInstanceWithData,
    suggestedSize: number,
    scalingDirection: AutoscalerScalingDirection
  ) {
    if (scalingDirection === AutoscalerScalingDirection.NONE) {
      return 'no change suggested';
    }

    if (suggestedSize === instance.metadata.currentSize) {
      return (
        'the suggested size is equal to the current size: ' +
        `${instance.metadata.currentSize}${getUnitsText(instance)}`
      );
    }

    const actualDirection = convertScalingDirectionToAutoscalerDirection(
      getScalingDirection(instance, suggestedSize),
      scalingDirection
    );

    if (actualDirection !== scalingDirection) {
      return (
        `matching rule was ${scalingDirection}, ` +
        `but suggesting to ${actualDirection} ` +
        `from ${instance.metadata.currentSize} ` +
        `to ${suggestedSize}${getUnitsText(instance)}`
      );
    }

    return (
      `suggesting to ${scalingDirection} ` +
      `from ${instance.metadata.currentSize} ` +
      `to ${suggestedSize}${getUnitsText(instance)}`
    );
  }

  /** Chooses which ScalingMethod to use. */
  protected chooseScalingMethod(
    instance: ScalableInstanceWithData
  ): IScalingMethod {
    const instanceLogger = getInstanceLogger(this.baseLogger, instance);

    if (!instance?.scalingConfig?.scalingMethod) {
      instanceLogger.info({
        message:
          'No scaling method configured. ' +
          `Using default scaling method: ${this.defaultScalingMethod.name}`,
      });
      return this.defaultScalingMethod;
    }

    const scalingMethod = instance.scalingConfig.scalingMethod;

    if (!this.scalingMethods) {
      instanceLogger.info({
        message:
          'No scaling methods exist for this autoscaler. ' +
          `Using default scaling method: ${this.defaultScalingMethod.name}`,
      });
      return this.defaultScalingMethod;
    }

    if (!this.scalingMethods.has(scalingMethod)) {
      instanceLogger.warn({
        message:
          `Unknown scaling method ${scalingMethod}. ` +
          `Using default scaling method: ${this.defaultScalingMethod.name}`,
      });
      return this.defaultScalingMethod;
    }

    const selectedScalingMethod = this.scalingMethods.get(scalingMethod);
    if (!selectedScalingMethod) {
      // This should not happen, but protecting for typing and safety.
      instanceLogger.info({
        message:
          `Unknown scaling method ${selectedScalingMethod}. ` +
          `Using default scaling method: ${this.defaultScalingMethod.name}`,
      });
      return this.defaultScalingMethod;
    }

    instanceLogger.info({
      message: `Using selected scaling method ${scalingMethod}:`,
    });
    return selectedScalingMethod;
  }
}
