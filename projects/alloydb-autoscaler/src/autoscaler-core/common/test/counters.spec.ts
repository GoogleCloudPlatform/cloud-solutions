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

/** @fileoverview Tests for base counters. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import {IOpenTelemetryMeterProvider} from '../open-telemetry-meter-provider';
import {CounterDefinition, CounterManager} from '../counters';
import {
  Attributes,
  BatchObservableCallback,
  Context,
  Counter,
  Gauge,
  Histogram,
  Meter,
  MeterOptions,
  MeterProvider,
  MetricAttributes,
  MetricOptions,
  Observable,
  ObservableCallback,
  ObservableCounter,
  ObservableGauge,
  ObservableUpDownCounter,
  UpDownCounter,
} from '@opentelemetry/api';
import {CounterAttributeMapper} from '../counter-attribute-mapper';
import {silentLogger} from '../../testing/testing-framework';
import {TEST_INSTANCE} from '../../testing/testing-data';

const SAMPLE_CUMULATIVE_COUNTER_DEFINITION: CounterDefinition = Object.freeze({
  counterName: 'test-cumulative',
  counterDesc: 'Test cumulative counter',
  counterType: 'CUMULATIVE',
  counterUnits: 'tests',
});

const SAMPLE_HISTOGRAM_COUNTER_DEFINITION: CounterDefinition = Object.freeze({
  counterName: 'test-histogram',
  counterDesc: 'Test histogram counter',
  counterType: 'HISTOGRAM',
  counterUnits: 'tests',
  counterHistogramBuckets: [1, 2, 3],
});

describe('CounterManager', () => {
  const counterAttributeMapper = new CounterAttributeMapper();

  describe('createCounters', () => {
    it('creates cumulative counter', async () => {
      const fakeCounter = new FakeCounter();
      const fakeMeter = new FakeMeter();
      const createCounterSpy = spyOn(
        fakeMeter,
        'createCounter'
      ).and.returnValue(fakeCounter);
      const counterManager = new CounterManager(
        /* namespace= */ 'cloudsolutions',
        /* serviceName= */ 'autoscaler-testing',
        /* logger= */ silentLogger,
        /* meterProvider= */ createFakeTelemetryWithMeter(fakeMeter),
        /* counterAttributeMapper= */ counterAttributeMapper
      );

      await counterManager.createCounters([
        SAMPLE_CUMULATIVE_COUNTER_DEFINITION,
      ]);

      expect(createCounterSpy).toHaveBeenCalledOnceWith(
        'cloudsolutions/autoscaler-testing/test-cumulative',
        {
          description: 'Test cumulative counter',
          unit: 'tests',
        }
      );
      expect(
        counterManager.counters.get('test-cumulative')?.cumulative
      ).toEqual(fakeCounter);
    });

    it('creates histogram counter', async () => {
      const fakeHistogram = new FakeHistogram();
      const fakeMeter = new FakeMeter();
      const createCounterSpy = spyOn(
        fakeMeter,
        'createHistogram'
      ).and.returnValue(fakeHistogram);
      const counterManager = new CounterManager(
        /* namespace= */ 'cloudsolutions',
        /* serviceName= */ 'autoscaler-testing',
        /* logger= */ silentLogger,
        /* meterProvider= */ createFakeTelemetryWithMeter(fakeMeter),
        /* counterAttributeMapper= */ counterAttributeMapper
      );

      await counterManager.createCounters([
        SAMPLE_HISTOGRAM_COUNTER_DEFINITION,
      ]);

      expect(createCounterSpy).toHaveBeenCalledOnceWith(
        'cloudsolutions/autoscaler-testing/test-histogram',
        {
          description: 'Test histogram counter',
          unit: 'tests',
          advice: {
            explicitBucketBoundaries: [1, 2, 3],
          },
        }
      );
      expect(counterManager.counters.get('test-histogram')?.histogram).toEqual(
        fakeHistogram
      );
    });

    it('creates multiple counters', async () => {
      const fakeMeter = new FakeMeter();
      const counterManager = new CounterManager(
        /* namespace= */ 'cloudsolutions',
        /* serviceName= */ 'autoscaler-testing',
        /* logger= */ silentLogger,
        /* meterProvider= */ createFakeTelemetryWithMeter(fakeMeter),
        /* counterAttributeMapper= */ counterAttributeMapper
      );

      await counterManager.createCounters([
        SAMPLE_CUMULATIVE_COUNTER_DEFINITION,
        SAMPLE_HISTOGRAM_COUNTER_DEFINITION,
      ]);

      expect(counterManager.counters.size).toEqual(2);
    });

    [
      {
        testCaseName: 'no counter name',
        counters: [
          {counterName: '', counterDesc: 'desc'},
        ] as CounterDefinition[],
        expectedError: new Error(
          'Invalid counter definition: {"counterName":"","counterDesc":"desc"}'
        ),
      },
      {
        testCaseName: 'no counter description',
        counters: [
          {counterName: 'name', counterDesc: ''},
        ] as CounterDefinition[],
        expectedError: new Error(
          'Invalid counter definition: {"counterName":"name","counterDesc":""}'
        ),
      },
      {
        testCaseName: 'repeated counter name',
        counters: [
          {
            counterName: 'test-cumulative',
            counterDesc: 'Test cumulative counter',
            counterType: 'CUMULATIVE',
            counterUnits: 'tests',
          },
          {
            counterName: 'test-cumulative',
            counterDesc: 'Test cumulative counter',
            counterType: 'CUMULATIVE',
            counterUnits: 'tests',
          },
        ] as CounterDefinition[],
        expectedError: new Error('Counter already created: test-cumulative'),
      },
    ].forEach(({testCaseName, counters, expectedError}) => {
      it(`throws for invalid counter definition: ${testCaseName}`, async () => {
        const fakeMeter = new FakeMeter();
        const counterManager = new CounterManager(
          /* namespace= */ 'cloudsolutions',
          /* serviceName= */ 'autoscaler-testing',
          /* logger= */ silentLogger,
          /* meterProvider= */ createFakeTelemetryWithMeter(fakeMeter),
          /* counterAttributeMapper= */ counterAttributeMapper
        );

        await expectAsync(
          counterManager.createCounters(counters)
        ).toBeRejectedWith(expectedError);
      });
    });
  });

  describe('incrementCounter', () => {
    it('increments a counter', async () => {
      const fakeCounter = new FakeCounter();
      const addSpy = spyOn(fakeCounter, 'add');
      const fakeMeter = new FakeMeter();
      spyOn(fakeMeter, 'createCounter').and.returnValue(fakeCounter);
      const counterManager = new CounterManager(
        /* namespace= */ 'cloudsolutions',
        /* serviceName= */ 'autoscaler-testing',
        /* logger= */ silentLogger,
        /* meterProvider= */ createFakeTelemetryWithMeter(fakeMeter),
        /* counterAttributeMapper= */ counterAttributeMapper
      );
      await counterManager.createCounters([
        SAMPLE_CUMULATIVE_COUNTER_DEFINITION,
      ]);

      counterManager.incrementCounter('test-cumulative', TEST_INSTANCE);

      expect(addSpy).toHaveBeenCalledWith(1, {project_id: 'project-123'});
    });

    [
      {
        testCaseName: 'counter does not exist',
        counters: [],
        counterName: 'not-existing',
        expectedError: new Error('Unknown cumulative counter: not-existing'),
      },
      {
        testCaseName: 'counter is histogram',
        counters: [SAMPLE_HISTOGRAM_COUNTER_DEFINITION],
        counterName: 'test-histogram',
        expectedError: new Error('Unknown cumulative counter: test-histogram'),
      },
    ].forEach(({testCaseName, counters, counterName, expectedError}) => {
      it(`fails when ${testCaseName}`, async () => {
        const fakeMeter = new FakeMeter();
        const counterManager = new CounterManager(
          /* namespace= */ 'cloudsolutions',
          /* serviceName= */ 'autoscaler-testing',
          /* logger= */ silentLogger,
          /* meterProvider= */ createFakeTelemetryWithMeter(fakeMeter),
          /* counterAttributeMapper= */ counterAttributeMapper
        );
        await counterManager.createCounters(counters);

        expect(() => {
          counterManager.incrementCounter(counterName, TEST_INSTANCE);
        }).toThrow(expectedError);
      });
    });
  });

  describe('recordValue', () => {
    it('records a value', async () => {
      const fakeHistogram = new FakeHistogram();
      const recordSpy = spyOn(fakeHistogram, 'record');
      const fakeMeter = new FakeMeter();
      spyOn(fakeMeter, 'createHistogram').and.returnValue(fakeHistogram);
      const counterManager = new CounterManager(
        /* namespace= */ 'cloudsolutions',
        /* serviceName= */ 'autoscaler-testing',
        /* logger= */ silentLogger,
        /* meterProvider= */ createFakeTelemetryWithMeter(fakeMeter),
        /* counterAttributeMapper= */ counterAttributeMapper
      );
      await counterManager.createCounters([
        SAMPLE_HISTOGRAM_COUNTER_DEFINITION,
      ]);

      counterManager.recordValue('test-histogram', 5, TEST_INSTANCE);

      expect(recordSpy).toHaveBeenCalledWith(5, {project_id: 'project-123'});
    });

    [
      {
        testCaseName: 'counter does not exist',
        counters: [],
        counterName: 'not-existing',
        expectedError: new Error('Unknown histogram counter: not-existing'),
      },
      {
        testCaseName: 'counter is cumulative',
        counters: [SAMPLE_CUMULATIVE_COUNTER_DEFINITION],
        counterName: 'test-cumulative',
        expectedError: new Error('Unknown histogram counter: test-cumulative'),
      },
    ].forEach(({testCaseName, counters, counterName, expectedError}) => {
      it(`fails when ${testCaseName}`, async () => {
        const fakeMeter = new FakeMeter();
        const counterManager = new CounterManager(
          /* namespace= */ 'cloudsolutions',
          /* serviceName= */ 'autoscaler-testing',
          /* logger= */ silentLogger,
          /* meterProvider= */ createFakeTelemetryWithMeter(fakeMeter),
          /* counterAttributeMapper= */ counterAttributeMapper
        );
        await counterManager.createCounters(counters);

        expect(() => {
          counterManager.recordValue(counterName, 5, TEST_INSTANCE);
        }).toThrow(expectedError);
      });
    });
  });
});

