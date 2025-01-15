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

/** @fileoverview Tests state-store. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import {
  ScalableInstanceWithData,
  StateDatabaseConfig,
  StateConfig,
} from '../../../common/instance-info';
import {StateStoreBuilder} from '../state-store';
import {FirestoreClientProvider, FirestoreStateStore} from '../state-firestore';
import {SpannerClientProvider, SpannerStateStore} from '../state-spanner';
import {TEST_INSTANCE_WITH_DATA} from '../../../testing/testing-data';

describe('StateStoreBuilder', () => {
  let stateStoreBuilder: StateStoreBuilder;

  beforeEach(() => {
    // Prevent actual connections to the database(s).
    spyOn(FirestoreClientProvider, 'getClient');
    spyOn(SpannerClientProvider, 'getClient');

    stateStoreBuilder = new StateStoreBuilder(
      'libName',
      'libVersion',
      'autoscaler-storage'
    );
  });

  describe('buildFor', () => {
    [
      {
        testCaseName: 'FirestoreStateStore',
        stateDatabase: {name: 'firestore'} as StateDatabaseConfig,
        expectedInstance: FirestoreStateStore,
      },
      {
        testCaseName: 'SpannerStateStore',
        stateDatabase: {
          name: 'spanner',
          instanceId: 'state-instance',
          databaseId: 'state-database',
        } as StateDatabaseConfig,
        expectedInstance: SpannerStateStore,
      },
    ].forEach(({testCaseName, stateDatabase, expectedInstance}) => {
      it(`produces ${testCaseName}`, () => {
        const instanceConfig: ScalableInstanceWithData = {
          ...TEST_INSTANCE_WITH_DATA,
          stateConfig: {
            stateProjectId: 'project-123',
            stateDatabase: stateDatabase,
          },
        };

        const output = stateStoreBuilder.buildFor(instanceConfig);

        expect(output).toBeInstanceOf(expectedInstance);
      });
    });

    [
      {
        testCaseName: 'stateProjectId is not set for Firestore',
        stateConfig: {
          stateDatabase: {name: 'firestore'},
        } as StateConfig,
        expectedError: new Error(
          'stateProjectId must be defined when using Firestore as the state ' +
            'storage.'
        ),
      },
      {
        testCaseName: 'stateProjectId is not set for Spanner',
        stateConfig: {
          stateDatabase: {name: 'spanner'},
        } as StateConfig,
        expectedError: new Error(
          'stateProjectId must be defined when using Spanner as the state ' +
            'storage.'
        ),
      },
      {
        testCaseName: 'instanceId is not set for Spanner',
        stateConfig: {
          stateProjectId: 'project-123',
          stateDatabase: {name: 'spanner'},
        } as StateConfig,
        expectedError: new Error(
          'stateDatabase.instanceId must be defined when using Spanner ' +
            'as the state storage.'
        ),
      },
      {
        testCaseName: 'databaseId is not set for Spanner',
        stateConfig: {
          stateProjectId: 'project-123',
          stateDatabase: {
            name: 'spanner',
            instanceId: 'spanner-instance',
          },
        } as StateConfig,
        expectedError: new Error(
          'stateDatabase.databaseId must be defined when using Spanner ' +
            'as the state storage.'
        ),
      },
    ].forEach(({testCaseName, stateConfig, expectedError}) => {
      it(`throws when ${testCaseName}`, () => {
        const instanceConfig: ScalableInstanceWithData = {
          ...TEST_INSTANCE_WITH_DATA,
          stateConfig: stateConfig,
        };

        expect(() => {
          stateStoreBuilder.buildFor(instanceConfig);
        }).toThrow(expectedError);
      });
    });
  });
});
