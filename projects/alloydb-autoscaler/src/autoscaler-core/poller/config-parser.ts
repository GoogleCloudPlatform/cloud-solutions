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

/** @fileoverview Provides a parser for Autoscaler configs. */

import {ConfigValidator, ValidationError} from './config-validator';
import {
  InstanceInfo,
  ScalableInstance,
  ScalingConfig,
  StateConfig,
} from '../common/instance-info';
import {FlatInstanceConfiguration} from '../common/instance-info';

/** Default values for the Instance config. */
export type DefaultInstanceConfig = {
  scalingConfig?: ScalingConfig;
  stateConfig?: StateConfig;
};

/** Parser for the Autoscaler configuration. */
export class ConfigParser {
  /**
   * Initializes config parser.
   * @param configValidator The Config Validator to use to validate config.
   * @param defaultInstanceConfig Generic configuration for not provided values.
   */
  constructor(
    protected configValidator: ConfigValidator = new ConfigValidator(),
    protected defaultInstanceConfig: DefaultInstanceConfig = {}
  ) {
    this.configValidator = configValidator;
    this.defaultInstanceConfig = defaultInstanceConfig;
  }

  /**
   * Parses user input configuration into a formatted ScalableInstance.
   * Adds default values where needed and possible.
   * @param configData Configuration from the user.
   * @return Parsed and enriched configuration.
   */
  parseAndEnrichConfig(configData: string): ScalableInstance[] {
    const parsedConfig =
      this.configValidator.parseAndAssertValidConfig(configData);

    return parsedConfig.map((instanceConfig: FlatInstanceConfiguration) => {
      const parsedInstanceConfig = this.addDefaultsToInstance(instanceConfig);
      this.validateInstanceConfig(parsedInstanceConfig);
      return parsedInstanceConfig;
    });
  }

  /**
   * Adds default values to the instance config.
   * @param instanceConfig The parsed configuration for this instance.
   * @return The formatted scaling configuration for one instance.
   */
  protected addDefaultsToInstance(
    instanceConfig: FlatInstanceConfiguration
  ): ScalableInstance {
    return {
      info: this.addInstanceInfoDefaults(instanceConfig),
      scalingConfig: this.addInstanceScaleDefaults(instanceConfig),
      stateConfig: this.addInstanceStateDefaults(instanceConfig),
    } as ScalableInstance;
  }

  /**
   * Adds defaults to instance information.
   * @param instanceConfig The parsed configuration for this instance.
   * @return Instance info based on the provided configuration.
   */
  protected addInstanceInfoDefaults(
    instanceConfig: FlatInstanceConfiguration
  ): InstanceInfo {
    return {
      projectId: instanceConfig.projectId,
      regionId: instanceConfig.regionId,
      resourcePath:
        instanceConfig.resourcePath ??
        `projects/${instanceConfig.projectId}/` +
          `locations/${instanceConfig.regionId}`,
    } as InstanceInfo;
  }

  /**
   * Adds defaults to scaling configuration.
   * @param instanceConfig The parsed configuration for this instance.
   * @return Scaling configuration based on the provided input and defaults.
   */
  protected addInstanceScaleDefaults(
    instanceConfig: FlatInstanceConfiguration
  ): ScalingConfig {
    return {
      units:
        instanceConfig?.units ??
        this.defaultInstanceConfig.scalingConfig?.units,
      minSize:
        instanceConfig?.minSize ??
        this.defaultInstanceConfig?.scalingConfig?.minSize,
      maxSize:
        instanceConfig?.maxSize ??
        this.defaultInstanceConfig?.scalingConfig?.maxSize,
      scalingMethod:
        instanceConfig?.scalingMethod ??
        this.defaultInstanceConfig?.scalingConfig?.scalingMethod,
      scalingProfile:
        instanceConfig?.scalingProfile ??
        this.defaultInstanceConfig?.scalingConfig?.scalingProfile,
      scalingRules:
        instanceConfig?.scalingRules ??
        this.defaultInstanceConfig?.scalingConfig?.scalingRules,
      stepSize:
        instanceConfig?.stepSize ??
        this.defaultInstanceConfig?.scalingConfig?.stepSize,
      scaleInLimit:
        instanceConfig?.scaleInLimit ??
        this.defaultInstanceConfig?.scalingConfig?.scaleInLimit,
      scaleOutLimit:
        instanceConfig?.scaleOutLimit ??
        this.defaultInstanceConfig?.scalingConfig?.scaleOutLimit,
      scaleInCoolingMinutes:
        instanceConfig?.scaleInCoolingMinutes ??
        this.defaultInstanceConfig?.scalingConfig?.scaleInCoolingMinutes,
      scaleOutCoolingMinutes:
        instanceConfig?.scaleOutCoolingMinutes ??
        this.defaultInstanceConfig?.scalingConfig?.scaleOutCoolingMinutes,
      scalerPubSubTopic:
        instanceConfig?.scalerPubSubTopic ??
        this.defaultInstanceConfig?.scalingConfig?.scalerPubSubTopic,
      downstreamPubSubTopic:
        instanceConfig?.downstreamPubSubTopic ??
        this.defaultInstanceConfig?.scalingConfig?.downstreamPubSubTopic,
    } as ScalingConfig;
  }

  /**
   * Adds defaults to state configuration.
   * @param instanceConfig The parsed configuration for this instance.
   * @return State configuration based on the provided input and defaults.
   */
  protected addInstanceStateDefaults(
    instanceConfig: FlatInstanceConfiguration
  ): StateConfig {
    return {
      stateProjectId:
        instanceConfig?.stateProjectId ??
        this.defaultInstanceConfig?.stateConfig?.stateProjectId,
      stateDatabase:
        instanceConfig?.stateDatabase ??
        this.defaultInstanceConfig?.stateConfig?.stateDatabase,
    } as StateConfig;
  }

  /**
   * Performs additional validations on a given instance configuration.
   *
   * These are business logic rules for the configuration, which are different
   * to what the config validator provides.
   * @param instanceConfig Instance to validate.
   */
  protected validateInstanceConfig(instanceConfig: ScalableInstance) {
    const minSize = instanceConfig?.scalingConfig?.minSize ?? 0;
    // minSize >= 1 is validated on the configValidator.
    const maxSize = instanceConfig?.scalingConfig?.maxSize ?? 0;
    if (minSize > maxSize) {
      throw new ValidationError(
        'INVALID CONFIG: ' +
          `minSize (${minSize}) is larger than maxSize (${maxSize}).`
      );
    }
  }
}
