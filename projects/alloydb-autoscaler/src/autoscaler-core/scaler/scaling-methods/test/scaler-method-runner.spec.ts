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

/** @fileoverview Tests scaler-method-runner. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import pino from 'pino';
import {createInstanceLoggerWithMocks} from '../../../testing/testing-framework';
import {ScalingMethodRunner} from '../scaling-method-runner';
import {IScalingMethod} from '../scaling-method';
import {IRulesEngine} from '../../scaler-rules-engine';
import {IScalingSizeValidator} from '../scaling-size-validator';
import {
  TEST_INSTANCE_WITH_DATA,
  TEST_CUSTOM_RULE_OUT,
  TEST_ENGINE_ANALYSIS,
} from '../../../testing/testing-data';
import {ScalableInstanceWithData} from '../../../common/instance-info';
import {AutoscalerScalingDirection} from '../scaling-direction';

describe('ScalingMethodRunner', () => {
  let scalingMethodAMock: jasmine.SpyObj<IScalingMethod>;
  let scalingMethodBMock: jasmine.SpyObj<IScalingMethod>;
  let scalingMethodCMock: jasmine.SpyObj<IScalingMethod>;
  let scalingMethodRunner: ScalingMethodRunner;
  const rules = {customRuleOut: TEST_CUSTOM_RULE_OUT};

  let rulesEngineMock: jasmine.SpyObj<IRulesEngine>;
  let scalingSizeValidator: jasmine.SpyObj<IScalingSizeValidator>;
  let baseLogger: jasmine.SpyObj<pino.Logger>;
  let instanceLogger: jasmine.SpyObj<pino.Logger>;

  beforeEach(() => {
    scalingMethodAMock = createScalingMethodMock();
    scalingMethodBMock = createScalingMethodMock();
    scalingMethodCMock = createScalingMethodMock();

    const scalingMethodMap = new Map([
      ['METHOD_1', scalingMethodAMock],
      ['METHOD_2', scalingMethodBMock],
    ]);

    const defaultScalingMethod = scalingMethodCMock;

    rulesEngineMock = jasmine.createSpyObj('RulesEngine', [
      'getEngineAnalysis',
    ]);
    rulesEngineMock.getEngineAnalysis.and.callFake(
      async () => TEST_ENGINE_ANALYSIS
    );
    scalingSizeValidator = jasmine.createSpyObj('ScalingSizeValidator', [
      'validateSuggestedSize',
    ]);
    [baseLogger, instanceLogger] = createInstanceLoggerWithMocks();

    scalingMethodRunner = new ScalingMethodRunner(
      baseLogger,
      rulesEngineMock,
      scalingSizeValidator,
      defaultScalingMethod,
      scalingMethodMap
    );
  });

  describe('getSuggestedSize', () => {
    // Chooses the right scaling method.
    it('uses default method if scalingMethod is not defined', async () => {
      const instance: ScalableInstanceWithData = {
        ...TEST_INSTANCE_WITH_DATA,
        scalingConfig: {
          ...TEST_INSTANCE_WITH_DATA.scalingConfig,
          scalingMethod: '',
        },
      };

      await scalingMethodRunner.getSuggestedSize(instance, rules);

      expect(
        scalingMethodCMock.calculateSuggestedSize
      ).toHaveBeenCalledOnceWith(
        instance,
        AutoscalerScalingDirection.NONE,
        TEST_ENGINE_ANALYSIS,
        instanceLogger
      );
    });

    it('uses default method if no scalingMethods map is defined', async () => {
      scalingMethodRunner = new ScalingMethodRunner(
        baseLogger,
        rulesEngineMock,
        scalingSizeValidator,
        scalingMethodCMock
      );
      const instance: ScalableInstanceWithData = {
        ...TEST_INSTANCE_WITH_DATA,
        scalingConfig: {
          ...TEST_INSTANCE_WITH_DATA.scalingConfig,
          scalingMethod: '',
        },
      };

      await scalingMethodRunner.getSuggestedSize(instance, rules);

      expect(
        scalingMethodCMock.calculateSuggestedSize
      ).toHaveBeenCalledOnceWith(
        instance,
        AutoscalerScalingDirection.NONE,
        TEST_ENGINE_ANALYSIS,
        instanceLogger
      );
    });

    it('uses default method if scalingMethod does not exist', async () => {
      const instance: ScalableInstanceWithData = {
        ...TEST_INSTANCE_WITH_DATA,
        scalingConfig: {
          ...TEST_INSTANCE_WITH_DATA.scalingConfig,
          scalingMethod: 'not_existing',
        },
      };

      await scalingMethodRunner.getSuggestedSize(instance, rules);

      expect(
        scalingMethodCMock.calculateSuggestedSize
      ).toHaveBeenCalledOnceWith(
        instance,
        AutoscalerScalingDirection.NONE,
        TEST_ENGINE_ANALYSIS,
        instanceLogger
      );
    });

    it('uses selected scalingMethod', async () => {
      const instance: ScalableInstanceWithData = {
        ...TEST_INSTANCE_WITH_DATA,
        scalingConfig: {
          ...TEST_INSTANCE_WITH_DATA.scalingConfig,
          scalingMethod: 'METHOD_1',
        },
      };
      rulesEngineMock.getEngineAnalysis.and.callFake(
        async () => TEST_ENGINE_ANALYSIS
      );

      await scalingMethodRunner.getSuggestedSize(instance, rules);

      expect(
        scalingMethodAMock.calculateSuggestedSize
      ).toHaveBeenCalledOnceWith(
        instance,
        AutoscalerScalingDirection.NONE,
        TEST_ENGINE_ANALYSIS,
        instanceLogger
      );
    });

    [
      {
        firingRuleCount: {
          [AutoscalerScalingDirection.SCALE_OUT]: 0,
          [AutoscalerScalingDirection.SCALE_UP]: 0,
          [AutoscalerScalingDirection.SCALE_IN]: 0,
          [AutoscalerScalingDirection.SCALE_DOWN]: 0,
          [AutoscalerScalingDirection.SCALE_SAME]: 0,
          [AutoscalerScalingDirection.NONE]: 0,
        },
        expectedDirection: AutoscalerScalingDirection.NONE,
      },
      {
        firingRuleCount: {
          [AutoscalerScalingDirection.SCALE_OUT]: 1,
          [AutoscalerScalingDirection.SCALE_UP]: 2,
          [AutoscalerScalingDirection.SCALE_IN]: 3,
          [AutoscalerScalingDirection.SCALE_DOWN]: 4,
          [AutoscalerScalingDirection.SCALE_SAME]: 0,
          [AutoscalerScalingDirection.NONE]: 0,
        },
        expectedDirection: AutoscalerScalingDirection.SCALE_OUT,
      },
      {
        firingRuleCount: {
          [AutoscalerScalingDirection.SCALE_OUT]: 0,
          [AutoscalerScalingDirection.SCALE_UP]: 2,
          [AutoscalerScalingDirection.SCALE_IN]: 3,
          [AutoscalerScalingDirection.SCALE_DOWN]: 4,
          [AutoscalerScalingDirection.SCALE_SAME]: 0,
          [AutoscalerScalingDirection.NONE]: 0,
        },
        expectedDirection: AutoscalerScalingDirection.SCALE_UP,
      },
      {
        firingRuleCount: {
          [AutoscalerScalingDirection.SCALE_OUT]: 0,
          [AutoscalerScalingDirection.SCALE_UP]: 0,
          [AutoscalerScalingDirection.SCALE_IN]: 3,
          [AutoscalerScalingDirection.SCALE_DOWN]: 4,
          [AutoscalerScalingDirection.SCALE_SAME]: 0,
          [AutoscalerScalingDirection.NONE]: 0,
        },
        expectedDirection: AutoscalerScalingDirection.SCALE_IN,
      },
      {
        firingRuleCount: {
          [AutoscalerScalingDirection.SCALE_OUT]: 0,
          [AutoscalerScalingDirection.SCALE_UP]: 0,
          [AutoscalerScalingDirection.SCALE_IN]: 0,
          [AutoscalerScalingDirection.SCALE_DOWN]: 4,
          [AutoscalerScalingDirection.SCALE_SAME]: 0,
          [AutoscalerScalingDirection.NONE]: 0,
        },
        expectedDirection: AutoscalerScalingDirection.SCALE_DOWN,
      },
    ].forEach(({firingRuleCount, expectedDirection}) => {
      it('calls method with expected parameters', async () => {
        const engineAnalysis = {...TEST_ENGINE_ANALYSIS, firingRuleCount};
        rulesEngineMock.getEngineAnalysis.and.callFake(
          async () => engineAnalysis
        );

        await scalingMethodRunner.getSuggestedSize(
          TEST_INSTANCE_WITH_DATA,
          rules
        );

        expect(scalingMethodCMock.calculateSuggestedSize).toHaveBeenCalledWith(
          TEST_INSTANCE_WITH_DATA,
          expectedDirection,
          engineAnalysis,
          instanceLogger
        );
      });
    });

    [
      {
        calculatedSize: 3,
        validatedSize: 4,
      },
      {
        calculatedSize: 9,
        validatedSize: 2,
      },
      {
        calculatedSize: 0,
        validatedSize: 5,
      },
      {
        calculatedSize: 5,
        validatedSize: 0,
      },
    ].forEach(({calculatedSize, validatedSize}) => {
      const testName =
        'returns validated size ' +
        `(initial: ${calculatedSize}, final: ${validatedSize})`;
      it(testName, async () => {
        rulesEngineMock.getEngineAnalysis.and.callFake(
          async () => TEST_ENGINE_ANALYSIS
        );
        scalingMethodCMock.calculateSuggestedSize.and.returnValue(
          calculatedSize
        );
        scalingSizeValidator.validateSuggestedSize.and.returnValue(
          validatedSize
        );

        const output = await scalingMethodRunner.getSuggestedSize(
          TEST_INSTANCE_WITH_DATA,
          rules
        );

        expect(output).toEqual(validatedSize);
      });
    });
  });
});

const createScalingMethodMock = (): jasmine.SpyObj<IScalingMethod> => {
  return jasmine.createSpyObj('ScalingMethod', ['calculateSuggestedSize']);
};
