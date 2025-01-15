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

/** @fileoverview Tests monitoring-metrics-reader. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import * as monitoring from '@google-cloud/monitoring';
import {MetricValueMap} from '../../common/instance-info';
import {
  DerivedMetricDefinitionMap,
  MonitoringMetricDefinition,
  MonitoringMetricDefinitionMap,
  MonitoringMetricsReader,
} from '../monitoring-metrics-reader';
import {silentLogger} from '../../testing/testing-framework';
import {TEST_INSTANCE} from '../../testing/testing-data';

/** Sample monitoring metrics definition for tests. */
const MONITORING_METRICS: MonitoringMetricDefinitionMap = Object.freeze({
  cpuMaximumUtilization: {
    name: 'cpuMaximumUtilization',
    filter: 'metric.type=cpu_maximum_utilization',
    interval: {
      startTime: {
        seconds: 0,
      },
      endTime: {
        seconds: 1000,
      },
    },
    aggregation: {
      alignmentPeriod: {seconds: 1000},
      crossSeriesReducer: 'REDUCE_MEAN',
      perSeriesAligner: 'ALIGN_MAX',
      groupByFields: ['resource.location'],
    },
    view: 'FULL',
  },
  cpuAverageUtilization: {
    name: 'cpuAverageUtilization',
    filter: 'metric.type=cpu_average_utilization',
    interval: {
      startTime: {
        seconds: 0,
      },
      endTime: {
        seconds: 1000,
      },
    },
    aggregation: {
      alignmentPeriod: {seconds: 1000},
      crossSeriesReducer: 'REDUCE_MEAN',
      perSeriesAligner: 'ALIGN_MAX',
      groupByFields: ['resource.location'],
    },
    view: 'FULL',
  },
});

/** Sample monitoring metrics definition for tests. */
const DERIVED_METRICS: DerivedMetricDefinitionMap = Object.freeze({
  // Made up metric for testing.
  cpuRatio: (metrics: MetricValueMap): number => {
    return metrics.cpuMaximumUtilization / metrics.cpuAverageUtilization;
  },
});

