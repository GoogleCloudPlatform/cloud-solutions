/**
 * Copyright 2024 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/**
 * @fileoverview Create a default LoggerConfig for pino structured logging.
 *
 * @see https://cloud.google.com/logging/docs/structured-logging
 */

import * as pino from 'pino';
import {EventId} from 'eventid';
import {
  Logging,
  ServiceContext,
  detectServiceContext,
} from '@google-cloud/logging';
import {
  createDiagnosticEntry,
  DIAGNOSTIC_INFO_KEY,
  populateInstrumentationInfo,
} from '@google-cloud/logging/build/src/utils/instrumentation';
import * as gax from 'google-gax';

/** Monotonically increasing ID for insertId. */
const eventId = new EventId();

/*
 * Uses release-please annotations to update with latest version.
 * See
 * https://github.com/googleapis/release-please/blob/main/docs/customizing.md#updating-arbitrary-files
 */
const NODEJS_GCP_PINO_LIBRARY_VERSION = '1.0.0'; // {x-release-please-version}
const NODEJS_GCP_PINO_LIBRARY_NAME = 'nodejs-gcppino';

const PINO_TO_GCP_LOG_LEVELS = Object.freeze(
  Object.fromEntries([
    ['trace', 'DEBUG'],
    ['debug', 'DEBUG'],
    ['info', 'INFO'],
    ['warn', 'WARNING'],
    ['error', 'ERROR'],
    ['fatal', 'CRITICAL'],
  ])
) as Record<pino.Level, string>;

/**
 * Parameters for configuring GCP logging for Pino, allows specifying
 * serviceContext for Error Reporting.
 */
export interface GCPLoggingPinoOptions {
  /**
   * Optional details of service to be logged, and used in Cloud Error
   * Reporting.
   *
   * If specified, the {@link ServiceContext.service} name must be given.
   *
   * If not specified, a service name will be auto-detected from the
   * environment.
   *
   * @see https://cloud.google.com/error-reporting/docs/formatting-error-messages
   *
   */
  serviceContext?: ServiceContext;

  /**
   * Optional GoogleAuth - used to override defaults when detecting
   * ServiceContext from the environment.
   */
  auth?: gax.GoogleAuth;
}

/**
 * Encapsulates configuration and methods for formatting pino logs for Google
 * Cloud Logging.
 */
class GcpLoggingPino {
  serviceContext: ServiceContext | null = null;

  constructor(options?: GCPLoggingPinoOptions) {
    if (options?.serviceContext) {
      if (
        typeof options.serviceContext?.service !== 'string' ||
        !options.serviceContext?.service?.length
      ) {
        throw new Error('options.serviceContext.service must be specified.');
      }
      this.serviceContext = {...options.serviceContext};
      this.outputDiagnosticEntry();
    } else {
      // Use the Cloud Logging libraries to retrieve the ServiceContext
      // automatically from the environment.
      //
      // This requires initialising a Cloud Logger, then using
      // detectServiceContext to asynchronously return the ServiceContext
      const cloudLog = new Logging({auth: options?.auth}).logSync(
        NODEJS_GCP_PINO_LIBRARY_NAME
      );

      detectServiceContext(cloudLog.logging.auth).then(
        serviceContext => {
          this.serviceContext = serviceContext;
          this.outputDiagnosticEntry();
        },
        () => {
          // Ignore any errors raised by detectServiceContext.
          // Errors can occur if not running in a GCP environment.
        }
      );
    }
  }

  /**
   * Outputs a single log line once per process containing the diagnostic info
   * for this logger.
   *
   * Note that it is not possible for this package to perform API level logging
   * with a line of the form cloud-solutions/pino-logging-gcp-config-v1.0.0
   */
  outputDiagnosticEntry() {
    const diagEntry = createDiagnosticEntry(
      NODEJS_GCP_PINO_LIBRARY_NAME,
      NODEJS_GCP_PINO_LIBRARY_VERSION
    );
    diagEntry.data[DIAGNOSTIC_INFO_KEY].runtime = process.version;

    const [entries, isInfoAdded] = populateInstrumentationInfo(diagEntry);
    if (!isInfoAdded || entries.length === 0) {
      return;
    }
    pino.version;
    // Create a temp pino logger instance just to log this diagnostic entry.
    pino
      .pino({
        level: 'info',
        ...this.getPinoLoggerOptions(),
      })
      .info({
        ...diagEntry.data,
      });
  }

  /**
   * Creates a JSON fragment string containing the timestamp in GCP logging
   * format.
   *
   * @example ', "timestamp": { "seconds": 123456789, "nanos": 123000000 }'
   *
   * Creating a string with seconds/nanos is ~10x faster than formatting the
   * timestamp as an ISO string.
   *
   * @see https://cloud.google.com/logging/docs/agent/logging/configuration#timestamp-processing
   *
   * As Javascript Date uses millisecond precision, in
   * {@link formatLogObject} the logger adds a monotonically increasing insertId
   * into the log object to preserve log order inside GCP logging.
   *
   * @see https://github.com/googleapis/nodejs-logging/blob/main/src/entry.ts#L189
   */
  static getGcpLoggingTimestamp() {
    const seconds = Date.now() / 1000;
    const secondsRounded = Math.floor(seconds);
    // The following line is 2x as fast as seconds % 1000
    // Uses Math.round, not Math.floor due to JS floating point...
    // eg for a Date.now()=1713024754120
    // (seconds-secondsRounded)*1000 => 119.99988555908203
    const millis = Math.round((seconds - secondsRounded) * 1000);
    return `,"timestamp":{"seconds":${secondsRounded},"nanos":${millis}000000}`;
  }

