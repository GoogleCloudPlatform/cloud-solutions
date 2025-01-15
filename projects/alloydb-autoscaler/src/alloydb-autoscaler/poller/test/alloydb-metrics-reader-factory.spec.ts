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

/** @fileoverview Tests alloydb-metrics-reader-factory. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import {MetricValueMap} from '../../../autoscaler-core/common/instance-info';
import * as monitoring from '@google-cloud/monitoring';
import {
  AlloyDbMetricsReaderFactory,
  TEST_ONLY,
} from '../alloydb-metrics-reader-factory';
import {silentLogger} from '../../../autoscaler-core/testing/testing-framework';
import {TEST_ALLOYDB_INSTANCE} from '../../testing/testing-data';

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

describe('alloydb-metrics-reader-factory', () => {
  describe('AlloyDbMetricsReaderFactory', () => {
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

      it('build a metrics reader with AlloyDB config', async () => {
        // Act.
        const metricsReaderFactory = new AlloyDbMetricsReaderFactory(
          metricsClientWithMocks,
          silentLogger
        );
        const metricsReader = metricsReaderFactory.buildMetricsReader(
          TEST_ALLOYDB_INSTANCE
        );

        // Assert.
        await metricsReader.getMetrics();
        // Expect one call for each MetricsReader metrics for AlloyDB.
        expect(listTimeSeriesSpy).toHaveBeenCalledTimes(4);
        // Test one sample to see that it is using the right reader.
        expect(listTimeSeriesSpy).toHaveBeenCalledWith({
          name: 'projects/project-123',
          filter:
            'resource.type="alloydb.googleapis.com/Instance" AND ' +
            'resource.labels.cluster_id="alloydb-cluster" AND ' +
            'resource.labels.instance_id="alloydb-instance" AND ' +
            'project="project-123" AND ' +
            'resource.labels.location="us-central1" AND ' +
            'metric.type=' +
            '"alloydb.googleapis.com/instance/cpu/maximum_utilization"',
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

  describe('derived metrics', () => {
    describe('connectionsUtilization', () => {
      it('calculates expected value', () => {
        const metrics: MetricValueMap = {
          connectionsTotal: 23,
          connectionsMax: 50,
        };

        const output =
          TEST_ONLY.DERIVED_METRICS.connectionsUtilization(metrics);

        expect(output).toEqual(0.46);
      });

      [
        {
          testName: 'missing connectionsTotal',
          metrics: {connectionsMax: 50} as MetricValueMap,
          expectedErrorMessage:
            'Unable to calculate connectionsUtilization, no value for ' +
            'connectionsTotal was found.',
        },
        {
          testName: 'missing connectionsMax',
          metrics: {connectionsTotal: 23} as MetricValueMap,
          expectedErrorMessage:
            'Unable to calculate connectionsUtilization, no value for ' +
            'connectionsMax was found.',
        },
        {
          testName: 'connectionsMax is zero',
          metrics: {
            connectionsMax: 0,
            connectionsTotal: 23,
          } as MetricValueMap,
          expectedErrorMessage:
            'Unable to calculate connectionsUtilization. ' +
            'Max connections are 0. Increase maximum number of connections.',
        },
      ].forEach(({testName, metrics, expectedErrorMessage}) => {
        it(`throws when ${testName}`, () => {
          expect(() =>
            TEST_ONLY.DERIVED_METRICS.connectionsUtilization(metrics)
          ).toThrow(new Error(expectedErrorMessage));
        });
      });
    });
  });
});
