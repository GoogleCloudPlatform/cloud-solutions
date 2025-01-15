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

/** @fileoverview Fetches State of scaling operations from the API. */

import pino from 'pino';
import {ScalableInstanceWithData} from '../common/instance-info';
import {StateData} from './state-stores/state';
import {IScalingOperationReporter} from './scaling-operation-reporter';
import {OperationState} from './scaling-operation';
import {getPayloadLogger} from '../common/logger';

/** The new state data and whether it was updated. */
export type StateDataFetchResult = [StateData, boolean];

/** Fetches the State of running scaling operations. */
export interface IStateFetcher {
  /** Fetches the State of running scaling operations. */
  fetchOperationState(
    instance: ScalableInstanceWithData,
    autoscalerState: StateData
  ): Promise<StateDataFetchResult>;
}

/** @inheritdoc */
export class StateFetcher implements IStateFetcher {
  /**
   * Initializes StateFetcher.
   * @param operationTypeRegExp RegExp of the expected operation type.
   */
  constructor(
    protected baseLogger: pino.Logger,
    protected operationTypeRegExp: RegExp,
    protected scalingOperationReporter: IScalingOperationReporter
  ) {}

  /** @inheritdoc */
  async fetchOperationState(
    instance: ScalableInstanceWithData,
    autoscalerState: StateData
  ): Promise<StateDataFetchResult> {
    try {
      const operationState =
        await this.fetchOperationStateFromApi(autoscalerState);
      this.validateOperationState(operationState, autoscalerState);
      return await this.getNewStateData(
        // Validated on validateOperationState.
        operationState as OperationState,
        instance,
        autoscalerState
      );
    } catch (e) {
      return this.processUnknownOperation(
        instance,
        autoscalerState,
        e as Error
      );
    }
  }

  /** Fetches Operation state from the API. */
  protected async fetchOperationStateFromApi(
    // Parameter will be needed by the methods which implement this.
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    autoscalerState: StateData
  ): Promise<OperationState | null | undefined> {
    throw new Error(
      'fetchOperationStateFromApi must be implemented in derived classes.'
    );
  }

  /**
   * Gets StateData with updated values.
   *
   * Report the status of the scaling operations in the process.
   *
   * This implementation does not require async runtime, but derived
   * class may require async processes or fetching. Hence, keeping to enable
   * future Autoscaler's flexibility.
   *
   * @return [
   *   newStateData: new StateData - it might be the same or updated,
   *   isStateUpdated: Whether the StateData was updated,
   * ]
   */
  protected async getNewStateData(
    operationState: OperationState,
    instance: ScalableInstanceWithData,
    autoscalerState: StateData
  ): Promise<StateDataFetchResult> {
    if (!this.isOperationDone(operationState)) {
      return this.processRunningOperation(
        operationState,
        instance,
        autoscalerState
      );
    }

    if (this.isOperationWithErrors(operationState)) {
      return this.processFailedOperation(
        operationState,
        instance,
        autoscalerState
      );
    }

    return this.processSuccessfulOperation(
      operationState,
      instance,
      autoscalerState
    );
  }

  /** Processes an operation that has failed. */
  protected processFailedOperation(
    operationState: OperationState,
    instance: ScalableInstanceWithData,
    autoscalerState: StateData
  ): StateDataFetchResult {
    this.scalingOperationReporter.reportFailedOperation(
      operationState,
      autoscalerState,
      instance
    );
    const newStateData = {
      ...autoscalerState,
      scalingOperationId: null,
      scalingRequestedSize: null,
      lastScalingCompleteTimestamp: 0,
      lastScalingTimestamp: 0,
      scalingPreviousSize: 0,
      scalingMethod: null,
    };
    return [newStateData, true];
  }

  /** Processes an operation that is ongoing. */
  protected processRunningOperation(
    operationState: OperationState,
    instance: ScalableInstanceWithData,
    autoscalerState: StateData
  ): StateDataFetchResult {
    if (this.isOperationCancelled(operationState)) {
      this.scalingOperationReporter.reportCancelledOperation(
        operationState,
        autoscalerState,
        instance
      );
    } else {
      this.scalingOperationReporter.reportInProgressOperation(
        operationState,
        autoscalerState,
        instance
      );
    }
    return [autoscalerState, false];
  }

