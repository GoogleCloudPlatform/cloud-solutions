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

/** @fileoverview Entrypoint for AlloyDB Autoscaler Poller Cloud Function. */

import {AlloyDbConfigParser} from './alloydb-config-parser';
import {AlloyDbMetricsReaderFactory} from './alloydb-metrics-reader-factory';
import {LIB_NAME, LIB_POLLER_VERSION} from '../common/libs';
import {CounterManager} from '../../autoscaler-core/common/counters';
import {createLogger} from '../../autoscaler-core/common/logger';
import {OpenTelemetryMeterProvider} from '../../autoscaler-core/common/open-telemetry-meter-provider';
import {PollerFunctionBuilder} from '../../autoscaler-core/poller/poller-builder';
import {POLLER_COUNTER_DEFINITIONS} from '../../autoscaler-core/poller/poller-counters';
import * as monitoring from '@google-cloud/monitoring';
import {AlloyDBAdminClient} from '@google-cloud/alloydb';
import {AlloyDbCounterAttributeMapper} from '../common/alloydb-counter-attribute-mapper';
import {AlloyDbMetadataReaderFactory} from './alloydb-metadata-reader';
import pino from 'pino';

/** Creates the metrics reader factory for AlloyDB poller. */
const createMetricsReaderFactory = (
  logger: pino.Logger
): AlloyDbMetricsReaderFactory => {
  const metricsClient = new monitoring.MetricServiceClient({
    libName: LIB_NAME,
    libVersion: LIB_POLLER_VERSION,
  });
  return new AlloyDbMetricsReaderFactory(metricsClient, logger);
};

/** Creates the metadata reader factory for AlloyDB poller. */
const createMetadataReaderFactory = (
  logger: pino.Logger
): AlloyDbMetadataReaderFactory => {
  const alloyDbClient = new AlloyDBAdminClient({
    libName: LIB_NAME,
    libVersion: LIB_POLLER_VERSION,
  });
  return new AlloyDbMetadataReaderFactory(alloyDbClient, logger);
};

/** Creates and initializes counter manager with the logger set. */
const createAndInitializeCounterManager = (logger: pino.Logger) => {
  const meterProvider = new OpenTelemetryMeterProvider(logger);
  const counterAttributeMapper = new AlloyDbCounterAttributeMapper();
  const counterManager = new CounterManager(
    LIB_NAME,
    LIB_POLLER_VERSION,
    logger,
    meterProvider,
    counterAttributeMapper
  );
  counterManager.createCounters(POLLER_COUNTER_DEFINITIONS);
  return counterManager;
};

/** Creates the Poller Builder to create entrypoints. */
const createPollerBuilder = (): PollerFunctionBuilder => {
  /** Logger for AlloyDB Autoscaler poller. */
  const logger = createLogger(LIB_NAME, LIB_POLLER_VERSION);

  return new PollerFunctionBuilder(
    logger,
    new AlloyDbConfigParser(),
    createMetricsReaderFactory(logger),
    createMetadataReaderFactory(logger),
    createAndInitializeCounterManager(logger)
  );
};

/** Builder to create Poller entrypoints. */
const pollerBuilder = createPollerBuilder();

/** Handles a PubSub message. */
export const handlePubSubRequest = pollerBuilder.buildRequestHandlerForPubSub();

/**
 * Handles an HTTP Request.
 * For testing with: https://cloud.google.com/functions/docs/functions-framework
 */
export const handleHttpRequest =
  pollerBuilder.buildRequestHandlerForHttpRequests(
    // Static values for testing.
    JSON.stringify([
      {
        projectId: 'alloydb-instance',
        regionId: 'us-central1',
        clusterId: 'autoscale-cluster-test',
        instanceId: 'autoscale-instance-test',
        scalerPubSubTopic: 'projects/alloydb-scaler/topics/test-scaling',
        minSize: 3,
        maxSize: 10,
        stateProjectId: 'state-project-id',
      },
    ])
  );

/** Handles entrypoint for local config (unified Poller/Scaler). */
export const handleLocalConfig = pollerBuilder.buildRequestHandler();
