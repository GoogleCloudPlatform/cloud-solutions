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
 * limitations under the License
 */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import {ConfigValidator, ValidationError} from '../config-validator';
import autoscalerConfig from '../../schema/autoscaler-config.json';
import autoscalerInstanceConfig from '../../schema/autoscaler-instance.json';
import autoscalerCoreDefs from '../../schema/autoscaler-core-defs.json';
import autoscalerRulesDefs from '../../schema/autoscaler-scaling-rules-defs.json';

describe('ConfigValidator', () => {
  [
    {
      testSuiteName: 'default validator',
      configValidator: new ConfigValidator(),
    },
    {
      testSuiteName: 'validator with custom schemas',
      // These schemas are the same as the default, so the same tests can be
      // run. However, this is done to test that assigning them dynamically also
      // works and validates in the same way.
      configValidator: new ConfigValidator(autoscalerConfig, [
        autoscalerInstanceConfig,
        autoscalerCoreDefs,
        autoscalerRulesDefs,
      ]),
    },
  ].forEach(({testSuiteName, configValidator}) => {
    describe(testSuiteName, () => {
      it('returns parsed value for valid configs', () => {
        const configToValidate = `
          [
            {
              "$comment": "Sample autoscaler config",
              "projectId": "my-project",
              "regionId": "us-central1",
              "scalerPubSubTopic": "projects/my-project/topics/scaler-topic",
              "minSize": 3,
              "maxSize": 10
            }
          ]`;

        const output =
          configValidator.parseAndAssertValidConfig(configToValidate);

        expect(output).toEqual(JSON.parse(configToValidate));
      });

      [
        {
          testCaseName: 'invalid JSON',
          configToValidate: 'wrong content',
          expectedError: new Error(
            'Invalid JSON in Autoscaler configuration:\nSyntaxError: ' +
              'Unexpected token \'w\', "wrong content" is not valid JSON'
          ),
        },
        {
          testCaseName: 'config is empty',
          configToValidate: '',
          expectedError: new Error(
            'Invalid JSON in Autoscaler configuration:\n' +
              'SyntaxError: Unexpected end of JSON input'
          ),
        },
        {
          testCaseName: 'config is not an array',
          configToValidate: '{}',
          expectedError: new ValidationError(
            'Invalid Autoscaler Configuration parameters:\n' +
              'AutoscalerConfig must be array'
          ),
        },
        {
          testCaseName: 'config is an empty array',
          configToValidate: '[]',
          expectedError: new ValidationError(
            'Invalid Autoscaler Configuration parameters:\n' +
              'AutoscalerConfig must NOT have fewer than 1 items'
          ),
        },
        {
          testCaseName: 'config does not contain required properties',
          configToValidate: '[{}]',
          expectedError: new ValidationError(
            'Invalid Autoscaler Configuration parameters:\n' +
              "AutoscalerConfig/0 must have required property 'projectId'\n" +
              "AutoscalerConfig/0 must have required property 'regionId'"
          ),
        },
        {
          testCaseName: 'config contains invalid properties',
          configToValidate: `[{
            "projectId": "my-project",
            "regionId": "us-central1",
            "invalidProp": "a-value"
          }]`,
          expectedError: new ValidationError(
            'Invalid Autoscaler Configuration parameters:\n' +
              'AutoscalerConfig/0 must NOT have additional properties'
          ),
        },
        {
          testCaseName: 'config contains invalid property values',
          configToValidate: `[{
            "projectId": "my-project",
            "regionId": "us-central1",
            "minSize": "should-be-a-number"
          }]`,
          expectedError: new ValidationError(
            'Invalid Autoscaler Configuration parameters:\n' +
              'AutoscalerConfig/0/minSize must be number'
          ),
        },
      ].forEach(({testCaseName, configToValidate, expectedError}) => {
        it(`fails when ${testCaseName}`, () => {
          expect(() => {
            configValidator.parseAndAssertValidConfig(configToValidate);
          }).toThrow(expectedError);
        });
      });
    });
  });
});
