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

/** @fileoverview Provides functionality to export metrics to Open Telemetry. */

import {MetricExporter as GcpMetricExporter} from '@google-cloud/opentelemetry-cloud-monitoring-exporter';
import {GcpDetectorSync} from '@google-cloud/opentelemetry-resource-util';
import {
  diag,
  DiagLogLevel,
  Exception as OpenTelemetryException,
  MeterProvider as IMeterProvider,
} from '@opentelemetry/api';
import {
  loggingErrorHandler as openTelemetryLoggingErrorHandler,
  setGlobalErrorHandler as openTelemetrySetGlobalErrorHandler,
} from '@opentelemetry/core';
import {OTLPMetricExporter} from '@opentelemetry/exporter-metrics-otlp-grpc';
import {IResource, Resource} from '@opentelemetry/resources';
import {SEMRESATTRS_K8S_POD_NAME} from '@opentelemetry/semantic-conventions';
import {
  MeterProvider,
  PeriodicExportingMetricReader,
  PushMetricExporter,
} from '@opentelemetry/sdk-metrics';

import {
  promiseWithResolvers,
  PromiseWithResolvers,
  sleep,
} from './promise-wrapper';
import {DiagToPinoLogger} from './diag-logger-wrapper';
import {createLogger} from './logger';
import pino from 'pino';

/** Exporting modes for OpenTelemetry. */
export enum ExporterMode {
  GCM_ONLY_FLUSHING,
  OTEL_PERIODIC,
  OTEL_ONLY_FLUSHING,
}

type ExporterParams = {
  PERIODIC_EXPORT_INTERVAL: number;
  FLUSH_MIN_INTERVAL: number;
  FLUSH_MAX_ATTEMPTS: number;
  FLUSH_ENABLED: boolean;
};

const EXPORTER_PARAMETERS: Record<ExporterMode, ExporterParams> = {
  // GCM direct pushing is only done in Cloud functions deployments, where
  // we only flush directly.
  //
  [ExporterMode.GCM_ONLY_FLUSHING]: {
    PERIODIC_EXPORT_INTERVAL: 0x7fffffff, // approx 24 days in milliseconds
    FLUSH_MIN_INTERVAL: 10_000,
    FLUSH_MAX_ATTEMPTS: 6,
    FLUSH_ENABLED: true,
  },

  // OTEL collector cannot handle receiving metrics from a single process
  // more frequently than its batching timeout, as it does not aggregate
  // them and reports the multiple metrics to the upstream metrics management
  // interface (eg GCM) which will then cause Duplicate TimeSeries errors.
  //
  // So when using flushing, disable periodic export, and when using periodic
  // export, disable flushing!
  //
  // OTEL collector mode is set by specifying the environment variable
  // OTEL_COLLECTOR_URL which is the address of the collector,
  // and whether to use flushing or periodic export is determined
  // by the environment variable OTEL_IS_LONG_RUNNING_PROCESS
  [ExporterMode.OTEL_ONLY_FLUSHING]: {
    PERIODIC_EXPORT_INTERVAL: 0x7fffffff, // approx 24 days in milliseconds
    FLUSH_MIN_INTERVAL: 15_000,
    FLUSH_MAX_ATTEMPTS: 6,
    FLUSH_ENABLED: true,
  },
  [ExporterMode.OTEL_PERIODIC]: {
    PERIODIC_EXPORT_INTERVAL: 20_000, // OTEL collector batches every 10s
    FLUSH_MIN_INTERVAL: 0,
    FLUSH_MAX_ATTEMPTS: 0,
    FLUSH_ENABLED: false,
  },
};

/** Provides a Meter to interact with OpenTelemetry */
export interface IOpenTelemetryMeterProvider {
  getMeterProvider(): Promise<IMeterProvider>;
  tryFlush(): Promise<void>;
  setTryFlushIsEnabled(isTryFlushEnabled: boolean): void;
}

/** Exporter to interact with OpenTelemetry. */
export class OpenTelemetryMeterProvider implements IOpenTelemetryMeterProvider {
  protected static resourceAttributes: Record<string, string> = {};
  protected static exporterMode: ExporterMode | null;
  protected static exporterParams: ExporterParams | null;
  protected static meterProvider: MeterProvider | null;

