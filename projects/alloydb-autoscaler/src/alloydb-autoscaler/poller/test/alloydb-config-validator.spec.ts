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

import {
  ConfigValidator,
  ValidationError,
} from '../../../autoscaler-core/poller/config-validator';
import alloyDbAutoscalerConfig from '../../schema/alloydb-autoscaler-config.json';
import alloyDbAutoscalerInstance from '../../schema/alloydb-autoscaler-instance.json';
import autoscalerCoreDefs from '../../../autoscaler-core/schema/autoscaler-core-defs.json';
import autoscalerRulesDefs from '../../../autoscaler-core/schema/autoscaler-scaling-rules-defs.json';

/**
 * Tests config validator with the alloydb-autoscaler-config.json schema.
 *
 * config-validator has its own unit tests, but this ensures that the custom
 * AlloyDB schema is working as expected in the config-validator.
 */

describe('ConfigValidator with alloydb-autoscaler-config.json', () => {
  const configValidator = new ConfigValidator(alloyDbAutoscalerConfig, [
    alloyDbAutoscalerInstance,
    autoscalerCoreDefs,
    autoscalerRulesDefs,
  ]);

  it('returns parsed value for valid config', () => {
    const configToValidate = `
      [
        {
          "projectId": "my-project",
          "regionId": "us-central1",
          "clusterId": "cluster-id",
          "instanceId": "instance-id",
          "minSize": 10
        }
      ]`;

    const output = configValidator.parseAndAssertValidConfig(configToValidate);

    expect(output).toEqual(JSON.parse(configToValidate));
  });

  [
    // Basic cases (e.g. bad JSON) will not be tested as those have been tested
    // in the config-validator tests. These are only tests relevant to the
    // AlloyDB autoscaler schema.
    {
      testCaseName: 'generic autoscaler config',
      // Lacks required parameters: clusterId, instanceId.
      configToValidate: `[
          {
            "projectId": "my-project",
            "regionId": "us-central1"
          }
        ]`,
      expectedError: new ValidationError(
        'Invalid Autoscaler Configuration parameters:\n' +
          "AutoscalerConfig/0 must have required property 'clusterId'\n" +
          "AutoscalerConfig/0 must have required property 'instanceId'"
      ),
    },
    {
      testCaseName: 'config with extra parameters',
      configToValidate: `
        [
          {
            "projectId": "my-project",
            "regionId": "us-central1",
            "clusterId": "cluster-id",
            "instanceId": "instance-id",
            "additionalInvalidProperty": "value"
          }
        ]`,
      expectedError: new ValidationError(
        'Invalid Autoscaler Configuration parameters:\n' +
          'AutoscalerConfig/0 must NOT have additional properties'
      ),
    },
    {
      testCaseName: 'config with parameters with bad values',
      configToValidate: `
        [
          {
            "projectId": "a",
            "regionId": "us-central",
            "clusterId": "x",
            "instanceId": 123
          }
        ]`,
      expectedError: new ValidationError(
        'Invalid Autoscaler Configuration parameters:\n' +
          'AutoscalerConfig/0/projectId ' +
          'must NOT have fewer than 2 characters\n' +
          'AutoscalerConfig/0/clusterId ' +
          'must NOT have fewer than 2 characters\n' +
          'AutoscalerConfig/0/instanceId must be string'
      ),
    },
  ].forEach(({testCaseName, configToValidate, expectedError}) => {
    it(`fails for ${testCaseName}`, () => {
      expect(() => {
        configValidator.parseAndAssertValidConfig(configToValidate);
      }).toThrow(expectedError);
    });
  });
});
