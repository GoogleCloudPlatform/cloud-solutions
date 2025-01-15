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
import {ConfigParser, DefaultInstanceConfig} from '../config-parser';
import {ConfigValidator, ValidationError} from '../config-validator';

const DEFAULT_CONFIG: DefaultInstanceConfig = Object.freeze({
  scalingConfig: {
    minSize: 1,
    maxSize: 100,
    scalingMethod: 'LINEAR',
    stepSize: 2,
    scaleInLimit: 3,
    scaleOutLimit: 4,
    scaleInCoolingMinutes: 15,
    scaleOutCoolingMinutes: 30,
    scalerPubSubTopic: 'projects/x/topics/default-scaler-topic',
    downstreamPubSubTopic: 'projects/x/topics/default-downstream-topic',
  },
  stateConfig: {
    stateProjectId: 'default-project',
    stateDatabase: {
      name: 'firestore',
      instanceId: 'default-state-instance',
      databaseId: 'default-state-database',
    },
  },
});

describe('ConfigParser', () => {
  const configValidator = new ConfigValidator();
  const configParser = new ConfigParser(configValidator, DEFAULT_CONFIG);

  describe('parseAndEnrichConfig', () => {
    it('should format complete config', () => {
      const userConfig = [
        {
          projectId: 'project-123',
          regionId: 'us-central1',
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
            resourcePath: 'projects/project-123/locations/us-central1',
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

    it('should format multiple configs', () => {
      const userConfig = [
        {
          projectId: 'project-123',
          regionId: 'us-central1',
        },
        {
          projectId: 'project-456',
          regionId: 'us-central2',
        },
      ];

      const output = configParser.parseAndEnrichConfig(
        JSON.stringify(userConfig)
      );

      expect(output.length).toEqual(2);
      expect(output[0].info).toEqual({
        projectId: 'project-123',
        regionId: 'us-central1',
        resourcePath: 'projects/project-123/locations/us-central1',
      });
      expect(output[1].info).toEqual({
        projectId: 'project-456',
        regionId: 'us-central2',
        resourcePath: 'projects/project-456/locations/us-central2',
      });
    });

    it('should add default values', () => {
      const userConfig = [
        {
          projectId: 'project-123',
          regionId: 'us-central1',
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
            resourcePath: 'projects/project-123/locations/us-central1',
          },
          scalingConfig: {
            units: undefined,
            minSize: 1,
            maxSize: 100,
            scalingMethod: 'LINEAR',
            scalingProfile: undefined,
            scalingRules: undefined,
            stepSize: 2,
            scaleInLimit: 3,
            scaleOutLimit: 4,
            scaleInCoolingMinutes: 15,
            scaleOutCoolingMinutes: 30,
            scalerPubSubTopic: 'projects/x/topics/default-scaler-topic',
            downstreamPubSubTopic: 'projects/x/topics/default-downstream-topic',
          },
          stateConfig: {
            stateProjectId: 'default-project',
            stateDatabase: {
              name: 'firestore',
              instanceId: 'default-state-instance',
              databaseId: 'default-state-database',
            },
          },
        },
      ]);
    });

    // Extensives checks are done on config-validator.
    it('should fail for invalid schema config', () => {
      const userConfig = '[]';
      const expectedError = new ValidationError(
        'Invalid Autoscaler Configuration parameters:\n' +
          'AutoscalerConfig must NOT have fewer than 1 items'
      );

      expect(() => {
        configParser.parseAndEnrichConfig(userConfig);
      }).toThrow(expectedError);
    });

    it('should fail for invalid instance config: minSize > maxSize', () => {
      const userConfig = [
        {
          projectId: 'project-123',
          regionId: 'us-central1',
          minSize: 5,
          maxSize: 3,
        },
      ];
      const userConfigStr = JSON.stringify(userConfig);
      const expectedError = new ValidationError(
        'INVALID CONFIG: minSize (5) is larger than maxSize (3).'
      );

      expect(() => {
        configParser.parseAndEnrichConfig(userConfigStr);
      }).toThrow(expectedError);
    });
  });
});
