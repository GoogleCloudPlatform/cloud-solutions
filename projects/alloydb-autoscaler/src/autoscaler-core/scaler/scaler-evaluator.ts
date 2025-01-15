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

/** @fileoverview Evaluates whether scaling is needed and to how much. */

import pino from 'pino';
import {CounterManager} from '../common/counters';
import {ScalableInstanceWithData} from '../common/instance-info';
import {IStateStore, StateData} from './state-stores/state';
import {ScalingRequestReporter} from './scaling-request-reporter';
import {IStateFetcher} from './state-fetcher';
import {IRulesManager} from './scaler-rules-manager';
import {
  ScalingDirection,
  getScalingDirection,
} from './scaling-methods/scaling-direction';
import {MS_IN_1_MIN} from '../common/date-utils';
import {convertMillisecondsToHumanReadable} from '../common/date-utils';
import {IScalingMethodRunner} from './scaling-methods/scaling-method-runner';

/**
 * The validated scaling details:
 * [
 *   boolean: whether scaling request is possible,
 *   number: suggested size to which to scale.
 * ]
 */
export type ScalingDetails = [boolean, number];

/**
 * Evaluator of Scaling operations.
 *
 * Decides if scaling is needed and how much.
 */
export class ScalerEvaluator {
  /**
   * Initializes ScalerEvaluator.
   * @param operationTypeRegExp RegExp of the expected scaling operation type.
   */
  constructor(
    protected payloadLogger: pino.Logger,
    protected stateStore: IStateStore,
    protected counterManager: CounterManager,
    protected stateFetcher: IStateFetcher,
    protected rulesManager: IRulesManager,
    protected scalingMethodRunner: IScalingMethodRunner
  ) {}

  /** Processes the request to check an instance request for scaling. */
  async processScalingRequest(
    instance: ScalableInstanceWithData
  ): Promise<ScalingDetails> {
    const savedState = await this.getScalingState(instance);
    const suggestedSize = await this.getSuggestedSize(instance);
    const isScalingPossible = await this.isScalingPossible(
      instance,
      savedState,
      suggestedSize
    );
    return [isScalingPossible, suggestedSize];
  }

  /** Gets the current scaling state for this instance. */
  private async getScalingState(
    instance: ScalableInstanceWithData
  ): Promise<StateData> {
    const savedState = await this.stateStore.getState();
    if (!savedState.scalingOperationId) {
      // No scaling operation (LRO) ongoing.
      return savedState;
    }

    const [newState, isStateUpdated] =
      await this.stateFetcher.fetchOperationState(instance, savedState);

    if (isStateUpdated) {
      await this.stateStore.updateState(newState);
    }

    return newState;
  }

  /** Calculates the suggested instance size. */
  private async getSuggestedSize(
    instance: ScalableInstanceWithData
  ): Promise<number> {
    const scalingRules = this.rulesManager.getRules(instance);
    return await this.scalingMethodRunner.getSuggestedSize(
      instance,
      scalingRules
    );
  }

  /** Returns whether it is possible/needed to execute a scaling operation. */
  private async isScalingPossible(
    instance: ScalableInstanceWithData,
    savedState: StateData,
    suggestedSize: number
  ): Promise<boolean> {
    const scalingStatusReporter = new ScalingRequestReporter(
      this.payloadLogger,
      this.counterManager,
      instance,
      savedState,
      suggestedSize
    );

    if (savedState.scalingOperationId) {
      await scalingStatusReporter.reportScalingOperationInProgress();
      return false;
    }

    if (
      instance.metadata.currentSize >= instance.scalingConfig?.maxSize &&
      // If suggestedSize is not greater, scale down/in is possible.
      suggestedSize >= instance.metadata.currentSize
    ) {
      await scalingStatusReporter.reportInstanceAtMaxSize();
      return false;
    }

    if (suggestedSize === instance.metadata.currentSize) {
      await scalingStatusReporter.reportInstanceAtSuggestedSize();
      return false;
    }

    if (
      await this.isScalingWithinCooldownPeriod(
        instance,
        suggestedSize,
        savedState
      )
    ) {
      await scalingStatusReporter.reportWithinCooldownPeriod();
      return false;
    }

    return true;
  }

  /** Checks whether Autoscaler is in post-scale cooldown. */
  private async isScalingWithinCooldownPeriod(
    instance: ScalableInstanceWithData,
    suggestedSize: number,
    autoscalerState: StateData
  ): Promise<boolean> {
    this.payloadLogger.debug({
      message:
        `-----  ${instance.info.resourcePath}: Verifying if scaling is ` +
        'allowed -----',
    });

    const lastScalingMilliseconds = autoscalerState.lastScalingCompleteTimestamp
      ? autoscalerState.lastScalingCompleteTimestamp
      : autoscalerState.lastScalingTimestamp;

    const suggestedDirection = getScalingDirection(instance, suggestedSize);
    let coolingMilliseconds;
    switch (suggestedDirection) {
      case ScalingDirection.SCALE_UP:
        coolingMilliseconds =
          instance.scalingConfig.scaleOutCoolingMinutes * MS_IN_1_MIN;
        break;
      case ScalingDirection.SCALE_DOWN:
        coolingMilliseconds =
          instance.scalingConfig.scaleInCoolingMinutes * MS_IN_1_MIN;
        break;
      default:
      case ScalingDirection.SCALE_SAME:
        // This should not happen. SCALE_SAME is and should be checked before
        // checking isScalingWithinCooldownPeriod.
        throw new Error(
          'Checking cooldown operation, but no operation should have been ' +
            'running'
        );
    }

    let cooldownPeriodOver;
    if (!lastScalingMilliseconds) {
      cooldownPeriodOver = true;
      this.payloadLogger.debug({
        message: '\tNo previous scaling operation found for this cluster',
      });
    } else {
      const elapsedMilliseconds = Date.now() - lastScalingMilliseconds;
      cooldownPeriodOver = elapsedMilliseconds >= coolingMilliseconds;
      this.payloadLogger.debug({
        message:
          '\tLast scaling operation was ' +
          `${convertMillisecondsToHumanReadable(elapsedMilliseconds)} ago.`,
      });
    }

    if (cooldownPeriodOver) {
      this.payloadLogger.info({message: '\t=> Autoscale allowed'});
      return false;
    } else {
      this.payloadLogger.info({message: '\t=> Autoscale NOT allowed yet'});
      return true;
    }
  }
}
