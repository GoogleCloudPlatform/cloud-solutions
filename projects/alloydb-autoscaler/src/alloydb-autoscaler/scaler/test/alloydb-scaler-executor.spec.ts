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

/** @fileoverview Tests alloydb-scaler-executor. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import {AlloyDBAdminClient} from '@google-cloud/alloydb';
import {AlloyDbScalerExecutor} from '../alloydb-scaler-executor';
import {silentLogger} from '../../../autoscaler-core/testing/testing-framework';
import {TEST_ALLOYDB_INSTANCE_WITH_DATA} from '../../testing/testing-data';

describe('AlloyDbScalerExecutor', () => {
  let alloyDbClient: jasmine.SpyObj<AlloyDBAdminClient>;
  let scalerExecutor: AlloyDbScalerExecutor;

  beforeEach(() => {
    alloyDbClient = jasmine.createSpyObj<AlloyDBAdminClient>(
      'AlloyDBAdminClient',
      ['updateInstance']
    );
    scalerExecutor = new AlloyDbScalerExecutor(silentLogger, alloyDbClient);
  });

  describe('scaleInstance', () => {
    it('executes scaling request', async () => {
      const instance = {
        ...TEST_ALLOYDB_INSTANCE_WITH_DATA,
        metadata: {
          ...TEST_ALLOYDB_INSTANCE_WITH_DATA.metadata,
          instanceType: 'READ_POOL',
        },
      };
      (alloyDbClient.updateInstance as jasmine.Spy).and.callFake(async () => {
        return [{name: 'operation-id'}];
      });

      await scalerExecutor.scaleInstance(instance, 7);

      expect(
        alloyDbClient.updateInstance as jasmine.Spy
      ).toHaveBeenCalledOnceWith(
        jasmine.objectContaining({
          instance: {
            name:
              'projects/project-123/clusters/alloydb-cluster/' +
              'instances/alloydb-instance',
            readPoolConfig: {nodeCount: 7},
          },
          updateMask: {paths: ['read_pool_config.node_count']},
        })
      );
    });

    it('returns operation name if available', async () => {
      const instance = {
        ...TEST_ALLOYDB_INSTANCE_WITH_DATA,
        metadata: {
          ...TEST_ALLOYDB_INSTANCE_WITH_DATA.metadata,
          instanceType: 'READ_POOL',
        },
      };
      (alloyDbClient.updateInstance as jasmine.Spy).and.callFake(async () => {
        return [{name: 'operation-id'}];
      });

      const output = await scalerExecutor.scaleInstance(instance, 7);

      expect(output).toEqual('operation-id');
    });

    it('returns null if operation has no name', async () => {
      const instance = {
        ...TEST_ALLOYDB_INSTANCE_WITH_DATA,
        metadata: {
          ...TEST_ALLOYDB_INSTANCE_WITH_DATA.metadata,
          instanceType: 'READ_POOL',
        },
      };
      (alloyDbClient.updateInstance as jasmine.Spy).and.callFake(async () => {
        return [{}]; // Operation without a name.
      });

      const output = await scalerExecutor.scaleInstance(instance, 7);

      expect(output).toBeNull();
    });

    [
      ['no resposne (undefined)', undefined],
      ['no operations (empty array)', []],
    ].forEach(([testCaseName, operationResult]) => {
      it(`throws if bad operation result: ${testCaseName}`, async () => {
        const instance = {
          ...TEST_ALLOYDB_INSTANCE_WITH_DATA,
          metadata: {
            ...TEST_ALLOYDB_INSTANCE_WITH_DATA.metadata,
            instanceType: 'READ_POOL',
          },
        };
        (alloyDbClient.updateInstance as jasmine.Spy).and.callFake(async () => {
          return operationResult;
        });

        await expectAsync(
          scalerExecutor.scaleInstance(instance, 7)
        ).toBeRejectedWithError(
          'Executing scaling operation to 7 for ' +
            'projects/project-123/clusters/alloydb-cluster/' +
            'instances/alloydb-instance failed for unknown reasons'
        );
      });
    });

    it('throws if instance has no resource path', async () => {
      const instance = {
        ...TEST_ALLOYDB_INSTANCE_WITH_DATA,
        info: {
          ...TEST_ALLOYDB_INSTANCE_WITH_DATA.info,
          resourcePath: '',
        },
        metadata: {
          ...TEST_ALLOYDB_INSTANCE_WITH_DATA.metadata,
          instanceType: 'READ_POOL',
        },
      };

      await expectAsync(
        scalerExecutor.scaleInstance(instance, 7)
      ).toBeRejectedWithError(
        'No resource path specified for instance. Unable to scale'
      );
    });

    it('throws if instance is not a read pool', async () => {
      const instance = {
        ...TEST_ALLOYDB_INSTANCE_WITH_DATA,
        metadata: {
          ...TEST_ALLOYDB_INSTANCE_WITH_DATA.metadata,
          instanceType: 'PRIMARY',
        },
      };

      await expectAsync(
        scalerExecutor.scaleInstance(instance, 7)
      ).toBeRejectedWithError(
        'Only AlloyDB read pool instances are currently supported. ' +
          'Instance projects/project-123/clusters/alloydb-cluster/' +
          'instances/alloydb-instance is of type PRIMARY'
      );
    });
  });
});
