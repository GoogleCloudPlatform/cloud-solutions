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

/** @fileoverview Maps attributes for Poller Counter names for AlloyDB. */

import {
  CounterAttributeNames,
  CounterAttributes,
  CounterAttributeMapper,
  ICounterAttributeMapper,
} from '../../autoscaler-core/common/counter-attribute-mapper';
import {
  AlloyDbScalableInstance,
  AlloyDbScalableInstanceWithData,
} from './alloydb-instance-info';

const ALLOYDB_COUNTER_ATTRIBUTE_NAMES: CounterAttributeNames = {
  PROJECT_ID: 'alloydb_project_id',
  CLUSTER_ID: 'alloydb_cluster_id',
  INSTANCE_ID: 'alloydb_instance_id',
};

/** Maps attributes for Poller Counter names for AlloyDB. */
export class AlloyDbCounterAttributeMapper
  extends CounterAttributeMapper
  implements ICounterAttributeMapper
{
  /** @inheritdoc */
  protected getInstanceAttributes(
    instance?: AlloyDbScalableInstance | AlloyDbScalableInstanceWithData
  ): CounterAttributes {
    if (!instance) return {};
    return {
      [ALLOYDB_COUNTER_ATTRIBUTE_NAMES.PROJECT_ID]: instance?.info?.projectId,
      [ALLOYDB_COUNTER_ATTRIBUTE_NAMES.CLUSTER_ID]: instance?.info?.clusterId,
      [ALLOYDB_COUNTER_ATTRIBUTE_NAMES.INSTANCE_ID]: instance?.info?.instanceId,
    };
  }
}
