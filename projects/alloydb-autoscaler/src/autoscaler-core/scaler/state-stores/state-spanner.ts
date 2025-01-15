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

/** @fileoview Provides a StateStore using Spanner as the storage. */

import {memoize} from 'lodash';
import {
  Spanner,
  Database as SpannerDatabase,
  Table as SpannerTable,
} from '@google-cloud/spanner';
import {
  IStateStore,
  StateData,
  STATE_KEY_DEFINITIONS,
  IStateDataConverter,
  BaseStateDataConverter,
  PartialStateDataWithoutComplexTypes,
} from './state';
import {ScalableInstanceWithData} from '../../common/instance-info';
import pino from 'pino';

/** StateData with Firestore data types. */
export type SpannerStateData = PartialStateDataWithoutComplexTypes & {
  lastScalingCompleteTimestamp?: string | Date | null;
  lastScalingTimestamp: string | Date | null;
  createdOn?: string | Date | null;
  updatedOn: string | Date | null;
  id?: string;
};

/** Provides the required client(s) for Spanner. */
export class SpannerClientProvider {
  /** Builds a Spanner Table client. */
  static getClient(
    projectId: string,
    instanceId: string,
    databaseId: string,
    tableName: string
  ): SpannerTable {
    const databaseClient = SpannerClientProvider.getDatabaseClient(
      projectId,
      instanceId,
      databaseId
    );
    return databaseClient.table(tableName);
  }

  /**
   * Gets the Spanner Database Client.
   *
   * Memoizes databaseClient so that we only create one Spanner database client
   * for each database ID.
   */
  private static getDatabaseClient = memoize(
    SpannerClientProvider.createDatabaseClient,
    SpannerClientProvider.getStateDatabasePath
  );

  /** Builds a Spanner Table client. */
  private static createDatabaseClient(
    projectId: string,
    instanceId: string,
    databaseId: string
  ): SpannerDatabase {
    const spannerClient = new Spanner({
      // libName and libVersion are not supported.
      projectId: projectId,
    });
    const instance = spannerClient.instance(instanceId);
    return instance.database(databaseId);
  }

  /** Builds a Spanner database path - used as the key for memoize. */
  static getStateDatabasePath(
    projectId: string,
    instanceId: string,
    databaseId: string
  ) {
    return (
      `projects/${projectId}/instances/${instanceId}` +
      `/databases/${databaseId}`
    );
  }
}

/**
 * Casts data to and from Spanner storage format.
 * implements IStateDataConverter<SpannerStateData>
 */
export class SpannerDataConverter
  extends BaseStateDataConverter
  implements IStateDataConverter<SpannerStateData>
{
  /**
   * Converts row data from Spanner.timestamp (implementation detail)
   * to standard JS timestamps, which are number of milliseconds since Epoch
   */
  convertFromStorage(storageData: SpannerStateData): StateData {
    // Cast to avoid Typescript issues when accessing properties with:
    // storageData[colDef.name].
    // Allow for any as the data storage is not controlled by us.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const sourceData: Record<string, any> = storageData;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const stateData: Record<string, any> = {};

    const rowDataKeys = Object.keys(sourceData);
    for (const colDef of STATE_KEY_DEFINITIONS) {
      if (!rowDataKeys.includes(colDef.name)) {
        stateData[colDef.name] = this.getDefaultStateValue(colDef);
        continue;
      }
      if (sourceData[colDef.name] instanceof Date) {
        stateData[colDef.name] = sourceData[colDef.name].getTime();
        continue;
      }
      if (
        colDef.type === 'timestamp' &&
        typeof sourceData[colDef.name] === 'string'
      ) {
        stateData[colDef.name] = Date.parse(sourceData[colDef.name]);
        continue;
      }
      stateData[colDef.name] = sourceData[colDef.name];
    }
    return stateData as StateData;
  }

  /**
   * Convert StateData to a row object only containing defined spanner
   * columns, including converting timestamps.
   */
  convertToStorage(stateData: StateData): SpannerStateData {
    // Cast to avoid Typescript issues when accessing properties with:
    // stateData[colDef.name].
    // Allow for any as the data storage is not controlled by us.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const sourceData: Record<string, any> = stateData;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const storageData: Record<string, any> = {};

    const stateDataKeys = Object.keys(sourceData);
    for (const colDef of STATE_KEY_DEFINITIONS) {
      if (!stateDataKeys.includes(colDef.name)) continue;

      if (
        colDef.type === 'timestamp' &&
        sourceData[colDef.name] !== null &&
        sourceData[colDef.name] !== undefined
      ) {
        storageData[colDef.name] = new Date(
          sourceData[colDef.name]
        ).toISOString();
        continue;
      }

      storageData[colDef.name] = sourceData[colDef.name];
    }
    return storageData as SpannerStateData;
  }
}

