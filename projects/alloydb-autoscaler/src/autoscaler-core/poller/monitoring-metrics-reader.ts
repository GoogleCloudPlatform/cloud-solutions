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

/** @fileoverview Provides a metric reader using Monitoring API. */

import {ScalableInstance, MetricValueMap} from '../common/instance-info';
import {MetricsReader} from './metrics-reader';
import * as monitoring from '@google-cloud/monitoring';
import {pino} from 'pino';

/** Definition of how to pull a certain metric from the monitoring API. */
export type MonitoringMetricDefinition =
  monitoring.protos.google.monitoring.v3.IListTimeSeriesRequest;

/** Map of metric names to its monitoring API definition. */
export type MonitoringMetricDefinitionMap = Record<
  string,
  MonitoringMetricDefinition
>;

/** Function definition to calculate derived metrics. */
export type DerivedMetricFunction = (metrics: MetricValueMap) => number;

/** Map of metric names to its derived metric calculation. */
export type DerivedMetricDefinitionMap = Record<string, DerivedMetricFunction>;

/**
 * Reads and pulls metrics and metadata from Monitoring API for instances.
 */
export class MonitoringMetricsReader implements MetricsReader {
  protected metrics: MetricValueMap;
  protected areMetricsPolled: boolean;

  /**
   * Initializes metrics poller, with an optional and initial metric polling.
   * @param instanceInfo Info about the instance.
   * @param monitoringMetrics Metrics to pull from the Monitoring API.
   * @param derivedMetrics Metrics to calculate after pulling data from API.
   * @param metricsClient Monitoring metrics client.
   */
  constructor(
    protected instance: ScalableInstance,
    protected monitoringMetrics: MonitoringMetricDefinitionMap,
    protected derivedMetrics: DerivedMetricDefinitionMap = {},
    protected metricsClient: monitoring.MetricServiceClient,
    protected logger: pino.Logger
  ) {
    this.metrics = {} as MetricValueMap;
    this.areMetricsPolled = false;
  }

  /**
   * Gets the metric values.
   *
   * If the metrics were polled, returns the metrics instance.
   * Othrwise, it will poll the metrics from the API.
   */
  async getMetrics(): Promise<MetricValueMap> {
    if (!this.areMetricsPolled) {
      await this.pollMetrics();
      this.getDerivedMetrics();
    }
    return this.metrics;
  }

  /** Reads metrics for this instance and writes them to metrics attribute. */
  private async pollMetrics() {
    this.logger.info(
      `----- ${this.instance.info.resourcePath}: Getting Metrics -----`
    );

    for (const [metricName, metricDefinition] of Object.entries(
      this.monitoringMetrics
    )) {
      const [maxMetricValue, maxLocation] =
        await this.getMetricFromMonitoringApi(metricDefinition);

      this.logger.debug(
        `  ${metricDefinition.name} = ${maxMetricValue}, ` +
          `location = ${maxLocation}`
      );

      this.metrics[metricName] = maxMetricValue;
    }

    this.areMetricsPolled = true;
  }

  /**
   * Gets the max value of metric over a window from the Monitoring API.
   * @param metricDefinition Metric definition to query Monitoring API.
   * @return Promise with the [metric value, and its location].
   */
  private async getMetricFromMonitoringApi(
    metricDefinition: MonitoringMetricDefinition
  ): Promise<[number, string]> {
    this.logger.debug(
      `Getting metric ${metricDefinition.name} ` +
        `from ${this.instance.info.resourcePath}.`
    );

    const metricResponses =
      await this.metricsClient.listTimeSeries(metricDefinition);

    const resources = metricResponses[0];
    let maxValue = 0;
    let maxLocation = 'global';

    for (const resource of resources) {
      const dataPoints = resource?.points;
      if (!dataPoints || dataPoints.length === 0) {
        throw new Error(
          `No data points found for metric ${metricDefinition.name}`
        );
      }
      for (const point of dataPoints) {
        const value = this.getValueFromPoint(point);
        if (value === null) {
          throw new Error(
            `No value for point in metric ${metricDefinition.name}`
          );
        }
        if (value < maxValue) continue;
        maxValue = value;
        if (resource.resource?.labels?.location) {
          maxLocation = resource.resource.labels.location;
        }
      }
    }

    return [maxValue, maxLocation];
  }

  /** Gets and calculates derived metrics. */
  private getDerivedMetrics() {
    if (!this.derivedMetrics) return;
    Object.entries(this.derivedMetrics).forEach(
      ([metricName, metricFn]: [string, DerivedMetricFunction]) => {
        this.metrics[metricName] = metricFn(this.metrics);
      }
    );
  }

  /**
   * Gets the value for a Monitoring metric data point.
   * Supports: doubleValue and int64Value.
   * @param point Point from which to get value.
   * @return Value of the point.
   */
  private getValueFromPoint(
    point: monitoring.protos.google.monitoring.v3.IPoint
  ): number | null {
    const value = point?.value;
    if (!value) return null;
    if (value.doubleValue !== null && value.doubleValue !== undefined) {
      return value.doubleValue;
    }
    if (value.int64Value !== null && value.int64Value !== undefined) {
      if (typeof value.int64Value === 'number') {
        return value.int64Value;
      }
      // Handles string and Long cases.
      const parsedValue = parseInt(value.int64Value.toString());
      return isNaN(parsedValue) ? null : parsedValue;
    }
    return null;
  }
}
