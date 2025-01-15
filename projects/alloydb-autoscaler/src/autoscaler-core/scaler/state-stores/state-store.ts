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

/** @file Provides a builder for StateStore. */

import pino from 'pino';
import {createLogger, getInstanceLogger} from '../../common/logger';
import {ScalableInstanceWithData} from '../../common/instance-info';
import {IStateStore} from './state';
import {FirestoreClientProvider, FirestoreStateStore} from './state-firestore';
import {SpannerClientProvider, SpannerStateStore} from './state-spanner';

/** Builds a StateStore. */
export class StateStoreBuilder {
  protected logger: pino.Logger;

  /**
   * Initializes the StateStoreBuilder.
   * @param libName Library name to use on the clients.
   * @param libVersion Library version to use on the clients.
   * @param storageIdentifier Identifier for the table or docRef.
   *   For Firestore, it acts as the docRefPrefix.
   *   For Spanner, it is used as the tableName.
   */
  constructor(
    protected libName: string,
    protected libVersion: string,
    protected storageIdentifier: string
  ) {
    this.logger = createLogger(libName, libVersion);
  }

  /**
   * Builds a StateStore object for the given configuration.
   *
   * @param instance Scaleable instance for which to build State.
   */
  buildFor(instance: ScalableInstanceWithData): IStateStore {
    if (!instance) {
      throw new Error('Instance should not be null.');
    }

    switch (instance?.stateConfig?.stateDatabase?.name?.toLowerCase()) {
      case 'spanner':
        return this.buildSpannerStateStoreFor(instance);
      case 'firestore':
        return this.buildFirestoreStateStoreFor(instance);
      default:
        throw new Error(
          'State Database must be one of Spanner or Firestore, got ' +
            instance?.stateConfig?.stateDatabase?.name
        );
    }
  }

  /** Builds a StateStore for Firestore. */
  private buildFirestoreStateStoreFor(
    instance: ScalableInstanceWithData
  ): FirestoreStateStore {
    if (!instance?.stateConfig?.stateProjectId) {
      throw new Error(
        'stateProjectId must be defined when using Firestore as the state ' +
          'storage.'
      );
    }

    const firestoreClient = FirestoreClientProvider.getClient(
      this.libName,
      this.libVersion,
      instance.stateConfig.stateProjectId
    );
    return new FirestoreStateStore(
      instance,
      this.storageIdentifier,
      firestoreClient
    );
  }

  /** Builds a StateStore for Spanner. */
  private buildSpannerStateStoreFor(
    instance: ScalableInstanceWithData
  ): SpannerStateStore {
    if (!instance?.stateConfig?.stateProjectId) {
      throw new Error(
        'stateProjectId must be defined when using Spanner as the state ' +
          'storage.'
      );
    }
    if (!instance?.stateConfig?.stateDatabase?.instanceId) {
      throw new Error(
        'stateDatabase.instanceId must be defined when using Spanner as the ' +
          'state storage.'
      );
    }
    if (!instance?.stateConfig?.stateDatabase?.databaseId) {
      throw new Error(
        'stateDatabase.databaseId must be defined when using Spanner as the ' +
          'state storage.'
      );
    }

    const instanceLogger = getInstanceLogger(this.logger, instance);

    const spannerTableClient = SpannerClientProvider.getClient(
      instance.stateConfig.stateProjectId,
      instance.stateConfig.stateDatabase.instanceId,
      instance.stateConfig.stateDatabase.databaseId,
      this.storageIdentifier
    );
    return new SpannerStateStore(instance, spannerTableClient, instanceLogger);
  }
}
