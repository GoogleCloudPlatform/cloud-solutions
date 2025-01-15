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

/** @fileoverview Provides basic counters functionality for Monitoring API. */

import {
  Attributes as OpenTelemetryAttributes,
  Counter as Cumulative, // Counter is in use by our own definition.
  Meter,
  Histogram,
} from '@opentelemetry/api';
import pino from 'pino';
import {IOpenTelemetryMeterProvider} from './open-telemetry-meter-provider';
import {
  InstanceInfo,
  ScalableInstance,
  ScalableInstanceWithData,
} from './instance-info';
import {
  CounterAttributes,
  ICounterAttributeMapper,
} from './counter-attribute-mapper';

/** Definition of a counter. */
export type CounterDefinition = {
  counterName: string;
  counterDesc: string;
  counterType?: 'CUMULATIVE' | 'HISTOGRAM';
  counterUnits?: string;
  counterHistogramBuckets?: number[];
};

/** A counter. */
export type Counter = {
  cumulative?: Cumulative;
  histogram?: Histogram;
};

/** Maps the name of the counter to the counter. */
export type CounterMap = Map<string, Counter>;

/** Initializes and creates counters. */
export class CounterManager {
  counters: CounterMap = new Map();
  protected counterPrefix: string;

  constructor(
    private namespace: string,
    private serviceName: string,
    protected logger: pino.Logger,
    protected meterProvider: IOpenTelemetryMeterProvider,
    protected counterAttributeMapper: ICounterAttributeMapper
  ) {
    this.counterPrefix = `${this.namespace}/${this.serviceName}/`;
  }

  /**
   * Initializes metrics with Cloud Monitoring.
   *
   * Note: counterName must be unique.
   */
  async createCounters(counterDefinitions: CounterDefinition[]) {
    const meterProvider = await this.meterProvider.getMeterProvider();

    if (!meterProvider) {
      // This should not happen if this.initializeMetrics is awaited.
      throw new Error('Meter initialization failed.');
    }
    const meter = meterProvider.getMeter(this.counterPrefix);

    for (const counterDefinition of counterDefinitions) {
      this.createCounter(meter, counterDefinition);
    }
  }

  /** Increments a cumulative counter. */
  incrementCounter(
    counterName: string,
    instance?: ScalableInstance | ScalableInstanceWithData,
    additionalAttributes?: CounterAttributes
  ) {
    const counter = this.counters.get(counterName);
    if (!counter?.cumulative) {
      throw new Error(`Unknown cumulative counter: ${counterName}`);
    }
    const counterAttributes: CounterAttributes =
      this.counterAttributeMapper.getCounterAttributes(
        instance,
        additionalAttributes
      );
    counter.cumulative.add(1, counterAttributes);
  }

  /** Records a histogram counter value. */
  recordValue(
    counterName: string,
    value: number,
    instance?: ScalableInstance | ScalableInstanceWithData,
    additionalAttributes?: CounterAttributes
  ) {
    const counter = this.counters.get(counterName);
    if (!counter?.histogram) {
      throw new Error(`Unknown histogram counter: ${counterName}`);
    }
    const counterAttributes: CounterAttributes =
      this.counterAttributeMapper.getCounterAttributes(
        instance,
        additionalAttributes
      );
    counter.histogram.record(value, counterAttributes);
  }

  /**
   * Flushes counters.
   * Flushing is dependent on the Open Telemtry implementation, so this may
   * not flush when it's not required.
   */
  async flush() {
    await this.meterProvider.tryFlush();
  }

  /**
   * Casts an InstanceInfo into OpenTelemetry attributes for counters.
   * @param instanceInfo Instance information to use for the counter.
   * @return Attributes to pass to the counters.
   */
  protected castInstanceInfoToAttributes(
    instanceInfo: InstanceInfo
  ): OpenTelemetryAttributes {
    return {projectId: instanceInfo.projectId} as OpenTelemetryAttributes;
  }

  /** Creates an individual counter. */
  protected createCounter(meter: Meter, counterDefinition: CounterDefinition) {
    if (!counterDefinition.counterName || !counterDefinition.counterDesc) {
      throw new Error(
        `Invalid counter definition: ${JSON.stringify(counterDefinition)}`
      );
    }

    if (this.counters.has(counterDefinition.counterName)) {
      throw new Error(
        `Counter already created: ${counterDefinition.counterName}`
      );
    }

    counterDefinition.counterType ??= 'CUMULATIVE'; // Default value.
    switch (counterDefinition.counterType) {
      case 'CUMULATIVE':
        this.createCumulativeCounter(meter, counterDefinition);
        break;
      case 'HISTOGRAM':
        this.createHistogramCounter(meter, counterDefinition);
        break;
      default:
        throw new Error(
          `Invalid counter type for ${counterDefinition.counterName}: ` +
            counterDefinition.counterType
        );
    }
  }

  /** Creates a cumulative counter. */
  protected createCumulativeCounter(
    meter: Meter,
    counterDefinition: CounterDefinition
  ) {
    this.counters.set(counterDefinition.counterName, {
      cumulative: meter.createCounter(
        `${this.counterPrefix}${counterDefinition.counterName}`,
        {
          description: counterDefinition.counterDesc,
          unit: counterDefinition.counterUnits,
        }
      ),
    });
  }

  /** Creates a histogram counter. */
  protected createHistogramCounter(
    meter: Meter,
    counterDefinition: CounterDefinition
  ) {
    this.counters.set(counterDefinition.counterName, {
      histogram: meter.createHistogram(
        `${this.counterPrefix}${counterDefinition.counterName}`,
        {
          description: counterDefinition.counterDesc,
          unit: counterDefinition.counterUnits,
          advice: {
            explicitBucketBoundaries: counterDefinition.counterHistogramBuckets,
          },
        }
      ),
    });
  }
}
