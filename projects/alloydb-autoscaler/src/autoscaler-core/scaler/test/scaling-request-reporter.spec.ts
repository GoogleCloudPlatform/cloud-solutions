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

/** @fileoverview Tests scaling-request-reporter. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import pino from 'pino';
import {createLoggerWithMocks} from '../../testing/testing-framework';
import {CounterManager} from '../../common/counters';
import {ScalingRequestReporter} from '../scaling-request-reporter';
import {
  TEST_INSTANCE_WITH_DATA,
  TEST_STATE_DATA,
} from '../../testing/testing-data';

describe('ScalingRequestReporter', () => {
  let scalingRequestReporter: ScalingRequestReporter;
  let loggerMock: jasmine.SpyObj<pino.Logger>;
  let counterManagerMock: jasmine.SpyObj<CounterManager>;

  beforeEach(() => {
    // Required for time calculations (e.g. x days ago).
    jasmine.clock().install().mockDate(new Date(1e7));

    loggerMock = createLoggerWithMocks();
    counterManagerMock = jasmine.createSpyObj('CounterManager', [
      'incrementCounter',
      'recordValue',
    ]);

    scalingRequestReporter = new ScalingRequestReporter(
      loggerMock,
      counterManagerMock,
      TEST_INSTANCE_WITH_DATA,
      TEST_STATE_DATA,
      /** suggestedSize= */ 3
    );
  });

  afterEach(() => {
    jasmine.clock().uninstall();
  });

  describe('reportScalingOperationInProgress', () => {
    it('logs expected message', async () => {
      await scalingRequestReporter.reportScalingOperationInProgress();

      expect(loggerMock.info).toHaveBeenCalledOnceWith(
        jasmine.objectContaining({
          message:
            '----- projects/project-123/locations/us-central1: has size 7, ' +
            'no scaling possible - last scaling operation (DIRECT to 5) is ' +
            'still in progress. Started: 1.9 Hrs ago).',
        })
      );
    });

    it('increases expected counters', async () => {
      await scalingRequestReporter.reportScalingOperationInProgress();

      expect(counterManagerMock.incrementCounter).toHaveBeenCalledOnceWith(
        'scaler/scaling-denied',
        TEST_INSTANCE_WITH_DATA,
        {
          scaling_denied_reason: 'IN_PROGRESS',
          scaling_method: 'DIRECT',
          scaling_direction: 'SCALE_DOWN',
        }
      );
    });
  });

  describe('reportWithinCooldownPeriod', () => {
    it('logs expected message', async () => {
      await scalingRequestReporter.reportWithinCooldownPeriod();

      expect(loggerMock.info).toHaveBeenCalledOnceWith(
        jasmine.objectContaining({
          message:
            '----- projects/project-123/locations/us-central1: has size 7, ' +
            'no scaling possible - within cooldown period',
        })
      );
    });

    it('increases expected counters', async () => {
      await scalingRequestReporter.reportWithinCooldownPeriod();

      expect(counterManagerMock.incrementCounter).toHaveBeenCalledOnceWith(
        'scaler/scaling-denied',
        TEST_INSTANCE_WITH_DATA,
        {
          scaling_denied_reason: 'WITHIN_COOLDOWN',
          scaling_method: 'DIRECT',
          scaling_direction: 'SCALE_DOWN',
        }
      );
    });
  });

  describe('reportInstanceAtMaxSize', () => {
    it('logs expected message', async () => {
      await scalingRequestReporter.reportInstanceAtMaxSize();

      // Note: while 7 does not equal 10, the reporter does not make any
      // judgements of size. It simply reports the status when requested.
      // This difference would have been caught before calling this method.
      // The test can be fixed by making currentSize = maxSize. However, for
      // simplicity in these tests, the sample test instance is not modified.
      expect(loggerMock.info).toHaveBeenCalledOnceWith(
        jasmine.objectContaining({
          message:
            '----- projects/project-123/locations/us-central1: has size 7, ' +
            'no scaling possible - at maxSize (10)',
        })
      );
    });

    it('increases expected counters', async () => {
      await scalingRequestReporter.reportInstanceAtMaxSize();

      expect(counterManagerMock.incrementCounter).toHaveBeenCalledOnceWith(
        'scaler/scaling-denied',
        TEST_INSTANCE_WITH_DATA,
        {
          scaling_denied_reason: 'MAX_SIZE',
          scaling_method: 'DIRECT',
          scaling_direction: 'SCALE_DOWN',
        }
      );
    });
  });

  describe('reportInstanceAtSuggestedSize', () => {
    it('logs expected message', async () => {
      await scalingRequestReporter.reportInstanceAtSuggestedSize();

      expect(loggerMock.info).toHaveBeenCalledOnceWith(
        jasmine.objectContaining({
          message:
            '----- projects/project-123/locations/us-central1: has size 7, ' +
            'no scaling needed at the moment',
        })
      );
    });

    it('increases expected counters', async () => {
      await scalingRequestReporter.reportInstanceAtSuggestedSize();

      expect(counterManagerMock.incrementCounter).toHaveBeenCalledOnceWith(
        'scaler/scaling-denied',
        TEST_INSTANCE_WITH_DATA,
        {
          scaling_denied_reason: 'CURRENT_SIZE',
          scaling_method: 'DIRECT',
          scaling_direction: 'SCALE_DOWN',
        }
      );
    });
  });

  describe('reportFailedScalingOperation', () => {
    it('logs expected message', async () => {
      await scalingRequestReporter.reportFailedScalingOperation('Error reason');

      expect(loggerMock.error).toHaveBeenCalledOnceWith(
        jasmine.objectContaining({
          message:
            '----- projects/project-123/locations/us-central1: ' +
            'Unsuccessful scaling attempt: Error reason',
        })
      );
    });

    it('increases expected counters', async () => {
      await scalingRequestReporter.reportFailedScalingOperation('Error reason');

      expect(counterManagerMock.incrementCounter).toHaveBeenCalledOnceWith(
        'scaler/scaling-failed',
        TEST_INSTANCE_WITH_DATA,
        {
          scaling_failed_reason: 'Error reason',
          scaling_method: 'DIRECT',
          scaling_direction: 'SCALE_DOWN',
        }
      );
    });
  });
});
