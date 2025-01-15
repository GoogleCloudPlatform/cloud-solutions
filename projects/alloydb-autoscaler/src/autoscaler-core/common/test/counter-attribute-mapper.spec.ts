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

/** @fileoverview Tests for counter-attribute-mapper. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import {CounterAttributeMapper} from '../counter-attribute-mapper';
import {TEST_INSTANCE} from '../../testing/testing-data';

describe('CounterAttributeMapper', () => {
  describe('getCounterAttributes', () => {
    [
      {
        testCaseName: 'instance only',
        inputInstance: TEST_INSTANCE,
        inputAttributes: undefined,
        expectedOutput: {project_id: 'project-123'},
      },
      {
        testCaseName: 'instance and additional attributes',
        inputInstance: TEST_INSTANCE,
        inputAttributes: {
          param1: 'value1',
          param2: 123,
        },
        expectedOutput: {
          project_id: 'project-123',
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
          const counterAttributeMapper = new CounterAttributeMapper();

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