describe('MonitoringMetricsReader', () => {
  // Combination of monitoring.MetricServiceClient and jasmine Spy.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let monitoringServiceClientWithMock: any;
  let listTimeSeriesSpy: jasmine.Spy;

  beforeEach(() => {
    monitoringServiceClientWithMock = new monitoring.MetricServiceClient();
    listTimeSeriesSpy = spyOn(
      monitoringServiceClientWithMock,
      'listTimeSeries'
    );
  });

  afterEach(() => {
    monitoringServiceClientWithMock.listTimeSeries.calls.reset();
  });

  describe('get_metrics', () => {
    describe('base tests', () => {
      beforeEach(() => {
        listTimeSeriesSpy.and.callFake(fakeListTimeSeries);
      });

      it('calls monitoring API for each metric', async () => {
        const metricReader = new MonitoringMetricsReader(
          TEST_INSTANCE,
          MONITORING_METRICS,
          /** derivedMetrics= */ {},
          monitoringServiceClientWithMock,
          silentLogger
        );

        await metricReader.getMetrics();

        expect(
          monitoringServiceClientWithMock.listTimeSeries
        ).toHaveBeenCalledTimes(2);
        const callArgs =
          monitoringServiceClientWithMock.listTimeSeries.calls.allArgs();
        expect(callArgs).toEqual(
          jasmine.arrayWithExactContents([
            [
              jasmine.objectContaining({
                filter: 'metric.type=cpu_maximum_utilization',
              }),
            ],
            [
              jasmine.objectContaining({
                filter: 'metric.type=cpu_average_utilization',
              }),
            ],
          ])
        );
      });

      it('returns the metrics for multiple metrics', async () => {
        const metricReader = new MonitoringMetricsReader(
          TEST_INSTANCE,
          MONITORING_METRICS,
          /** derivedMetrics= */ {},
          monitoringServiceClientWithMock,
          silentLogger
        );

        const metrics = await metricReader.getMetrics();

        expect(metrics).toEqual({
          cpuMaximumUtilization: 0.75,
          cpuAverageUtilization: 0.25,
        });
      });

      it('does not poll twice if metrics were already polled', async () => {
        const metricReader = new MonitoringMetricsReader(
          TEST_INSTANCE,
          MONITORING_METRICS,
          /** derivedMetrics= */ {},
          monitoringServiceClientWithMock,
          silentLogger
        );
        await metricReader.getMetrics();
        await metricReader.getMetrics();

        // It must be called twice, one for each metric, as opposed to 4 times
        // (2 times per metric x 2 calls).
        expect(
          monitoringServiceClientWithMock.listTimeSeries
        ).toHaveBeenCalledTimes(2);
      });

      it('calculates derived metrics', async () => {
        const metricReader = new MonitoringMetricsReader(
          TEST_INSTANCE,
          MONITORING_METRICS,
          /** derivedMetrics= */ DERIVED_METRICS,
          monitoringServiceClientWithMock,
          silentLogger
        );

        const metrics = await metricReader.getMetrics();

        expect(metrics).toEqual(jasmine.objectContaining({cpuRatio: 3}));
      });
    });

    describe('data type tests', () => {
      [
        {
          testCaseName: 'using double values',
          monitoringResponse: createSampleResponseWithPoints([
            {value: {doubleValue: 0.99}},
          ]),
          expectedValue: 0.99,
        },
        {
          testCaseName: 'finding the max value',
          monitoringResponse: createSampleResponseWithPoints([
            {value: {doubleValue: 0.33}},
            {value: {doubleValue: 0.95}},
            {value: {doubleValue: 0.67}},
          ]),
          expectedValue: 0.95,
        },
        {
          testCaseName: 'using int64value number',
          monitoringResponse: createSampleResponseWithPoints([
            {value: {int64Value: 5}},
          ]),
          expectedValue: 5,
        },
        {
          testCaseName: 'using int64value string',
          monitoringResponse: createSampleResponseWithPoints([
            {value: {int64Value: '7'}},
          ]),
          expectedValue: 7,
        },
        // TODO: add use case for int64value=Long.
      ].forEach(({testCaseName, monitoringResponse, expectedValue}) => {
        it(`returns expected metric ${testCaseName}`, async () => {
          listTimeSeriesSpy.and.returnValue(monitoringResponse);
          const metricReader = new MonitoringMetricsReader(
            TEST_INSTANCE,
            /** monitoringMetrics= */ {
              cpuMetric: MONITORING_METRICS.cpuMaximumUtilization,
            },
            /** derivedMetrics= */ {},
            monitoringServiceClientWithMock,
            silentLogger
          );

          const metrics = await metricReader.getMetrics();

          const expectedOutput = {cpuMetric: expectedValue} as MetricValueMap;
          expect(metrics).toEqual(jasmine.objectContaining(expectedOutput));
        });
      });

      [
        {
          testCaseName: 'there are no resource points (null)',
          monitoringResponse: createSampleResponseWithPoints(null),
          expectedError: new Error(
            'No data points found for metric cpuMaximumUtilization'
          ),
        },
        {
          testCaseName: 'there are no resource points (empty array)',
          monitoringResponse: createSampleResponseWithPoints([]),
          expectedError: new Error(
            'No data points found for metric cpuMaximumUtilization'
          ),
        },
        {
          testCaseName: 'value is null',
          monitoringResponse: createSampleResponseWithPoints([{value: null}]),
          expectedError: new Error(
            'No value for point in metric cpuMaximumUtilization'
          ),
        },
        {
          testCaseName: 'not supported metric types',
          monitoringResponse: createSampleResponseWithPoints([
            {value: {boolValue: true}},
          ]),
          expectedError: new Error(
            'No value for point in metric cpuMaximumUtilization'
          ),
        },
      ].forEach(({testCaseName, monitoringResponse, expectedError}) => {
        it(`throws when ${testCaseName}`, async () => {
          listTimeSeriesSpy.and.returnValue(monitoringResponse);
          const metricReader = new MonitoringMetricsReader(
            TEST_INSTANCE,
            /** monitoringMetrics= */ {
              cpuMetric: MONITORING_METRICS.cpuMaximumUtilization,
            },
            /** derivedMetrics= */ {},
            monitoringServiceClientWithMock,
            silentLogger
          );

          await expectAsync(metricReader.getMetrics()).toBeRejectedWith(
            expectedError
          );
        });
      });
    });
  });
});

/**
 * Implements a fake listTimeSeries method.
 * Returns a fake time series response with the minimal required data.
 */
async function fakeListTimeSeries(
  request: MonitoringMetricDefinition,
  // Adding options to match the function signature, but options is not used,
  // so defining it as any and disabling linter.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any, @typescript-eslint/no-unused-vars
  options: any
): Promise<
  [
    monitoring.protos.google.monitoring.v3.ITimeSeries[],
    monitoring.protos.google.monitoring.v3.IListTimeSeriesRequest | null,
    monitoring.protos.google.monitoring.v3.IListTimeSeriesResponse,
  ]
> {
  // Return arbitrary, but different, values for the metrics.
  switch (request.filter) {
    case 'metric.type=cpu_maximum_utilization':
      return createSampleResponseWithPoints([{value: {doubleValue: 0.75}}]);
    case 'metric.type=cpu_average_utilization':
      return createSampleResponseWithPoints([{value: {doubleValue: 0.25}}]);
    default:
      throw new Error('Metric not added to fake.');
  }
}

/**
 * Creates a sample Monitoring API response.
 * @param points Points of data returned by the API.
 * @return Full response from the monitoring API
 */
function createSampleResponseWithPoints(
  points: monitoring.protos.google.monitoring.v3.IPoint[] | null,
  location: string = 'us-central1'
): [
  monitoring.protos.google.monitoring.v3.ITimeSeries[],
  monitoring.protos.google.monitoring.v3.IListTimeSeriesRequest | null,
  monitoring.protos.google.monitoring.v3.IListTimeSeriesResponse,
] {
  return [
    [
      {
        resource: {
          labels: {
            location: location,
          },
        },
        points: points,
      },
    ],
    {}, // IListTimeSeriesRequest, unused.
    {}, // IListTimeSeriesResponse, unused.
  ];
}
