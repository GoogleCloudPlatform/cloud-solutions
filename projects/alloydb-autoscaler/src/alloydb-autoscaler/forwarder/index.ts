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

/** @fileoverview Entrypoint for AlloyDB Autoscaler Forwarder Cloud Function. */

import {LIB_NAME, LIB_FORWARDER_FUNCTION} from '../common/libs';
import {createLogger} from '../../autoscaler-core/common/logger';
import {ForwarderFunctionBuilder} from '../../autoscaler-core/forwarder/forwarder-builder';

/** Logger for AlloyDB Autoscaler forwarder. */
const logger = createLogger(LIB_NAME, LIB_FORWARDER_FUNCTION);

/** Builder to create Poller entrypoints. */
const forwarderBuilder = new ForwarderFunctionBuilder(logger);

/**
 * Handles an HTTP Request.
 * For testing with: https://cloud.google.com/functions/docs/functions-framework
 */
export const handleHttpRequest =
  forwarderBuilder.buildRequestHandlerForHttpRequests(
    // Static testing payload.
    JSON.stringify({
      projectId: 'alloydb-test-project',
      regionId: 'us-central1',
      clusterId: 'alloydb-test-cluster',
      instanceId: 'alloydb-test-instance',
      minSize: 1,
      maxSize: 10,
    }),
    {
      POLLER_TOPIC: 'projects/project-id/topics/poller-topic',
    }
  );

/** Handles a PubSub message. */
export const handlePubSubRequest =
  forwarderBuilder.buildRequestHandlerForPubSub();
