# Serverless event processing

This reference architecture is aimed at implementing an event-driven data
processing pipeline without having to manage the underlying infrastructure.

![Serverless event processing architecture](./serverless-event-processing-architecture.svg "Serverless event processing architecture")

For more information, see the
[Serverless event processing reference architecture](https://cloud.google.com/architecture/serverless-event-processing)
in the Google Cloud Architecture Center.

In this reference architecture, we use the creation of objects in a
[Cloud Storage bucket](https://cloud.google.com/storage/docs/buckets) as an
example of an event source, but it can be any
[event type and provider that Eventarc supports](https://cloud.google.com/eventarc/docs/event-providers-targets).

The example event processing workload that you deploy on Cloud Run emits the
events it receives in its log. You can refactor it to implement your event
processing business logic. For example, you can process the event, and save the
results in a Cloud Storage bucket or in a Firestore database.

## Prerequisites

To deploy this reference architecture in a Google Cloud project, you need to
authenticate with an account that has the `owner` role on that project.

## Deploy the reference architecture

In order to deploy this reference architecture, do the following from
[Cloud Shell](https://cloud.google.com/shell/docs):

1. Clone this repository.
1. Change the working directory to the directory where you cloned this repository.
1. Change the working directory to the `projects/serverless-event-processing/terraform` directory:

    ```sh
    cd projects/serverless-event-processing/terraform
    ```

1. Initialize the Terraform environment:

    ```sh
    terraform init
    ```

1. Run the provisioning process with Terraform:

    ```sh
    terraform apply
    ```

  Confirm and authorize Terraform when asked.

  When you run the provisioning process for the first time, Terraform asks for
  inputs, such as the Google Cloud project ID where you want to provision
  resources in. Terraform then stores the inputs you provided in a variables
  file that it automatically generates from a template.

  Also, during this first run of the provisioning process, Terraform stores the
  backend locally because there's no remote backend available yet.

1. Re-run the provisioning process to migrate the local Terraform backend to a
  remote backend on Cloud Storage:

    ```sh
    terraform init -migrate-state
    ```

  If Terraform asks for confirmation to migrate the backend, answer affirmatively.

## Create example events and outputs

As an example, you can create objects in the Cloud Storage bucket we use as an
event source. In order to deploy this reference architecture, do the following
from Cloud Shell:

1. Get the name of the source Cloud Storage bucket:

    ```sh
    SOURCE_CLOUD_STORAGE_BUCKET_NAME="$(terraform output -raw source_cloud_storage_bucket_name)"
    ```

1. Create an example file:

    ```sh
    echo "Hello World" > random.txt
    ```

1. Upload the example file in the Cloud Storage bucket:

    ```sh
    gsutil cp random.txt "gs://${SOURCE_CLOUD_STORAGE_BUCKET_NAME}/random.txt"
    ```

1. View the log entries related to the event processing service:

    ```sh
    gcloud logging read "resource.type=cloud_run_revision \
      AND resource.labels.service_name=$(terraform output -raw event_processor_cloud_run_service_name) \
      AND jsonPayload.event.bucket=${SOURCE_CLOUD_STORAGE_BUCKET_NAME}"
    ```

## Clean up

In order to delete the resources that this reference architecture provisions,
do the following:

1. Delete the remote backend configuration:

    ```sh
    rm backend.tf
    ```

1. Initialize a local backend with and migrate the state stored in the remote
  backend to the local backend:

    ```sh
    terraform init -migrate-state
    ```

    If Terraform asks for confirmation to migrate the backend, answer affirmatively.

    Migrating back from a remote backend to a local backend is necessary because
    the resource deletion process deletes the remote backend storage.

1. Delete resources:

    ```sh
    terraform destroy
    ```

  If Terraform asks for confirmation to migrate the backend, answer affirmatively.

## Troubleshooting

- When running `terraform apply`, you may get an error about the Eventarc
  Service Agent not being ready, similar to the following:

    ```text
    Error: Error creating Trigger: googleapi: Error 400: Invalid resource state for "":
    Permission denied while using the Eventarc Service Agent. If you recently
    started to use Eventarc, it may take a few minutes before all necessary
    permissions are propagated to the Service Agent. Otherwise, verify that it
    has Eventarc Service Agent role.
    ```

  If that happens, try running `terraform apply` again.
