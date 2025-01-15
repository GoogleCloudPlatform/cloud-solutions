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

/** @fileoverview Tests alloydb-metadata-reader. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import {AlloyDBAdminClient} from '@google-cloud/alloydb';
import {
  AlloyDbMetadataReader,
  AlloyDbMetadataReaderFactory,
} from '../alloydb-metadata-reader';
import {silentLogger} from '../../../autoscaler-core/testing/testing-framework';
import {TEST_ALLOYDB_INSTANCE} from '../../testing/testing-data';

describe('AlloyDbMetadataReaderFactory', () => {
  describe('buildMetadataReader', () => {
    it('builds expected client', () => {
      const metadataReaderFactory = new AlloyDbMetadataReaderFactory(
        new AlloyDBAdminClient(),
        silentLogger
      );

      const output = metadataReaderFactory.buildMetadataReader(
        TEST_ALLOYDB_INSTANCE
      );

      expect(output).toBeInstanceOf(AlloyDbMetadataReader);
    });
  });

  describe('AlloyDbMetadataReader', () => {
    let alloyDbClient: jasmine.SpyObj<AlloyDBAdminClient>;
    let metadataReader: AlloyDbMetadataReader;

    beforeEach(() => {
      alloyDbClient = jasmine.createSpyObj<AlloyDBAdminClient>(
        'AlloyDBAdminClient',
        ['getInstance']
      );
      metadataReader = new AlloyDbMetadataReader(
        TEST_ALLOYDB_INSTANCE,
        alloyDbClient,
        silentLogger
      );
    });

    it('fetches expected instance', () => {
      (alloyDbClient.getInstance as jasmine.Spy).and.returnValue([
        {
          instanceType: 'READ_POOL',
          readPoolConfig: {nodeCount: 5},
          machineConfig: {cpuCount: 8},
        },
        undefined,
      ]);

      metadataReader.getMetadata();

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      expect(alloyDbClient.getInstance as any).toHaveBeenCalledOnceWith({
        name: 'projects/project-123/clusters/alloydb-cluster/instances/alloydb-instance',
      });
    });

    it('returns expected metadata', async () => {
      (alloyDbClient.getInstance as jasmine.Spy).and.returnValue([
        {
          instanceType: 'READ_POOL',
          readPoolConfig: {nodeCount: 5},
          machineConfig: {cpuCount: 8},
        },
        undefined,
      ]);

      const output = await metadataReader.getMetadata();

      expect(output).toEqual({
        currentSize: 5,
        nodeCount: 5,
        cpuCount: 8,
        instanceType: 'READ_POOL',
      });
    });

    [
      {
        testCaseName: 'no instance',
        outputInstance: undefined,
        expectedErrorMessage:
          'Unable to read metadata from AlloyDB instance ' +
          'projects/project-123/clusters/alloydb-cluster/instances/alloydb-instance',
      },
      {
        testCaseName: 'invalid instanceType',
        outputInstance: {
          instanceType: 'PRIMARY',
          readPoolConfig: {nodeCount: 5},
          machineConfig: {cpuCount: 8},
        },
        expectedErrorMessage:
          'Only AlloyDB read pool instances are currently supported. ' +
          'Instance ' +
          'projects/project-123/clusters/alloydb-cluster/instances/alloydb-instance' +
          ' is of type PRIMARY',
      },
      {
        testCaseName: 'no nodeCount',
        outputInstance: {
          instanceType: 'READ_POOL',
          machineConfig: {cpuCount: 8},
        },
        expectedErrorMessage:
          'Unable to read current node count for AlloyDB instance ' +
          'projects/project-123/clusters/alloydb-cluster/instances/alloydb-instance',
      },
    ].forEach(({testCaseName, outputInstance, expectedErrorMessage}) => {
      it(`throws when ${testCaseName}`, async () => {
        (alloyDbClient.getInstance as jasmine.Spy).and.returnValue([
          outputInstance,
          undefined,
        ]);

        await expectAsync(metadataReader.getMetadata()).toBeRejectedWithError(
          expectedErrorMessage
        );
      });
    });
  });
});
