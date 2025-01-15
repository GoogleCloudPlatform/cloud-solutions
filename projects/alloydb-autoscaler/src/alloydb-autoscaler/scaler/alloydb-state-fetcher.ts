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

/** @fileoverview Fetches scaling operations state. */

import pino from 'pino';
import {google as GoogleApis, alloydb_v1} from 'googleapis';
import {LIB_NAME, LIB_SCALER_VERSION} from '../common/libs';
import {CounterManager} from '../../autoscaler-core/common/counters';
import {StateData} from '../../autoscaler-core/scaler/state-stores/state';
import {
  IStateFetcher,
  StateFetcher,
} from '../../autoscaler-core/scaler/state-fetcher';
import {ScalingOperationReporter} from '../../autoscaler-core/scaler/scaling-operation-reporter';

const ALLOYDB_OPERATION_TYPE_REGEXP = new RegExp(
  'type.googleapis.com/google.cloud.alloydb.[a-zA-Z0-9]+.' + 'OperationMetadata'
);

export type AlloyDbOperationState = alloydb_v1.Schema$Operation;

/** Fetches scaling operations state. */
export class AlloyDbStateFetcher extends StateFetcher implements IStateFetcher {
  protected alloyDbRestApi: alloydb_v1.Alloydb;

  constructor(
    baseLogger: pino.Logger,
    counterManager: CounterManager,
    // Testing only.
    scalingOperationReporter?: ScalingOperationReporter,
    alloyDbRestApi?: alloydb_v1.Alloydb
  ) {
    scalingOperationReporter =
      scalingOperationReporter ??
      new ScalingOperationReporter(baseLogger, counterManager);
    super(baseLogger, ALLOYDB_OPERATION_TYPE_REGEXP, scalingOperationReporter);

    this.alloyDbRestApi =
      alloyDbRestApi ??
      GoogleApis.alloydb({
        version: 'v1',
        auth: new GoogleApis.auth.GoogleAuth({
          scopes: ['https://www.googleapis.com/auth/cloud-platform'],
        }),
        // This adds a user-agent header in the format
        // "cloud-solutions/alloydb-autoscaler-scaler-usage-v999"
        userAgentDirectives: [
          {
            product: LIB_NAME,
            version: LIB_SCALER_VERSION,
          },
        ],
      });
  }

  /** Fetches Operation state from the API. */
  protected async fetchOperationStateFromApi(
    autoscalerState: StateData
  ): Promise<AlloyDbOperationState> {
    const operationResponse =
      this.alloyDbRestApi.projects.locations.operations.get({
        name: autoscalerState.scalingOperationId ?? '',
      });
    const operationOutput = await operationResponse;
    const {data: operationState} = operationOutput;
    return operationState;
  }
}
