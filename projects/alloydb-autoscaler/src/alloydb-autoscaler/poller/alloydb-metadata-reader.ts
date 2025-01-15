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

import pino from 'pino';
import {AlloyDBAdminClient} from '@google-cloud/alloydb';
import {MetadataValueMap} from '../../autoscaler-core/common/instance-info';
import {
  MetadataReader,
  MetadataReaderFactory,
} from '../../autoscaler-core/poller/metadata-reader';
import {AlloyDbScalableInstance} from '../common/alloydb-instance-info';
import {getInstanceLogger} from '../../autoscaler-core/common/logger';

/** @fileoverview Provides a metadata reader for AlloyDB. */

/** Reads Metadata from an AlloyDB instance. */
export class AlloyDbMetadataReader implements MetadataReader {
  constructor(
    protected instance: AlloyDbScalableInstance,
    protected alloyDbClient: AlloyDBAdminClient,
    protected logger: pino.Logger
  ) {}

  /** Gets AlloyDB instance metadata. */
  async getMetadata(): Promise<MetadataValueMap> {
    this.logger.info({
      message: `----- ${this.instance.info.resourcePath}: Metadata -----`,
    });

    const response = await this.alloyDbClient.getInstance({
      name: this.instance.info.resourcePath,
    });
    if (!response || !Array.isArray(response)) {
      throw new Error(
        'Unable to read metadata from AlloyDB instance ' +
          this.instance.info.resourcePath
      );
    }

    const [instance] = response;
    if (!instance) {
      throw new Error(
        'Unable to read metadata from AlloyDB instance ' +
          this.instance.info.resourcePath
      );
    }

    const instanceType = instance?.instanceType;
    const nodeCount = instance?.readPoolConfig?.nodeCount;
    const cpuCount = instance?.machineConfig?.cpuCount;

    this.logger.debug({message: `instanceType: ${instanceType}`});
    this.logger.debug({message: `nodeCount: ${nodeCount}`});
    this.logger.debug({message: `cpuCount: ${cpuCount}`});

    if (instanceType !== 'READ_POOL') {
      throw new Error(
        'Only AlloyDB read pool instances are currently supported. ' +
          `Instance ${this.instance.info.resourcePath} is of type ` +
          instanceType
      );
    }

    if (!nodeCount) {
      throw new Error(
        'Unable to read current node count for AlloyDB instance ' +
          this.instance.info.resourcePath
      );
    }

    return {
      currentSize: nodeCount,
      nodeCount: nodeCount,
      cpuCount: cpuCount ?? 0,
      instanceType: instance.instanceType ?? '',
    };
  }
}

/** Provides a MetadataReader for AlloyDB. */
export class AlloyDbMetadataReaderFactory implements MetadataReaderFactory {
  constructor(
    protected alloyDbClient: AlloyDBAdminClient,
    protected baseLogger: pino.Logger
  ) {}

  /** Builds a MetadataReader for AlloyDB instances. */
  buildMetadataReader(instance: AlloyDbScalableInstance): MetadataReader {
    const instanceLogger = getInstanceLogger(this.baseLogger, instance);

    return new AlloyDbMetadataReader(
      instance,
      this.alloyDbClient,
      instanceLogger
    );
  }
}
