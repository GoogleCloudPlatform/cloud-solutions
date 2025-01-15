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

/** @fileoverview Reports the status of scaling requests. */

import pino from 'pino';
import {CounterManager} from '../common/counters';
import {getUnitsText, ScalableInstanceWithData} from '../common/instance-info';
import {convertMillisecondsToHumanReadable} from '../common/date-utils';
import {SCALER_COUNTER_DEFINITION_MAP} from './scaler-counters';
import {COUNTER_ATTRIBUTE_NAMES} from '../common/counter-attribute-mapper';
import {getScalingDirection} from './scaling-methods/scaling-direction';
import {StateData} from './state-stores/state';

enum ScalingReportReason {
  CURRENT_SIZE = 'CURRENT_SIZE',
  IN_PROGRESS = 'IN_PROGRESS',
  MAX_SIZE = 'MAX_SIZE',
  WITHIN_COOLDOWN = 'WITHIN_COOLDOWN',
}

/** Reports (logs) the status of scaling requests. */
export class ScalingRequestReporter {
  constructor(
    protected payloadLogger: pino.Logger,
    protected counterManager: CounterManager,
    protected instance: ScalableInstanceWithData,
    protected savedState: StateData,
    protected suggestedSize: number
  ) {}

  /** Reports denied scaling operation due to an ongoing scaling operation. */
  async reportScalingOperationInProgress() {
    const timeSinceLastScaling = convertMillisecondsToHumanReadable(
      Date.now() - this.savedState.lastScalingTimestamp
    );
    this.logScalingNotPossible(
      `last scaling operation (${this.savedState.scalingMethod} to ` +
        `${this.savedState.scalingRequestedSize}) is still in progress. ` +
        `Started: ${timeSinceLastScaling} ago).`
    );
    await this.increaseDeniedCounter(ScalingReportReason.IN_PROGRESS);
  }

  /**
   * Reports denied scaling operation due to the last scaling operation being
   * too recent.
   */
  async reportWithinCooldownPeriod() {
    this.logScalingNotPossible('within cooldown period');
    await this.increaseDeniedCounter(ScalingReportReason.WITHIN_COOLDOWN);
  }

  /** Reports denied scaling operation due to the instance being at max size. */
  async reportInstanceAtMaxSize() {
    this.logScalingNotPossible(
      `at maxSize (${this.instance.scalingConfig?.maxSize})`
    );
    await this.increaseDeniedCounter(ScalingReportReason.MAX_SIZE);
  }

  /**
   * Reports denied scaling operation due to the suggested size being the
   * current instance size.
   */
  async reportInstanceAtSuggestedSize() {
    this.logScalingNotNeeded();
    await this.increaseDeniedCounter(ScalingReportReason.CURRENT_SIZE);
  }

  /** Reports that a scale operation failed for a given reason. */
  async reportFailedScalingOperation(reason: string) {
    this.payloadLogger.error({
      message:
        `----- ${this.instance.info.resourcePath}: ` +
        `Unsuccessful scaling attempt: ${reason}`,
      err: reason,
    });

    await this.counterManager.incrementCounter(
      SCALER_COUNTER_DEFINITION_MAP.SCALING_FAILED.counterName,
      this.instance,
      {
        [COUNTER_ATTRIBUTE_NAMES.SCALING_FAILED_REASON]: reason,

        [COUNTER_ATTRIBUTE_NAMES.SCALING_METHOD]:
          this.instance.scalingConfig.scalingMethod,

        [COUNTER_ATTRIBUTE_NAMES.SCALING_DIRECTION]: getScalingDirection(
          this.instance,
          this.suggestedSize
        ),
      }
    );
  }

  /** Increases the counter for denied scaling operation. */
  private async increaseDeniedCounter(reason: ScalingReportReason) {
    await this.counterManager.incrementCounter(
      SCALER_COUNTER_DEFINITION_MAP.SCALING_DENIED.counterName,
      this.instance,
      {
        [COUNTER_ATTRIBUTE_NAMES.SCALING_DENIED_REASON]: reason,

        [COUNTER_ATTRIBUTE_NAMES.SCALING_METHOD]:
          this.instance.scalingConfig.scalingMethod,

        [COUNTER_ATTRIBUTE_NAMES.SCALING_DIRECTION]: getScalingDirection(
          this.instance,
          this.suggestedSize
        ),
      }
    );
  }

  /** Logs a message informing that scaling is not possible and the reason. */
  private logScalingNotPossible(reason: string) {
    this.logScalingStatusMessage(`no scaling possible - ${reason}`);
  }

  /** Logs a message informing that scaling is not needed. */
  private logScalingNotNeeded() {
    this.logScalingStatusMessage('no scaling needed at the moment');
  }

  /** Logs a message with the current scaling status and a given message. */
  private logScalingStatusMessage(message: string) {
    const unitsText = getUnitsText(this.instance);
    const sizeMessageFragment =
      (!unitsText ? 'size ' : '') +
      this.instance.metadata.currentSize +
      unitsText;

    this.payloadLogger.info({
      message:
        `----- ${this.instance.info.resourcePath}: has ` +
        `${sizeMessageFragment}, ${message}`,
    });
  }
}
