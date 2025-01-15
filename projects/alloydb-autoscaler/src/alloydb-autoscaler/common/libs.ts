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

/** @fileoverview Provides information about this module. */

import {version as packageVersion} from '../../../package.json';

export const LIB_NAME: string = 'cloud-solutions';
export const LIB_BASE_VERSION: string = 'alloydb-autoscaler';
export const LIB_VERSION_NUMBER: string = packageVersion;

// Formats to cloud-solutions/alloydb-autoscaler-poller-usage-v999.
export const LIB_POLLER_VERSION: string = `${LIB_BASE_VERSION}-poller-usage-v${packageVersion}`;

// Formats to cloud-solutions/alloydb-autoscaler-forwarder-usage-v999.
export const LIB_FORWARDER_FUNCTION: string = `${LIB_BASE_VERSION}-forwarder-usage-v${packageVersion}`;

// Formats to cloud-solutions/alloydb-autoscaler-scaler-usage-v999.
export const LIB_SCALER_VERSION: string = `${LIB_BASE_VERSION}-scaler-usage-v${packageVersion}`;

// Formats to cloud-solutions/alloydb-autoscaler-unified-usage-v999.
export const LIB_UNIFIED_VERSION: string = `${LIB_BASE_VERSION}-unified-usage-v${packageVersion}`;
