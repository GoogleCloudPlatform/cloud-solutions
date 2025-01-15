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

/** @fileoverview Provides rules for Scaling decisions. */

import pino from 'pino';
import {ScalableInstanceWithData} from '../common/instance-info';
import {RuleSet} from './scaler-rules';
import {getInstanceLogger} from '../common/logger';
import {AutoscalerScalingDirection} from './scaling-methods/scaling-direction';

/** A map of a rule name to its defined RuleSet. */
export type Rules = Record<string, RuleSet>;

/** Map of profiles to RuleSets. */
export type RulesProfileMap = Map<string, Rules>;

/** Name of the ScalingProfile to use for custom rules. */
export const CUSTOM_RULE_NAME = 'CUSTOM';

/** Gets and determines which rules to use for Scaling purposes. */
export interface IRulesManager {
  /** Gets the rules to use for scaling. */
  getRules(instance: ScalableInstanceWithData): Rules;
}

/** @inheritdoc. */
export class RulesManager implements IRulesManager {
  constructor(
    protected baseLogger: pino.Logger,
    protected defaultRules: Rules,
    protected profileRules?: RulesProfileMap
  ) {}

  /**
   * @inheritdoc
   *
   * If scalingProfile is CUSTOM and scalingRules are provided, uses provided
   * custom scalingRules.
   *
   * If scalingProfile is any other value, and exists in profileRules, uses that
   * set of rules
   *
   * Otherwise, uses defaultRules.
   *
   * Logs all the rules used.
   */
  getRules(instance: ScalableInstanceWithData): Rules {
    const instanceLogger = getInstanceLogger(this.baseLogger, instance);
    const rules = this.getRulesForProfile(instance, instanceLogger);
    for (const rule of Object.keys(rules)) {
      instanceLogger.info({message: `	Rule: ${rule}`});
    }
    return rules;
  }

  /** See getRules. Internal implementation for getRules. */
  private getRulesForProfile(
    instance: ScalableInstanceWithData,
    instanceLogger: pino.Logger
  ): Rules {
    if (!instance?.scalingConfig?.scalingProfile) {
      instanceLogger.info({
        message: 'No scaling profile configured. Using default rules:',
      });
      return this.defaultRules;
    }

    const scalingProfile = instance.scalingConfig.scalingProfile;

    if (scalingProfile === CUSTOM_RULE_NAME) {
      if (
        !instance?.scalingConfig?.scalingRules ||
        instance.scalingConfig.scalingRules.length === 0
      ) {
        instanceLogger.info({
          message:
            'CUSTOM rule profile was selected, but no scalingRules were ' +
            'passed. Using default rules:',
        });
        return this.defaultRules;
      }

      instanceLogger.info({
        message: 'Using custom rules:',
      });
      const customRulesList = instance.scalingConfig.scalingRules;
      const customRules: Rules = {};
      customRulesList.forEach(ruleSet => {
        const ruleName = ruleSet?.name as string;
        customRules[ruleName] = ruleSet;
      });
      return customRules;
    }

    if (!this.profileRules) {
      instanceLogger.info({
        message: 'No profiles exist for this autoscaler. Using default rules:',
      });
      return this.defaultRules;
    }

    if (!this.profileRules.has(scalingProfile)) {
      instanceLogger.info({
        message: `Unknown scaling profile ${scalingProfile}. Using default rules:`,
      });
      return this.defaultRules;
    }

    const currentProfileRules = this.profileRules.get(scalingProfile);
    if (!currentProfileRules) {
      // This should not happen, but protecting for typing and safety.
      instanceLogger.info({
        message: `Unknown scaling profile ${scalingProfile}. Using default rules: `,
      });
      return this.defaultRules;
    }

    instanceLogger.info({
      message: `Using predefined scaling rules for profile ${scalingProfile}:`,
    });
    return currentProfileRules;
  }
}

/**
 * Metric operators for rules.
 *
 * This is not a complete enum of all possible operators, but the common ones
 * used for the Autoscalers.
 *
 * To see all potential rules see:
 * https://www.npmjs.com/package/json-rules-engine
 */
export enum MetricOperator {
  GREATER_THAN = 'greaterThan',
  EQUAL = 'equal',
  LESS_THAN = 'lessThan',
}

/**
 * Creates a simple scaling rule with one condition.
 *
 * This is not a complete implementation of all possible rules, but the common
 * pattern used for the Autoscalers.
 *
 * To see all potential rules see:
 * https://www.npmjs.com/package/json-rules-engine
 *
 * @param ruleType Type of scaling: IN, OUT, UP, DOWN.
 */
export const createSimpleRule = (
  ruleName: string,
  ruleDirection: AutoscalerScalingDirection,
  metricName: string,
  metricOperator: MetricOperator,
  metricValue: number,
  message: string
): RuleSet => {
  return {
    name: ruleName,
    conditions: {
      all: [
        {
          fact: metricName,
          operator: metricOperator,
          value: metricValue,
        },
      ],
    },
    event: {
      type: ruleDirection,
      params: {
        message: message,
        scalingMetrics: [metricName],
      },
    },
    priority: 1,
  };
};