  protected static isInitialized: boolean = false;
  protected static pendingInit: PromiseWithResolvers<null> | null = null;

  // Creating a default, but this is will be overriden when initialized.
  private static diagPinoLogger: DiagToPinoLogger = new DiagToPinoLogger(
    createLogger()
  );

  protected static openTelemetryErrorCount: number = 0;

  protected static pendingFlush: PromiseWithResolvers<null> | null = null;
  protected static isTryFlushEnabled: boolean = true;

  protected static lastForceFlushTime: number = 0;

  /** Initializes OpenTelemetryMeterProvider. */
  constructor(logger: pino.Logger) {
    OpenTelemetryMeterProvider.initializeTelemetry();
    OpenTelemetryMeterProvider.diagPinoLogger = new DiagToPinoLogger(logger);
  }

  /**
   * Gets the MeterProvider to interact with OpenTelemetry.
   * @return OpenTelemetry meter provider.
   */
  async getMeterProvider(): Promise<MeterProvider> {
    if (!OpenTelemetryMeterProvider.meterProvider) {
      await OpenTelemetryMeterProvider.initializeTelemetry();
    }

    if (!OpenTelemetryMeterProvider.meterProvider) {
      throw new Error('OpenTelemetry initialization failed.');
    }

    return OpenTelemetryMeterProvider.meterProvider;
  }

  /**
   * Specify whether the tryFlush function should try to flush or not.
   *
   * In long-running processes, disabling flushing will give better results
   * while in short-lived processes, without flushing, counters may not
   * be reported to cloud monitoring.
   */
  setTryFlushIsEnabled(isTryFlushEnabled: boolean) {
    OpenTelemetryMeterProvider.isTryFlushEnabled = isTryFlushEnabled;
  }

  /**
   * Sets the diag logger to a custom one.
   * @param logger DiagToPinoLogger to use for logging.
   */
  static setLogger(logger: DiagToPinoLogger) {
    OpenTelemetryMeterProvider.diagPinoLogger = logger;
  }

  /**
   * Try to flush any as-yet-unsent counters to cloud montioring.
   * if setTryFlushEnabled(false) has been called, this function is a no-op.
   *
   * Will only actually call forceFlush once every MIN_FORCE_FLUSH_INTERVAL
   * seconds. It will retry if an error is detected during flushing.
   *
   * (Note on transient errors: in a long running process, these are not an
   * issue as periodic export will succeed next time, but in short-lived
   * processes there is not a 'next time', so we need to check for errors
   * and retry)
   */
  async tryFlush() {
    if (OpenTelemetryMeterProvider.pendingInit) {
      await OpenTelemetryMeterProvider.pendingInit.promise;
    }

    if (
      !OpenTelemetryMeterProvider.isTryFlushEnabled ||
      !OpenTelemetryMeterProvider.exporterParams?.FLUSH_ENABLED
    ) {
      // Flushing disabled, do nothing!
      return;
    }

    // Avoid simultaneous flushing.
    if (OpenTelemetryMeterProvider.pendingFlush) {
      await OpenTelemetryMeterProvider.pendingFlush.promise;
      return;
    }
    OpenTelemetryMeterProvider.pendingFlush = promiseWithResolvers();

    if (
      !OpenTelemetryMeterProvider.exporterParams ||
      !OpenTelemetryMeterProvider.meterProvider
    ) {
      // This should not happen since we are awaiting the init.
      // Done to avoid typing issues.
      throw new Error('Counters have not been initialized.');
    }

    try {
      await OpenTelemetryMeterProvider.waitUntilNextFlushTime();

      // OpenTelemetry's forceFlush() will always succeed, even if the backend
      // fails and reports an error...
      //
      // So we use the OpenTelemetry Global Error Handler installed above
      // to keep a count of the number of errors reported, and if an error
      // is reported during a flush, we wait a while and try again.
      // Not perfect, but the best we can do.
      //
      // To avoid end-users seeing these errors, we supress error messages
      // until the very last flush attempt.
      //
      // Note that if the OpenTelemetry metrics are exported to Google Cloud
      // Monitoring, the first time a counter is used, it will fail to be
      // exported and will need to be retried.
      let attempts =
        OpenTelemetryMeterProvider.exporterParams.FLUSH_MAX_ATTEMPTS;
      while (attempts > 0) {
        const beforeFlushErrorCount =
          OpenTelemetryMeterProvider.openTelemetryErrorCount;

        // Suppress OTEL Diag error messages on all but the last flush attempt.
        OpenTelemetryMeterProvider.diagPinoLogger.suppressErrors = attempts > 1;
        await OpenTelemetryMeterProvider.meterProvider.forceFlush();
        OpenTelemetryMeterProvider.diagPinoLogger.suppressErrors = false;

        OpenTelemetryMeterProvider.lastForceFlushTime = Date.now();

        const afterFlushErrorCount =
          OpenTelemetryMeterProvider.openTelemetryErrorCount;
        if (beforeFlushErrorCount === afterFlushErrorCount) {
          // Success!
          return;
        }

        OpenTelemetryMeterProvider.diagPinoLogger.warn(
          'Opentelemetry reported errors during flushing, retrying.'
        );
        await sleep(
          OpenTelemetryMeterProvider.exporterParams.FLUSH_MIN_INTERVAL
        );
        attempts--;
      }

      if (attempts <= 0) {
        OpenTelemetryMeterProvider.diagPinoLogger.error(
          'Failed to flush counters after ' +
            OpenTelemetryMeterProvider.exporterParams.FLUSH_MAX_ATTEMPTS +
            'attempts - see OpenTelemetry logging'
        );
      }
    } catch (e) {
      OpenTelemetryMeterProvider.diagPinoLogger.error(
        `Error while flushing counters: ${e}`
      );
    } finally {
      OpenTelemetryMeterProvider.pendingFlush.resolve(null);
      OpenTelemetryMeterProvider.pendingFlush = null;
    }
  }

