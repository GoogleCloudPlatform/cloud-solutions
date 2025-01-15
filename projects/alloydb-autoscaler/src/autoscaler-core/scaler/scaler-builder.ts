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

/** @fileoverview Provides the entrypoint for the Autoscaler Scaler. */

import pino from 'pino';
import {
  BaseEntrypointBuilder,
  EntrypointBuilder,
  EntrypointHandler,
  EnvironmentVariables,
  HttpHandler,
  PubSubHandler,
} from '../common/entrypoint-builder';
import {ScalableInstanceWithData} from '../common/instance-info';
import {StateStoreBuilder} from './state-stores/state-store';
import {CounterManager} from '../common/counters';
import {SCALER_COUNTER_DEFINITION_MAP} from './scaler-counters';
import {IStateStore} from './state-stores/state';
import {ScalerEvaluator} from './scaler-evaluator';
import {IStateFetcher} from './state-fetcher';
import {IRulesManager} from './scaler-rules-manager';
import {IScalingMethodRunner} from './scaling-methods/scaling-method-runner';
import {IScalerExecutor} from './scaler-executor';
import {COUNTER_ATTRIBUTE_NAMES} from '../common/counter-attribute-mapper';
import {getScalingDirection} from './scaling-methods/scaling-direction';
import {ScalingRequestReporter} from './scaling-request-reporter';
import {PubSubMessenger} from '../common/pubsub-messenger';
import {ProtobufEncoder} from '../common/protobuf';

