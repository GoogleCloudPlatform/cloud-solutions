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

/** @fileoverview Tests monitoring-metrics-builder. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import {MonitoringMetricBuilder} from '../monitoring-metrics-builder';
import {ScalableInstance} from '../../common/instance-info';

describe('MonitoringMetricBuilder', () => {
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
      const instance: ScalableInstance = Object.freeze({
        info: Object.freeze({
          projectId: 'project-123',
          regionId: 'us-central1',
          resourcePath: 'us-central1/project-123/',
        }),
        scalingConfig: Object.freeze({
          minSize: 1,
          maxSize: 10,
          scalingMethod: 'DIRECT',
          scaleInCoolingMinutes: 15,
          scaleOutCoolingMinutes: 5,
        }),
        stateConfig: Object.freeze({}),
      });
      const metrics = {
        metric1: 'abc-1',
        metric2: 'xyz-2',
      };

      const metricBuilder = new MonitoringMetricBuilder(
        instance,
        /* metricPeriodInSeconds= */ 10,
        /* metricWindow= */ 3
      );
      const output = metricBuilder.buildMonitoringMetricDefinitions(metrics);

      expect(output).toEqual({
        metric1: {
          name: 'projects/project-123',
          filter:
            'project="project-123" ' +
            'AND resource.labels.location="us-central1" ' +
            'AND metric.type="abc-1"',
          interval: {
            startTime: {seconds: 9970},
            endTime: {seconds: 10000},
          },
          aggregation: {
            alignmentPeriod: {seconds: 10},
            crossSeriesReducer: 'REDUCE_MEAN',
            perSeriesAligner: 'ALIGN_MAX',
            groupByFields: ['resource.location'],
          },
          view: 'FULL',
        },
        metric2: {
          name: 'projects/project-123',
          filter:
            'project="project-123" ' +
            'AND resource.labels.location="us-central1" ' +
            'AND metric.type="xyz-2"',
          interval: {
            startTime: {seconds: 9970},
            endTime: {seconds: 10000},
          },
          aggregation: {
            alignmentPeriod: {seconds: 10},
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
