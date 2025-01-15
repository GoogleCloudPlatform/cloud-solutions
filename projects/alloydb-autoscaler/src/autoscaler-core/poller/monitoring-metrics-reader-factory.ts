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

/** @fileoverview Provides a factory that builds MonitoringMetricsReader. */

import {ScalableInstance} from '../common/instance-info';
import {MetricsReaderFactory} from './metrics-reader';
import {
  MonitoringMetricBuilder,
  MetricTypeMap,
} from './monitoring-metrics-builder';
import {
  MonitoringMetricsReader,
  DerivedMetricDefinitionMap,
} from './monitoring-metrics-reader';
import {pino} from 'pino';
import * as monitoring from '@google-cloud/monitoring';

/** Factory for MonitoringMetricsReader. */
export class MonitoringMetricsReaderFactory implements MetricsReaderFactory {
  /**
   * @param metricPeriodInSeconds How much each time window lasts (in seconds).
   * @param metricWindow How many time windows to query.
   */
  constructor(
    protected metricsClient: monitoring.MetricServiceClient,
    protected baseLogger: pino.Logger,
    protected metrics: MetricTypeMap,
    protected derivedMetrics: DerivedMetricDefinitionMap,
    protected metricPeriodInSeconds?: number,
    protected metricWindow?: number
  ) {}

  /** Builds a MonitoringMetricsReader for an instance. */
  buildMetricsReader(instance: ScalableInstance): MonitoringMetricsReader {
    return new MonitoringMetricsReader(
      instance,
      this.buildMetricsDefinitions(instance),
      this.derivedMetrics,
      this.metricsClient,
      this.baseLogger.child(instance.info)
    );
  }

  /**
   * Builds the metrics builder for the metrics reader.
   * @param instance Instance ofr which to create metrics builder.
   * @return MetricsBuilder for this instance.
   */
  protected buildMetricsDefinitions(instance: ScalableInstance) {
    const metricsBuilder = new MonitoringMetricBuilder(
      instance,
      this.metricPeriodInSeconds,
      this.metricWindow
    );
    return metricsBuilder.buildMonitoringMetricDefinitions(this.metrics);
  }
}
