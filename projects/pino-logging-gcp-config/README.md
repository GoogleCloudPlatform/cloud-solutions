# Pino Google Cloud Logging configuration for Node.JS

This library contains the code to generate a Pino configuration which outputs
[JSON structured logs for Google Cloud Logging](https://cloud.google.com/logging/docs/structured-logging).

This can be used with any Google Cloud service that captures logs written to
stdout (such as Cloud Run, Cloud Run Functions and Google Kubernetes Engine
workloads), so that the logging is formatted correctly in [Google Cloud
Logging](https://cloud.google.com/logging/docs). This then alllows filtering by
log level, the ability to include structured data in the logs, and reporting of
errors with stack traces to
[Google Cloud Error Reporting](https://cloud.google.com/error-reporting/docs)

## Features

-   Converts Pino log levels to Google Cloud Logging log levels.
-   Uses `message` instead of `msg` for the message key.
-   Adds a millisecond-granularity timestamp in a
    [format recognised by Google Cloud Logging](https://cloud.google.com/logging/docs/agent/logging/configuration#timestamp-processing),
    eg:\
    `"timestamp":{"seconds":1445470140,"nanos":123000000}`.
-   Adds a sequential
    [insertId](https://cloud.google.com/logging/docs/reference/v2/rest/v2/LogEntry#FIELDS.insert_id)
    to ensure log messages with identical timestamps are ordered correctly.
-   Logs including an Error object have the
    [stack_trace property](https://cloud.google.com/error-reporting/docs/formatting-error-messages#log-error)
    set so that the error is forwarded to Google Cloud Error Reporting.
-   Includes a
    [ServiceContext](https://cloud.google.com/error-reporting/reference/rest/v1beta1/ServiceContext)
    object in the logs for Google Cloud Error Reporting.
-   Maps the OpenTelemetry properties `span_id`, `trace_id`, `trace_flags` to
    the equivalent
    [Google Cloud Logging fields](https://cloud.google.com/logging/docs/structured-logging#structured_logging_special_fields).

See the full [documentation on Github](https://googlecloudplatform.github.io/cloud-solutions/pino-logging-gcp-config).
