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

/** @fileoverview Defines the entrypoint for Google Kubernetes Engine. */

import {createLogger} from '../autoscaler-core/common/logger';
import {LIB_UNIFIED_VERSION, LIB_NAME} from './common/libs';
import {UnifiedScalerFunctionBuilder} from '../autoscaler-core/unified/unified-scaler-builder';
import {pollerHandleLocalConfig, scalerHandleLocalConfig} from './index';

const logger = createLogger(LIB_NAME, LIB_UNIFIED_VERSION);

const unifiedBuilder = new UnifiedScalerFunctionBuilder(
  logger,
  pollerHandleLocalConfig,
  scalerHandleLocalConfig
);

/** Startup function for unified poller/scaler. */
export const main = unifiedBuilder.buildRequestHandler();
