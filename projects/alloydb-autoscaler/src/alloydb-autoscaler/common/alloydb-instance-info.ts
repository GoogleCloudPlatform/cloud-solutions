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

/** @fileoverview Provides types and info related to the AlloyDB instance. */

import {
  InstanceInfo,
  ScalingConfig,
  ScalableInstance,
  StateConfig,
  ScalableGeneratedAttributes,
} from '../../autoscaler-core/common/instance-info';

/** AlloyDB instance information. */
export type AlloyDbInstanceInfo = InstanceInfo & {
  clusterId: string;
  instanceId: string;
};

export type AlloyDbScalingConfig = ScalingConfig & {
  units: 'NODES';
};

/**
 * AlloyDB Autoscaler scalable configuration.
 * Includes: instance information, scaling configuration, state configuration
 * and metrics values.
 */
export type AlloyDbScalableInstance = ScalableInstance & {
  info: AlloyDbInstanceInfo;
  scalingConfig: ScalingConfig;
};

export type FlatAlloyDbInstanceConfiguration = AlloyDbInstanceInfo &
  AlloyDbScalingConfig &
  StateConfig;

export type AlloyDbScalableInstanceWithData = AlloyDbScalableInstance &
  ScalableGeneratedAttributes;
