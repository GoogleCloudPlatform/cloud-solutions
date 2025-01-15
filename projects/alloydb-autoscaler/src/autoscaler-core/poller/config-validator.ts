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

/**
 * @fileoverview Validates a given configuration against the JSON schema.
 */

import Ajv, {ValidateFunction} from 'ajv';
import {FlatInstanceConfiguration} from '../common/instance-info';
import autoscalerConfig from '../schema/autoscaler-config.json';
import autoscalerInstanceConfig from '../schema/autoscaler-instance.json';
import autoscalerCoreDefs from '../schema/autoscaler-core-defs.json';
import autoscalerRulesDefs from '../schema/autoscaler-scaling-rules-defs.json';

/** Error thrown when validation fails. */
export class ValidationError extends Error {}

/** Encapsulates the Ajv validator initialization and checks. */
export class ConfigValidator {
  protected ajv: Ajv;
  protected validateConfig: ValidateFunction;

  /**
   * Creates the class launches async initialization.
   * @param mainSchema JSON config schema to use to validate.
   * @param otherSchemas Additional schemas with definitions.
   */
  constructor(
    // TODO: The type here should be JSONSchemaType.
    // This is not currently possible as it may not be known what is the output
    // type. JSONSchemaType also does not seem to support any.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    mainSchema: /* JSONSchemaType<T> */ any = autoscalerConfig,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    otherSchemas: /* JSONSchemaType<?> */ any[] = [
      autoscalerInstanceConfig,
      autoscalerCoreDefs,
      autoscalerRulesDefs,
    ]
  ) {
    this.ajv = new Ajv({allErrors: true});
    for (const schema of otherSchemas) {
      this.ajv = this.ajv.addSchema(schema);
    }
    this.validateConfig = this.ajv.compile(mainSchema);
  }

  /**
   * Validates the given object against the config schema.
   * @param instancesConfig to validate.
   */
  private assertValidConfig(instancesConfig: object[]) {
    const valid = this.validateConfig(instancesConfig);
    if (!valid) {
      throw new ValidationError(
        'Invalid Autoscaler Configuration parameters:\n' +
          this.ajv.errorsText(this.validateConfig.errors, {
            separator: '\n',
            dataVar: 'AutoscalerConfig',
          })
      );
    }
  }

  /**
   * Parses the given string as JSON and validate it against the
   * AutoscalerConfig schema. Throws an Error if the config is not valid.
   * @param jsonString Configuration in string format from the user.
   * @return Parsed configuration.
   */
  parseAndAssertValidConfig(jsonString: string): FlatInstanceConfiguration[] {
    let configJson;
    try {
      configJson = JSON.parse(jsonString);
    } catch (e) {
      throw new Error(`Invalid JSON in Autoscaler configuration:\n${e}`);
    }
    this.assertValidConfig(configJson);
    return configJson;
  }
}
