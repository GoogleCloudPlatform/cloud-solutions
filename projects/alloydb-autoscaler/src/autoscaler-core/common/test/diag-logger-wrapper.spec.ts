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

/** @fileoverview Tests for base logger. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import pino from 'pino';
import {DiagToPinoLogger} from '../diag-logger-wrapper';
import {createLoggerWithMocks} from '../../testing/testing-framework';

describe('DiagToPinoLogger', () => {
  let pinoLoggerMock: jasmine.SpyObj<pino.Logger>;
  const otherArgs = [1, false];

  beforeEach(() => {
    pinoLoggerMock = createLoggerWithMocks();
  });

  it('logs verbose messages', () => {
    const logger = new DiagToPinoLogger(pinoLoggerMock);
    const otherArgs = [1, false];

    logger.verbose('verbose', ...otherArgs);

    expect(pinoLoggerMock.trace).toHaveBeenCalledOnceWith(
      'otel: verbose',
      otherArgs
    );
  });

  it('logs debug messages', () => {
    const logger = new DiagToPinoLogger(pinoLoggerMock);

    logger.debug('debug', ...otherArgs);

    expect(pinoLoggerMock.debug).toHaveBeenCalledWith('otel: debug', otherArgs);
  });

  it('logs info messages', () => {
    const logger = new DiagToPinoLogger(pinoLoggerMock);

    logger.info('info', ...otherArgs);

    expect(pinoLoggerMock.info).toHaveBeenCalledWith('otel: info', otherArgs);
  });

  it('logs warning messages', () => {
    const logger = new DiagToPinoLogger(pinoLoggerMock);

    logger.warn('warn', ...otherArgs);

    expect(pinoLoggerMock.warn).toHaveBeenCalledWith('otel: warn', otherArgs);
  });

  it('logs error messages', () => {
    const logger = new DiagToPinoLogger(pinoLoggerMock);

    logger.error('error', ...otherArgs);

    expect(pinoLoggerMock.error).toHaveBeenCalledWith('otel: error', otherArgs);
  });

  it('does not log error messages when surpressed', () => {
    const logger = new DiagToPinoLogger(pinoLoggerMock);

    logger.suppressErrors = true;
    logger.error('error', ...otherArgs);

    expect(pinoLoggerMock.error).not.toHaveBeenCalled();
  });
});
