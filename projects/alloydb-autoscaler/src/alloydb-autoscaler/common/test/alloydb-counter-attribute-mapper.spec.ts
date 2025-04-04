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

/** @fileoverview Tests for alloydb-counter-attribute-mapper. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import {AlloyDbCounterAttributeMapper} from '../alloydb-counter-attribute-mapper';
import {TEST_ALLOYDB_INSTANCE} from '../../testing/testing-data';

describe('AlloyDbCounterAttributeMapper', () => {
  describe('getCounterAttributes', () => {
    [
      {
        testCaseName: 'instance only',
        inputInstance: TEST_ALLOYDB_INSTANCE,
        inputAttributes: undefined,
        expectedOutput: {
          alloydb_project_id: 'project-123',
          alloydb_cluster_id: 'alloydb-cluster',
          alloydb_instance_id: 'alloydb-instance',
        },
      },
      {
        testCaseName: 'instance and additional attributes',
        inputInstance: TEST_ALLOYDB_INSTANCE,
        inputAttributes: {
          param1: 'value1',
          param2: 123,
        },
        expectedOutput: {
          alloydb_project_id: 'project-123',
          alloydb_cluster_id: 'alloydb-cluster',
          alloydb_instance_id: 'alloydb-instance',
          param1: 'value1',
          param2: 123,
        },
      },
      {
        testCaseName: 'no instance, with additional attributes',
        inputInstance: undefined,
        inputAttributes: {
          param1: 'value1',
          param2: 123,
        },
        expectedOutput: {
          param1: 'value1',
          param2: 123,
        },
      },
      {
        testCaseName: 'no instance, no additional attributes',
        inputInstance: undefined,
        inputAttributes: undefined,
        expectedOutput: {},
      },
    ].forEach(
      ({testCaseName, inputInstance, inputAttributes, expectedOutput}) => {
        it(`gets expected attributes: ${testCaseName}`, () => {
          const counterAttributeMapper = new AlloyDbCounterAttributeMapper();

          const output = counterAttributeMapper.getCounterAttributes(
            inputInstance,
            inputAttributes
          );

          expect(output).toEqual(expectedOutput);
        });
      }
    );
  });
});
