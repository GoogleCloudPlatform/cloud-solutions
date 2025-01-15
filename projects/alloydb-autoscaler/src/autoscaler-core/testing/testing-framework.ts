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

/** @fileoverview Provides utilities for testing. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import pino from 'pino';

type LoggerMock = jasmine.SpyObj<pino.Logger>;

/**
 * Creates a pino.Logger with mocks.
 *
 * Output from logs is also muted.
 */
export const createLoggerWithMocks = (): LoggerMock => {
  const loggerWithMocks = jasmine.createSpyObj('Logger', [
    'debug',
    'error',
    'info',
    'trace',
    'warn',
    'child',
  ]);
  loggerWithMocks.child.and.callFake(() => createLoggerWithMocks());
  return loggerWithMocks;
};

/**
 * Creates an instanceLogger mock with its baseLogger.
 *
 * Returns:
 *   baseLogger: used in classes which will create instance loggers from base.
 *   instanceLogger: to be used for mocks.
 */
export const createInstanceLoggerWithMocks = (): [LoggerMock, LoggerMock] => {
  const baseLogger: LoggerMock = createLoggerWithMocks();
  const instanceLogger: LoggerMock = createLoggerWithMocks();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  baseLogger.child.and.returnValue(instanceLogger as any);
  return [baseLogger, instanceLogger];
};

/**
 * Creates an payloadLogger mock with its baseLogger.
 *
 * Returns:
 *   baseLogger: used in classes which will create instance loggers from base.
 *   payloadLogger: to be used for mocks.
 */
export const createPayloadLoggerWithMocks = (): [LoggerMock, LoggerMock] => {
  const [baseLogger, instanceLogger] = createInstanceLoggerWithMocks();
  const payloadLogger = createLoggerWithMocks();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  instanceLogger.child.and.returnValue(payloadLogger as any);
  return [baseLogger, payloadLogger];
};

/** Mock of pino.Logger with no output. */
export const silentLogger: jasmine.SpyObj<pino.Logger> =
  createLoggerWithMocks();
