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

/** @file Provides a StateStore using Firestore as the storage. */

import {memoize} from 'lodash';
import {ScalableInstanceWithData} from '../../common/instance-info';
import {
  IStateStore,
  StateData,
  STATE_KEY_DEFINITIONS,
  PartialStateDataWithoutComplexTypes,
  IStateDataConverter,
  BaseStateDataConverter,
} from './state';
import {
  DocumentData,
  DocumentReference,
  DocumentSnapshot,
  Firestore,
  Timestamp,
} from '@google-cloud/firestore';

/** StateData with Firestore data types. */
export type FirestoreStateData = PartialStateDataWithoutComplexTypes & {
  lastScalingCompleteTimestamp?: Timestamp | null;
  lastScalingTimestamp: Timestamp | null;
  createdOn?: Timestamp | null;
  updatedOn: Timestamp | null;
};

/** Provides the required client for Firestore. */
export class FirestoreClientProvider {
  /**
   * Gets the Firestore Client.
   *
   * Memoizes createClient() so that we only create one Firestore
   * client for each stateProject.
   */
  static getClient = memoize(FirestoreClientProvider.createClient);

  /** Builds a Firestore Client. */
  private static createClient(
    libName: string,
    libVersion: string,
    projectId: string
  ): Firestore {
    return new Firestore({
      libName: libName,
      libVersion: libVersion,
      projectId: projectId,
    });
  }
}

/** Casts data to and from Firestore document format. */
class FirestoreDataConverter
  extends BaseStateDataConverter
  implements IStateDataConverter<FirestoreStateData>
{
  /** Initializes FirestoreDataConverter. */
  constructor() {
    super();
  }

  /**
   * Converts document data from Firestore.Timestamp (implementation detail)
   * to standard JS timestamps, which are number of milliseconds since Epoch
   * https://googleapis.dev/nodejs/firestore/latest/Timestamp.html
   */
  convertFromStorage(storageData: FirestoreStateData): StateData {
    // Cast to avoid Typescript issues when accessing properties with:
    // storageData[colDef.name].
    // Allow for any since the data storage is not controlled by us.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const sourceData: Record<string, any> = storageData;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const stateData: Record<string, any> = {};

    const docDataKeys = Object.keys(storageData);
    for (const colDef of STATE_KEY_DEFINITIONS) {
      if (!docDataKeys.includes(colDef.name)) {
        stateData[colDef.name] = this.getDefaultStateValue(colDef);
        continue;
      }
      if (sourceData[colDef.name] instanceof Timestamp) {
        stateData[colDef.name] = sourceData[colDef.name].toMillis();
        continue;
      }

      stateData[colDef.name] = sourceData[colDef.name];
    }

    return stateData as StateData;
  }

  /**
   * Converts StateData to an object only containing defined
   * columns, including converting timestamps from millis to Firestore.Timestamp
   */
  convertToStorage(stateData: StateData): FirestoreStateData {
    // Cast to avoid Typescript issues when accessing properties with:
    // stateData[colDef.name].
    // Allow for any as the data storage is not controlled by us.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const sourceData: Record<string, any> = stateData;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const storageData: Record<string, any> = {};

    const stateDataKeys = Object.keys(stateData);
    for (const colDef of STATE_KEY_DEFINITIONS) {
      if (!stateDataKeys.includes(colDef.name)) continue;

      if (colDef.type === 'timestamp') {
        storageData[colDef.name] = Timestamp.fromMillis(
          sourceData[colDef.name]
        );
        continue;
      }

      storageData[colDef.name] = sourceData[colDef.name];
    }
    return storageData as FirestoreStateData;
  }
}

/**
 * Manages the Autoscaler persistent state in Firestore.
 *
 * The default database for state management is firestore.
 * It is also possible to manage with firestore
 * by explicitly setting `stateDatabase.name` to 'firestore'.
 * The following is an example.
 *
 * {
 *   "stateDatabase": {
 *       "name": "firestore"
 *   }
 * }
 */
export class FirestoreStateStore implements IStateStore {
  private _docRef?: DocumentReference;
  protected converter: FirestoreDataConverter = new FirestoreDataConverter();

  /**
   * Initializes FirestoreStateStore.
   * @param instance Instance configuration.
   * @param docRefPrefix Prefix for the document reference.
   * @param firestore Initialized Firestore client.
   */
  constructor(
    protected instance: ScalableInstanceWithData,
    protected docRefPrefix: string,
    protected firestore: Firestore
  ) {
    if (!instance?.stateConfig?.stateProjectId) {
      throw new Error(
        'Firestore Project ID not specified. ' +
          'Add stateProjectId to your configuration.'
      );
    }
  }

  /** @inheritdoc */
  async init(): Promise<FirestoreStateData> {
    const initData = this.converter.getInitStateData();
    const initFirestoreData = this.converter.convertToStorage(initData);
    if (!this.docRef) {
      throw new Error('Failed to set docRef during initialization.');
    }
    await this.docRef.set(initFirestoreData);
    return initFirestoreData;
  }

  /** @inheritdoc */
  async getState() {
    const snapshot: DocumentSnapshot<DocumentData, DocumentData> =
      await this.docRef.get();
    const storageData = snapshot.exists ? snapshot.data() : await this.init();
    if (!storageData) {
      throw new Error(
        `Failed to retrieve State data for instance: ${this.instance}`
      );
    }
    return this.converter.convertFromStorage(storageData as FirestoreStateData);
  }

  /** @inheritdoc */
  async updateState(stateData: StateData) {
    const writeData = {
      ...stateData, // Avoid modifying original object.
      updatedOn: Date.now(),
    };
    const storageData = this.converter.convertToStorage(writeData);
    // We never want to update createdOn.
    delete storageData.createdOn;
    await this.docRef.update(storageData);
  }

  /** @inheritdoc */
  async close() {}

  /** Builds or returns the document reference. */
  protected get docRef(): DocumentReference {
    if (!this.instance.info.resourcePath) {
      throw new Error(
        'Instance.info must have a resourcePath, but got: ' +
          JSON.stringify(this.instance)
      );
    }

    if (!this._docRef) {
      this._docRef = this.firestore.doc(
        `${this.docRefPrefix}/state/${this.instance.info.resourcePath}`
      );
    }

    if (!this._docRef) {
      // If still empty after getting the document.
      throw new Error('Failed to set docRef during initialization.');
    }

    return this._docRef;
  }
}
