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

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import {AlloyDbConfigParser} from '../alloydb-config-parser';
import {ValidationError} from '../../../autoscaler-core/poller/config-validator';

describe('AlloyDbConfigParser', () => {
  const configParser = new AlloyDbConfigParser();

  describe('parseAndEnrichConfig', () => {
    it('should format complete config', () => {
      const userConfig = [
        {
          projectId: 'project-123',
          regionId: 'us-central1',
          clusterId: 'cluster-A',
          instanceId: 'readpool-1',
          units: 'NODES',
          minSize: 3,
          maxSize: 10,
          scalingMethod: 'DIRECT',
          scalingProfile: 'CUSTOM',
          scalingRules: [
            {
              name: 'custom_rule',
              conditions: {
                all: [
                  {
                    fact: 'metric_name',
                    operator: 'lessThan',
                    value: 0.7,
                  },
                ],
              },
              event: {
                type: 'IN',
                params: {
                  message: 'low metric name',
                  scalingMetrics: ['metric_name'],
                },
              },
              priority: 1,
            },
          ],
          stepSize: 1,
          scaleInLimit: 2,
          scaleOutLimit: 5,
          scaleInCoolingMinutes: 7,
          scaleOutCoolingMinutes: 27,
          scalerPubSubTopic: 'projects/1/topics/scaler-topic',
          downstreamPubSubTopic: 'projects/1/topics/downstream-topic',
          stateProjectId: 'project-2',
          stateDatabase: {
            name: 'firestore',
            instanceId: 'state-instance',
            databaseId: 'state-database',
          },
        },
      ];

      const output = configParser.parseAndEnrichConfig(
        JSON.stringify(userConfig)
      );

      expect(output).toEqual([
        {
          info: {
            projectId: 'project-123',
            regionId: 'us-central1',
            clusterId: 'cluster-A',
            instanceId: 'readpool-1',
            resourcePath:
              'projects/project-123/locations/us-central1/clusters/cluster-A/' +
              'instances/readpool-1',
          },
          scalingConfig: {
            units: 'NODES',
            minSize: 3,
            maxSize: 10,
            scalingMethod: 'DIRECT',
            scalingProfile: 'CUSTOM',
            scalingRules: [
              {
                name: 'custom_rule',
                conditions: {
                  all: [
                    {
                      fact: 'metric_name',
                      operator: 'lessThan',
                      value: 0.7,
                    },
                  ],
                },
                event: {
                  type: 'IN',
                  params: {
                    message: 'low metric name',
                    scalingMetrics: ['metric_name'],
                  },
                },
                priority: 1,
              },
            ],
            stepSize: 1,
            scaleInLimit: 2,
            scaleOutLimit: 5,
            scaleInCoolingMinutes: 7,
            scaleOutCoolingMinutes: 27,
            scalerPubSubTopic: 'projects/1/topics/scaler-topic',
            downstreamPubSubTopic: 'projects/1/topics/downstream-topic',
          },
          stateConfig: {
            stateProjectId: 'project-2',
            stateDatabase: {
              name: 'firestore',
              instanceId: 'state-instance',
              databaseId: 'state-database',
            },
          },
        },
      ]);
    });

    it('should add default values', () => {
      const userConfig = [
        {
          projectId: 'project-123',
          regionId: 'us-central1',
          clusterId: 'cluster-A',
          instanceId: 'readpool-1',
        },
      ];

      const output = configParser.parseAndEnrichConfig(
        JSON.stringify(userConfig)
      );

      expect(output).toEqual([
        {
          info: {
            projectId: 'project-123',
            regionId: 'us-central1',
            clusterId: 'cluster-A',
            instanceId: 'readpool-1',
            resourcePath:
              'projects/project-123/locations/us-central1/clusters/cluster-A/' +
              'instances/readpool-1',
          },
          scalingConfig: {
            units: 'NODES',
            minSize: 1,
            maxSize: 20,
            scalingMethod: 'STEPWISE',
            scalingProfile: undefined,
            scalingRules: undefined,
            stepSize: 1,
            scaleInLimit: undefined,
            scaleOutLimit: undefined,
            scaleInCoolingMinutes: 10,
            scaleOutCoolingMinutes: 10,
            scalerPubSubTopic: undefined,
            downstreamPubSubTopic: undefined,
          },
          stateConfig: {
            stateProjectId: undefined,
            stateDatabase: undefined,
          },
        },
      ]);
    });

    [
      {
        testCaseName: 'maxSize > 20',
        userConfig: [
          {
            projectId: 'project-123',
            regionId: 'us-central1',
            clusterId: 'cluster-A',
            instanceId: 'readpool-1',
            maxSize: 35,
          },
        ],
        expectedError: new ValidationError(
          'INVALID CONFIG: maxSize (35) is larger than the maximum size of 20.'
        ),
      },
      {
        testCaseName: 'minSize > 20',
        userConfig: [
          {
            projectId: 'project-123',
            regionId: 'us-central1',
            clusterId: 'cluster-A',
            instanceId: 'readpool-1',
            minSize: 35,
          },
        ],
        expectedError: new ValidationError(
          'INVALID CONFIG: minSize (35) is larger than maxSize (20).'
        ),
      },
    ].forEach(({testCaseName, userConfig, expectedError}) => {
      it(`should fail for invalid instance config: ${testCaseName}`, () => {
        const userConfigStr = JSON.stringify(userConfig);

        expect(() => {
          configParser.parseAndEnrichConfig(userConfigStr);
        }).toThrow(expectedError);
      });
    });
  });
});
