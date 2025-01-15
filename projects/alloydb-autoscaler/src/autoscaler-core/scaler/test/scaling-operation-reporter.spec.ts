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

/** @fileoverview Tests scaling-operation-reporter. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import pino from 'pino';
import {ScalingOperationReporter} from '../scaling-operation-reporter';
import {CounterManager} from '../../common/counters';
import {OperationState} from '../scaling-operation';
import {createPayloadLoggerWithMocks} from '../../testing/testing-framework';
import {
  TEST_INSTANCE_WITH_DATA,
  TEST_STATE_DATA,
} from '../../testing/testing-data';

/**
 * Sample Operation State.
 * Not all states (e.g. failed and pendong) are possible at once. However,
 * reporter does not care about the actual state, it only logs the status. As
 * such, the sample state will contain the elements that all the reporters need.
 */
const OPERATION_STATE: OperationState = Object.freeze({
  done: true,
  name: 'testOperation',
  metadata: Object.freeze({
    createTime: '2024-01-01T00:00:00Z',
    endTime: '2024-01-01T00:01:00Z',
  }),
  error: Object.freeze({
    message: 'Error: Something went wrong',
  }),
});

describe('ScalingOperationReporter', () => {
  let baseLogger: jasmine.SpyObj<pino.Logger>;
  let payloadLoggerMock: jasmine.SpyObj<pino.Logger>;
  let counterManager: jasmine.SpyObj<CounterManager>;
  let scalingOperationReporter: ScalingOperationReporter;

  beforeEach(() => {
    [baseLogger, payloadLoggerMock] = createPayloadLoggerWithMocks();

    counterManager = jasmine.createSpyObj('CounterManager', [
      'incrementCounter',
      'recordValue',
    ]);

    scalingOperationReporter = new ScalingOperationReporter(
      baseLogger,
      counterManager
    );
  });

  describe('reportCancelledOperation', () => {
    it('logs expected message', () => {
      scalingOperationReporter.reportCancelledOperation(
        OPERATION_STATE,
        TEST_STATE_DATA,
        TEST_INSTANCE_WITH_DATA
      );

      expect(payloadLoggerMock.info).toHaveBeenCalledOnceWith(
        jasmine.objectContaining({
          message:
            '----- projects/project-123/locations/us-central1: Last scaling ' +
            'request for size 5 CANCEL REQUESTED. Started: ' +
            '2024-01-01T00:00:00Z',
        })
      );
    });
  });

  describe('reportFailedOperation', () => {
    it('logs expected message', () => {
      scalingOperationReporter.reportFailedOperation(
        OPERATION_STATE,
        TEST_STATE_DATA,
        TEST_INSTANCE_WITH_DATA
      );

      expect(payloadLoggerMock.error).toHaveBeenCalledOnceWith(
        jasmine.objectContaining({
          message:
            '----- projects/project-123/locations/us-central1: Last scaling ' +
            'request for size 5 FAILED: Error: Something went wrong. ' +
            'Started: 2024-01-01T00:00:00Z, completed: 2024-01-01T00:01:00Z',
          error: {
            message: 'Error: Something went wrong',
          },
        })
      );
    });

    it('increases failed counter', () => {
      scalingOperationReporter.reportFailedOperation(
        OPERATION_STATE,
        TEST_STATE_DATA,
        TEST_INSTANCE_WITH_DATA
      );

      expect(counterManager.incrementCounter).toHaveBeenCalledOnceWith(
        'scaler/scaling-failed',
        TEST_INSTANCE_WITH_DATA,
        {
          scaling_failed_reason: {message: 'Error: Something went wrong'},
          scaling_method: 'DIRECT',
          scaling_direction: 'SCALE_UP',
        }
      );
    });
  });

  describe('reportInProgressOperation', () => {
    it('logs expected message', () => {
      scalingOperationReporter.reportInProgressOperation(
        OPERATION_STATE,
        TEST_STATE_DATA,
        TEST_INSTANCE_WITH_DATA
      );

      expect(payloadLoggerMock.info).toHaveBeenCalledOnceWith(
        jasmine.objectContaining({
          message:
            '----- projects/project-123/locations/us-central1: Last scaling ' +
            'request for size 5 IN PROGRESS. Started: 2024-01-01T00:00:00Z',
        })
      );
    });
  });

  describe('reportSuccessfulOperation', () => {
    it('logs expected message', () => {
      scalingOperationReporter.reportSuccessfulOperation(
        OPERATION_STATE,
        TEST_STATE_DATA,
        TEST_INSTANCE_WITH_DATA
      );

      expect(payloadLoggerMock.info).toHaveBeenCalledOnceWith(
        jasmine.objectContaining({
          message:
            '----- projects/project-123/locations/us-central1: Last scaling ' +
            'request for size 5 SUCCEEDED. Started: 2024-01-01T00:00:00Z, ' +
            'completed: 2024-01-01T00:01:00Z',
        })
      );
    });

    it('increases successful counter', () => {
      scalingOperationReporter.reportSuccessfulOperation(
        OPERATION_STATE,
        TEST_STATE_DATA,
        TEST_INSTANCE_WITH_DATA
      );

      expect(counterManager.incrementCounter).toHaveBeenCalledOnceWith(
        'scaler/scaling-success',
        TEST_INSTANCE_WITH_DATA,
        {
          scaling_method: 'DIRECT',
          scaling_direction: 'SCALE_UP',
        }
      );
    });

    it('records a value for duration counter', () => {
      scalingOperationReporter.reportSuccessfulOperation(
        OPERATION_STATE,
        TEST_STATE_DATA,
        TEST_INSTANCE_WITH_DATA
      );

      expect(counterManager.recordValue).toHaveBeenCalledOnceWith(
        'scaler/scaling-duration',
        1e6, // 4e6 - 3e6
        TEST_INSTANCE_WITH_DATA,
        {
          scaling_method: 'DIRECT',
          scaling_direction: 'SCALE_UP',
        }
      );
    });
  });

  describe('reportUnknownOperationAsSuccessful', () => {
    it('increases successful counter', () => {
      scalingOperationReporter.reportUnknownOperationAsSuccessful(
        TEST_STATE_DATA,
        TEST_INSTANCE_WITH_DATA
      );

      expect(counterManager.incrementCounter).toHaveBeenCalledOnceWith(
        'scaler/scaling-success',
        TEST_INSTANCE_WITH_DATA,
        {
          scaling_method: 'DIRECT',
          scaling_direction: 'SCALE_UP',
        }
      );
    });

    it('records a value for duration counter', () => {
      scalingOperationReporter.reportUnknownOperationAsSuccessful(
        TEST_STATE_DATA,
        TEST_INSTANCE_WITH_DATA
      );

      expect(counterManager.recordValue).toHaveBeenCalledOnceWith(
        'scaler/scaling-duration',
        1e6, // 4e6 - 3e6
        TEST_INSTANCE_WITH_DATA,
        {
          scaling_method: 'DIRECT',
          scaling_direction: 'SCALE_UP',
        }
      );
    });
  });
});
