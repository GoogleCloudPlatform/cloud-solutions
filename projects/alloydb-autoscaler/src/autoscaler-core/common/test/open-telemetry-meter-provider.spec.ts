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

/** @fileoverview Tests for Open Telemtry meter provider. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import {SEMRESATTRS_K8S_POD_NAME} from '@opentelemetry/semantic-conventions';
import {
  ExporterMode,
  OpenTelemetryMeterProvider,
} from '../open-telemetry-meter-provider';
import {MeterProvider} from '@opentelemetry/sdk-metrics';
import {silentLogger} from '../../testing/testing-framework';

describe('OpenTelemetryMeterProvider', () => {
  beforeEach(() => {
    TestableMeterProvider.resetStaticAttributes();
    resetEnvironmentVariables();
  });

  describe('constructor (initializeMetrics)', () => {
    it('sets kubernetes pod name', async () => {
      process.env.KUBERNETES_SERVICE_HOST = 'localhost';
      process.env.K8S_POD_NAME = 'autoscaler_pod';

      const meterProvider = new TestableMeterProvider(silentLogger);
      await meterProvider.getPendingInit()?.promise;

      const resourceAttributes = meterProvider.getResourceAttributes();
      expect(resourceAttributes[SEMRESATTRS_K8S_POD_NAME]).toEqual(
        'autoscaler_pod'
      );
    });

    it('does not set kubernetes pod name when missing host', async () => {
      process.env.K8S_POD_NAME = 'ignored value';

      const meterProvider = new TestableMeterProvider(silentLogger);
      await meterProvider.getPendingInit()?.promise;

      const resourceAttributes = meterProvider.getResourceAttributes();
      expect(resourceAttributes).toBeDefined();
      expect(SEMRESATTRS_K8S_POD_NAME in resourceAttributes).toBeFalse();
    });

    it('does not set kubernetes pod name when missing pod name', async () => {
      process.env.KUBERNETES_SERVICE_HOST = 'localhost';

      const meterProvider = new TestableMeterProvider(silentLogger);
      await meterProvider.getPendingInit()?.promise;

      const resourceAttributes = meterProvider.getResourceAttributes();
      expect(resourceAttributes).toBeDefined();
      expect(SEMRESATTRS_K8S_POD_NAME in resourceAttributes).toBeFalse();
    });

    it('sets exporter mode for otel periodic', async () => {
      process.env.OTEL_COLLECTOR_URL = 'https://localhost/collector';
      process.env.OTEL_IS_LONG_RUNNING_PROCESS = 'true';

      const meterProvider = new TestableMeterProvider(silentLogger);
      await meterProvider.getPendingInit()?.promise;

      expect(meterProvider.getExporterMode()).toEqual(
        ExporterMode.OTEL_PERIODIC
      );
    });

    it('sets exporter mode for otel only flushing', async () => {
      process.env.OTEL_COLLECTOR_URL = 'https://localhost/collector';
      process.env.OTEL_IS_LONG_RUNNING_PROCESS = 'false';

      const meterProvider = new TestableMeterProvider(silentLogger);
      await meterProvider.getPendingInit()?.promise;

      expect(meterProvider.getExporterMode()).toEqual(
        ExporterMode.OTEL_ONLY_FLUSHING
      );
    });

    it('sets exporter mode for gcm only flushing', async () => {
      const meterProvider = new TestableMeterProvider(silentLogger);
      await meterProvider.getPendingInit()?.promise;

      expect(meterProvider.getExporterMode()).toEqual(
        ExporterMode.GCM_ONLY_FLUSHING
      );
    });

    it('throws error when isLongRunningProcess is not set', done => {
      process.env.OTEL_COLLECTOR_URL = 'https://localhost/collector';

      const meterProvider = new TestableMeterProvider(silentLogger);

      const pendingInitPromise = meterProvider.getPendingInit();
      expect(pendingInitPromise).not.toBe(null);
      pendingInitPromise?.promise?.then(
        () => {
          done.fail(
            new Error(
              'pendingInit was resolved and it was expected to be rejected'
            )
          );
        },
        reason => {
          expect(reason).toEqual(
            new Error(
              'Invalid value for env var OTEL_IS_LONG_RUNNING_PROCESS: "undefined"'
            )
          );
          done();
        }
      );
    });

    it('throws error when isLongRunningProcess has an invalid value', done => {
      process.env.OTEL_COLLECTOR_URL = 'https://localhost/collector';
      process.env.OTEL_IS_LONG_RUNNING_PROCESS = 'invalid';

      const meterProvider = new TestableMeterProvider(silentLogger);

      const pendingInitPromise = meterProvider.getPendingInit();
      expect(pendingInitPromise).not.toBe(null);
      pendingInitPromise?.promise?.then(
        () => {
          done.fail(
            new Error(
              'pendingInit was resolved and it was expected to be rejected'
            )
          );
        },
        reason => {
          expect(reason).toEqual(
            new Error(
              'Invalid value for env var OTEL_IS_LONG_RUNNING_PROCESS: "invalid"'
            )
          );
          done();
        }
      );
    });
  });

  describe('getMeterProvider', () => {
    // One for each config.
    it('gets the expected meter for OTEL_PERIODIC', async () => {
      process.env.OTEL_COLLECTOR_URL = 'https://localhost/collector';
      process.env.OTEL_IS_LONG_RUNNING_PROCESS = 'true';

      const telemetryProvider = new OpenTelemetryMeterProvider(silentLogger);
      const meterProvider = await telemetryProvider.getMeterProvider();
      const meter = meterProvider.getMeter('test');

      expect(meterProvider).toBeInstanceOf(MeterProvider);
      expect(meter.constructor.name).toEqual('Meter');
    });

    it('gets the expected meter for OTEL_ONLY_FLUSHING', async () => {
      process.env.OTEL_COLLECTOR_URL = 'https://localhost/collector';
      process.env.OTEL_IS_LONG_RUNNING_PROCESS = 'false';

      const telemetryProvider = new OpenTelemetryMeterProvider(silentLogger);
      const meterProvider = await telemetryProvider.getMeterProvider();
      const meter = meterProvider.getMeter('test');

      expect(meterProvider).toBeInstanceOf(MeterProvider);
      expect(meter.constructor.name).toEqual('Meter');
    });

    it('gets the expected meter for OTEL_PERIODIC', async () => {
      const telemetryProvider = new OpenTelemetryMeterProvider(silentLogger);
      const meterProvider = await telemetryProvider.getMeterProvider();
      const meter = meterProvider.getMeter('test');

      expect(meterProvider).toBeInstanceOf(MeterProvider);
      expect(meter.constructor.name).toEqual('Meter');
    });
  });

  describe('tryFlush', () => {
    const meterProviderWithMocks: MeterProvider = new MeterProvider();
    let forceFlushSpy: jasmine.Spy;

    beforeEach(() => {
      jasmine.clock().install();
      forceFlushSpy = spyOn(meterProviderWithMocks, 'forceFlush');
      // Sets an environment where flush is needed.
      process.env.OTEL_COLLECTOR_URL = 'https://localhost/collector';
      process.env.OTEL_IS_LONG_RUNNING_PROCESS = 'false';
    });

    afterEach(() => {
      jasmine.clock().uninstall();
      forceFlushSpy.calls.reset();
    });

    it('does nothing if flush is disabled', async () => {
      setEnvironmentWhereFlushIsNeeded();
      const telemetryProvider = new TestableMeterProvider(silentLogger);
      telemetryProvider.setMeterProvider(meterProviderWithMocks);
      telemetryProvider.setLastForceFlushTime(Date.now());

      telemetryProvider.setTryFlushIsEnabled(false); // Disable flush.
      await telemetryProvider.tryFlush();

      expect(forceFlushSpy).not.toHaveBeenCalled();
    });

    it('does nothing if flush is disabled in exporter', async () => {
      // Default environment does not require flush.
      const telemetryProvider = new TestableMeterProvider(silentLogger);
      telemetryProvider.setMeterProvider(meterProviderWithMocks);
      telemetryProvider.setLastForceFlushTime(Date.now());

      telemetryProvider.setTryFlushIsEnabled(false); // Disable flush.
      await telemetryProvider.tryFlush();

      expect(forceFlushSpy).not.toHaveBeenCalled();
    });

    it('flushes and updates its last run time', async () => {
      setEnvironmentWhereFlushIsNeeded();
      jasmine.clock().mockDate(new Date(999_999_999));
      const telemetryProvider = new TestableMeterProvider(silentLogger);
      await telemetryProvider.getPendingInit()?.promise; // Must initialize.
      telemetryProvider.setMeterProvider(meterProviderWithMocks);
      telemetryProvider.setLastForceFlushTime(0);
      telemetryProvider.setTryFlushIsEnabled(true);

      await telemetryProvider.tryFlush();

      expect(forceFlushSpy).toHaveBeenCalled();
      expect(telemetryProvider.getLastForceFlushTime()).toEqual(999_999_999);
    });

    it('waits if under min interval', async () => {
      setEnvironmentWhereFlushIsNeeded();
      jasmine.clock().mockDate(new Date(1_000_000));
      const telemetryProvider = new TestableMeterProvider(silentLogger);
      await telemetryProvider.getPendingInit()?.promise; // Must initialize.
      telemetryProvider.setMeterProvider(meterProviderWithMocks);
      telemetryProvider.setLastForceFlushTime(1_000_000);
      telemetryProvider.setTryFlushIsEnabled(true);

      const tryFlushPromise = telemetryProvider.tryFlush();
      // Arbitrarily large number larger than the min waiting time.
      jasmine.clock().tick(100_000);
      await tryFlushPromise;

      expect(forceFlushSpy).toHaveBeenCalled();
      expect(telemetryProvider.getLastForceFlushTime()).toEqual(
        1_000_000 + 100_000
      );
    });
  });
});

/**
 * Testable version of OpenTelemetryMeterProvider with methods to access
 * protected variables.
 */
