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

/** @fileoverview Provides a DiagLogger that converts to Pino log levels. */

import {pino} from 'pino';
import {DiagLogger} from '@opentelemetry/api';

/**
 * Wrapper class for OpenTelemetry DiagLogger to convert to Pino log levels.
 */
export class DiagToPinoLogger implements DiagLogger {
  suppressErrors: boolean;

  constructor(private logger: pino.Logger) {
    // In some cases where errors may be expected, we want to be able to supress
    // them.
    this.suppressErrors = false;
  }

  /**
   * Logs a verbose message.
   * @param message
   * @param args
   */
  verbose(
    message: string,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ...args: any[]
  ) {
    this.logger.trace(`otel: ${message}`, args);
  }

  /**
   * Logs a verbose message.
   * @param message
   * @param args
   */
  debug(
    message: string,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ...args: any[]
  ) {
    this.logger.debug(`otel: ${message}`, args);
  }

  /**
   * Logs a verbose message.
   * @param message
   * @param args
   */
  info(
    message: string,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ...args: any[]
  ) {
    this.logger.info(`otel: ${message}`, args);
  }

  /**
   * Logs a verbose message.
   * @param message
   * @param args
   */
  warn(
    message: string,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ...args: any[]
  ) {
    this.logger.warn(`otel: ${message}`, args);
  }

  /**
   * Logs a verbose message.
   * @param message
   * @param args
   */
  error(
    message: string,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ...args: any[]
  ) {
    if (!this.suppressErrors) {
      this.logger.error(`otel: ${message}`, args);
    }
  }
}