  /**
   * Converts pino log level to Google severity level.
   *
   * @see pino.LoggerOptions.formatters.level
   */
  static pinoLevelToGcpSeverity(
    pinoSeverityLabel: string,
    pinoSeverityLevel: number
  ): Record<string, unknown> {
    const pinoLevel = pinoSeverityLabel as pino.Level;
    const severity = PINO_TO_GCP_LOG_LEVELS[pinoLevel] ?? 'INFO';
    return {
      severity,
      level: pinoSeverityLevel,
    };
  }

  /**
   * Reformats log entry record for GCP.
   *
   * * Adds OpenTelemetry properties with correct key.
   * * Adds stack_trace if an Error is given in the err property.
   * * Adds serviceContext
   * * Adds sequential insertId to preserve logging order.
   */
  formatLogObject(entry: Record<string, unknown>): Record<string, unknown> {
    // OpenTelemetry adds properties trace_id, span_id, trace_flags. If these
    // are present, not null and not blank, convert them to the property keys
    // specified by GCP logging.
    //
    // @see https://cloud.google.com/logging/docs/structured-logging#special-payload-fields
    // @see https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/logs/data-model.md#trace-context-fields
    if ((entry.trace_id as string | undefined)?.length) {
      entry['logging.googleapis.com/trace'] = entry.trace_id;
      delete entry.trace_id;
    }
    if ((entry.span_id as string | undefined)?.length) {
      entry['logging.googleapis.com/spanId'] = entry.span_id;
      delete entry.span_id;
    }
    // Trace flags is a bit field even though there is one on defined bit,
    // so lets convert it to an int and test against a bitmask.
    // @see https://www.w3.org/TR/trace-context/#trace-flags
    const trace_flags_bits = parseInt(entry.trace_flags as string);
    if (!!trace_flags_bits && (trace_flags_bits & 0x1) === 1) {
      entry['logging.googleapis.com/trace_sampled'] = true;
    }
    delete entry.trace_flags;

    if (this.serviceContext) {
      entry.serviceContext = this.serviceContext;
    }

    // If there is an Error, add the stack trace for Event Reporting.
    if (entry.err instanceof Error && entry.err.stack) {
      entry.stack_trace = entry.err.stack;
    }

    // Add a sequential EventID.
    //
    // This is required because Javascript Date has a very coarse granularity
    // (millisecond), which makes it quite likely that multiple log entries
    // would have the same timestamp.
    //
    // The GCP Logging API doesn't guarantee to preserve insertion order for
    // entries with the same timestamp. The service does use `insertId` as a
    // secondary ordering for entries with the same timestamp. `insertId` needs
    // to be globally unique (within the project) however.
    //
    // We use a globally unique monotonically increasing EventId as the
    // insertId.
    //
    // @see https://github.com/googleapis/nodejs-logging/blob/main/src/entry.ts#L189
    entry['logging.googleapis.com/insertId'] = eventId.new();

    return entry;
  }

  /**
   * Creates a pino.LoggerOptions configured for GCP structured logging.
   */
  getPinoLoggerOptions(
    pinoOptionsMixin?: pino.LoggerOptions
  ): pino.LoggerOptions {
    const formattersMixin = pinoOptionsMixin?.formatters;
    return {
      ...pinoOptionsMixin,
      // Use 'message' instead of 'msg' as log entry message key.
      messageKey: 'message',
      formatters: {
        ...formattersMixin,
        level: GcpLoggingPino.pinoLevelToGcpSeverity,
        log: (entry: Record<string, unknown>) => this.formatLogObject(entry),
      },
      timestamp: () => GcpLoggingPino.getGcpLoggingTimestamp(),
    };
  }
}

/**
 * Creates a {@link pino.LoggerOptions} object which configures pino to output
 * JSON records compatible with
 * {@link https://cloud.google.com/logging/docs/structured-logging|Google Cloud structured Logging}.
 *
 * @param pinoLoggerOptions Additional Pino Logger settings that will be added to
 * the returned value.
 *
 * @example
 *      const logger = pino.pino(
 *        createGcpLoggingPinoConfig(
 *          {
 *            serviceContext: {
 *              service: 'my-service',
 *              version: '1.2.3',
 *            },
 *          },
 *          {
 *            // Set Pino log level to 'debug'.
 *            level: 'debug',
 *          }
 *        )
 *      );
 *
 *      logger.info('hello world');
 *      logger.error(err, 'failure: ' + err);
 */
export function createGcpLoggingPinoConfig(
  options?: GCPLoggingPinoOptions,
  pinoLoggerOptions?: pino.LoggerOptions
): pino.LoggerOptions {
  return new GcpLoggingPino(options).getPinoLoggerOptions(pinoLoggerOptions);
}

export const TEST_ONLY = {
  PINO_TO_GCP_LOG_LEVELS,
};
