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

/** @file Provides a util to interact with PubSub. */

import {PubSub} from '@google-cloud/pubsub';
import protobuf from 'protobufjs';
import pino from 'pino';

/** Provider to post messages to PubSub topics. */
export class PubSubMessenger {
  /** Initializes PubSubMessenger. */
  constructor(
    private logger: pino.Logger,
    private pubSub: PubSub = new PubSub()
  ) {}

  /**
   * Posts a message to PubSub.
   * @param pubSubTopic Topic to which to publish message.
   * @param payload Message payload to publish.
   * @param extraLogInfo Additional information to log on the messages.
   */
  async postPubSubMessage(
    pubSubTopic: string,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    payload: string | Record<string, any>
  ) {
    try {
      if (typeof payload !== 'string') {
        payload = JSON.stringify(payload);
      }
      const payloadBuffer = Buffer.from(payload, 'utf-8');
      const topic = this.pubSub.topic(pubSubTopic);
      await topic.publishMessage({data: payloadBuffer});
      this.logger.info({
        message: `----- Published message to topic: ${pubSubTopic}`,
        payload: payload,
      });
    } catch (e) {
      this.logger.error({
        message:
          'An error occurred when publishing the message to ' +
          `${pubSubTopic}: ${e}`,
        err: payload,
      });
    }
  }

  /**
   * Posts a proto message to PubSub.
   * @param pubSubTopic Topic to which to publish message.
   * @param message Protobuf message to publish.
   */
  async postPubSubProtoMessage(
    pubSubTopic: string,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    message: protobuf.Message
  ) {
    const payload = JSON.stringify(message.toJSON());
    return this.postPubSubMessage(pubSubTopic, payload);
  }
}
