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

/** @fileoverview Provides the entrypoint for the Autoscaler Forwarder. */

import {pino} from 'pino';
import {PubSubMessenger} from '../common/pubsub-messenger';
import {
  BaseEntrypointBuilder,
  EntrypointBuilder,
  EntrypointHandler,
  EnvironmentVariables,
  HttpHandler,
  PubSubHandler,
} from '../common/entrypoint-builder';

/** Creates the entrypoint functions for the Forwader. */
export class ForwarderFunctionBuilder
  extends BaseEntrypointBuilder
  implements EntrypointBuilder
{
  constructor(protected logger: pino.Logger) {
    super();
  }

  /** Builds the entrypoint for the Forwarder function. */
  buildRequestHandler(): EntrypointHandler {
    /**
     * Handles the request to the Forwarder function.
     * @param payload Body payload in string format.
     */
    return async (payload: string) => {
      try {
        // Log exception in App project if payload cannot be parsed.
        JSON.parse(payload);

        if (!process?.env?.POLLER_TOPIC) {
          throw new Error(
            'Poller topic must be defined. ' +
              'Please define POLLER_TOPIC environment variable.'
          );
        }

        const pollerTopicName = process.env.POLLER_TOPIC;
        const pubSubMessenger = new PubSubMessenger(this.logger);
        await pubSubMessenger.postPubSubMessage(pollerTopicName, payload);

        this.logger.debug({
          message: `Poll request forwarded to PubSub Topic ${pollerTopicName}`,
        });
      } catch (e) {
        this.logger.error({
          message: `An error occurred in the Autoscaler forwarder: ${e}`,
          err: e,
          payload: payload,
        });
      }
    };
  }

  /**
   * Builds the entrypoint for the Forwarder function for HTTP.
   * @param payload Fixed payload to use for testing.
   * @returns HTTP Entrypoint for the Forwarder function.
   */
  buildRequestHandlerForHttpRequests(
    payload: string,
    env?: EnvironmentVariables
  ): HttpHandler {
    /**
     * Handles the request to the Forwader function from HTTP, local tests.
     * @param _ HTTP Request.
     * @param res HTTP response object.
     */
    return async (_, res) => {
      try {
        this.setEnvironmentVariables(env);
        const requestHandler = this.buildRequestHandler();
        await requestHandler(payload);
        res.status(200).end();
      } catch (e) {
        this.logger.error({
          message: `An error occurred in the Autoscaler forwarder (HTTP): ${e}`,
          err: e,
          payload: payload,
        });
        res.status(500).end('An exception occurred');
      }
    };
  }

  /** Builds the entrypoint for the Forwarder function for PubSub. */
  buildRequestHandlerForPubSub(): PubSubHandler {
    /**
     * Handles the request to the Forwarder function from PubSub.
     * @param pubSubEvent PubSub event data.
     * @param _ Context from the PubSub. Unused.
     */
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    return async (pubSubEvent, _) => {
      try {
        const payload = Buffer.from(pubSubEvent.data, 'base64').toString();
        if (!payload) throw new Error('Payload is empty.');
        const requestHandler = this.buildRequestHandler();
        await requestHandler(payload);
      } catch (e) {
        this.logger.error({
          message:
            'An error occurred in the Autoscaler ' + `forwarder (PubSub): ${e}`,
          err: e,
          payload: pubSubEvent.data,
        });
      }
    };
  }
}
