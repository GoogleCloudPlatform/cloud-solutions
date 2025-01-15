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
 * limitations under the License
 */

/** @fileoverview Entrypoint for AlloyDB Autoscaler Scaler Cloud Function. */

import {CounterManager} from '../../autoscaler-core/common/counters';
import {createLogger} from '../../autoscaler-core/common/logger';
import {OpenTelemetryMeterProvider} from '../../autoscaler-core/common/open-telemetry-meter-provider';
import {ScalerFunctionBuilder} from '../../autoscaler-core/scaler/scaler-builder';
import {StateStoreBuilder} from '../../autoscaler-core/scaler/state-stores/state-store';
import {AlloyDbScalableInstanceWithData} from '../common/alloydb-instance-info';
import {AlloyDbCounterAttributeMapper} from '../common/alloydb-counter-attribute-mapper';
import {LIB_NAME, LIB_SCALER_VERSION} from '../common/libs';
import {
  ALLOYDB_STORE_NAME,
  DEFAULT_SCALING_METHOD,
  DOWNSTREA_PROTO_SCHEMA_NAME,
  DOWNSTREAM_PROTO_SCHEMA_PATH,
  MAX_NODES_PER_INSTANCE,
  MIN_NODES_PER_INSTANCE,
} from '../common/config';
import {SCALER_COUNTER_DEFINITIONS} from '../../autoscaler-core/scaler/scaler-counters';
import {AlloyDbStateFetcher} from './alloydb-state-fetcher';
import {RulesManager} from '../../autoscaler-core/scaler/scaler-rules-manager';
import {DEFAULT_RULESET} from './scaling-profiles/profiles';
import {
  DEFAULT_SCALING_METHODS,
  ScalingMethodRunner,
} from '../../autoscaler-core/scaler/scaling-methods/scaling-method-runner';
import {RulesEngine} from '../../autoscaler-core/scaler/scaler-rules-engine';
import {ScalingSizeValidator} from '../../autoscaler-core/scaler/scaling-methods/scaling-size-validator';
import {AlloyDbScalerExecutor} from './alloydb-scaler-executor';
import {AlloyDBAdminClient} from '@google-cloud/alloydb';
import pino from 'pino';

/** Creates and initializes CounterManager for AlloyDB Autoscaler. */
const createAndInitializeCounterManager = (logger: pino.Logger) => {
  const meterProvider = new OpenTelemetryMeterProvider(logger);
  const counterAttributeMapper = new AlloyDbCounterAttributeMapper();
  const counterManager = new CounterManager(
    LIB_NAME,
    LIB_SCALER_VERSION,
    logger,
    meterProvider,
    counterAttributeMapper
  );
  counterManager.createCounters(SCALER_COUNTER_DEFINITIONS);
  return counterManager;
};

/** Creates the StateFetcher for AlloyDB Autoscaler. */
const createStateFetcher = (
  logger: pino.Logger,
  counterManager: CounterManager
): AlloyDbStateFetcher => {
  const stateFetcher = new AlloyDbStateFetcher(logger, counterManager);
  return stateFetcher;
};

/** Creates the RulesManager for AlloyDB Autoscaler. */
const createRulesManager = (logger: pino.Logger): RulesManager => {
  const rulesManager = new RulesManager(
    logger,
    DEFAULT_RULESET
    // TODO: consider adding different profiles with different rule combinations.
  );
  return rulesManager;
};

/** Creates the ScalingMethodRunner for AlloyDB Autoscaler. */
const createScalingMethodRunner = (
  logger: pino.Logger
): ScalingMethodRunner => {
  const rulesEngine = new RulesEngine(logger);

  const scalingSizeValidator = new ScalingSizeValidator(
    logger,
    MIN_NODES_PER_INSTANCE,
    MAX_NODES_PER_INSTANCE
  );

  const defaultScalingMethod = DEFAULT_SCALING_METHODS.get(
    DEFAULT_SCALING_METHOD
  );
  if (!defaultScalingMethod) {
    throw new Error(
      `Default scaling method ${DEFAULT_SCALING_METHOD} does not exist. ` +
        'Select a different scaling method'
    );
  }

  const scalingMethodRunner = new ScalingMethodRunner(
    logger,
    rulesEngine,
    scalingSizeValidator,
    defaultScalingMethod,
    DEFAULT_SCALING_METHODS
  );
  return scalingMethodRunner;
};

/** Creates the ScalerExecutor for AlloyDB Autoscaler. */
const createScalerExecutor = (logger: pino.Logger): AlloyDbScalerExecutor => {
  const alloyDbClient = new AlloyDBAdminClient({
    libName: LIB_NAME,
    libVersion: LIB_SCALER_VERSION,
  });
  const scalerExecutor = new AlloyDbScalerExecutor(logger, alloyDbClient);
  return scalerExecutor;
};

const createScalerBuilder = (): ScalerFunctionBuilder => {
  const logger = createLogger(LIB_NAME, LIB_SCALER_VERSION);
  const counterManager = createAndInitializeCounterManager(logger);
  const stateStore = new StateStoreBuilder(
    LIB_NAME,
    LIB_SCALER_VERSION,
    ALLOYDB_STORE_NAME
  );

  return new ScalerFunctionBuilder(
    logger,
    stateStore,
    counterManager,
    createStateFetcher(logger, counterManager),
    createRulesManager(logger),
    createScalingMethodRunner(logger),
    createScalerExecutor(logger),
    DOWNSTREAM_PROTO_SCHEMA_PATH,
    DOWNSTREA_PROTO_SCHEMA_NAME
  );
};

const scalerBuilder = createScalerBuilder();

/** Handles a PubSub message. */
export const handlePubSubRequest = scalerBuilder.buildRequestHandlerForPubSub();

/** Handles entrypoint for local config (unified Poller/Scaler). */
export const handleLocalConfig = scalerBuilder.buildRequestHandler();

/**
 * Handles an HTTP Request.
 * For testing with: https://cloud.google.com/functions/docs/functions-framework
 */
export const handleHttpRequest =
  scalerBuilder.buildRequestHandlerForHttpRequests(
    // Static values for testing.
    JSON.stringify({
      info: {
        projectId: 'alloydb-instance',
        regionId: 'us-central1',
        clusterId: 'autoscale-cluster-test',
        instanceId: 'autoscale-instance-test',
      },
      scalingConfig: {
        scalerPubSubTopic: 'projects/alloydb-scaler/topics/test-scaling',
        downstreamPubSubTopic: 'projects/alloydb-scaler/topics/downstream',
        minSize: 3,
        maxSize: 10,
        scalingMethod: 'DIRECT',
        scaleInCoolingMinutes: 15,
        scaleOutCoolingMinutes: 10,
      },
      stateConfig: {
        stateProjectId: 'state-project-id',
        stateDatabase: {
          name: 'firestore',
          instanceId: 'projects/firestore/firestore-instance',
        },
      },
      metadata: {
        currentSize: 5,
        instanceType: 'READ_POOL',
      },
      metrics: {
        cpuMaximumUtilization: 0.9,
        cpuAverageUtilization: 0.8,
        connectionsTotal: 800,
        connectionsLimit: 1000,
        connectionsUtilization: 0.8,
      },
    } as AlloyDbScalableInstanceWithData)
  );