/**
 * Manages the Autoscaler persistent state in Spanner.
 *
 * To manage the Autoscaler state in a spanner database,
 * set the `stateDatabase.name` parameter to 'spanner' in the Cloud Scheduler
 * configuration. The following is an example.
 *
 * {
 *   "stateDatabase": {
 *       "name":       "spanner",
 *       "instanceId": "autoscale-test", // your instance id
 *       "databaseId": "my-database"     // your database id
 *   }
 * }
 */
export class SpannerStateStore implements IStateStore {
  protected converter: SpannerDataConverter = new SpannerDataConverter();
  protected databasePath: string;

  /**
   * Initializes FirestoreStateStore.
   * @param instance Instance configuration.
   * @param spannerTable Initialized Spanner client to the required table.
   */
  constructor(
    protected instance: ScalableInstanceWithData,
    protected spannerTable: SpannerTable,
    protected logger: pino.Logger
  ) {
    if (!this.instance.info.resourcePath) {
      throw new Error(
        'Instance.info must have a resourcePath, but got: ' +
          JSON.stringify(this.instance)
      );
    }

    if (!this.instance?.stateConfig?.stateProjectId) {
      throw new Error(
        'Spanner Project ID not specified. ' +
          'Add stateProjectId to your configuration.'
      );
    }

    if (!this.instance?.stateConfig?.stateDatabase?.instanceId) {
      throw new Error(
        'Spanner Instance ID not specified. ' +
          'Add stateDatabase.instanceId to your configuration.'
      );
    }

    if (!this.instance?.stateConfig?.stateDatabase?.databaseId) {
      throw new Error(
        'Spanner Database ID not specified. ' +
          'Add stateDatabase.databaseId to your configuration.'
      );
    }

    this.databasePath = SpannerClientProvider.getStateDatabasePath(
      this.instance.stateConfig.stateProjectId,
      this.instance.stateConfig.stateDatabase.instanceId,
      this.instance.stateConfig.stateDatabase.databaseId
    );
  }

  /** @inheritdoc */
  async init(): Promise<SpannerStateData> {
    const initData = this.converter.getInitStateData();
    const spannerData = this.converter.convertToStorage(initData);
    await this.writeToSpanner(spannerData);
    return spannerData;
  }

  /** @inheritdoc */
  async getState(): Promise<StateData> {
    try {
      const rowId = this.instance.info.resourcePath;
      const query = {
        columns: STATE_KEY_DEFINITIONS.map(c => c.name),
        keySet: {keys: [{values: [{stringValue: rowId}]}]},
      };
      const [rows] = await this.spannerTable.read(query);
      if (rows.length === 0 || !rows[0]) {
        return this.converter.convertFromStorage(await this.init());
      }
      return this.converter.convertFromStorage(rows[0].toJSON());
    } catch (e) {
      this.logger.fatal({
        message:
          'Failed to read from Spanner State storage: ' +
          `${this.databasePath}/tables/${this.spannerTable.name}: ${e}`,
        err: e,
      });
      throw e;
    }
  }

  /** @inheritdoc */
  async updateState(stateData: StateData): Promise<void> {
    stateData.updatedOn = Date.now();
    const row = this.converter.convertToStorage(stateData);
    delete row.createdOn;
    await this.writeToSpanner(row);
  }

  /** @inheritdoc */
  async close(): Promise<void> {}

  /**
   * Writes the given row to spanner, retrying with the older schema if a column
   * not found error is returned.
   */
  private async writeToSpanner(rowData: SpannerStateData) {
    try {
      const writeData = {
        ...rowData, // Avoid modifying original object.
        id: this.instance.info.resourcePath,
      };
      await this.spannerTable.upsert(writeData);
    } catch (e) {
      this.logger.fatal({
        message:
          'Failed to write from Spanner State storage: ' +
          `${this.databasePath}/tables/${this.spannerTable.name}: ${e}`,
        err: e,
      });
      throw e;
    }
  }
}
