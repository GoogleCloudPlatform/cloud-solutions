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

/** @fileoverview Provides AlloyDB common data for testing. */

import {
  TEST_INSTANCE,
  TEST_INSTANCE_WITH_DATA,
} from '../../autoscaler-core/testing/testing-data';
import {
  AlloyDbInstanceInfo,
  AlloyDbScalableInstance,
  AlloyDbScalableInstanceWithData,
} from '../common/alloydb-instance-info';

const ALLOYDB_INFO: AlloyDbInstanceInfo = Object.freeze({
  projectId: 'project-123',
  regionId: 'us-central1',
  clusterId: 'alloydb-cluster',
  instanceId: 'alloydb-instance',
  resourcePath:
    'projects/project-123/clusters/alloydb-cluster/instances/alloydb-instance',
});

/** An AlloyDBScaleableInstance for testing. */
export const TEST_ALLOYDB_INSTANCE: AlloyDbScalableInstance = Object.freeze({
  ...TEST_INSTANCE,
  info: ALLOYDB_INFO,
});

/** An AlloyDBScaleableInstance with data for testing. */
export const TEST_ALLOYDB_INSTANCE_WITH_DATA: AlloyDbScalableInstanceWithData =
  Object.freeze({
    ...TEST_INSTANCE_WITH_DATA,
    info: ALLOYDB_INFO,
  });
