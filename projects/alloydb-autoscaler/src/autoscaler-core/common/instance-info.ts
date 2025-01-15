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

import {RuleSet} from '../scaler/scaler-rules';

/** @fileoverview Provides types and info related to the scalable instance. */

/** Basic information of a database instance. */
export type InstanceInfo = {
  projectId: string;
  regionId: string;
  resourcePath?: string;
};

/** Configuration for the scaling of the database instance. */
export type ScalingConfig = {
  units?: string; // Each autoscaler should implements its own enum if required.

  minSize: number;
  maxSize: number;

  scalingMethod: string;
  scalingProfile?: string;
  scalingRules?: RuleSet[];

  stepSize?: number;

  scaleInLimit?: number;
  scaleOutLimit?: number;
  scaleInCoolingMinutes: number;
  scaleOutCoolingMinutes: number;

  scalerPubSubTopic?: string;
  downstreamPubSubTopic?: string;
};

/** Configuration for the state configuration of the state database instance. */
export type StateDatabaseConfig = {
  name: 'firestore' | 'spanner';
  instanceId?: string;
  databaseId?: string;
};

/** Configuration for the state configuration of the state database. */
export type StateConfig = {
  stateProjectId?: string;
  stateDatabase?: StateDatabaseConfig;
};

/** Information and configuration for a database instance. */
export type ScalableInstance = {
  info: InstanceInfo;
  scalingConfig: ScalingConfig;
  stateConfig: StateConfig;
};

/** Flat configuration for ScalableInstance. Used for user input. */
export type FlatInstanceConfiguration = InstanceInfo &
  ScalingConfig &
  StateConfig;

/**
 * Map of metric names to its current value.
 * The key is the custom metric name.
 * The value is its current value to use for rule evaluation.
 */
export type MetricValueMap = Record<string, number>;

/** Value of a metadata entry. */
export type MetadataValue = number | string;

/**
 * At least currentSize is required as a metadata value.
 *
 * Other Autoscalers may choose to add additional parameters.
 */
export type RequiredMetadataValueMap = {
  currentSize: number;
};

/**
 * Map of metadata attributes to its current value.
 * The key is the custom metadata field.
 */
export type MetadataValueMap = RequiredMetadataValueMap &
  Record<string, MetadataValue>;

/** Additional attributes added to the user config by the Poller. */
export type ScalableGeneratedAttributes = {
  metadata: MetadataValueMap;
  metrics: MetricValueMap;
};

/** Scalable instance enriched with metadata and metrics. */
export type ScalableInstanceWithData = ScalableInstance &
  ScalableGeneratedAttributes;

/** Gets the units text for a given instance. */
export const getUnitsText = (
  instance: ScalableInstance | ScalableInstanceWithData
): string => {
  if (!instance?.scalingConfig?.units) return '';
  return ` ${instance.scalingConfig.units}`;
};
