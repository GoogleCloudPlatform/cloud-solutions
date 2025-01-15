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

/** @fileoverview Provides the engine to evaluate rules. */

import pino from 'pino';
import {ScalableInstanceWithData} from '../common/instance-info';
import {AutoscalerScalingDirection} from './scaling-methods/scaling-direction';
import {Rules} from './scaler-rules-manager';
import {
  Engine,
  ConditionPropertiesResult,
  RuleResult,
  NestedConditionResult,
} from 'json-rules-engine';
import {getInstanceLogger} from '../common/logger';

/**
 * Output of the RulesEngine determining what rules matched for each scaling
 * direction.
 */
export type RulesEngineAnalysis = {
  /** Count of how many rules for the given scaling direction. */
  firingRuleCount: Record<AutoscalerScalingDirection, number>;
  /** Record of which conditions matched for the given direction. */
  matchedConditions: Record<
    AutoscalerScalingDirection,
    ConditionPropertiesResult[]
  >;
  /** Record of which metric names triggered the conditions. */
  scalingMetrics: Record<AutoscalerScalingDirection, Set<string>>;
};

/** Evaluates rules and outputs the anayslis. */
export interface IRulesEngine {
  /** Evaluates rules and outputs the anayslis. */
  getEngineAnalysis(
    instance: ScalableInstanceWithData,
    rules: Rules
  ): Promise<RulesEngineAnalysis | null>;
}

/** @inheritdoc. */
export class RulesEngine implements IRulesEngine {
  constructor(
    protected baseLogger: pino.Logger,
    protected rulesEngine?: Engine
  ) {}

  /** @inheritdoc */
  async getEngineAnalysis(
    instance: ScalableInstanceWithData,
    rules?: Rules
  ): Promise<RulesEngineAnalysis | null> {
    // Must be initialized on each call. Otherwise, the Engine keeps adding the
    // same rules until it times out.
    const rulesEngine = this.rulesEngine ?? new Engine();

    if (!rules || Object.keys(rules).length === 0) return null;

    const instanceLogger = getInstanceLogger(this.baseLogger, instance);
    instanceLogger.debug({
      message:
        `---- ${instance.info.resourcePath}: ` +
        `${instance.scalingConfig.scalingMethod} rules engine ----`,
    });

    Object.values(rules).forEach(rule => {
      rulesEngine.addRule(rule);
    });

    const engineAnalysis = this.getEmptyEngineAnalysis();
    rulesEngine.on('success', (event, _, ruleResult) => {
      instanceLogger.debug({
        message: `\tRule firing: ${event.params?.message} => ${event.type}`,
        event: event,
      });

      if (!(event.type in AutoscalerScalingDirection)) {
        instanceLogger.debug({
          message: `\tIgnoring unexpectedly firing rule of type ${event.type}`,
          event: event,
        });
        return;
      }
      const scalingEventType =
        event.type as keyof typeof AutoscalerScalingDirection;

      const ruleConditions = this.getRuleConditionMetrics(ruleResult);
      const scalingMetrics: Set<string> =
        event.params?.scalingMetrics ?? new Set();

      engineAnalysis.firingRuleCount[scalingEventType]++;
      engineAnalysis.matchedConditions[scalingEventType].push(
        ...Object.values(ruleConditions)
      );
      for (const scalingMetric of scalingMetrics) {
        engineAnalysis.scalingMetrics[scalingEventType].add(scalingMetric);
      }
    });

    await rulesEngine.run(instance.metrics);
    return engineAnalysis;
  }

  /** Gets the initial engine analysis to be filled in. */
  private getEmptyEngineAnalysis(): RulesEngineAnalysis {
    return {
      firingRuleCount: {
        [AutoscalerScalingDirection.SCALE_UP]: 0,
        [AutoscalerScalingDirection.SCALE_DOWN]: 0,
        [AutoscalerScalingDirection.SCALE_OUT]: 0,
        [AutoscalerScalingDirection.SCALE_IN]: 0,
        [AutoscalerScalingDirection.SCALE_SAME]: 0,
        [AutoscalerScalingDirection.NONE]: 0,
      },
      matchedConditions: {
        [AutoscalerScalingDirection.SCALE_UP]: [],
        [AutoscalerScalingDirection.SCALE_DOWN]: [],
        [AutoscalerScalingDirection.SCALE_OUT]: [],
        [AutoscalerScalingDirection.SCALE_IN]: [],
        [AutoscalerScalingDirection.SCALE_SAME]: [],
        [AutoscalerScalingDirection.NONE]: [],
      },
      scalingMetrics: {
        [AutoscalerScalingDirection.SCALE_UP]: new Set(),
        [AutoscalerScalingDirection.SCALE_DOWN]: new Set(),
        [AutoscalerScalingDirection.SCALE_OUT]: new Set(),
        [AutoscalerScalingDirection.SCALE_IN]: new Set(),
        [AutoscalerScalingDirection.SCALE_SAME]: new Set(),
        [AutoscalerScalingDirection.NONE]: new Set(),
      },
    };
  }

  /** Gets a map of matched metric rules with its value and threshold. */
  private getRuleConditionMetrics(
    ruleResult: RuleResult
  ): ConditionPropertiesResult[] {
    let ruleConditions: NestedConditionResult[] = [];
    if (ruleResult?.conditions && 'all' in ruleResult.conditions) {
      ruleConditions = ruleResult.conditions.all as NestedConditionResult[];
    } else if (ruleResult?.conditions && 'any' in ruleResult.conditions) {
      ruleConditions = ruleResult?.conditions?.any as NestedConditionResult[];
    } else {
      ruleConditions = [] as NestedConditionResult[];
    }

    const ruleConditionsList: ConditionPropertiesResult[] = [];
    for (const ruleCondition of ruleConditions) {
      /*
       * Narrow down typing and skip NestedConditions.
       * TODO: add support for nested conditions.
       */
      if (!('result' in ruleCondition)) continue;
      if (!('fact' in ruleCondition)) continue;
      if (!('factResult' in ruleCondition)) continue;
      if (!('value' in ruleCondition)) continue;

      // Only consider rules if they triggered the scale (i.e. result=true).
      if (!ruleCondition.result) continue;

      ruleConditionsList.push(ruleCondition);
    }

    return ruleConditionsList;
  }
}
