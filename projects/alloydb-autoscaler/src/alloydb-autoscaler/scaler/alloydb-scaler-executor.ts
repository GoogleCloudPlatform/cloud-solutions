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

/** @fileoverview Executes a scaling request for an AlloyDB read pool. */

import pino from 'pino';
import {AlloyDBAdminClient} from '@google-cloud/alloydb';
import {getUnitsText} from '../../autoscaler-core/common/instance-info';
import {IScalerExecutor} from '../../autoscaler-core/scaler/scaler-executor';
import {getPayloadLogger} from '../../autoscaler-core/common/logger';
import {AlloyDbScalableInstanceWithData} from '../common/alloydb-instance-info';

/** @inheritdoc */
export class AlloyDbScalerExecutor implements IScalerExecutor {
  constructor(
    protected baseLogger: pino.Logger,
    protected alloyDbClient: AlloyDBAdminClient
  ) {}

  /** @inheritdoc */
  async scaleInstance(
    instance: AlloyDbScalableInstanceWithData,
    suggestedSize: number
  ): Promise<string | null> {
    if (!instance?.info?.resourcePath) {
      throw new Error(
        'No resource path specified for instance. Unable to scale'
      );
    }

    if (instance?.metadata?.instanceType !== 'READ_POOL') {
      throw new Error(
        'Only AlloyDB read pool instances are currently supported. ' +
          `Instance ${instance.info.resourcePath} is of type ` +
          `${instance?.metadata?.instanceType}`
      );
    }

    const payloadLogger = getPayloadLogger(this.baseLogger, instance, instance);
    payloadLogger.info({
      message:
        `----- ${instance.info.resourcePath}: ` +
        'Scaling AlloyDB read pool instance to ' +
        `${suggestedSize}${getUnitsText(instance)} -----`,
    });

    const scaleRequest = {
      instance: {
        name: instance.info.resourcePath,
        readPoolConfig: {nodeCount: suggestedSize},
      },
      updateMask: {paths: ['read_pool_config.node_count']},
    };

    const response = await this.alloyDbClient.updateInstance(scaleRequest);
    if (!response || !Array.isArray(response)) {
      throw new Error(
        `Executing scaling operation to ${suggestedSize} for ` +
          `${instance.info.resourcePath} failed for unknown reasons`
      );
    }

    const [operation] = response;
    if (!operation) {
      throw new Error(
        `Executing scaling operation to ${suggestedSize} for ` +
          `${instance.info.resourcePath} failed for unknown reasons`
      );
    }

    if (!operation?.name) {
      payloadLogger.error({
        message:
          `Scaling operation for ${instance.info.resourcePath} returned an ` +
          'empty operation name. Operation may not be running',
      });
    } else {
      payloadLogger.debug({
        message: `Started the scaling operation: ${operation.name}`,
      });
    }

    return operation?.name ?? null;
  }
}
