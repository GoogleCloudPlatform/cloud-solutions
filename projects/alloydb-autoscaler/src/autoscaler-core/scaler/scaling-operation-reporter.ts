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

/** @fileoverview Reports the status of scaling operations. */

import pino from 'pino';
import {StateData} from './state-stores/state';
import {OperationState} from './scaling-operation';
import {ScalableInstanceWithData} from '../common/instance-info';
import {CounterManager} from '../common/counters';
import {SCALER_COUNTER_DEFINITION_MAP} from './scaler-counters';
import {COUNTER_ATTRIBUTE_NAMES} from '../common/counter-attribute-mapper';
import {getScalingDirection} from './scaling-methods/scaling-direction';
import {getPayloadLogger} from '../common/logger';

/** Reports state of the Scale operations. */
export interface IScalingOperationReporter {
  /** Reports that the scaling operation was cancelled. */
  reportCancelledOperation(
    operationState: OperationState,
    autoscalerState: StateData,
    instance: ScalableInstanceWithData
  ): void;

  /** Reports that the scaling operation failed. */
  reportFailedOperation(
    operationState: OperationState,
    autoscalerState: StateData,
    instance: ScalableInstanceWithData
  ): void;

  /** Reports that the scaling operation is in progress. */
  reportInProgressOperation(
    operationState: OperationState,
    autoscalerState: StateData,
    instance: ScalableInstanceWithData
  ): void;

  /** Reports that the scaling operation was completed successfully. */
  reportSuccessfulOperation(
    operationState: OperationState,
    autoscalerState: StateData,
    instance: ScalableInstanceWithData
  ): void;

  /** Reports the last operation as successful since its status is unknown. */
  reportUnknownOperationAsSuccessful(
    autoscalerState: StateData,
    instance: ScalableInstanceWithData
  ): void;
}

/** Reports the state of Scaling Operations. */
export class ScalingOperationReporter {
  constructor(
    protected baseLogger: pino.Logger,
    protected counterManager: CounterManager
  ) {}

  /** @inheritdoc */
  reportCancelledOperation(
    operationState: OperationState,
    autoscalerState: StateData,
    instance: ScalableInstanceWithData
  ): void {
    this.logMessage(
      `----- ${instance.info.resourcePath}: ` +
        'Last scaling request for size ' +
        `${autoscalerState.scalingRequestedSize} CANCEL REQUESTED. ` +
        `Started: ${operationState?.metadata?.createTime}`,
      instance
    );
  }

  /** @inheritdoc */
  reportFailedOperation(
    operationState: OperationState,
    autoscalerState: StateData,
    instance: ScalableInstanceWithData
  ): void {
    const payloadLogger = getPayloadLogger(this.baseLogger, instance, instance);
    payloadLogger.error({
      message:
        `----- ${instance.info.resourcePath}: Last scaling request for size ` +
        `${autoscalerState.scalingRequestedSize} FAILED: ` +
        `${operationState.error?.message}. Started: ` +
        `${operationState?.metadata?.createTime}, completed: ` +
        operationState?.metadata?.endTime,
      error: operationState.error,
    });

    this.counterManager.incrementCounter(
      SCALER_COUNTER_DEFINITION_MAP.SCALING_FAILED.counterName,
      instance,
      {
        [COUNTER_ATTRIBUTE_NAMES.SCALING_FAILED_REASON]: operationState.error,
        [COUNTER_ATTRIBUTE_NAMES.SCALING_METHOD]: autoscalerState.scalingMethod,
        [COUNTER_ATTRIBUTE_NAMES.SCALING_DIRECTION]: getScalingDirection(
          instance,
          autoscalerState.scalingRequestedSize ?? 0,
          autoscalerState.scalingPreviousSize ?? 0
        ),
      }
    );
  }

  /** @inheritdoc */
  reportInProgressOperation(
    operationState: OperationState,
    autoscalerState: StateData,
    instance: ScalableInstanceWithData
  ): void {
    this.logMessage(
      `----- ${instance.info.resourcePath}: Last scaling request for ` +
        `size ${autoscalerState.scalingRequestedSize} IN PROGRESS. Started: ` +
        `${operationState?.metadata?.createTime}`,
      instance
    );
  }

  /** @inheritdoc */
  reportSuccessfulOperation(
    operationState: OperationState,
    autoscalerState: StateData,
    instance: ScalableInstanceWithData
  ): void {
    this.logMessage(
      `----- ${instance.info.resourcePath}: Last scaling request for size ` +
        `${autoscalerState.scalingRequestedSize} SUCCEEDED. Started: ` +
        `${operationState?.metadata?.createTime}, completed: ` +
        operationState?.metadata?.endTime,
      instance
    );

    this.recordScalingDuration(autoscalerState, instance);
    this.increaseSuccessfulCounter(autoscalerState, instance);
  }

  /** @inheritdoc */
  reportUnknownOperationAsSuccessful(
    autoscalerState: StateData,
    instance: ScalableInstanceWithData
  ): void {
    this.recordScalingDuration(autoscalerState, instance);
    this.increaseSuccessfulCounter(autoscalerState, instance);
  }

  /** Logs a message with the required metadata. */
  private logMessage(message: string, instance: ScalableInstanceWithData) {
    const payloadLogger = getPayloadLogger(this.baseLogger, instance, instance);
    payloadLogger.info({message: message});
  }

  /** Increases the successful scaling operation counter. */
  private increaseSuccessfulCounter(
    autoscalerState: StateData,
    instance: ScalableInstanceWithData
  ) {
    this.counterManager.incrementCounter(
      SCALER_COUNTER_DEFINITION_MAP.SCALING_SUCCESS.counterName,
      instance,
      {
        [COUNTER_ATTRIBUTE_NAMES.SCALING_METHOD]: autoscalerState.scalingMethod,
        [COUNTER_ATTRIBUTE_NAMES.SCALING_DIRECTION]: getScalingDirection(
          instance,
          autoscalerState.scalingRequestedSize ?? 0,
          autoscalerState.scalingPreviousSize ?? 0
        ),
      }
    );
  }

  /** Records an entry on the ScalingDuration counter. */
  private recordScalingDuration(
    autoscalerState: StateData,
    instance: ScalableInstanceWithData
  ) {
    const operationDuration =
      (autoscalerState.lastScalingCompleteTimestamp ?? 0) -
      autoscalerState.lastScalingTimestamp;

    this.counterManager.recordValue(
      SCALER_COUNTER_DEFINITION_MAP.SCALING_DURATION.counterName,
      Math.floor(operationDuration),
      instance,
      {
        [COUNTER_ATTRIBUTE_NAMES.SCALING_METHOD]: autoscalerState.scalingMethod,
        [COUNTER_ATTRIBUTE_NAMES.SCALING_DIRECTION]: getScalingDirection(
          instance,
          autoscalerState.scalingRequestedSize ?? 0,
          autoscalerState.scalingPreviousSize ?? 0
        ),
      }
    );
  }
}
