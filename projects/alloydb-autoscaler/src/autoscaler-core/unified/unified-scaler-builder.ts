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

/** @fileoverview Provides the entrypoint for the GKE unified Autoscaler. */

import pino from 'pino';
import * as fs from 'node:fs';
import yaml from 'js-yaml';
import {LIB_VERSION_NUMBER} from '../../alloydb-autoscaler/common/libs';
import {
  BaseEntrypointBuilder,
  EntrypointHandler,
} from '../common/entrypoint-builder';
import {LocalPollerHandler} from '../poller/poller-builder';

/** Entrypoint for the Unified Autoscaler for the GKE (local) use case. */
export type LocalUnifiedHandler = () => Promise<void>;

const DEFAULT_CONFIG_LOCATION = '/etc/autoscaler-config/autoscaler-config.yaml';

export class UnifiedScalerFunctionBuilder extends BaseEntrypointBuilder {
  /**
   * Initializes UnifiedScalerFunctionBuilder.
   *
   * @param defaultConfigLocation Location of the YAML file with the
   *  configuration. This is overriden if AUTOSCALER_CONFIG env is passed.
   * @param baseLogger Logger for event management.
   * @param counterManager Counter Manager to use for Kubernetes.
   */
  constructor(
    protected baseLogger: pino.Logger,
    protected pollerEntrypoint: LocalPollerHandler,
    protected scalerEntrypoint: EntrypointHandler,
    protected defaultConfigLocation: string = DEFAULT_CONFIG_LOCATION
  ) {
    super();
  }

  buildRequestHandler(): LocalUnifiedHandler {
    /**
     * Handles metrics polling and scaling in a single unified endpoint.
     */
    return async () => {
      this.baseLogger.info(
        `Autoscaler unified Poller/Scaler v${LIB_VERSION_NUMBER} job started`
      );

      let configLocation = this.defaultConfigLocation;
      if (process.env.AUTOSCALER_CONFIG) {
        /*
         * If set, the AUTOSCALER_CONFIG environment variable is used to
         * retrieve the configuration for this instance of the Poller.
         * Please refer to the documentation in the README.md for GKE
         * deployment for more details.
         */
        configLocation = process.env.AUTOSCALER_CONFIG;
        this.baseLogger.debug(`Using custom config location ${configLocation}`);
      } else {
        this.baseLogger.debug(
          `Using default config location ${configLocation}`
        );
      }

      try {
        const config = await fs.readFileSync(configLocation, 'utf8');
        const instances = await this.pollerEntrypoint(
          JSON.stringify(yaml.load(config))
        );

        for (const instance of instances) {
          await this.scalerEntrypoint(JSON.stringify(instance));
        }
      } catch (e) {
        this.baseLogger.error({
          message: `Error in unified poller/scaler wrapper: ${e}`,
          err: e,
        });
      }
    };
  }
}
