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

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import {createGcpLoggingPinoConfig, TEST_ONLY} from './pino_gcp_config';
import * as pino from 'pino';
import {setInstrumentationStatus} from '@google-cloud/logging/build/src/utils/instrumentation';
import * as fs from 'node:fs/promises';
import * as os from 'node:os';
import * as crypto from 'node:crypto';

const serviceContext = {
  service: 'test',
  version: '0.1.0',
};

describe('Pino config', () => {
  describe('Without project ID', () => {
    const loggerConfig = {
      serviceContext,
      // Blank project ID prevents env lookup, but means no project ID set.
      traceGoogleCloudProjectId: '',
      inihibitDiagnosticMessage: true,
    };
    const config = createGcpLoggingPinoConfig(loggerConfig);

    it('should add mixins to the config object', () => {
      const pinoLoggerOptions: pino.LoggerOptions = {
        level: 'defaultLevel',
        formatters: {
          bindings: x => {
            return {a: x};
          },
        },
      };

      const configWithMixins = createGcpLoggingPinoConfig(
        loggerConfig,
        pinoLoggerOptions
      );

      expect(configWithMixins.level).toEqual('defaultLevel');
      expect(configWithMixins.formatters?.bindings).toBeDefined();
    });

    describe('Log level conversion', () => {
      // Need to define the return type of levelConverter because pino leaves it
      // as a plain `object`
      // eslint-disable-next-line @typescript-eslint/no-non-null-asserted-optional-chain
      const levelConverter = config.formatters?.level! as (
        label: string,
        level: number
      ) => Record<string, unknown>;

      Object.entries(TEST_ONLY.PINO_TO_GCP_LOG_LEVELS).forEach(e => {
        it(`converts pino level ${e[0]} to GCP ${e[1]}`, () => {
          const convertedLevel = levelConverter(e[0], 42);

          expect(convertedLevel.severity).toEqual(e[1]);
        });
      });

      it('defaults to INFO for an unknown level', () => {
        expect(levelConverter('blah', 66).severity).toEqual('INFO');
      });
    });

    describe('log formatter', () => {
      // eslint-disable-next-line @typescript-eslint/no-non-null-asserted-optional-chain
      const formatLogObject = config.formatters?.log!;
      const TEST_DATE = new Date('2024-04-13T16:12:34.123Z');

      beforeEach(() => {
        jasmine.clock().install();
        jasmine.clock().mockDate(TEST_DATE);
      });

      afterEach(() => {
        jasmine.clock().uninstall();
      });

      it('should add serviceContext', () => {
        const logObject = formatLogObject({});

        expect(logObject.serviceContext).toEqual({
          service: 'test',
          version: '0.1.0',
        });
      });

      it('should add insertId', () => {
        const logObject = formatLogObject({});

        expect(logObject['logging.googleapis.com/insertId']).toBeDefined();
        expect(
          (logObject['logging.googleapis.com/insertId'] as string).length
        ).toBeGreaterThan(1);
      });

      it('should add stack_trace when err is an Error', () => {
        const logObject = formatLogObject({
          err: new Error('some error message'),
          message: 'thrown an exception',
        });

        expect(logObject.stack_trace).toMatch('Error: some error message\n');
      });

      it('should not add stack_trace when err is not an Error', () => {
        const logObject = formatLogObject({
          err: 'some error message',
          message: 'thrown a string as an exception',
        });

        expect(logObject.stack_trace).toBeUndefined();
      });

      it('should not map span and trace properties when not present', () => {
        const formattedLog = formatLogObject({message: 'hello'});

        expect(
          formattedLog['logging.googleapis.com/trace_sampled']
        ).toBeUndefined();
        expect(formattedLog['logging.googleapis.com/trace']).toBeUndefined();
        expect(formattedLog['logging.googleapis.com/spanId']).toBeUndefined();
      });

      it('should replace span and trace properties when present', () => {
        const formattedLog = formatLogObject({
          message: 'hello',
          trace_id: 'trace:12345',
          span_id: 'span:23456',
          trace_flags: 1,
        });

        expect(formattedLog['logging.googleapis.com/trace_sampled']).toBeTrue();
        expect(formattedLog['logging.googleapis.com/trace']).toBe(
          'trace:12345'
        );
        expect(formattedLog['logging.googleapis.com/spanId']).toBe(
          'span:23456'
        );
        expect(formattedLog.trace_id).toBeUndefined();
        expect(formattedLog.span_id).toBeUndefined();
        expect(formattedLog.trace_flags).toBeUndefined();
      });

      it('should not mutate input', () => {
        const input = {};
        formatLogObject(input);

        expect(input).toEqual({});
      });

      it('should call user-defined formatter.log before GCP formatting', () => {
        // userLog will add a custom property, which should be present in the final GCP-formatted log
        const userLog = jasmine.createSpy('userLog').and.callFake(entry => {
          return {...entry, custom: 'user'};
        });
        const configWithUserLog = createGcpLoggingPinoConfig(loggerConfig, {
          formatters: {
            log: userLog,
          },
        });
        const logObj = {foo: 'bar'};
        const result = configWithUserLog.formatters!.log!(logObj);
        expect(userLog).toHaveBeenCalled();
        expect(result).toBeDefined();
        expect(result.foo).toBe('bar');
        expect(result.custom).toBe('user');
        expect(result.serviceContext).toEqual(serviceContext);
        expect(result['logging.googleapis.com/insertId']).toBeDefined();
      });

      it('adds a timestamp as seconds:nanos JSON fragment', () => {
        const timestampGenerator = config.timestamp as () => string;

        expect(timestampGenerator()).toEqual(
          ',"timestamp":{"seconds":1713024754,"nanos":123000000}'
        );
      });

      it('adds a timestamp as seconds:nanos JSON fragment when nanos is 0', () => {
        jasmine.clock().mockDate(new Date('2024-04-13T16:12:34.000Z'));
        const timestampGenerator = config.timestamp as () => string;

        expect(timestampGenerator()).toEqual(
          ',"timestamp":{"seconds":1713024754,"nanos":0}'
        );
      });
    });
  });
  describe('with project ID', () => {
    const config = createGcpLoggingPinoConfig({
      serviceContext,
      // Blank project ID prevents env lookup, but means no project ID set.
      traceGoogleCloudProjectId: 'test-project',
      inihibitDiagnosticMessage: true,
    });

    it('should replace span and trace properties when present', () => {
      const formattedLog = config.formatters!.log!({
        message: 'hello',
        trace_id: 'trace:12345',
        span_id: 'span:23456',
        trace_flags: 1,
      });

      expect(formattedLog['logging.googleapis.com/trace_sampled']).toBeTrue();
      expect(formattedLog['logging.googleapis.com/trace']).toBe(
        'projects/test-project/traces/trace:12345'
      );
      expect(formattedLog['logging.googleapis.com/spanId']).toBe('span:23456');
      expect(formattedLog.trace_id).toBeUndefined();
      expect(formattedLog.span_id).toBeUndefined();
      expect(formattedLog.trace_flags).toBeUndefined();
    });
  });
});