  /**
   * Initialize the OpenTelemetry metric exporters.
   *
   * If called more than once, will wait for the first call to complete.
   */
  static async initializeTelemetry(): Promise<void> {
    if (OpenTelemetryMeterProvider.isInitialized) return;

    if (OpenTelemetryMeterProvider.pendingInit) {
      await OpenTelemetryMeterProvider.pendingInit.promise;
      return;
    }
    OpenTelemetryMeterProvider.pendingInit = promiseWithResolvers();

    OpenTelemetryMeterProvider.initializeOpenTelemetryLogging();

    try {
      OpenTelemetryMeterProvider.diagPinoLogger.debug('initializing metrics');
      const resources = await OpenTelemetryMeterProvider.getResources();
      const [exporter, exporterMode] =
        OpenTelemetryMeterProvider.getExporterAndMode();

      OpenTelemetryMeterProvider.exporterMode = exporterMode;
      OpenTelemetryMeterProvider.exporterParams =
        EXPORTER_PARAMETERS[exporterMode];
      await OpenTelemetryMeterProvider.setMeterProvider(resources, exporter);
    } catch (e) {
      OpenTelemetryMeterProvider.pendingInit.reject(e);
    }

    OpenTelemetryMeterProvider.isInitialized = true;
    OpenTelemetryMeterProvider.pendingInit.resolve(null);
  }

  /** Sets up OpenTelemetry client libraries for logging. */
  private static initializeOpenTelemetryLogging() {
    diag.setLogger(OpenTelemetryMeterProvider.diagPinoLogger, {
      logLevel: DiagLogLevel.INFO,
      suppressOverrideMessage: true,
    });

    openTelemetrySetGlobalErrorHandler((error: OpenTelemetryException) => {
      OpenTelemetryMeterProvider.openTelemetryErrorCount++;
      // Delegate to Otel's own error handler for stringification.
      openTelemetryLoggingErrorHandler()(error);
    });
  }

