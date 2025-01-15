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

import {
  AlloyDbInstanceInfo,
  AlloyDbScalableInstance,
  FlatAlloyDbInstanceConfiguration,
} from '../common/alloydb-instance-info';
import {ConfigParser} from '../../autoscaler-core/poller/config-parser';
import {
  ConfigValidator,
  ValidationError,
} from '../../autoscaler-core/poller/config-validator';
import alloyDbAutoscalerConfig from '../schema/alloydb-autoscaler-config.json';
import alloyDbAutoscalerInstance from '../schema/alloydb-autoscaler-instance.json';
import autoscalerCoreDefs from '../../autoscaler-core/schema/autoscaler-core-defs.json';
import autoscalerRulesDefs from '../../autoscaler-core/schema/autoscaler-scaling-rules-defs.json';

/** AlloyDB default config values. */
const DEFAULT_INSTANCE_CONFIG = Object.freeze({
  info: {}, // No defaults.
  scalingConfig: {
    units: 'NODES',
    minSize: 1,
    maxSize: 20,
    scalingMethod: 'STEPWISE',
    stepSize: 1,
    scaleInCoolingMinutes: 10,
    scaleOutCoolingMinutes: 10,
  },
  stateConfig: {}, // No defaults.
});

/** Maximum size of a read pool instance. */
const MAX_INSTANCE_SIZE = 20;

/**
 * Parser for the user provided configuration for AlloyDB autoscaler.
 */
export class AlloyDbConfigParser extends ConfigParser {
  constructor() {
    const configValidator = new ConfigValidator(alloyDbAutoscalerConfig, [
      alloyDbAutoscalerInstance,
      autoscalerCoreDefs,
      autoscalerRulesDefs,
    ]);
    super(configValidator, DEFAULT_INSTANCE_CONFIG);
  }

  /**
   * Adds defaults to AlloyDB instance information.
   * @param instanceConfig The parsed configuration for this instance.
   * @return AlloyDB Instance info based on the provided configuration.
   */
  protected addInstanceInfoDefaults(
    instanceConfig: FlatAlloyDbInstanceConfiguration
  ): AlloyDbInstanceInfo {
    const instanceInfo = super.addInstanceInfoDefaults(instanceConfig);
    return {
      ...instanceInfo,
      clusterId: instanceConfig.clusterId,
      instanceId: instanceConfig.instanceId,
      resourcePath:
        `projects/${instanceInfo.projectId}/` +
        `locations/${instanceInfo.regionId}/` +
        `clusters/${instanceConfig.clusterId}/` +
        `instances/${instanceConfig.instanceId}`,
    } as AlloyDbInstanceInfo;
  }

  /**
   * Performs additional validations on a given AlloyDB instance configuration.
   * @param instanceConfig AlloyDB instance to validate.
   */
  protected validateInstanceConfig(instanceConfig: AlloyDbScalableInstance) {
    super.validateInstanceConfig(instanceConfig);

    const maxSize = instanceConfig?.scalingConfig?.maxSize ?? 0;
    if (maxSize > MAX_INSTANCE_SIZE) {
      throw new ValidationError(
        `INVALID CONFIG: maxSize (${maxSize}) is larger than the maximum ` +
          `size of ${MAX_INSTANCE_SIZE}.`
      );
    }
  }

  // Methods where only typing is overriden.

  /**
   * See ConfigParser.addDefaultsToInstance.
   * @param instanceConfig
   */
  protected addDefaultsToInstance(
    instanceConfig: FlatAlloyDbInstanceConfiguration
  ): AlloyDbScalableInstance {
    return super.addDefaultsToInstance(
      instanceConfig
    ) as AlloyDbScalableInstance;
  }

  /**
   * See ConfigParser.addDefaultsToInstance.
   * @param configData
   */
  parseAndEnrichConfig(configData: string): AlloyDbScalableInstance[] {
    return super.parseAndEnrichConfig(configData) as AlloyDbScalableInstance[];
  }
}