describe('Instrumentation', () => {
  let tempPath: string;
  // Initialise pinoDestinationStream with stdout to get the correct type
  // info.
  let pinoDestinationStream = pino.destination(1);

  beforeEach(() => {
    setInstrumentationStatus(false);
    // This resets a global property set by cloud logging which enforces
    // that instrumentation is only written once per process. However we want
    // to retest it multiple times in the same process...
    (
      global as {shouldSkipInstrumentationCheck?: boolean}
    ).shouldSkipInstrumentationCheck = false;

    // Create tempfile and destinationStream.
    tempPath =
      os.tmpdir() + '/pino-test-' + crypto.randomBytes(16).toString('hex');
    pinoDestinationStream = pino.destination({dest: tempPath, sync: true});
  });

  afterEach(async () => {
    // Cleanup tempfile.
    pinoDestinationStream?.destroy();
    await fs.rm(tempPath);
  });

  it('Should log instrumentation to specified stream', async () => {
    const config = createGcpLoggingPinoConfig({
      serviceContext,
      traceGoogleCloudProjectId: 'test-project',
      pinoDestinationStream: pinoDestinationStream,
    });
    pino.pino(config, pinoDestinationStream).info('hello world');
    pinoDestinationStream.flushSync();

    const logged = (await fs.readFile(tempPath, 'utf8'))
      .trim()
      .split('\n')
      .map(s => JSON.parse(s));

    expect(
      logged[0]['logging.googleapis.com/diagnostic']?.instrumentation_source[0]
        ?.name
    ).toBe('nodejs-gcppino');
    expect(logged[1]?.message).toBe('hello world');
  });

  it('Should not log any instrumentation', async () => {
    const config = createGcpLoggingPinoConfig({
      serviceContext,
      traceGoogleCloudProjectId: 'test-project',
      pinoDestinationStream: pinoDestinationStream,
      inihibitDiagnosticMessage: true,
    });
    pino.pino(config, pinoDestinationStream).info('hello world');
    pinoDestinationStream.flushSync();

    const logged = await fs.readFile(tempPath, 'utf8');

    expect(logged).not.toContain('logging.googleapis.com/diagnostic');
    expect(logged).toContain('hello world');
  });

  it('Should inlude pinoOptionsMixins results into any instrumentation', async () => {
    createGcpLoggingPinoConfig(
      {
        serviceContext,
        traceGoogleCloudProjectId: 'test-project',
        pinoDestinationStream: pinoDestinationStream,
      },
      {
        name: 'CustomLoggerName',
      }
    );
    pinoDestinationStream.flushSync();

    const logged = JSON.parse(await fs.readFile(tempPath, 'utf8'));
    expect(
      logged['logging.googleapis.com/diagnostic']?.instrumentation_source[0]
        ?.name
    ).toBe('nodejs-gcppino');
    expect(logged.name).toBe('CustomLoggerName');
  });

  it('Should log instrumentation asynchronously after construction', async () => {
    // Creating the logging without serviceContext or projectID to trigger
    // retrieving them async via the environment.
    // Use the TEST_ONLY constructor to access the pendingInit member
    const gcpLoggingPino = new TEST_ONLY.GcpLoggingPino({
      pinoDestinationStream: pinoDestinationStream,
    });
    expect(gcpLoggingPino.pendingInit).toBeInstanceOf(Promise);
    await gcpLoggingPino.pendingInit;

    pino
      .pino(gcpLoggingPino.pinoLoggerOptions, pinoDestinationStream)
      .info('hello world');

    pinoDestinationStream.flushSync();

    const logged = await fs.readFile(tempPath, 'utf8');

    expect(logged).toContain('logging.googleapis.com/diagnostic');
    expect(logged).toContain('hello world');
  });
});
