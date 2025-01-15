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

/** Provides a builder that creates monitoring metric definitions. */

import {ScalableInstance} from '../common/instance-info';
import {
  MonitoringMetricDefinition,
  MonitoringMetricDefinitionMap,
} from './monitoring-metrics-reader';
import * as monitoring from '@google-cloud/monitoring';

/** Default lookback window for monitoring metrics. */
const DEFAULT_METRIC_PERIOD_IN_SECONDS = 60;

/** Default number of period windows to check back. */
const DEFAULT_METRIC_WINDOW = 5;

/** A map between the name of the metric and the metric type. */
export type MetricTypeMap = Record<string, string>;

/** Builds metric definitions to poll data from the Monitoring API. */
export class MonitoringMetricBuilder {
  /**
   * @param instance Instance for which metrics will be built.
   * @param metricPeriodInSeconds How much each time window lasts (in seconds).
   * @param metricWindow How many time windows to query.
   */
  constructor(
    protected instance: ScalableInstance,
    protected metricPeriodInSeconds: number = DEFAULT_METRIC_PERIOD_IN_SECONDS,
    protected metricWindow: number = DEFAULT_METRIC_WINDOW
  ) {}

  /**
   * Gets the name for the metric.
   * @return Name to use for querying the metric.
   */
  protected getMetricName(): string {
    return `projects/${this.instance.info.projectId}`;
  }

  /**
   * Gets the filter for the given metric.
   * @param metricType The metric type for which to filter.
   * @return Filter to use for querying the metric.
   */
  protected getMetricFilter(metricType: string): string {
    return (
      `project="${this.instance.info.projectId}" ` +
      `AND resource.labels.location="${this.instance.info.regionId}" ` +
      `AND metric.type="${metricType}"`
    );
  }

  /**
   * Gets the interval for the given metric.
   * @return Interval to use for querying the metric.
   */
  protected getMetricInterval(): monitoring.protos.google.monitoring.v3.ITimeInterval {
    return {
      startTime: {
        seconds:
          Date.now() / 1000 - this.metricPeriodInSeconds * this.metricWindow,
      },
      endTime: {
        seconds: Date.now() / 1000,
      },
    };
  }

  /**
   * Gets the aggregation for the given metric.
   * @return Aggregation to use for querying the metric.
   */
  protected getMetricAggregation(): monitoring.protos.google.monitoring.v3.IAggregation {
    return {
      alignmentPeriod: {seconds: this.metricPeriodInSeconds},
      crossSeriesReducer: 'REDUCE_MEAN',
      perSeriesAligner: 'ALIGN_MAX',
      groupByFields: ['resource.location'],
    };
  }

  /**
   * Gets the filter for the metric.
   * @param metricType Type of metric for which to create definition.
   */
  protected buildMonitoringMetricDefinition(
    metricType: string
  ): MonitoringMetricDefinition {
    return {
      name: this.getMetricName(),
      filter: this.getMetricFilter(metricType),
      interval: this.getMetricInterval(),
      aggregation: this.getMetricAggregation(),
      view: 'FULL',
    };
  }

  /**
   * Builds the list of metrics to request.
   * @param metrics Map of metric names to metric types for which to generate
   *  metric definitions.
   * @return Map of metric names to its monitoring metric definitions.
   */
  buildMonitoringMetricDefinitions(
    metrics: MetricTypeMap
  ): MonitoringMetricDefinitionMap {
    const monitoringMetrics = {} as MonitoringMetricDefinitionMap;
    Object.entries(metrics).forEach(([metricName, metricType]) => {
      monitoringMetrics[metricName] =
        this.buildMonitoringMetricDefinition(metricType);
    });
    return monitoringMetrics;
  }
}
