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

/** @fileoverview Tests alloydb-state-fetcher. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import {AlloyDbStateFetcher} from '../alloydb-state-fetcher';
import {StateData} from '../../../autoscaler-core/scaler/state-stores/state';
import {CounterManager} from '../../../autoscaler-core/common/counters';
import {alloydb_v1} from 'googleapis';
import {MethodOptions, GaxiosPromise, GaxiosOptions} from 'googleapis-common';
import {ScalingOperationReporter} from '../../../autoscaler-core/scaler/scaling-operation-reporter';
import {silentLogger} from '../../../autoscaler-core/testing/testing-framework';
import {TEST_ALLOYDB_INSTANCE_WITH_DATA} from '../../testing/testing-data';
import {TEST_STATE_DATA} from '../../../autoscaler-core/testing/testing-data';

const OPERATION = Object.freeze({
  done: true,
  name: 'successfulOperation',
  metadata: Object.freeze({
    createTime: '2024-01-01T00:00:00Z',
    endTime: '2024-01-01T00:01:00Z',
  }),
});

const BASE_GET_RESPONSE = Object.freeze({
  data: Object.freeze({}), // Change on each test.
  // Unused.
  config: Object.freeze({}) as GaxiosOptions,
  status: 200,
  statusText: 'OK',
  headers: Object.freeze({}) as Headers,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  request: Object.freeze({}) as any, // GaxiosXMLHttpRequest
});

type AlloyDbRestApiGet = (
  params?: alloydb_v1.Params$Resource$Projects$Locations$Operations$Get,
  options?: MethodOptions
) => GaxiosPromise<alloydb_v1.Schema$Operation>;

describe('AlloyDbStateFetcher', () => {
  let counterManager: jasmine.SpyObj<CounterManager>;
  let scalingOperationReporter: jasmine.SpyObj<ScalingOperationReporter>;
  let alloyDbRestApi: jasmine.SpyObj<alloydb_v1.Alloydb>;
  let alloyDbRestApiGetSpy: jasmine.Spy<AlloyDbRestApiGet>;

  beforeEach(() => {
    counterManager = jasmine.createSpyObj('CounterManager', [
      'incrementCounter',
      'recordValue',
    ]);
    scalingOperationReporter = jasmine.createSpyObj(
      'ScalingOperationReporter',
      [
        'reportCancelledOperation',
        'reportFailedOperation',
        'reportInProgressOperation',
        'reportSuccessfulOperation',
        'reportUnknownOperationAsSuccessful',
      ]
    );
    alloyDbRestApiGetSpy = jasmine.createSpy();
    alloyDbRestApi = jasmine.createSpyObj('AlloyDbRestAPI', [], {
      projects: {locations: {operations: {get: alloyDbRestApiGetSpy}}},
    });
  });

  describe('fetchOperationStateFromApi', () => {
    it('fetches the expected operation', async () => {
      alloyDbRestApiGetSpy.and.callFake(async () => BASE_GET_RESPONSE);
      const alloyDbStateFetcher = new TestableAlloyDbStateFetcher(
        silentLogger,
        counterManager,
        scalingOperationReporter,
        alloyDbRestApi
      );

      await alloyDbStateFetcher.publicFetchOperationStateFromApi(
        TEST_STATE_DATA
      );

      expect(alloyDbRestApiGetSpy).toHaveBeenCalledOnceWith({name: 'id-123'});
    });
  });

  // Most behaviours are tested on state-fetcher. Here, just reaffirming that
  // the interaction with the new methods and RegExp is working as intended.
  describe('fetchOperationState', () => {
    [
      'type.googleapis.com/google.cloud.alloydb.v1.OperationMetadata',
      'type.googleapis.com/google.cloud.alloydb.v1beta.OperationMetadata',
    ].forEach(operationType => {
      it(`succeeds for valid operation type: ${operationType}`, async () => {
        const expectedOperation = {
          ...OPERATION,
          metadata: {
            ...OPERATION.metadata,
            '@type': operationType,
          },
        };
        alloyDbRestApiGetSpy.and.callFake(async () => {
          return {
            ...BASE_GET_RESPONSE,
            data: expectedOperation,
          };
        });
        const alloyDbStateFetcher = new AlloyDbStateFetcher(
          silentLogger,
          counterManager,
          scalingOperationReporter,
          alloyDbRestApi
        );

        const output = await alloyDbStateFetcher.fetchOperationState(
          TEST_ALLOYDB_INSTANCE_WITH_DATA,
          TEST_STATE_DATA
        );

        expect(output).toEqual([
          {
            createdOn: 1e6,
            updatedOn: 2e6,
            lastScalingTimestamp: 3e6,

            scalingOperationId: null,
            scalingRequestedSize: null,
            scalingPreviousSize: null,
            scalingMethod: null,
            lastScalingCompleteTimestamp: 1704067260000,
          },
          true,
        ]);
        expect(
          scalingOperationReporter.reportSuccessfulOperation
        ).toHaveBeenCalledOnceWith(
          expectedOperation,
          {...TEST_STATE_DATA, lastScalingCompleteTimestamp: 1704067260000},
          TEST_ALLOYDB_INSTANCE_WITH_DATA
        );
      });
    });

    it('is marked as unknown for invalid operation type', async () => {
      const expectedOperation = {
        ...OPERATION,
        metadata: {
          ...OPERATION.metadata,
          '@type': 'invalid-operation-type',
        },
      };
      alloyDbRestApiGetSpy.and.callFake(async () => {
        return {
          ...BASE_GET_RESPONSE,
          data: expectedOperation,
        };
      });
      const alloyDbStateFetcher = new AlloyDbStateFetcher(
        silentLogger,
        counterManager,
        scalingOperationReporter,
        alloyDbRestApi
      );

      const output = await alloyDbStateFetcher.fetchOperationState(
        TEST_ALLOYDB_INSTANCE_WITH_DATA,
        TEST_STATE_DATA
      );

      expect(output).toEqual([
        {
          createdOn: 1e6,
          updatedOn: 2e6,
          lastScalingTimestamp: 3e6,
          scalingOperationId: null,
          scalingRequestedSize: null,
          scalingPreviousSize: null,
          scalingMethod: null,
          lastScalingCompleteTimestamp: 3000000,
        },
        true,
      ]);
      expect(
        scalingOperationReporter.reportUnknownOperationAsSuccessful
      ).toHaveBeenCalledOnceWith(
        {
          createdOn: 1e6,
          updatedOn: 2e6,
          lastScalingTimestamp: 3e6,
          scalingOperationId: null,
          scalingRequestedSize: 5,
          scalingPreviousSize: 3,
          scalingMethod: 'DIRECT',
          lastScalingCompleteTimestamp: 3000000,
        },
        TEST_ALLOYDB_INSTANCE_WITH_DATA
      );
    });
  });
});

class TestableAlloyDbStateFetcher extends AlloyDbStateFetcher {
  /** Public interface for fetchOperationStateFromApi. */
  async publicFetchOperationStateFromApi(autoscalerState: StateData) {
    return await this.fetchOperationStateFromApi(autoscalerState);
  }
}