class TestableMeterProvider extends OpenTelemetryMeterProvider {
  /**
   * Resets static variables.
   *
   * This is needed because OpenTelemetryMeterProvider works as singleton-like
   * entity where all the values are static and must be initialized only once
   * depending on the environment. However, for testing, we need to initialize
   * multiple times with multiple configurations. As such, the workaround here
   * is to re-initialize them to their initial values.
   */
  static resetStaticAttributes() {
    OpenTelemetryMeterProvider.resourceAttributes = {};
    OpenTelemetryMeterProvider.exporterMode = null;
    OpenTelemetryMeterProvider.exporterParams = null;
    OpenTelemetryMeterProvider.meterProvider = null;
    OpenTelemetryMeterProvider.isInitialized = false;
    OpenTelemetryMeterProvider.pendingInit = null;
    OpenTelemetryMeterProvider.openTelemetryErrorCount = 0;
    OpenTelemetryMeterProvider.pendingFlush = null;
    OpenTelemetryMeterProvider.isTryFlushEnabled = true;
    OpenTelemetryMeterProvider.lastForceFlushTime = 0;
  }
  getExporterMode() {
    return OpenTelemetryMeterProvider.exporterMode;
  }
  getPendingInit() {
    return OpenTelemetryMeterProvider.pendingInit;
  }
  getResourceAttributes() {
    return OpenTelemetryMeterProvider.resourceAttributes;
  }
  getLastForceFlushTime() {
    return OpenTelemetryMeterProvider.lastForceFlushTime;
  }
  setLastForceFlushTime(timestamp: number) {
    OpenTelemetryMeterProvider.lastForceFlushTime = timestamp;
  }
  setMeterProvider(meterProvider: MeterProvider) {
    OpenTelemetryMeterProvider.meterProvider = meterProvider;
  }
}

/** Resets used environment variables. */
function resetEnvironmentVariables() {
  delete process.env.KUBERNETES_SERVICE_HOST;
  delete process.env.K8S_POD_NAME;
  delete process.env.OTEL_COLLECTOR_URL;
  delete process.env.OTEL_IS_LONG_RUNNING_PROCESS;
}

/** Sets the environment for an exporter mode that needs flushing. */
function setEnvironmentWhereFlushIsNeeded() {
  process.env.OTEL_COLLECTOR_URL = 'https://localhost/collector';
  process.env.OTEL_IS_LONG_RUNNING_PROCESS = 'false';
}
