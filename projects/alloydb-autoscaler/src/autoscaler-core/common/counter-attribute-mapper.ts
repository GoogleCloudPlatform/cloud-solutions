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

/** @fileoverview Maps instance and additional attributes to counter names. */

import {ScalableInstance, ScalableInstanceWithData} from './instance-info';

/** Attributes to add to the Counter. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type CounterAttributes = Record<string, any>;

/** Map of names of the counter attributes. */
export type CounterAttributeNames = Record<string, string>;

export const COUNTER_ATTRIBUTE_NAMES: CounterAttributeNames = {
  // Instance attributes.
  PROJECT_ID: 'project_id',
  CLUSTER_ID: 'cluster_id',
  INSTANCE_ID: 'instance_id',
  // Scaler attributes.
  SCALING_DENIED_REASON: 'scaling_denied_reason',
  SCALING_DIRECTION: 'scaling_direction',
  SCALING_FAILED_REASON: 'scaling_failed_reason',
  SCALING_SUGGESTED_SIZE: 'scaling_suggested_size',
  SCALING_METHOD: 'scaling_method',
};

/** Maps attributes for Counters. */
export interface ICounterAttributeMapper {
  /** Gets the attributes to report in the counter for a given instance. */
  getCounterAttributes(
    instance?: ScalableInstance | ScalableInstanceWithData,
    additionalAttributes?: CounterAttributes
  ): CounterAttributes;
}

/** Maps attributes for Counters. */
export class CounterAttributeMapper implements ICounterAttributeMapper {
  /** @inheritdoc */
  getCounterAttributes(
    instance?: ScalableInstance | ScalableInstanceWithData,
    additionalAttributes?: CounterAttributes
  ): CounterAttributes {
    return {
      ...this.getInstanceAttributes(instance),
      ...(additionalAttributes ?? {}),
    };
  }

  /** @inheritdoc */
  protected getInstanceAttributes(
    instance?: ScalableInstance | ScalableInstanceWithData
  ) {
    if (!instance) return {};
    return {
      [COUNTER_ATTRIBUTE_NAMES.PROJECT_ID]: instance?.info?.projectId,
    };
  }
}