  /** Processes an operation that is completed successfully. */
  protected processSuccessfulOperation(
    operationState: OperationState,
    instance: ScalableInstanceWithData,
    autoscalerState: StateData
  ): StateDataFetchResult {
    const payloadLogger = getPayloadLogger(this.baseLogger, instance, instance);
    let newStateData = {...autoscalerState};

    if (operationState?.metadata?.endTime) {
      newStateData.lastScalingCompleteTimestamp = Date.parse(
        operationState.metadata.endTime
      );
    } else {
      payloadLogger.warn(
        'Failed to parse operation endTime: ' +
          operationState?.metadata?.endTime
      );
      // Assume start time since end time is invalid.
      newStateData.lastScalingCompleteTimestamp =
        newStateData.lastScalingTimestamp;
    }

    // Send the newStateData instead of autoscalerState to utilize the
    // lastScalingTimestamp, and before clearing the state up.
    this.scalingOperationReporter.reportSuccessfulOperation(
      operationState,
      newStateData,
      instance
    );

    newStateData = {
      ...newStateData,
      scalingOperationId: null,
      scalingRequestedSize: null,
      scalingPreviousSize: null,
      scalingMethod: null,
    };

    return [newStateData, true];
  }

  /** Processes an unknown operation. */
  protected processUnknownOperation(
    instance: ScalableInstanceWithData,
    autoscalerState: StateData,
    error: Error
  ): StateDataFetchResult {
    const payloadLogger = getPayloadLogger(this.baseLogger, instance, instance);
    payloadLogger.error({
      message:
        'Failed to retrieve state of operation, assume completed. ' +
        `ID: ${autoscalerState.scalingOperationId}: ${error}`,
      error: error,
    });

    // Fallback - API failed or returned invalid status.
    // Assume the operation was completed.
    let newStateData = {
      ...autoscalerState,
      lastScalingCompleteTimestamp: autoscalerState.lastScalingTimestamp,
      scalingOperationId: null,
    };
    this.scalingOperationReporter.reportUnknownOperationAsSuccessful(
      newStateData,
      instance
    );
    newStateData = {
      ...newStateData,
      scalingRequestedSize: null,
      scalingPreviousSize: null,
      scalingMethod: null,
    };
    return [newStateData, true];
  }

  /**
   * Validates the Operation data fetched from the API.
   *
   * Throws if:
   *   - no operation was fetched.
   *   - operation had no metadata.
   *   - metadata is not of expected type.
   *
   *
   * @param autoscalerState State as stored in StateStore.
   * @param operationState State as fetched from the API.
   */
  protected validateOperationState(
    operationState: OperationState | null | undefined,
    autoscalerState: StateData
  ) {
    if (!operationState) {
      throw new Error(
        `GetOperation(${autoscalerState.scalingOperationId}) returned no ` +
          'results'
      );
    }

    if (
      !operationState?.metadata ||
      !operationState?.metadata?.['@type'] ||
      !this.operationTypeRegExp.test(operationState?.metadata?.['@type'])
    ) {
      throw new Error(
        `GetOperation(${autoscalerState.scalingOperationId}) contained no ` +
          `operation of type ${this.operationTypeRegExp}`
      );
    }
  }

  /** Checks whether a certain operation is cancelled. */
  protected isOperationCancelled(operationState: OperationState): boolean {
    return !!operationState?.metadata?.requestedCancellation;
  }

  /** Checks whether a certain operation is done. */
  protected isOperationDone(operationState: OperationState): boolean {
    if (operationState?.done === undefined || operationState?.done === null) {
      throw new Error(
        `GetOperation(${operationState.name}) contained no information about ` +
          'its completion state.'
      );
    }
    return operationState.done;
  }

  /** Checks whether a certain operation failed with errors. */
  protected isOperationWithErrors(operationState: OperationState): boolean {
    return !!operationState.error;
  }
}
