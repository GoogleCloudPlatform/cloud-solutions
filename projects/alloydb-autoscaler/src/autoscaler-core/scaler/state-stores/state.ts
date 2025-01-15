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

/** @file Provides basic definitions for handling State. */

/** A column definition. */
export type StateColumnDefinition = {
  name: string;
  type: string;
};

/** List of state key column definitions. */
export const STATE_KEY_DEFINITIONS: StateColumnDefinition[] = [
  {name: 'lastScalingTimestamp', type: 'timestamp'},
  {name: 'createdOn', type: 'timestamp'},
  {name: 'updatedOn', type: 'timestamp'},
  {name: 'lastScalingCompleteTimestamp', type: 'timestamp'},
  {name: 'scalingOperationId', type: 'string'},
  {name: 'scalingRequestedSize', type: 'number'},
  {name: 'scalingPreviousSize', type: 'number'},
  {name: 'scalingMethod', type: 'string'},
];

/** State Data for the scaling operation. */
export interface StateData {
  /** The timestamp when the last scaling operation completed. */
  lastScalingCompleteTimestamp?: number | null;
  /** The ID of the currently in progress scaling operation. */
  scalingOperationId?: string | null;
  /** The requested size of the currently in progress scaling operation. */
  scalingRequestedSize?: number | null;
  /**
   * The size of the cluster before the currently in progress scaling operation
   * started.
   */
  scalingPreviousSize?: number | null;
  /**
   * The scaling method used to calculate the size for the currently in progress
   * scaling operation.
   */
  scalingMethod?: string | null;
  /** The timestamp when the last scaling operation was started. */
  lastScalingTimestamp: number;
  /** The timestamp when this record was created */
  createdOn?: number;
  /** The timestamp when this record was updated. */
  updatedOn?: number;
}

/**
 * StateData without complex types.
 * Complex types like Timestamp tend to differ in typing among storages.
 * This omits those typings so a new StorageStateData can be defined.
 */
export type PartialStateDataWithoutComplexTypes = Omit<
  StateData,
  | 'lastScalingCompleteTimestamp'
  | 'lastScalingTimestamp'
  | 'createdOn'
  | 'updatedOn'
>;

/** Handles the State storage in a given database type. */
export interface IStateStore {
  // Initializes the storage StateStore instance.
  // new(instance: ScalableInstanceWithData): IStateStore;
  /** Initialize the value in storage. */
  // Use any to avoid cyclical dependencies or having to break this module down.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  init(): Promise<any>; // FirestoreStateData | SpannerStateData
  /** Get state data from storage. */
  getState(): Promise<StateData>;
  /** Updates the state data in storage with the given values. */
  updateState(stateData: StateData): Promise<void>;
  /** Closes the storage. */
  close(): Promise<void>;
}

/** Converts StateData into and from Storage format. */
export interface IStateDataConverter<T> {
  convertFromStorage(storageData: T): StateData;
  convertToStorage(stateData: StateData): T;
}

/** Provides basic functionality to interact with StateData. */
export class BaseStateDataConverter {
  /** Adds a default value for a column definition for StateData. */
  protected getDefaultStateValue(colDef: StateColumnDefinition): number | null {
    if (colDef.type === 'timestamp') return 0;
    return null;
  }

  /** Gets the initial StateData. */
  getInitStateData(): StateData {
    const now = Date.now();
    return {
      createdOn: now,
      updatedOn: now,
      lastScalingTimestamp: 0,
      lastScalingCompleteTimestamp: 0,
      scalingOperationId: null,
      scalingRequestedSize: null,
      scalingMethod: null,
      scalingPreviousSize: null,
    };
  }
}
