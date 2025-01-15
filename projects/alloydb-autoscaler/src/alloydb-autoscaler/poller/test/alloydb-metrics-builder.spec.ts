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

/** @fileoverview Tests alloydb-metrics-builder. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import {AlloyDbMetricBuilder} from '../alloydb-metrics-builder';
import {TEST_ALLOYDB_INSTANCE} from '../../testing/testing-data';

describe('AlloyDbMetricBuilder', () => {
  describe('buildMonitoringMetricDefinitions', () => {
    beforeEach(() => {
      jasmine
        .clock()
        .install()
        .mockDate(new Date(Math.pow(10, 7)));
    });

    afterEach(() => {
      jasmine.clock().uninstall();
    });

    it('builds expected metric definitions', () => {
      const metrics = {
        cpuMaximumUtilization:
          'alloydb.googleapis.com/instance/cpu/maximum_utilization',
      };

      const metricBuilder = new AlloyDbMetricBuilder(TEST_ALLOYDB_INSTANCE);
      const output = metricBuilder.buildMonitoringMetricDefinitions(metrics);

      expect(output).toEqual({
        cpuMaximumUtilization: {
          name: 'projects/project-123',
          filter:
            'resource.type="alloydb.googleapis.com/Instance" ' +
            'AND resource.labels.cluster_id="alloydb-cluster" ' +
            'AND resource.labels.instance_id="alloydb-instance" ' +
            'AND project="project-123" ' +
            'AND resource.labels.location="us-central1" ' +
            'AND metric.type=' +
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
        },
      });
    });
  });
});