  /** Gets resources. */
  private static async getResources(): Promise<IResource> {
    const resources = new GcpDetectorSync()
      .detect()
      .merge(new Resource(OpenTelemetryMeterProvider.resourceAttributes));
    if (resources.waitForAsyncAttributes) {
      await resources.waitForAsyncAttributes();
    }

    if (process.env.KUBERNETES_SERVICE_HOST) {
      if (process.env.K8S_POD_NAME) {
        OpenTelemetryMeterProvider.resourceAttributes[
          SEMRESATTRS_K8S_POD_NAME
        ] = process.env.K8S_POD_NAME;
      } else {
        OpenTelemetryMeterProvider.diagPinoLogger.warn(
          'WARNING: running under Kubernetes, but K8S_POD_NAME ' +
            'environment variable is not set. ' +
            'This may lead to Send TimeSeries errors'
        );
      }
    }

    return resources;
  }

  /** Gets the exporter and its mode. */
  private static getExporterAndMode(): [PushMetricExporter, ExporterMode] {
    let exporterMode;
    if (process.env.OTEL_COLLECTOR_URL) {
      switch (process.env.OTEL_IS_LONG_RUNNING_PROCESS) {
        case 'true':
          exporterMode = ExporterMode.OTEL_PERIODIC;
          break;
        case 'false':
          exporterMode = ExporterMode.OTEL_ONLY_FLUSHING;
          break;
        default:
          throw new Error(
            'Invalid value for env var OTEL_IS_LONG_RUNNING_PROCESS: ' +
              `"${process.env.OTEL_IS_LONG_RUNNING_PROCESS}"`
          );
      }

      OpenTelemetryMeterProvider.diagPinoLogger.info(
        `Counters mode: ${exporterMode} OTEL collector: ` +
          process.env.OTEL_COLLECTOR_URL
      );

      return [
        new OTLPMetricExporter({
          url: process.env.OTEL_COLLECTOR_URL,
          // @ts-expect-error: CompressionAlgorithm.NONE is not exported.
          compression: 'none',
        }),
        exporterMode,
      ];
    }

    exporterMode = ExporterMode.GCM_ONLY_FLUSHING;
    OpenTelemetryMeterProvider.diagPinoLogger.info(
      `Counters mode: ${exporterMode} using GCP monitoring`
    );
    return [
      new GcpMetricExporter({prefix: 'workload.googleapis.com'}),
      exporterMode,
    ];
  }

  /** Creates the meter provider for open telemetry. */
  private static async setMeterProvider(
    resources: IResource,
    exporter: PushMetricExporter
  ) {
    if (
      // Do not use bare !OpenTelemetryMeterProvider.exporterMode since enum
      // could be 0 while holding the first value.
      OpenTelemetryMeterProvider.exporterMode === null ||
      OpenTelemetryMeterProvider.exporterMode === undefined ||
      !OpenTelemetryMeterProvider.exporterParams
    ) {
      // This should not happen since exporter mode will be called and defined
      // first. This avoids null type errors.
      throw new Error('Exporter mode must be defined first.');
    }

    OpenTelemetryMeterProvider.meterProvider = new MeterProvider({
      resource: resources,
      readers: [
        new PeriodicExportingMetricReader({
          exportIntervalMillis:
            OpenTelemetryMeterProvider.exporterParams.PERIODIC_EXPORT_INTERVAL,
          exportTimeoutMillis:
            OpenTelemetryMeterProvider.exporterParams.PERIODIC_EXPORT_INTERVAL,
          exporter: exporter,
        }),
      ],
    });
  }

  /** Waits until the next force flush time. */
  private static async waitUntilNextFlushTime() {
    if (
      OpenTelemetryMeterProvider.exporterParams === null ||
      OpenTelemetryMeterProvider.exporterParams === undefined
    ) {
      // This should not happen since we are awaiting the init.
      // Done to avoid typing issues.
      throw new Error('Counters have not been initialized.');
    }
    // If flushed recently, wait for the min interval to pass.
    const millisUntilNextForceFlush =
      OpenTelemetryMeterProvider.lastForceFlushTime +
      OpenTelemetryMeterProvider.exporterParams.FLUSH_MIN_INTERVAL -
      Date.now();

    if (millisUntilNextForceFlush > 0) {
      // Wait until we can force flush again!
      OpenTelemetryMeterProvider.diagPinoLogger.debug(
        'Counters.tryFlush() waiting until flushing again'
      );
      await sleep(millisUntilNextForceFlush);
    }
  }
}
