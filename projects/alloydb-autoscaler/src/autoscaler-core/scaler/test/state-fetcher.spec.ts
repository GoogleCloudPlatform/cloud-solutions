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

/** @fileoverview Tests state-fetcher. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import pino from 'pino';
import {OperationState} from '../scaling-operation';
import {IScalingOperationReporter} from '../scaling-operation-reporter';
import {StateData} from '../state-stores/state';
import {StateFetcher, StateDataFetchResult} from '../state-fetcher';
import {createPayloadLoggerWithMocks} from '../../testing/testing-framework';
import {
  TEST_INSTANCE_WITH_DATA,
  TEST_STATE_DATA,
  TEST_OPERATION_CANCELLED,
  TEST_OPERATION_RUNNING,
  TEST_OPERATION_FAILED,
  TEST_OPERATION_SUCCESSFUL,
  TEST_OPERATION_SUCCESSFUL_WITHOUT_END_TIME,
} from '../../testing/testing-data';

describe('StateFetcher', () => {
  let baseLogger: jasmine.SpyObj<pino.Logger>;
  let payloadLoggerMock: jasmine.SpyObj<pino.Logger>;
  let stateFetcher: TestableStateFetcher;
  let scalingOperationReporter: jasmine.SpyObj<IScalingOperationReporter>;

  beforeEach(() => {
    [baseLogger, payloadLoggerMock] = createPayloadLoggerWithMocks();

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

    stateFetcher = new TestableStateFetcher(
      baseLogger,
      new RegExp('Oper[a-z]{4}nMetadata'),
      scalingOperationReporter
    );
  });

  describe('fetchOperationState', () => {
    [
      {
        testCaseName: 'cancelled operation',
        stateData: TEST_STATE_DATA,
        operationState: TEST_OPERATION_CANCELLED,
        expectedStateData: TEST_STATE_DATA,
        expectedIsModified: false,
      },
      {
        testCaseName: 'running operation',
        stateData: TEST_STATE_DATA,
        operationState: TEST_OPERATION_RUNNING,
        expectedStateData: TEST_STATE_DATA,
        expectedIsModified: false,
      },
      {
        testCaseName: 'failed operation',
        stateData: TEST_STATE_DATA,
        operationState: TEST_OPERATION_FAILED,
        expectedStateData: {
          createdOn: 1e6,
          updatedOn: 2e6,
          scalingOperationId: null,
          scalingRequestedSize: null,
          lastScalingCompleteTimestamp: 0,
          lastScalingTimestamp: 0,
          scalingPreviousSize: 0,
          scalingMethod: null,
        },
        expectedIsModified: true,
      },
      {
        testCaseName: 'sucessful operation, with end time',
        stateData: TEST_STATE_DATA,
        operationState: TEST_OPERATION_SUCCESSFUL,
        expectedStateData: {
          createdOn: 1e6,
          updatedOn: 2e6,
          lastScalingCompleteTimestamp: 1704067260000,
          lastScalingTimestamp: 3e6,
          scalingOperationId: null,
          scalingRequestedSize: null,
          scalingPreviousSize: null,
          scalingMethod: null,
        },
        expectedIsModified: true,
      },
      {
        testCaseName: 'sucessful operation, without end time',
        stateData: TEST_STATE_DATA,
        operationState: TEST_OPERATION_SUCCESSFUL_WITHOUT_END_TIME,
        expectedStateData: {
          createdOn: 1e6,
          updatedOn: 2e6,
          lastScalingCompleteTimestamp: 3e6,
          lastScalingTimestamp: 3e6,
          scalingOperationId: null,
          scalingRequestedSize: null,
          scalingPreviousSize: null,
          scalingMethod: null,
        },
        expectedIsModified: true,
      },
      {
        testCaseName: 'unknown operation',
        // Forces an error on the testing class.
        stateData: {...TEST_STATE_DATA, scalingOperationId: 'error'},
        operationState: Object.freeze({}),
        expectedStateData: {
          createdOn: 1e6,
          updatedOn: 2e6,
          lastScalingCompleteTimestamp: 3e6,
          lastScalingTimestamp: 3e6,
          scalingOperationId: null,
          scalingRequestedSize: null,
          scalingPreviousSize: null,
          scalingMethod: null,
        },
        expectedIsModified: true,
      },
    ].forEach(
      ({
        testCaseName,
        stateData,
        operationState,
        expectedStateData,
        expectedIsModified,
      }) => {
        it(`returns expected state data for ${testCaseName}`, async () => {
          stateFetcher.setOperationState(operationState);

          const output = await stateFetcher.fetchOperationState(
            TEST_INSTANCE_WITH_DATA,
            stateData
          );

          expect(output).toEqual([
            expectedStateData,
            expectedIsModified,
          ] as StateDataFetchResult);
        });
      }
    );

    [
      {
        testCaseName: 'operationState is undefined',
        operationState: undefined,
        expectedError: new Error('GetOperation(id-123) returned no results'),
      },
      {
        testCaseName: 'operationState is undefined',
        operationState: null,
        expectedError: new Error('GetOperation(id-123) returned no results'),
      },
      {
        testCaseName: 'operationState is empty',
        operationState: {},
        expectedError: new Error(
          'GetOperation(id-123) contained no operation of type ' +
            '/Oper[a-z]{4}nMetadata/'
        ),
      },
      {
        testCaseName: 'operationState lacks metadata',
        operationState: {done: true},
        expectedError: new Error(
          'GetOperation(id-123) contained no operation of type ' +
            '/Oper[a-z]{4}nMetadata/'
        ),
      },
      {
        testCaseName: 'operationState lacks metadata @type',
        operationState: {
          done: true,
          metadata: {other: 'value'},
        },
        expectedError: new Error(
          'GetOperation(id-123) contained no operation of type ' +
            '/Oper[a-z]{4}nMetadata/'
        ),
      },
      {
        testCaseName: 'operationState is not of expected metadata @type',
        operationState: {
          done: true,
          metadata: {
            '@type': 'not-expected-type',
          },
        },
        expectedError: new Error(
          'GetOperation(id-123) contained no operation of type ' +
            '/Oper[a-z]{4}nMetadata/'
        ),
      },
    ].forEach(({testCaseName, operationState, expectedError}) => {
      it(`fails validation and calls unknown operation when ${testCaseName}`, async () => {
        stateFetcher.setOperationState(operationState);

        await stateFetcher.fetchOperationState(
          TEST_INSTANCE_WITH_DATA,
          TEST_STATE_DATA
        );

        expect(payloadLoggerMock.error).toHaveBeenCalledOnceWith(
          jasmine.objectContaining({
            message:
              'Failed to retrieve state of operation, assume completed. ID: ' +
              'id-123: ' +
              expectedError,
            error: expectedError,
          })
        );
      });

      it(`reports unknown operation when ${testCaseName}`, async () => {
        stateFetcher.setOperationState(operationState);

        await stateFetcher.fetchOperationState(
          TEST_INSTANCE_WITH_DATA,
          TEST_STATE_DATA
        );

        const modifiedStateData = {
          ...TEST_STATE_DATA,
          lastScalingCompleteTimestamp: 3e6, // from lastScalingTimestamp
          scalingOperationId: null,
        };
        expect(
          scalingOperationReporter.reportUnknownOperationAsSuccessful
        ).toHaveBeenCalledOnceWith(modifiedStateData, TEST_INSTANCE_WITH_DATA);
      });
    });

    it('reports cancelled operation', async () => {
      stateFetcher.setOperationState(TEST_OPERATION_CANCELLED);

      await stateFetcher.fetchOperationState(
        TEST_INSTANCE_WITH_DATA,
        TEST_STATE_DATA
      );

      expect(
        scalingOperationReporter.reportCancelledOperation
      ).toHaveBeenCalledOnceWith(
        TEST_OPERATION_CANCELLED,
        TEST_STATE_DATA,
        TEST_INSTANCE_WITH_DATA
      );
    });

    it('reports in progress operation', async () => {
      stateFetcher.setOperationState(TEST_OPERATION_RUNNING);

      await stateFetcher.fetchOperationState(
        TEST_INSTANCE_WITH_DATA,
        TEST_STATE_DATA
      );

      expect(
        scalingOperationReporter.reportInProgressOperation
      ).toHaveBeenCalledOnceWith(
        TEST_OPERATION_RUNNING,
        TEST_STATE_DATA,
        TEST_INSTANCE_WITH_DATA
      );
    });

    it('reports failed operation', async () => {
      stateFetcher.setOperationState(TEST_OPERATION_FAILED);

      await stateFetcher.fetchOperationState(
        TEST_INSTANCE_WITH_DATA,
        TEST_STATE_DATA
      );

      expect(
        scalingOperationReporter.reportFailedOperation
      ).toHaveBeenCalledOnceWith(
        TEST_OPERATION_FAILED,
        TEST_STATE_DATA,
        TEST_INSTANCE_WITH_DATA
      );
    });

    it('reports successful operation', async () => {
      stateFetcher.setOperationState(TEST_OPERATION_SUCCESSFUL);

      await stateFetcher.fetchOperationState(
        TEST_INSTANCE_WITH_DATA,
        TEST_STATE_DATA
      );

      const modifiedStateData = {
        ...TEST_STATE_DATA,
        lastScalingCompleteTimestamp: 1704067260000, // 2024-01-01T00:01:00Z
      };
      expect(
        scalingOperationReporter.reportSuccessfulOperation
      ).toHaveBeenCalledOnceWith(
        TEST_OPERATION_SUCCESSFUL,
        modifiedStateData,
        TEST_INSTANCE_WITH_DATA
      );
    });

    it('reports successful operation without end date', async () => {
      stateFetcher.setOperationState(
        TEST_OPERATION_SUCCESSFUL_WITHOUT_END_TIME
      );

      await stateFetcher.fetchOperationState(
        TEST_INSTANCE_WITH_DATA,
        TEST_STATE_DATA
      );

      const modifiedStateData = {
        ...TEST_STATE_DATA,
        lastScalingCompleteTimestamp: 3e6, // from lastScalingTimestamp
      };
      expect(
        scalingOperationReporter.reportSuccessfulOperation
      ).toHaveBeenCalledOnceWith(
        TEST_OPERATION_SUCCESSFUL_WITHOUT_END_TIME,
        modifiedStateData,
        TEST_INSTANCE_WITH_DATA
      );
    });
  });
});

class TestableStateFetcher extends StateFetcher {
  private operationState?: OperationState | null;

  /** Sets OperationState for tests. */
  setOperationState(operationState?: OperationState | null) {
    this.operationState = operationState;
  }

  /**
   * Fetches data from the API.
   *
   * This method is not implemented on the base class. Each derived class must
   * implement its own. For testing purpose, its value will be hard coded. To
   * set the value, setOperationState(operationState) needs to be called.
   */
  protected async fetchOperationStateFromApi(autoscalerState: StateData) {
    if (autoscalerState.scalingOperationId === 'error') {
      throw new Error('Forced error for testing.');
    }
    return this.operationState;
  }
}
