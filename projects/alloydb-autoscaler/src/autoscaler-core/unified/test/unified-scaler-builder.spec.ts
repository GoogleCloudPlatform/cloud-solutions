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

/** @fileoverview Tests unified-scaler-builder. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import pino from 'pino';
import {silentLogger} from '../../testing/testing-framework';
import {EntrypointHandler} from '../../common/entrypoint-builder';
import {LocalPollerHandler} from '../../poller/poller-builder';
import {UnifiedScalerFunctionBuilder} from '../unified-scaler-builder';
import {ScalableInstanceWithData} from '../../common/instance-info';
import {TEST_INSTANCE_WITH_DATA} from '../../testing/testing-data';

describe('UnifiedScalerFunctionBuilder', () => {
  let logger: jasmine.SpyObj<pino.Logger>;
  let pollerEndpointMock: jasmine.Spy<LocalPollerHandler>;
  let scalerEndpointMock: jasmine.Spy<EntrypointHandler>;
  let unifiedBuilder: UnifiedScalerFunctionBuilder;

  beforeEach(() => {
    logger = silentLogger;
    pollerEndpointMock = jasmine.createSpy();
    scalerEndpointMock = jasmine.createSpy();

    pollerEndpointMock.and.callFake(async () => []);

    // const dir = 'src/autoscaler-config-validator/test/resources';
    unifiedBuilder = new UnifiedScalerFunctionBuilder(
      logger,
      pollerEndpointMock,
      scalerEndpointMock,
      'src/autoscaler-core/unified/test/testdata/default.yaml'
    );
  });

  afterEach(() => {
    delete process.env.AUTOSCALER_CONFIG;
  });

  describe('buildRequestHandler', () => {
    it('builds without errors', () => {
      unifiedBuilder.buildRequestHandler();
    });

    it('loads default config for poller', async () => {
      pollerEndpointMock.and.callFake(async () => {
        return [] as ScalableInstanceWithData[];
      });
      const unifiedEndpoint = unifiedBuilder.buildRequestHandler();

      await unifiedEndpoint();

      expect(pollerEndpointMock).toHaveBeenCalledOnceWith(
        JSON.stringify([
          {
            projectId: 'default',
            regionId: 'us-central1',
            scalerPubSubTopic: 'projects/default/topics/autoscaler-scaling',
            minSize: 5,
            maxSize: 30,
            scalingMethod: 'DIRECT',
          },
        ])
      );
    });

    it('loads env config for poller', async () => {
      pollerEndpointMock.and.callFake(async () => {
        return [] as ScalableInstanceWithData[];
      });
      unifiedBuilder.setEnvironmentVariables({
        AUTOSCALER_CONFIG: 'src/autoscaler-core/unified/test/testdata/env.yaml',
      });
      const unifiedEndpoint = unifiedBuilder.buildRequestHandler();

      await unifiedEndpoint();

      expect(pollerEndpointMock).toHaveBeenCalledOnceWith(
        JSON.stringify([
          {
            projectId: 'custom',
            regionId: 'us-central1',
            scalerPubSubTopic: 'projects/custom/topics/autoscaler-scaling',
            minSize: 3,
            maxSize: 10,
            scalingMethod: 'DIRECT',
          },
        ])
      );
    });

    it('calls scaler with expected instance data', async () => {
      pollerEndpointMock.and.callFake(async () => {
        return [TEST_INSTANCE_WITH_DATA, TEST_INSTANCE_WITH_DATA];
      });
      const unifiedEndpoint = unifiedBuilder.buildRequestHandler();

      await unifiedEndpoint();

      expect(scalerEndpointMock).toHaveBeenCalledTimes(2);
      expect(scalerEndpointMock).toHaveBeenCalledWith(
        JSON.stringify(TEST_INSTANCE_WITH_DATA)
      );
    });
  });
});