/** Creates the entrypoint functions for the Scaler. */
export class ScalerFunctionBuilder
  extends BaseEntrypointBuilder
  implements EntrypointBuilder
{
  /** Initializes Scaler function builder. */
  constructor(
    protected baseLogger: pino.Logger,
    protected stateStoreBuilder: StateStoreBuilder,
    protected counterManager: CounterManager,
    protected stateFetcher: IStateFetcher,
    protected rulesManager: IRulesManager,
    protected scalingMethodRunner: IScalingMethodRunner,
    protected scalerExecutor: IScalerExecutor,
    protected downstreamProtobufPath: string,
    protected downstreamProtobufName: string
  ) {
    super();
  }

  /** Builds the entrypoint for the Scaler function. */
  buildRequestHandler(): EntrypointHandler {
    /**
     * Handles the request to the Scaler function.
     * @param payload Body payload in string format.
     */
    return async (payload: string) => {
      try {
        await this.runScalerForPayload(payload);
        this.counterManager.incrementCounter(
          SCALER_COUNTER_DEFINITION_MAP.REQUESTS_SUCCESS.counterName
        );
      } catch (e) {
        this.baseLogger.error({
          message: `Failed to process scaling request: ${e}`,
          payload: payload,
          err: e,
        });
        this.counterManager.incrementCounter(
          SCALER_COUNTER_DEFINITION_MAP.REQUESTS_FAILED.counterName
        );
      } finally {
        await this.counterManager.flush();
      }
    };
  }

  /**
   * Builds the entrypoint for the Scaler function for HTTP.
   * @param payload Fixed payload to use for testing.
   * @param env Fixed set of environment variables to set.
   * @returns HTTP Entrypoint for the Scaler function.
   */
  buildRequestHandlerForHttpRequests(
    payload: string,
    env?: EnvironmentVariables
  ): HttpHandler {
    /**
     * Handles the request to the Scaler function from HTTP, local tests.
     * @param _ HTTP Request.
     * @param res HTTP response object.
     */
    return async (_, res) => {
      try {
        this.setEnvironmentVariables(env);
        await this.runScalerForPayload(payload);
        this.counterManager.incrementCounter(
          SCALER_COUNTER_DEFINITION_MAP.REQUESTS_SUCCESS.counterName
        );
        res.status(200).end();
      } catch (e) {
        this.baseLogger.error({
          message: `Failed to parse http scaling request ${e}`,
          err: e,
        });
        res.status(500).contentType('text/plain').end('An exception occurred');
        this.counterManager.incrementCounter(
          SCALER_COUNTER_DEFINITION_MAP.REQUESTS_FAILED.counterName
        );
      } finally {
        await this.counterManager.flush();
      }
    };
  }

  /** Builds the entrypoint for the Scaler function for PubSub. */
  buildRequestHandlerForPubSub(): PubSubHandler {
    /**
     * Handles the request to the Scaler function from PubSub.
     * @param pubSubEvent PubSub event data.
     * @param _ Context from the PubSub. Unused.
     */
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    return async (pubSubEvent, _) => {
      try {
        const payload = Buffer.from(pubSubEvent.data, 'base64').toString();
        await this.runScalerForPayload(payload);
        this.counterManager.incrementCounter(
          SCALER_COUNTER_DEFINITION_MAP.REQUESTS_SUCCESS.counterName
        );
      } catch (e) {
        this.baseLogger.error({
          message: `Failed to parse pubSub scaling request: ${e}`,
          payload: pubSubEvent.data,
          err: e,
        });
        this.counterManager.incrementCounter(
          SCALER_COUNTER_DEFINITION_MAP.REQUESTS_FAILED.counterName
        );
      } finally {
        await this.counterManager.flush();
      }
    };
  }

  /** Runs the Scaler logic for a given payload (instance). */
  private async runScalerForPayload(payload: string) {
    let stateStore: IStateStore | undefined;
    try {
      const instance = JSON.parse(payload) as ScalableInstanceWithData;
      const payloadLogger = this.baseLogger.child({
        ...instance.info,
        payload: instance,
      });

      payloadLogger.info({
        message: `----- ${instance.info.resourcePath}: Scaling request received`,
      });
      stateStore = this.stateStoreBuilder.buildFor(instance);
      const scalerEvaluator = new ScalerEvaluator(
        payloadLogger,
        stateStore,
        this.counterManager,
        this.stateFetcher,
        this.rulesManager,
        this.scalingMethodRunner
      );

      const [isScalingPossible, suggestedSize] =
        await scalerEvaluator.processScalingRequest(instance);

      // Reasons for whether scaling is (or is not) possible or not are logged
      // within the scalerEvaluator.
      if (isScalingPossible) {
        const scalingStatus = await this.executeScalingRequest(
          instance,
          payloadLogger,
          stateStore,
          suggestedSize
        );
        await this.publishDownstreamEvent(
          instance,
          payloadLogger,
          scalingStatus,
          suggestedSize
        );
      }
    } finally {
      if (stateStore) stateStore.close();
    }
  }

  /**
   * Processes the request to scale.
   *
   * @return Event status.
   */
  async executeScalingRequest(
    instance: ScalableInstanceWithData,
    payloadLogger: pino.Logger,
    stateStore: IStateStore,
    suggestedSize: number
  ): Promise<string> {
    const currentState = await stateStore.getState();
    try {
      const operationId = await this.scalerExecutor.scaleInstance(
        instance,
        suggestedSize
      );
      await stateStore.updateState({
        ...currentState,
        scalingOperationId: operationId,
        scalingRequestedSize: suggestedSize,
        lastScalingTimestamp: Date.now(),
        lastScalingCompleteTimestamp: null,
        scalingPreviousSize: instance.metadata.currentSize,
        scalingMethod: instance.scalingConfig.scalingMethod,
      });
      this.counterManager.incrementCounter(
        SCALER_COUNTER_DEFINITION_MAP.SCALING_SUCCESS.counterName,
        instance,
        {
          [COUNTER_ATTRIBUTE_NAMES.SCALING_METHOD]:
            instance.scalingConfig.scalingMethod,
          [COUNTER_ATTRIBUTE_NAMES.SCALING_DIRECTION]: getScalingDirection(
            instance,
            suggestedSize,
            instance.metadata.currentSize
          ),
        }
      );
      return 'SCALING';
    } catch (e) {
      payloadLogger.error({
        message:
          `----- ${instance.info.resourcePath}: ` +
          `Unsuccessful scaling attempt: ${e}`,
        err: e,
      });
      const scalingStatusReporter = new ScalingRequestReporter(
        payloadLogger,
        this.counterManager,
        instance,
        currentState,
        suggestedSize
      );
      await scalingStatusReporter.reportFailedScalingOperation(`${e}`);

      this.counterManager.incrementCounter(
        SCALER_COUNTER_DEFINITION_MAP.SCALING_FAILED.counterName,
        instance,
        {
          [COUNTER_ATTRIBUTE_NAMES.SCALING_FAILED_REASON]: e,
          [COUNTER_ATTRIBUTE_NAMES.SCALING_METHOD]:
            instance.scalingConfig.scalingMethod,
          [COUNTER_ATTRIBUTE_NAMES.SCALING_DIRECTION]: getScalingDirection(
            instance,
            suggestedSize,
            instance.metadata.currentSize
          ),
        }
      );
      return 'SCALING_FAILURE';
    }
  }

  /** Sends a PubSub downstream message with the scaling operation info. */
  private async publishDownstreamEvent(
    instance: ScalableInstanceWithData,
    payloadLogger: pino.Logger,
    scalingStatus: string,
    suggestedSize: number
  ) {
    const topicId = instance?.scalingConfig?.downstreamPubSubTopic;
    if (!topicId) {
      payloadLogger.debug(
        `downstreamPubSubTopic is not configured, no ${scalingStatus} ` +
          'message has sent downstream'
      );
      return;
    }

    const protobufEncoder = new ProtobufEncoder(
      this.downstreamProtobufPath,
      this.downstreamProtobufName
    );
    const downstreamData = {
      ...instance.info,
      currentSize: instance.metadata.currentSize,
      suggestedSize: suggestedSize,
      units: instance.scalingConfig.units,
      metrics: Object.entries(instance.metrics).map(([metricName, value]) => {
        return {
          name: metricName,
          value: value,
          // TODO: bring threshold and margin here. Keeping fields for
          // compatibility with the existing Autoscalers.
          threshold: 0,
          margin: 0,
        };
      }),
    };
    const downstreamMessage =
      await protobufEncoder.encodeDataAsProtobufMessage(downstreamData);

    const pubSubMessenger = new PubSubMessenger(payloadLogger);
    await pubSubMessenger.postPubSubProtoMessage(topicId, downstreamMessage);

    payloadLogger.info(
      `Published ${scalingStatus} message downstream to topic: ${topicId}`
    );
  }
}
