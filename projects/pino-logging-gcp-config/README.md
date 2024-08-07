# Pino GCP Logging configuration for Node.JS

This project contains the Typescript code to generate a Pino configuration which
will output
[JSON structured logs for Google Cloud Logging](https://cloud.google.com/logging/docs/structured-logging).

This can be used with any Google Cloud service that captures logs written to
stdout, for example Cloud Run and Cloud Functions.

## Features

-   uses "message" not "msg" for log message field.
-   Converts Pino log levels to Google Cloud Logging log levels.
-   Adds an
    [insertId](https://cloud.google.com/logging/docs/reference/v2/rest/v2/LogEntry#FIELDS.insert_id)
    to ensure log messages with identical timestamps are kept in order.
-   Adds a timestamp in a
    [format recognised by Google Cloud Logging](https://cloud.google.com/logging/docs/agent/logging/configuration#timestamp-processing).
-   Logs including an Error have the
    [stack_trace property](https://cloud.google.com/error-reporting/docs/formatting-error-messages#log-error)
    set so that the error is forwarded to Google Cloud Error Reporting.
-   Includes a
    [ServiceContext](https://cloud.google.com/error-reporting/reference/rest/v1beta1/ServiceContext)
    object in the logs for Google Cloud Error Reporting.
-   Maps the OpenTelemetry properties `span_id`, `trace_id`, `trace_flags` to
    the equivalent
    [Google Cloud Logging fields](https://cloud.google.com/logging/docs/structured-logging#structured_logging_special_fields).

## Example Usage

Install required dependencies

```bash
npm install --save pino eventid @google-cloud/logging google-gax
```

```typescript
import as pino from 'pino';
import {...createGcpLoggingPinoConfig} from './pino_gcp_config';

const logger = pino.pino(
  createGcpLoggingPinoConfig(
    {
      serviceContext: {
        service: 'my-service',
        version: '1.2.3',
      },
    },
    {
      // set Pino log level to 'debug'
      level: 'debug',
    }
  )
);

logger.info('hello world');
const err = new Error('some exception');
logger.error(err, 'Caught an exception: %s', err);
logger.debug(
  {
    someProperties: 'some value',
  },
  'logging with extra properties'
);
```

## Example output (reformatted)

<!-- markdownlint-capture -->
<!-- markdownlint-disable MD013 -->

```json
  {
    "severity": "INFO",
    "level": 30,
    "timestamp": {
      "seconds": 1717778097,
      "nanos": 375000000
    },
    "pid": 601658,
    "hostname": "myHostName",
    "logging.googleapis.com/insertId": "..........40FL7.zwt0uNYGdcmFiUn_",
    "serviceContext": {
      "service": "my-service",
      "version": "0.0.1"
    },
    "message": "hello world"
  }
  {
    "severity": "ERROR",
    "level": 50,
    "timestamp": {
      "seconds": 1717778097,
      "nanos": 377000000
    },
    "pid": 601658,
    "hostname": "myHostName",
    "err": {
      "type": "Error",
      "message": "some exception",
      "stack": "Error: some exception\n    at Object.<anonymous> (/some/dir/pino-logging-gcp-config/build/src/example.js:14:13)\n    at Module._compile (node:internal/modules/cjs/loader:1434:14)\n    at Module._extensions..js (node:internal/modules/cjs/loader:1518:10)\n    at Module.load (node:internal/modules/cjs/loader:1249:32)\n    at Module._load (node:internal/modules/cjs/loader:1065:12)\n    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:158:12)\n    at node:internal/main/run_main_module:30:49"
    },
    "logging.googleapis.com/insertId": "..........80FL7.zwt0uNYGdcmFiUn_",
    "serviceContext": {
      "service": "my-service",
      "version": "0.0.1"
    },
    "stack_trace": "Error: some exception\n    at Object.<anonymous> (/some/dir/pino-logging-gcp-config/build/src/example.js:14:13)\n    at Module._compile (node:internal/modules/cjs/loader:1434:14)\n    at Module._extensions..js (node:internal/modules/cjs/loader:1518:10)\n    at Module.load (node:internal/modules/cjs/loader:1249:32)\n    at Module._load (node:internal/modules/cjs/loader:1065:12)\n    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:158:12)\n    at node:internal/main/run_main_module:30:49",
    "message": "Caught an exception: Error: some exception"
  }
  {
    "severity": "DEBUG",
    "level": 20,
    "timestamp": {
      "seconds": 1717778097,
      "nanos": 378000000
    },
    "pid": 601658,
    "hostname": "myHostName",
    "someProperties": "some value",
    "logging.googleapis.com/insertId": "..........C0FL7.zwt0uNYGdcmFiUn_",
    "serviceContext": {
      "service": "my-service",
      "version": "0.0.1"
    },
    "message": "logging with extra properties"
  }
```

<!-- markdownlint-restore -->
