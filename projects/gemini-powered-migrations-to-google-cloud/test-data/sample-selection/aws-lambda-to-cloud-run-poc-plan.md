# AWS Lambda function selection plan: aws-lambda-to-cloud-run-poc-plan

## AWS Lambda function analysis summary

| AWS Lambda Function Name  | Critical production system | Code size | Trigger type          | Programming language | External dependencies | Notes                                                                                   |
| ------------------------- | -------------------------- | --------- | --------------------- | -------------------- | --------------------- | --------------------------------------------------------------------------------------- |
| my-first-lambda-function  | ❌ No                      | 1064      | API Gateway (HTTP)    | python3.9            | No Layers             | Good for testing the basic migration process, but not a representative workload.        |
| image-processing-function | ❔ Maybe                   | 5120      | S3                    | nodejs18.x           | No Layers             | Triggered by S3 events, would require setting up Cloud Storage triggers.                |
| user-auth-service         | ✅ Yes                     | 20480     | API Gateway (HTTP)    | java11               | No Layers             | Critical production system, not suitable for a PoC.                                     |
| data-aggregator           | ❔ Maybe                   | 3072      | Kinesis               | go1.x                | No Layers             | Triggered by Kinesis stream, would require mapping to a Google Cloud streaming service. |
| api-gateway-authorizer    | ✅ Yes                     | 1536      | API Gateway (HTTP)    | nodejs16.x           | No Layers             | Good candidate, but focused on authorization logic.                                     |
| scheduled-backup-task     | ✅ Yes                     | 2048      | EventBridge (assumed) | python3.8            | No Layers             | Critical production task, not suitable for a PoC. Triggered by scheduled events.        |
| webhook-processor         | ❌ No                      | 1800      | API Gateway (HTTP)    | nodejs18.x           | No Layers             | ✅ Excellent candidate. HTTP-triggered, non-critical, and representative workload.      |
| iot-data-ingestor         | ❔ Maybe                   | 4096      | IoT Rule (assumed)    | python3.9            | No Layers             | Proprietary trigger (IoT Rule) makes it a complex candidate for a PoC.                  |
| file-conversion-service   | ❔ Maybe                   | 8192      | S3                    | dotnet6              | No Layers             | Triggered by S3 events, would require setting up Cloud Storage triggers.                |
| metrics-publisher         | ❔ Maybe                   | 1024      | EventBridge (assumed) | python3.9            | No Layers             | Triggered by scheduled events.                                                          |

## Recommendations for proof of concept migration

The recommended function for the proof of concept migration is the
**webhook-processor**.

### Reasoning

- **HTTP-Triggered**: The `webhook-processor` is confirmed to be triggered by
  API Gateway, meaning it's HTTP-triggered. This is a perfect match for Cloud
  Run's service model and simplifies the migration significantly.
- **Non-Critical**: Processing webhooks is often an asynchronous task that
  doesn't directly impact the main user-facing application, making it a safe
  choice for a PoC.
- **Representative Workload**: A webhook processor is a common use case and is
  representative of a real-world workload that receives data, processes it, and
  potentially calls other services.
- **Stateless**: Webhook processors are typically stateless, which aligns with
  the stateless nature of Cloud Run.
- **Minimal Proprietary Triggers**: An HTTP-triggered function has a clear and
  simple migration path to a Cloud Run service with a public endpoint, unlike
  functions triggered by IoT Rules or S3 events that require more complex
  mapping to Google Cloud equivalents.

### Assumptions and Missing Data

- **External Dependencies**: The assessment data does not show any of the
  functions using AWS Lambda Layers for external dependencies. However, it is
  common to package third-party libraries directly into the deployment zip file.
  We assume that the `webhook-processor` function may contain such libraries,
  which will allow us to test the container build process. If it does not, we
  can still proceed with it as the primary candidate and document the process of
  adding dependencies in a containerized environment.
- **Statelessness**: We are assuming the functions are stateless based on their
  names and triggers. A deeper code-level analysis would be required to confirm
  this, which is outside the scope of this initial assessment.
- **Scheduled Triggers**: For `scheduled-backup-task` and `metrics-publisher`,
  we are assuming an EventBridge (CloudWatch Events) trigger based on their
  names, as no event source mappings were found for them.

The **api-gateway-authorizer** is also a good HTTP-triggered candidate, but the
**webhook-processor** is a more general-purpose function that will provide a
better understanding of the migration process for a wider range of Lambda
functions.
