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

/** @fileoverview Provides common variables about AlloyDB and the Autoscaler. */

// Store name. Used for Firestore documents or Spanner tables.
export const ALLOYDB_STORE_NAME = 'alloyDbAutoscaler';

// Minimum number of nodes per read pool instance.
export const MIN_NODES_PER_INSTANCE = 1;

// Maximum number of nodes per read pool instance.
export const MAX_NODES_PER_INSTANCE = 20;

// Default scaling method.
export const DEFAULT_SCALING_METHOD = 'STEPWISE';

// Path to the downstream schema (from alloydb-autoscaler).
export const DOWNSTREAM_PROTO_SCHEMA_PATH =
  'src/alloydb-autoscaler/schema/downstream_event.proto';

// Path of the downstream proto message.
export const DOWNSTREA_PROTO_SCHEMA_NAME = 'DownstreamEvent';
