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
import {createLogger} from '../logger';

describe('logger', () => {
  describe('createLogger', () => {
    beforeEach(() => {
      process.env.LOG_LEVEL = undefined;
      process.env.NODE_ENV = undefined;
    });

    it('returns a logger instance that can log', () => {
      const output = createLogger();

      expect(() => {
        output.debug('message');
        output.error('message');
        output.fatal('message');
        output.info('message');
        output.trace('message');
        output.warn('message');
      }).not.toThrow();
    });

    it('sets level from env LOG_LEVEL', () => {
      process.env.LOG_LEVEL = 'info';

      const output = createLogger();

      expect(output.level).toEqual('info');
    });

    it('maps GCP level to Pino level from env LOG_LEVEL', () => {
      process.env.LOG_LEVEL = 'warning';

      const output = createLogger();

      expect(output.level).toEqual('warn');
    });

    it('sets level to debug by default', () => {
      const output = createLogger();

      expect(output.level).toEqual('debug');
    });

    it('sets level to fatal by default, in test mode', () => {
      process.env.NODE_ENV = 'test';

      const output = createLogger();

      expect(output.level).toEqual('fatal');
    });

    it('sets level to default, if env log level is invalid', () => {
      process.env.LOG_LEVEL = 'made-up-level';

      const output = createLogger();

      expect(output.level).toEqual('debug');
    });
  });
});
