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

/** @fileoverview Tests metrics-reader-factory. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import * as monitoring from '@google-cloud/monitoring';
import {MonitoringMetricsReaderFactory} from '../monitoring-metrics-reader-factory';
import {MetricTypeMap} from '../monitoring-metrics-builder';
import {silentLogger} from '../../testing/testing-framework';
import {TEST_INSTANCE} from '../../testing/testing-data';

/** Sample monitoring metrics definition for tests. */
const MONITORING_METRICS: MetricTypeMap = Object.freeze({
  cpuMaximumUtilization: 'cpu_maximum_utilization',
});

/** Sample Monitoring API response for testing. */
const MONITORING_API_RESPONSE: [
  monitoring.protos.google.monitoring.v3.ITimeSeries[],
  monitoring.protos.google.monitoring.v3.IListTimeSeriesRequest | null,
  monitoring.protos.google.monitoring.v3.IListTimeSeriesResponse,
] = [
  [
    {
      resource: {labels: {location: 'us-central1'}},
      points: [{value: {doubleValue: 0.75}}],
    },
  ],
  {}, // IListTimeSeriesRequest, unused.
  {}, // IListTimeSeriesResponse, unused.
];

describe('MonitoringMetricsReaderFactory', () => {
  describe('buildMetricsReader', () => {
    let metricsClientWithMocks: monitoring.MetricServiceClient;
    let listTimeSeriesSpy: jasmine.Spy;

    beforeEach(() => {
      metricsClientWithMocks = new monitoring.MetricServiceClient();
      listTimeSeriesSpy = spyOn(metricsClientWithMocks, 'listTimeSeries');
      listTimeSeriesSpy.and.returnValue(MONITORING_API_RESPONSE);
      jasmine
        .clock()
        .install()
        .mockDate(new Date(Math.pow(10, 7)));
    });

    afterEach(() => {
      jasmine.clock().uninstall();
    });

    it('build a metrics reader', async () => {
      // Act.
      const metricsReaderFactory = new MonitoringMetricsReaderFactory(
        metricsClientWithMocks,
        silentLogger,
        MONITORING_METRICS,
        /** derivedMetrics= */ {},
        /** metricPeriodInSeconds */ undefined, // Use default.
        /** metricWindow */ undefined // Use default.
      );
      const metricsReader =
        metricsReaderFactory.buildMetricsReader(TEST_INSTANCE);

      // Assert.
      await metricsReader.getMetrics();
      expect(listTimeSeriesSpy).toHaveBeenCalledOnceWith({
        name: 'projects/project-123',
        filter:
          'project="project-123" AND ' +
          'resource.labels.location="us-central1" AND ' +
          'metric.type="cpu_maximum_utilization"',
        interval: {
          startTime: {seconds: 9700},
          endTime: {seconds: 10000},
        },
        aggregation: {
          alignmentPeriod: {seconds: 60},
          crossSeriesReducer: 'REDUCE_MEAN',
          perSeriesAligner: 'ALIGN_MAX',
          groupByFields: ['resource.location'],
        },
        view: 'FULL',
      });
    });
  });
});