/** Creates a fake telemetry object which will use the provided meter. */
function createFakeTelemetryWithMeter(
  meter: Meter
): IOpenTelemetryMeterProvider {
  const meterProvider = new FakeMeterProvider(meter);
  return new FakeTelemetryProvider(meterProvider);
}

/* eslint-disable @typescript-eslint/no-unused-vars */
class FakeMeterProvider implements MeterProvider {
  constructor(private meter: Meter) {}
  getMeter(name: string, version?: string, options?: MeterOptions): Meter {
    return this.meter;
  }
}

class FakeTelemetryProvider implements IOpenTelemetryMeterProvider {
  constructor(private meterProvider: MeterProvider) {}
  async getMeterProvider(): Promise<MeterProvider> {
    return this.meterProvider;
  }
  setTryFlushIsEnabled(isTryFlushEnabled: boolean): void {}
  async tryFlush(): Promise<void> {}
}

/** Fake empty implementation of Meter. Methods will be mocked. */
class FakeMeter implements Meter {
  createCounter<AttributesTypes extends Attributes>(
    name: string,
    options?: MetricOptions
  ): Counter<AttributesTypes> {
    return new FakeCounter();
  }
  createGauge<AttributesTypes extends Attributes>(
    name: string,
    options?: MetricOptions
  ): Gauge<AttributesTypes> {
    return new FakeGauge();
  }
  createHistogram<AttributesTypes extends Attributes>(
    name: string,
    options?: MetricOptions
  ): Histogram<AttributesTypes> {
    return new FakeHistogram();
  }
  createObservableCounter<AttributesTypes extends Attributes>(
    name: string,
    options?: MetricOptions
  ): ObservableCounter<AttributesTypes> {
    return new FakeObservableCounter();
  }
  createObservableGauge<AttributesTypes extends Attributes>(
    name: string,
    options?: MetricOptions
  ): ObservableGauge<AttributesTypes> {
    return new FakeObservableGauge();
  }
  createObservableUpDownCounter<AttributesTypes extends Attributes>(
    name: string,
    options?: MetricOptions
  ): ObservableUpDownCounter<AttributesTypes> {
    return new FakeObservableUpDownCounter();
  }
  createUpDownCounter<AttributesTypes extends Attributes>(
    name: string,
    options?: MetricOptions
  ): UpDownCounter<AttributesTypes> {
    return new FakeUpDownCounter();
  }
  addBatchObservableCallback<
    AttributesTypes extends MetricAttributes = Attributes,
  >(
    callback: BatchObservableCallback<AttributesTypes>,
    observables: Observable<AttributesTypes>[]
  ): void {}
  removeBatchObservableCallback<
    AttributesTypes extends MetricAttributes = Attributes,
  >(
    callback: BatchObservableCallback<AttributesTypes>,
    observables: Observable<AttributesTypes>[]
  ): void {}
}

class FakeCounter implements Counter {
  add(
    value: number,
    attributes?: Attributes | undefined,
    context?: Context
  ): void {}
}

class FakeGauge implements Gauge {
  record(
    value: number,
    attributes?: Attributes | undefined,
    context?: Context
  ): void {}
}

class FakeHistogram implements Histogram {
  record(
    value: number,
    attributes?: Attributes | undefined,
    context?: Context
  ): void {}
}

class FakeObservableCounter implements ObservableCounter {
  addCallback(callback: ObservableCallback<Attributes>): void {}
  removeCallback(callback: ObservableCallback<Attributes>): void {}
}

class FakeObservableGauge implements ObservableGauge {
  addCallback(callback: ObservableCallback<Attributes>): void {}
  removeCallback(callback: ObservableCallback<Attributes>): void {}
}

class FakeObservableUpDownCounter implements ObservableUpDownCounter {
  addCallback(callback: ObservableCallback<Attributes>): void {}
  removeCallback(callback: ObservableCallback<Attributes>): void {}
}

class FakeUpDownCounter implements UpDownCounter {
  add(
    value: number,
    attributes?: Attributes | undefined,
    context?: Context
  ): void {}
}
/* eslint-enable @typescript-eslint/no-unused-vars */
