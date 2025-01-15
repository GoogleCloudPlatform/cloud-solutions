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

/** @file Tests for protobuf helper. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import {ProtobufEncoder} from '../protobuf';
import protobuf from 'protobufjs';

describe('ProtobufEncoder', () => {
  describe('encodeDataAsProtobufMessage', () => {
    let protoSchema: protobuf.Root;
    let TestMessage: protobuf.Type;
    let protobufEncoder: ProtobufEncoder;

    beforeAll(async () => {
      protoSchema = await protobuf.load(
        './src/autoscaler-core/common/test/test.proto'
      );
      TestMessage = protoSchema.lookupType('TestMessage');
      protobufEncoder = new ProtobufEncoder(
        './src/autoscaler-core/common/test/test.proto',
        'TestMessage'
      );
    });

    [
      {
        testCaseName: 'with a full proto',
        jsonData: {
          projectId: 'project-123',
          regionId: 'us-central1',
          size: 5,
          metrics: [
            {name: 'metric1', value: 5},
            {name: 'metric2', value: 99},
          ],
        },
      },
      {
        testCaseName: 'with a partial proto',
        jsonData: {projectId: 'project-123'},
      },
    ].forEach(({testCaseName, jsonData}) => {
      it(`encodes JSON data as protobuf ${testCaseName}`, async () => {
        const output =
          await protobufEncoder.encodeDataAsProtobufMessage(jsonData);

        expect(TestMessage.verify(output)).toBeNull(); // Returns null if valid.
        expect(output.toJSON()).toEqual(jsonData);
      });
    });

    it('ignores additional parameters', async () => {
      const output = await protobufEncoder.encodeDataAsProtobufMessage({
        projectId: 'project-123',
        extraParams: 'value',
      });

      expect(TestMessage.verify(output)).toBeNull(); // Returns null if valid.
      expect(output.toJSON()).toEqual({projectId: 'project-123'});
    });
  });
});
