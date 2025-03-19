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

/** Provides a builder that creates AlloyDB metric definitions. */

import {AlloyDbScalableInstance} from '../common/alloydb-instance-info';
import {MonitoringMetricBuilder} from '../../autoscaler-core/poller/monitoring-metrics-builder';

/** Builds Monitoring API metric definitions for AlloyDB. */
export class AlloyDbMetricBuilder extends MonitoringMetricBuilder {
  /**
   * @param instanceInfo AlloyDB instance information.
   */
  constructor(protected instance: AlloyDbScalableInstance) {
    super(instance);
  }

  /**
   * Gets the filter for the given metric.
   * @param metricType The metric type for which to filter.
   * @return Filter to use for querying the metric.
   */
  protected getMetricFilter(metricType: string): string {
    return (
      'resource.type="alloydb.googleapis.com/Instance" ' +
      `AND resource.labels.cluster_id="${this.instance.info.clusterId}" ` +
      `AND resource.labels.instance_id="${this.instance.info.instanceId}" ` +
      `AND ${super.getMetricFilter(metricType)}`
    );
  }
}
