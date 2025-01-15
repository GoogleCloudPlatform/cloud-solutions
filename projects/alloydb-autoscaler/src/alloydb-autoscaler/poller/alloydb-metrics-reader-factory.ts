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

/** @fileoverview Provides a factory that builds a MetricsReader for AlloyDB. */

import {MonitoringMetricsReaderFactory} from '../../autoscaler-core/poller/monitoring-metrics-reader-factory';
import {AlloyDbScalableInstance} from '../common/alloydb-instance-info';
import {MetricValueMap} from '../../autoscaler-core/common/instance-info';
import {AlloyDbMetricBuilder} from './alloydb-metrics-builder';
import {MetricTypeMap} from '../../autoscaler-core/poller/monitoring-metrics-builder';
import {
  DerivedMetricDefinitionMap,
  MonitoringMetricsReader,
} from '../../autoscaler-core/poller/monitoring-metrics-reader';
import * as monitoring from '@google-cloud/monitoring';
import {pino} from 'pino';

/** Map of metric names to Monitoring API metric types. */
const METRIC_FILTER_MAP: MetricTypeMap = Object.freeze({
  cpuMaximumUtilization:
    'alloydb.googleapis.com/instance/cpu/maximum_utilization',
  cpuAverageUtilization:
    'alloydb.googleapis.com/instance/cpu/average_utilization',
  connectionsTotal:
    'alloydb.googleapis.com/instance/postgres/total_connections',
  connectionsMax: 'alloydb.googleapis.com/instance/postgres/connections_limit',
});

/**
 * Map of metrics that are derived from other metrics with their function to
 * calculate the value.
 */
const DERIVED_METRICS: DerivedMetricDefinitionMap = Object.freeze({
  connectionsUtilization: (metrics: MetricValueMap) => {
    if (
      metrics?.connectionsMax === null ||
      metrics?.connectionsMax === undefined
    ) {
      throw new Error(
        'Unable to calculate connectionsUtilization, no value for ' +
          'connectionsMax was found.'
      );
    }

    if (metrics.connectionsMax <= 0) {
      throw new Error(
        'Unable to calculate connectionsUtilization. ' +
          'Max connections are 0. Increase maximum number of connections.'
      );
    }

    if (
      metrics?.connectionsTotal === null ||
      metrics?.connectionsTotal === undefined
    ) {
      throw new Error(
        'Unable to calculate connectionsUtilization, no value for ' +
          'connectionsTotal was found.'
      );
    }

    // Calculation is the ratio between the the current connections and the
    // limit of connections for the instance. In other words:
    // connectionsTotal / connectionsMax.
    return metrics.connectionsTotal / metrics.connectionsMax;
  },
});

/** Factory to produce Metrics Reader for AlloyDB Autoscaler. */
export class AlloyDbMetricsReaderFactory extends MonitoringMetricsReaderFactory {
  /**
   * Initializes factory.
   * @param metricsClient Monitoring API metrics client.
   * @param baseLogger Logger to use for logging.
   */
  constructor(
    protected metricsClient: monitoring.MetricServiceClient,
    protected baseLogger: pino.Logger
  ) {
    super(
      metricsClient,
      baseLogger,
      /** metrics= */ METRIC_FILTER_MAP,
      /** derivedMetrics= */ DERIVED_METRICS,
      /** metricPeriodInSeoncds= */ undefined, // Use default.
      /** metricWindow= */ undefined // Use default.
    );
  }

  /** See MonitoringMetricReaderFactory. */
  buildMetricsReader(
    instance: AlloyDbScalableInstance
  ): MonitoringMetricsReader {
    return new MonitoringMetricsReader(
      instance,
      this.buildMetricsDefinitions(instance),
      this.derivedMetrics,
      this.metricsClient,
      this.baseLogger.child(instance.info)
    );
  }

  /** See MonitoringMetricReaderFactory. */
  protected buildMetricsDefinitions(instance: AlloyDbScalableInstance) {
    const metricsBuilder = new AlloyDbMetricBuilder(instance);
    return metricsBuilder.buildMonitoringMetricDefinitions(this.metrics);
  }
}

export const TEST_ONLY = {
  DERIVED_METRICS, // Export to test the logic of specific derived metrics.
};
