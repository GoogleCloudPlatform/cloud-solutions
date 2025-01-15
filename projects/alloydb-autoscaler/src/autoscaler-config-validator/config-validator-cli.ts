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
import * as yaml from 'js-yaml';
import * as fs from 'node:fs';
import {
  ConfigValidator,
  ValidationError,
} from '../autoscaler-core/poller/config-validator';

/**
 * Validates the specified Autoscaler JSON configuration file.
 * Throws an Error and reports to console if the config is not valid.
 * @param configValidator Config Validator to use for validation.
 * @param filename Filepath of the JSON file to validate.
 */
function assertValidJsonFile(
  configValidator: ConfigValidator,
  filename: string
) {
  try {
    const configText = fs.readFileSync(filename, 'utf-8');
    configValidator.parseAndAssertValidConfig(configText);
  } catch (e) {
    if (e instanceof ValidationError) {
      console.error(
        `Validation of config in file ${filename} failed:\n${e.message}`
      );
    } else {
      console.error(`Processing of config in file ${filename} failed: ${e}`);
    }
    throw new Error(`${filename} Failed validation`);
  }
}

/**
 * Validates all the Autoscaler YAML config files specified in the
 * GKE configMap. Throws an Error and reports to console if any of the
 * configmaps do not pass validation.
 * @param configValidator Config Validator to use for validation.
 * @param filename Filepath of the GKE config map file to validate.
 */
function assertValidGkeConfigMapFile(
  configValidator: ConfigValidator,
  filename: string
) {
  // Allow any type since the configMap is not in our control.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let configMap: any;

  try {
    const configText = fs.readFileSync(filename, 'utf-8');
    configMap = yaml.load(configText) as object;
  } catch (e) {
    console.error(`Could not parse YAML from ${filename}: ${e}`);
    throw e;
  }

  if (configMap?.kind !== 'ConfigMap') {
    console.error(`${filename} is not a GKE ConfigMap`);
    throw new Error(`${filename} is not a GKE ConfigMap`);
  }

  let success = true;
  for (const configMapFile of Object.keys(configMap?.data)) {
    const configMapData = configMap?.data[configMapFile];
    try {
      const config = yaml.load(configMapData);
      configValidator.parseAndAssertValidConfig(JSON.stringify(config));
    } catch (e) {
      if (e instanceof ValidationError) {
        console.error(
          `Validation of configMap entry data.${configMapFile} in file ` +
            `${filename} failed:\n${e.message}`
        );
      } else if (e instanceof yaml.YAMLException) {
        console.error(
          'Could not parse YAML from value data. ' +
            `${configMapFile} in ${filename}: ${e}`
        );
      } else {
        console.error(
          `Processing of configMap entry data.${configMapFile} in file ` +
            `${filename} failed: ${e}`
        );
      }
      success = false;
    }
  }
  if (!success) {
    throw new Error(`${filename} Failed validation`);
  }
}

/**
 * Validates a configuration file is valid.
 * @param configValidator Config Validator to use for validation.
 * @param filename Filepath of the GKE config map file to validate.
 */
function validateFile(configValidator: ConfigValidator, filename: string) {
  if (filename.toLowerCase().endsWith('.yaml')) {
    assertValidGkeConfigMapFile(configValidator, filename);
  } else if (filename.toLowerCase().endsWith('.json')) {
    assertValidJsonFile(configValidator, filename);
  } else {
    throw new Error(
      `filename ${filename} must either be JSON (.json) or a YAML ` +
        'configmap (.yaml) file'
    );
  }
}

/**
 * Validates a configuration file passed in on the command line.
 *
 * Usage:
 * validate-config-file <CONFIG_FILE_NAME>
 *
 * TODO: decide how to create CLI validators for derived configs (e.g. AlloyDB).
 * @param configValidator Config validator to use for validation.
 */
export function main(configValidator: ConfigValidator = new ConfigValidator()) {
  if (
    process.argv.length <= 1 ||
    process.argv[1] === '-h' ||
    process.argv[1] === '--help'
  ) {
    console.log('Usage: validate-config-file CONFIG_FILE_NAME');
    console.log(
      'Validates that the specified Autoscaler JSON config is defined ' +
        'correctly'
    );
    process.exitCode = 1;
    return;
  }

  const filename = process.argv[1];
  try {
    validateFile(configValidator, filename);
    process.exitCode = 0;
  } catch (e) {
    process.exitCode = 1;
    throw e;
  }
}

export const TEST_ONLY = {validateFile};
