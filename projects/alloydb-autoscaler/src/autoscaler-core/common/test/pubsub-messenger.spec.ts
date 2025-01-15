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

/** @fileoverview Tests for PubSubMessenger. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import {PubSubMessenger} from '../pubsub-messenger';
import {PubSub, Topic} from '@google-cloud/pubsub';
import {ProtobufEncoder} from '../protobuf';
import {silentLogger} from '../../testing/testing-framework';

describe('PubSubMessenger', () => {
  let pubSubWithMocks: PubSub;
  let pubSubTopicWithMocks: Topic;
  let topicSpy: jasmine.Spy;
  let publishMessageSpy: jasmine.Spy;

  beforeEach(() => {
    pubSubWithMocks = new PubSub();
    pubSubTopicWithMocks = new Topic(pubSubWithMocks, 'testPubSub');

    topicSpy = spyOn(pubSubWithMocks, 'topic').and.returnValue(
      pubSubTopicWithMocks
    );
    publishMessageSpy = spyOn(pubSubTopicWithMocks, 'publishMessage');
  });

  describe('postPubSubMessage', () => {
    [
      {
        testCaseName: 'a string message',
        topic: 'new-topic-string',
        message: 'message-value',
        expectedMessage: 'message-value',
      },
      {
        testCaseName: 'an object message',
        topic: 'new-topic-object',
        message: {dataX: 'value'},
        expectedMessage: '{"dataX":"value"}',
      },
    ].forEach(({testCaseName, topic, message, expectedMessage}) => {
      it(`posts ${testCaseName} to the topic`, async () => {
        const pubSubMessenger = new PubSubMessenger(
          silentLogger,
          pubSubWithMocks
        );

        await pubSubMessenger.postPubSubMessage(topic, message);

        expect(topicSpy).toHaveBeenCalledOnceWith(topic);
        expect(publishMessageSpy).toHaveBeenCalledOnceWith({
          data: Buffer.from(expectedMessage, 'utf-8'),
        });
      });
    });
  });

  describe('postPubSubProtoMessage', () => {
    it('posts protobuf message to the topic', async () => {
      const protobufEncoder = new ProtobufEncoder(
        './src/autoscaler-core/common/test/test.proto',
        'TestMessage'
      );
      const protobufData = await protobufEncoder.encodeDataAsProtobufMessage({
        projectId: 'p123',
        metrics: [{name: 'm1', value: 14}],
      });
      const pubSubMessenger = new PubSubMessenger(
        silentLogger,
        pubSubWithMocks
      );

      await pubSubMessenger.postPubSubMessage('proto-topic', protobufData);

      expect(topicSpy).toHaveBeenCalledOnceWith('proto-topic');
      expect(publishMessageSpy).toHaveBeenCalledOnceWith({
        data: Buffer.from(
          '{"projectId":"p123","metrics":[{"name":"m1","value":14}]}',
          'utf-8'
        ),
      });
    });
  });
});
