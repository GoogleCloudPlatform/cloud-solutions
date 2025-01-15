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

/** @fileoverview Provides the entrypoint for the Autoscaler Poller. */

import {pino} from 'pino';
import {createLogger} from '../common/logger';
import {ConfigParser} from './config-parser';
import {MetricsReaderFactory} from './metrics-reader';
import {CounterManager} from '../common/counters';
import {POLLER_COUNTER_DEFINITION_MAP} from './poller-counters';
import {
  ScalableInstance,
  ScalableInstanceWithData,
} from '../common/instance-info';
import {PubSubMessenger} from '../common/pubsub-messenger';
import {
  BaseEntrypointBuilder,
  EntrypointBuilder,
  EnvironmentVariables,
  HttpHandler,
  PubSubHandler,
} from '../common/entrypoint-builder';
import {MetadataReaderFactory} from './metadata-reader';

/** Entrypoint for the Poller for the GKE (local) use case. */
export type LocalPollerHandler = (
  payload: string
) => Promise<ScalableInstanceWithData[]>;

/** Creates the entrypoint functions for the Poller. */
export class PollerFunctionBuilder
  extends BaseEntrypointBuilder
  implements EntrypointBuilder
{
  /**
   * Initializes the Poller function builder.
   * @param logger Default logger to use until instances are available.
   * @param configParser ConfigParser to use to parse the request.
   * @param metricsReaderFactory MetricsReaderFactory to use to build the read
   *  which will poll the information.
   * @param counterManager CounterManager to use for counting polling data.
   *    Counter must have created and initialized the Poller counters.
   */
  constructor(
    protected logger: pino.Logger = createLogger(),
    protected configParser: ConfigParser,
    protected metricsReaderFactory: MetricsReaderFactory,
    protected metadataReaderFactory: MetadataReaderFactory,
    protected counterManager: CounterManager
  ) {
    super();
  }

  /** Builds the entrypoint for the Poller function. */
  buildRequestHandler(): LocalPollerHandler {
    /**
     * Handles the request to the Poller function.
     * @param payload Body payload in string format.
     */
    return async (payload: string): Promise<ScalableInstanceWithData[]> => {
      let instances: ScalableInstanceWithData[] = [];
      try {
        instances = await this.pollDataForPayload(payload);
        this.counterManager.incrementCounter(
          POLLER_COUNTER_DEFINITION_MAP.REQUESTS_SUCCESS.counterName
        );
      } catch (e) {
        this.logger.error({
          message: `An error occurred in the Autoscaler poller function: ${e}`,
          err: e,
          payload: payload,
        });
        this.counterManager.incrementCounter(
          POLLER_COUNTER_DEFINITION_MAP.REQUESTS_FAILED.counterName
        );
      } finally {
        await this.counterManager.flush();
      }
      return instances;
    };
  }

  /** Builds the entrypoint for the Poller function for PubSub. */
  buildRequestHandlerForPubSub(): PubSubHandler {
    /**
     * Handles the request to the Poller function from PubSub.
     * @param pubSubEvent PubSub event data.
     * @param _ Context from the PubSub. Unused.
     */
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    return async (pubSubEvent, _) => {
      try {
        const payload = Buffer.from(pubSubEvent.data, 'base64').toString();
        if (!payload) throw new Error('Payload is empty.');
        const instances = await this.pollDataForPayload(payload);
        await this.sendInstanceData(instances);
        this.counterManager.incrementCounter(
          POLLER_COUNTER_DEFINITION_MAP.REQUESTS_SUCCESS.counterName
        );
      } catch (e) {
        this.logger.error({
          message: `An error occurred in the Autoscaler poller function: ${e}`,
          err: e,
          payload: pubSubEvent.data,
        });
        this.counterManager.incrementCounter(
          POLLER_COUNTER_DEFINITION_MAP.REQUESTS_FAILED.counterName
        );
      } finally {
        await this.counterManager.flush();
      }
    };
  }

  /**
   * Builds the entrypoint for the Poller function for HTTP.
   * @param payload Fixed payload to use for testing.
   * @param env Fixed set of environment variables to set.
   * @returns HTTP Entrypoint for the Poller function.
   */
  buildRequestHandlerForHttpRequests(
    payload: string,
    env?: EnvironmentVariables
  ): HttpHandler {
    /**
     * Handles the request to the Poller function from HTTP, local tests.
     * @param _ HTTP Request.
     * @param res HTTP response object.
     */
    return async (_, res) => {
      try {
        this.setEnvironmentVariables(env);
        const instances = await this.pollDataForPayload(payload);
        await this.sendInstanceData(instances);
        this.counterManager.incrementCounter(
          POLLER_COUNTER_DEFINITION_MAP.REQUESTS_SUCCESS.counterName
        );
        res.status(200).end();
      } catch (e) {
        this.logger.error({
          err: e,
          payload: payload,
          message:
            'An error occurred in the Autoscaler poller function ' +
            `(HTTP): ${e}`,
        });
        this.counterManager.incrementCounter(
          POLLER_COUNTER_DEFINITION_MAP.REQUESTS_FAILED.counterName
        );
        res.status(500).contentType('text/plain').end('An exception occurred');
      } finally {
        await this.counterManager.flush();
      }
    };
  }

  /**
   * Polls data for payload (instances).
   * @return Instance(s) data with configuration and metrics.
   */
  private async pollDataForPayload(
    payload: string
  ): Promise<ScalableInstanceWithData[]> {
    const instances = this.configParser.parseAndEnrichConfig(payload);
    this.logger.debug({
      message: 'Autoscaler Poller started.',
      payload: instances,
    });

    const instancesWithData = [];
    for (const instance of instances) {
      const instanceWithData = await this.getInstanceWithData(instance);
      if (!instanceWithData) continue; // Error already logged.
      instancesWithData.push(instanceWithData);
    }
    return instancesWithData;
  }

  /** Sends the instance(s) information to the Scaler endpoint. */
  private async sendInstanceData(
    instancesWithData: ScalableInstanceWithData[]
  ): Promise<void> {
    for (const instanceWithData of instancesWithData) {
      await this.sendInstanceDataToPubSub(instanceWithData);
    }
  }

  /**
   * Gets the metrics and metadata for a given instance.
   * @param instance Instance for which metrics will be polled and assigned.
   */
  private async getInstanceWithData(
    instance: ScalableInstance
  ): Promise<ScalableInstanceWithData | void> {
    try {
      const metricsReader =
        this.metricsReaderFactory.buildMetricsReader(instance);
      const instanceMetrics = await metricsReader.getMetrics();

      const metadataReader =
        this.metadataReaderFactory.buildMetadataReader(instance);
      const instanceMetadata = await metadataReader.getMetadata();

      const instanceWithData: ScalableInstanceWithData = {
        ...instance,
        metrics: instanceMetrics,
        metadata: instanceMetadata,
      };
      this.counterManager.incrementCounter(
        POLLER_COUNTER_DEFINITION_MAP.POLLING_SUCCESS.counterName
      );
      return instanceWithData;
    } catch (e) {
      this.counterManager.incrementCounter(
        POLLER_COUNTER_DEFINITION_MAP.POLLING_FAILED.counterName
      );
    }
  }

  /**
   * Sends the instance information to PubSub.
   * @param instance Instance to send to PubSub.
   */
  private async sendInstanceDataToPubSub(instance: ScalableInstanceWithData) {
    const pubSubMessenger = new PubSubMessenger(this.logger);
    if (!instance.scalingConfig.scalerPubSubTopic) {
      throw new Error(
        `scalerPubSubTopic not defined for instance: ${instance.info}`
      );
    }
    await pubSubMessenger.postPubSubMessage(
      instance.scalingConfig.scalerPubSubTopic,
      JSON.stringify(instance)
    );
  }
}
