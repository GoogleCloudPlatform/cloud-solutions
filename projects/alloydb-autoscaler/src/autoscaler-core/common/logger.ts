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

/** @fileoverview Provides a basic logger. */

import {createGcpLoggingPinoConfig} from '@google-cloud/pino-logging-gcp-config';
import packageJson from '../../../package.json';
import process from 'node:process';
import {pino} from 'pino';
import {ScalableInstance, ScalableInstanceWithData} from './instance-info';

/**
 * Maps GCP log severity to Pino log levels.
 *
 * @see https://cloud.google.com/logging/docs/reference/v2/rest/v2/LogEntry#logseverity
 */
const GcpSeverityToPinoLevel: Map<string, pino.Level> = new Map([
  ['debug', 'debug'],
  ['error', 'error'],
  ['critical', 'fatal'],
  ['info', 'info'],
  ['debug', 'trace'],
  ['warning', 'warn'],
]);

const DEFAULT_LOG_LEVEL: pino.Level = 'debug';
const DEFAULT_TEST_LOG_LEVEL: pino.Level = 'fatal';

/** Gets the default Pino log level based on environment. */
const getDefaultLogLevel = () => {
  if (process.env.NODE_ENV?.toLowerCase() === 'test') {
    return DEFAULT_TEST_LOG_LEVEL;
  }
  return DEFAULT_LOG_LEVEL;
};

/**
 * Returns a pino log level based on environment variable LOG_LEVEL which can
 * be either a GCP or a pino log level.
 *
 * If not defined, use DEBUG normally, or CRITICAL/FATAL in NODE_ENV=test
 * mode.
 * @return Logging level in Pino format.
 */
const getLogLevel = (): pino.Level => {
  const envLogLevel = process.env.LOG_LEVEL
    ? process.env.LOG_LEVEL.toLowerCase()
    : null;

  if (!envLogLevel) return getDefaultLogLevel();

  const pinoLevel = GcpSeverityToPinoLevel.has(envLogLevel)
    ? GcpSeverityToPinoLevel.get(envLogLevel)
    : envLogLevel;

  if (!pinoLevel) return getDefaultLogLevel();

  if (Object.values(pino.levels.labels).includes(pinoLevel)) {
    return pinoLevel as pino.Level;
  }

  return getDefaultLogLevel();
};

/**
 * Creates a Pino logger.
 * @param service Service which is logging.
 * @param version Version of the service which is logging.
 */
export function createLogger(
  service: string = packageJson.name,
  version: string = packageJson.version
): pino.Logger {
  return pino(
    createGcpLoggingPinoConfig(
      /* options= */ {
        serviceContext: {
          service: service,
          version: version,
        },
      },
      /* pinoLoggerOptions= */ {
        level: getLogLevel(),
      }
    )
  );
}

/** Creates a logger with the instance information. */
export const getInstanceLogger = (
  baseLogger: pino.Logger,
  instance: ScalableInstance | ScalableInstanceWithData
): pino.Logger => {
  return baseLogger.child({...instance.info});
};

/** Creates a logger with the payload and optionally the instance info. */
export const getPayloadLogger = (
  baseLogger: pino.Logger,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload: Record<string, any>,
  instance: ScalableInstance | ScalableInstanceWithData
): pino.Logger => {
  const derivedLogger = instance
    ? getInstanceLogger(baseLogger, instance)
    : baseLogger;
  return derivedLogger.child({payload: payload});
};
