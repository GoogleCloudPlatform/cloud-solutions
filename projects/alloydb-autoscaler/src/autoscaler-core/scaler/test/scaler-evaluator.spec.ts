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

/** @fileoverview Tests scaler-evaluator. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import {ScalerEvaluator} from '../scaler-evaluator';
import {silentLogger} from '../../testing/testing-framework';
import {IStateStore, StateData} from '../state-stores/state';
import {CounterManager} from '../../common/counters';
import {IStateFetcher} from '../state-fetcher';
import {
  TEST_INSTANCE_WITH_DATA,
  TEST_STATE_DATA,
  TEST_CUSTOM_RULE_OUT,
} from '../../testing/testing-data';
import {IRulesManager} from '../scaler-rules-manager';
import {IScalingMethodRunner} from '../scaling-methods/scaling-method-runner';
import {ScalableInstanceWithData} from '../../common/instance-info';

describe('ScalerEvaluator', () => {
  let scalerEvaluator: ScalerEvaluator;
  let stateStoreMock: jasmine.SpyObj<IStateStore>;
  let counterManagerMock: jasmine.SpyObj<CounterManager>;
  let stateFetcherMock: jasmine.SpyObj<IStateFetcher>;
  let rulesManagerMock: jasmine.SpyObj<IRulesManager>;
  let scalingMethodRunner: jasmine.SpyObj<IScalingMethodRunner>;
  const fixedTimestamp = Math.pow(10, 7);

  beforeEach(() => {
    // Required for checking within cooldown times.
    jasmine.clock().install().mockDate(new Date(fixedTimestamp));

    stateStoreMock = jasmine.createSpyObj('StateStore', [
      'getState',
      'updateState',
    ]);
    counterManagerMock = jasmine.createSpyObj('CounterManager', [
      'incrementCounter',
      'recordValue',
    ]);
    stateFetcherMock = jasmine.createSpyObj('StateFetcher', [
      'fetchOperationState',
    ]);
    rulesManagerMock = jasmine.createSpyObj('RulesManager', ['getRules']);
    scalingMethodRunner = jasmine.createSpyObj('ScalerMethodRunner', [
      'getSuggestedSize',
    ]);

    scalerEvaluator = new ScalerEvaluator(
      silentLogger,
      stateStoreMock,
      counterManagerMock,
      stateFetcherMock,
      rulesManagerMock,
      scalingMethodRunner
    );
  });

  afterEach(() => {
    jasmine.clock().uninstall();
  });

  describe('processScalingRequest', () => {
    it('stores state if updated', async () => {
      const newStateData: StateData = {
        ...TEST_STATE_DATA,
        scalingOperationId: null,
      };
      stateStoreMock.getState.and.callFake(async () => TEST_STATE_DATA);
      stateFetcherMock.fetchOperationState.and.callFake(async () => [
        newStateData,
        true,
      ]);
      scalingMethodRunner.getSuggestedSize.and.callFake(async () => 100);

      await scalerEvaluator.processScalingRequest(TEST_INSTANCE_WITH_DATA);

      expect(stateStoreMock.updateState).toHaveBeenCalledOnceWith(newStateData);
    });

    it('does not fetch or store state if no operation id', async () => {
      const stateWithNoOperationId = {
        ...TEST_STATE_DATA,
        scalingOperationId: null,
      };
      stateStoreMock.getState.and.callFake(async () => stateWithNoOperationId);
      scalingMethodRunner.getSuggestedSize.and.callFake(async () => 100);

      await scalerEvaluator.processScalingRequest(TEST_INSTANCE_WITH_DATA);

      expect(stateFetcherMock.fetchOperationState).not.toHaveBeenCalled();
      expect(stateStoreMock.updateState).not.toHaveBeenCalled();
    });

    it('does not store state if not updated', async () => {
      stateStoreMock.getState.and.callFake(async () => TEST_STATE_DATA);
      stateFetcherMock.fetchOperationState.and.callFake(async () => [
        TEST_STATE_DATA,
        false,
      ]);

      await scalerEvaluator.processScalingRequest(TEST_INSTANCE_WITH_DATA);

      expect(stateStoreMock.updateState).not.toHaveBeenCalled();
    });

    it('does not scale if scaling operation is in progress', async () => {
      const stateData = {...TEST_STATE_DATA, scalingOperationId: 'id-123'};
      stateStoreMock.getState.and.callFake(async () => stateData);
      stateFetcherMock.fetchOperationState.and.callFake(async () => [
        stateData,
        false,
      ]);

      const [isScalingPossible] = await scalerEvaluator.processScalingRequest(
        TEST_INSTANCE_WITH_DATA
      );

      expect(isScalingPossible).toBeFalse();
      expect(counterManagerMock.incrementCounter).toHaveBeenCalledOnceWith(
        'scaler/scaling-denied',
        TEST_INSTANCE_WITH_DATA,
        {
          scaling_denied_reason: 'IN_PROGRESS',
          scaling_method: 'DIRECT',
          scaling_direction: 'SCALE_SAME',
        }
      );
    });

    it('does not scale if suggested size is current size', async () => {
      const stateData = {...TEST_STATE_DATA, scalingOperationId: null};
      stateStoreMock.getState.and.callFake(async () => stateData);
      stateFetcherMock.fetchOperationState.and.callFake(async () => [
        stateData,
        false,
      ]);
      scalingMethodRunner.getSuggestedSize.and.callFake(
        async () => TEST_INSTANCE_WITH_DATA.metadata.currentSize
      );

      const [isScalingPossible] = await scalerEvaluator.processScalingRequest(
        TEST_INSTANCE_WITH_DATA
      );

      expect(isScalingPossible).toBeFalse();
      expect(counterManagerMock.incrementCounter).toHaveBeenCalledOnceWith(
        'scaler/scaling-denied',
        TEST_INSTANCE_WITH_DATA,
        {
          scaling_denied_reason: 'CURRENT_SIZE',
          scaling_method: 'DIRECT',
          scaling_direction: 'SCALE_SAME',
        }
      );
    });

    it('does not scale if current size is at max and it is scaling up', async () => {
      const maxSize = 10;
      const instance: ScalableInstanceWithData = {
        ...TEST_INSTANCE_WITH_DATA,
        scalingConfig: {
          ...TEST_INSTANCE_WITH_DATA.scalingConfig,
          maxSize: maxSize,
        },
        metadata: {
          ...TEST_INSTANCE_WITH_DATA.metadata,
          currentSize: maxSize,
        },
      };
      const stateData = {...TEST_STATE_DATA, scalingOperationId: null};
      stateStoreMock.getState.and.callFake(async () => stateData);
      stateFetcherMock.fetchOperationState.and.callFake(async () => [
        stateData,
        false,
      ]);
      scalingMethodRunner.getSuggestedSize.and.callFake(
        async () => maxSize + 1
      );

      const [isScalingPossible] =
        await scalerEvaluator.processScalingRequest(instance);

      expect(isScalingPossible).toBeFalse();
      expect(counterManagerMock.incrementCounter).toHaveBeenCalledOnceWith(
        'scaler/scaling-denied',
        instance,
        {
          scaling_denied_reason: 'MAX_SIZE',
          scaling_method: 'DIRECT',
          scaling_direction: 'SCALE_UP',
        }
      );
    });

    it('does not scale if scale UP is within cooldown period', async () => {
      const stateData = {
        ...TEST_STATE_DATA,
        scalingOperationId: null,
        // These times are within the cooldown period.
        lastScalingTimestamp: fixedTimestamp - 2,
        lastScalingCompleteTimestamp: fixedTimestamp - 1,
      };
      const instance: ScalableInstanceWithData = {
        ...TEST_INSTANCE_WITH_DATA,
        scalingConfig: {
          ...TEST_INSTANCE_WITH_DATA.scalingConfig,
          scaleOutCoolingMinutes: 10,
        },
      };
      stateStoreMock.getState.and.callFake(async () => stateData);
      stateFetcherMock.fetchOperationState.and.callFake(async () => [
        stateData,
        false,
      ]);
      scalingMethodRunner.getSuggestedSize.and.callFake(async () => 100); // Scale UP.

      const [isScalingPossible] =
        await scalerEvaluator.processScalingRequest(instance);

      expect(isScalingPossible).toBeFalse();
      expect(counterManagerMock.incrementCounter).toHaveBeenCalledOnceWith(
        'scaler/scaling-denied',
        instance,
        {
          scaling_denied_reason: 'WITHIN_COOLDOWN',
          scaling_method: 'DIRECT',
          scaling_direction: 'SCALE_UP',
        }
      );
    });

    it('does not scale if scale DOWN operation is within cooldown period', async () => {
      const stateData = {
        ...TEST_STATE_DATA,
        scalingOperationId: null,
        // These times are within the cooldown period.
        lastScalingTimestamp: fixedTimestamp - 2,
        lastScalingCompleteTimestamp: fixedTimestamp - 1,
      };
      const instance: ScalableInstanceWithData = {
        ...TEST_INSTANCE_WITH_DATA,
        scalingConfig: {
          ...TEST_INSTANCE_WITH_DATA.scalingConfig,
          scaleInCoolingMinutes: 10,
        },
      };
      stateStoreMock.getState.and.callFake(async () => stateData);
      stateFetcherMock.fetchOperationState.and.callFake(async () => [
        stateData,
        true,
      ]);
      scalingMethodRunner.getSuggestedSize.and.callFake(async () => 1); // Scale DOWN.

      const [isScalingPossible] =
        await scalerEvaluator.processScalingRequest(instance);

      expect(isScalingPossible).toBeFalse();
      expect(counterManagerMock.incrementCounter).toHaveBeenCalledOnceWith(
        'scaler/scaling-denied',
        instance,
        {
          scaling_denied_reason: 'WITHIN_COOLDOWN',
          scaling_method: 'DIRECT',
          scaling_direction: 'SCALE_DOWN',
        }
      );
    });

    [
      {
        testCaseName: 'no previous scaling operation',
        stateData: {
          ...TEST_STATE_DATA,
          scalingOperationId: null,
          lastScalingTimestamp: 0,
          lastScalingCompleteTimestamp: 0,
        },
      },
      {
        testCaseName: 'previous operation cooldown over',
        stateData: {
          ...TEST_STATE_DATA,
          scalingOperationId: null,
          // These times are outisde the cooldown period.
          lastScalingTimestamp: 1,
          lastScalingCompleteTimestamp: 1,
        },
      },
    ].forEach(({testCaseName, stateData}) => {
      it(`suggests scaling UP to size when ${testCaseName}`, async () => {
        const instance: ScalableInstanceWithData = {
          ...TEST_INSTANCE_WITH_DATA,
          scalingConfig: {
            ...TEST_INSTANCE_WITH_DATA.scalingConfig,
            scaleOutCoolingMinutes: 10,
          },
        };
        stateStoreMock.getState.and.callFake(async () => stateData);
        stateFetcherMock.fetchOperationState.and.callFake(async () => [
          stateData,
          false,
        ]);
        scalingMethodRunner.getSuggestedSize.and.callFake(async () => 100); // Scale UP.

        const [isScalingPossible, suggestedSize] =
          await scalerEvaluator.processScalingRequest(instance);

        expect(isScalingPossible).toBeTrue();
        expect(suggestedSize).toEqual(100);
      });

      it(`suggests scaling DOWN to size when ${testCaseName}`, async () => {
        const instance: ScalableInstanceWithData = {
          ...TEST_INSTANCE_WITH_DATA,
          scalingConfig: {
            ...TEST_INSTANCE_WITH_DATA.scalingConfig,
            scaleInCoolingMinutes: 10,
          },
        };
        stateStoreMock.getState.and.callFake(async () => stateData);
        stateFetcherMock.fetchOperationState.and.callFake(async () => [
          stateData,
          false,
        ]);
        scalingMethodRunner.getSuggestedSize.and.callFake(async () => 1); // Scale DOWN.

        const [isScalingPossible, suggestedSize] =
          await scalerEvaluator.processScalingRequest(instance);

        expect(isScalingPossible).toBeTrue();
        expect(suggestedSize).toEqual(1);
      });
    });

    it('calculates size with expected rules', async () => {
      stateStoreMock.getState.and.callFake(async () => TEST_STATE_DATA);
      stateFetcherMock.fetchOperationState.and.callFake(async () => [
        TEST_STATE_DATA,
        false,
      ]);
      scalingMethodRunner.getSuggestedSize.and.callFake(async () => 100);
      const rules = {customRuleOut: TEST_CUSTOM_RULE_OUT};
      rulesManagerMock.getRules.and.returnValue(rules);

      await scalerEvaluator.processScalingRequest(TEST_INSTANCE_WITH_DATA);

      expect(scalingMethodRunner.getSuggestedSize).toHaveBeenCalledOnceWith(
        TEST_INSTANCE_WITH_DATA,
        rules
      );
    });
  });
});
