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

/** @fileoverview Tests state-spanner. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import {Table as SpannerTable} from '@google-cloud/spanner';
import {ScalableInstanceWithData} from '../../../common/instance-info';
import {SpannerStateData, SpannerStateStore} from '../state-spanner';
import {silentLogger} from '../../../testing/testing-framework';
import {TEST_INSTANCE_WITH_DATA} from '../../../testing/testing-data';

/** Sample instance with Spanner stateConfig for testing. */
const SAMPLE_INSTANCE: ScalableInstanceWithData = Object.freeze({
  ...TEST_INSTANCE_WITH_DATA,
  stateConfig: Object.freeze({
    stateProjectId: 'project-2',
    stateDatabase: Object.freeze({
      name: 'spanner',
      instanceId: 'state-instance',
      databaseId: 'state-database',
    }),
  }),
});

describe('SpannerStateStore', () => {
  let spannerTableSpy: SpannerTable;
  let spannerStateStore: SpannerStateStore;

  beforeEach(() => {
    jasmine
      .clock()
      .install()
      .mockDate(new Date(Math.pow(10, 7)));

    spannerTableSpy = jasmine.createSpyObj('SpannerTable', ['read', 'upsert']);
    spannerStateStore = new SpannerStateStore(
      SAMPLE_INSTANCE,
      spannerTableSpy,
      silentLogger
    );
  });

  afterEach(() => {
    jasmine.clock().uninstall();
  });

  describe('init', () => {
    const defaultSpannerState: SpannerStateData = {
      createdOn: '1970-01-01T02:46:40.000Z', // new Date(1e7), // '1970-01-01T02:46:40.000Z', // 1e7
      updatedOn: '1970-01-01T02:46:40.000Z', // new Date(1e7), // '1970-01-01T02:46:40.000Z', // 1e7
      lastScalingTimestamp: '1970-01-01T00:00:00.000Z', // new Date(0), // '1970-01-01T00:00:00.000Z', // 0
      lastScalingCompleteTimestamp: '1970-01-01T00:00:00.000Z', // new Date(0), // '1970-01-01T00:00:00.000Z', // 0
      scalingOperationId: null,
      scalingRequestedSize: null,
      scalingPreviousSize: null,
      scalingMethod: null,
    };

    it('returns default data', async () => {
      const output = await spannerStateStore.init();

      expect(output).toEqual(defaultSpannerState);
    });

    it('writes default data to the table', async () => {
      await spannerStateStore.init();

      expect(spannerTableSpy.upsert as jasmine.Spy).toHaveBeenCalledOnceWith({
        id: 'projects/project-123/locations/us-central1',
        ...defaultSpannerState,
      });
    });
  });

  describe('getState', () => {
    it('queries expected row', async () => {
      const readSpy = spannerTableSpy.read as jasmine.Spy;
      readSpy.and.returnValue([[]]);

      await spannerStateStore.getState();

      expect(readSpy).toHaveBeenCalledOnceWith({
        columns: [
          // See STATE_KEY_DEFINITIONS.
          'lastScalingTimestamp',
          'createdOn',
          'updatedOn',
          'lastScalingCompleteTimestamp',
          'scalingOperationId',
          'scalingRequestedSize',
          'scalingPreviousSize',
          'scalingMethod',
        ],
        keySet: {
          keys: [
            {
              values: [
                {
                  stringValue: 'projects/project-123/locations/us-central1',
                },
              ],
            },
          ],
        },
      });
    });

    it('returns state data, if row data exists', async () => {
      const rowSpy = jasmine.createSpyObj('Row', ['toJSON']);
      const readSpy = spannerTableSpy.read as jasmine.Spy;
      readSpy.and.returnValue([[rowSpy]]);
      const rowToJsonSpy = rowSpy.toJSON as jasmine.Spy;
      rowToJsonSpy.and.returnValue({
        createdOn: new Date(1e8),
        updatedOn: new Date(1e9),
        lastScalingTimestamp: new Date(3e9),
        lastScalingCompleteTimestamp: new Date(4e9),
        scalingOperationId: '123',
        scalingRequestedSize: 2,
        scalingPreviousSize: 9,
        scalingMethod: 'DIRECT',
      });

      const output = await spannerStateStore.getState();

      expect(output).toEqual({
        createdOn: 1e8,
        updatedOn: 1e9,
        lastScalingTimestamp: 3e9,
        lastScalingCompleteTimestamp: 4e9,
        scalingOperationId: '123',
        scalingRequestedSize: 2,
        scalingPreviousSize: 9,
        scalingMethod: 'DIRECT',
      });
    });

    it('gets default data, if row data does not exist', async () => {
      const readSpy = spannerTableSpy.read as jasmine.Spy;
      readSpy.and.returnValue([[]]);

      const output = await spannerStateStore.getState();

      expect(output).toEqual({
        createdOn: 1e7,
        updatedOn: 1e7,
        lastScalingTimestamp: 0,
        lastScalingCompleteTimestamp: 0,
        scalingOperationId: null,
        scalingRequestedSize: null,
        scalingPreviousSize: null,
        scalingMethod: null,
      });
    });
  });

  describe('updateState', () => {
    it('writes the state data to the Spanner table', async () => {
      await spannerStateStore.updateState({
        lastScalingTimestamp: 999_999,
        lastScalingCompleteTimestamp: 1_000_000,
        scalingOperationId: 'xyz',
        scalingPreviousSize: 3,
        scalingRequestedSize: 5,
        scalingMethod: 'DIRECT',
        // This will be deleted. Normally, this parameter will not be present on
        // the real call, but this helps to test this behaviour.
        createdOn: 123,
      });

      expect(spannerTableSpy.upsert as jasmine.Spy).toHaveBeenCalledOnceWith({
        id: 'projects/project-123/locations/us-central1',
        updatedOn: '1970-01-01T02:46:40.000Z', // 1e7
        lastScalingTimestamp: '1970-01-01T00:16:39.999Z', // 999_999
        lastScalingCompleteTimestamp: '1970-01-01T00:16:40.000Z', // 1_000_000
        scalingOperationId: 'xyz',
        scalingPreviousSize: 3,
        scalingRequestedSize: 5,
        scalingMethod: 'DIRECT',
      });
    });
  });
});
