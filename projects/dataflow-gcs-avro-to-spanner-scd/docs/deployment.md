# Build and Deploy Dataflow Flex Template for Avro to Cloud Spanner with Slowly Changing Dimensions (SCD)

The following are instructions to build and deploy this Dataflow Flex Template.

This article provides instructions for creating a Dataflow Flex template for the
pipeline, followed by deploying a Dataflow pipeline to insert Avro records into
a Cloud Spanner database using one of the supported SCD Types.

## Cloud costs

This solution uses billable components of Google Cloud, including the following:

*   [Dataflow](https://cloud.google.com/dataflow/pricing)
*   [Cloud Storage](https://cloud.google.com/storage/pricing)
*   [Artifact Registry](https://cloud.google.com/artifact-registry/pricing)
*   [Cloud Spanner](https://cloud.google.com/spanner/pricing)

Consider
[cleaning up the resources](https://cloud.google.com/dataflow/docs/guides/templates/using-flex-templates#clean-up)
when they are no longer needed.

## Getting started

<!--
  TODO: create Terraform script deployment to facilitate end-to-end deployment.
-->

### Steps to set up your project

1.  Open the [Cloud Console](https://console.cloud.google.com/) for your
    project.

1.  Activate [Cloud Shell](https://console.cloud.google.com/?cloudshell=true).
    At the bottom of the Cloud Console, a Cloud Shell session starts and
    displays a command-line prompt. Cloud Shell is a shell environment with the
    Cloud SDK already installed, including the gcloud command-line tool, and
    with values already set for your current project. It can take a few seconds
    for the session to initialize.

1.  Enable the required Google Cloud services.

    ```bash
    gcloud services enable \
      artifactregistry.googleapis.com \
      cloudbuild.googleapis.com \
      cloudresourcemanager.googleapis.com \
      compute.googleapis.com \
      dataflow.googleapis.com \
      servicenetworking.googleapis.com \
      spanner.googleapis.com \
      storage.googleapis.com
    ```

This tutorial assumes that you already have:

*   Avro files uploaded to a Google Cloud Storage bucket that you want to insert
    to your database.

*   A
    [Cloud Spanner instance](https://cloud.google.com/spanner/docs/create-manage-instances),
    with a
    [database](https://cloud.google.com/spanner/docs/create-manage-databases#console)
    and [tables created](https://cloud.google.com/spanner/docs/named-schemas),
    where the Avro data will be inserted or updated.

Please set them up before proceeding ahead. Consider using the files under
`src/test/resources/AvroToSpannerScdPipelineITTest` if you do not have a
specific schema or Avro files with which to test this pipeline.

### Steps to build the template

This is a
[Dataflow Flex template](https://cloud.google.com/dataflow/docs/concepts/dataflow-templates#flex-templates),
which means that the pipeline code will be containerized and the container will
be used to launch the Dataflow pipeline.

1.  Access this project folder.

    ```bash
    git clone https://github.com/GoogleCloudPlatform/cloud-solutions.git
    cd cloud-solutions/projects/dataflow-gcs-avro-to-spanner/
    ```

1.  Configure the environment variables by editing the file
    `dataflow_template_variables.sh` using the text editor of your choice.

1.  Set the environment variables.

    ```bash
    source dataflow_template_variables.sh
    gcloud config set project ${PROJECT_ID}
    ```

1.  Create the Artifact Registry repository where the template image will be
    uploaded.

    ```bash
    gcloud artifacts repositories create $REPOSITORY_NAME \
      --repository-format=docker \
      --location=$REGION
    ```

1.  Build the Dataflow Flex template.

    ```bash
    gcloud builds submit \
      --substitutions=_DATAFLOW_TEMPLATE_GCS_PATH="${DATAFLOW_TEMPLATE_GCS_PATH}",_DATAFLOW_TEMPLATE_IMAGE="${DATAFLOW_TEMPLATE_IMAGE}" \
      .
    ```

### Steps to launch and run the template

Once the template is deployed, it can be launched from the Dataflow UI which
will allow you to see the configuration parameters and their descriptions.

Alternatively, the template can be run from the same Cloud Shell. The parameters
below will depend on your configuration and pipeline requirements.

1.  If you have not yet done it, configure the environment variables by editing
    the file `dataflow_template_variables.sh` using the text editor of your
    choice.

1.  Set the environment variables.

    ```bash
    source dataflow_template_variables.sh
    ```

1.  Launch the Dataflow Flex Template.

    ```bash
    gcloud dataflow flex-template run "${JOB_NAME}" \
      --project "${PROJECT_ID}" \
      --region "${REGION}" \
      --template-file-gcs-location "${DATAFLOW_TEMPLATE_GCS_PATH}" \
      --parameters "inputFilePattern=${INPUT_FILE_PATTERN}" \
      --parameters "spannerProjectId=${SPANNER_PROJECT_ID}" \
      --parameters "instanceId=${SPANNER_INSTANCE_ID}" \
      --parameters "databaseId=${SPANNER_DATABASE_ID}" \
      --parameters "spannerPriority=${SPANNER_PRIORITY}" \
      --parameters "spannerBatchSize=${SPANNER_BATCH_SIZE}" \
      --parameters "tableName=${SPANNER_TABLE_NAME}" \
      --parameters "scdType=${SCD_TYPE}" \
      --parameters "primaryKeyColumnNames=${SPANNER_PRIMARY_KEY_COLUMN_NAMES}" \
      --parameters "startDateColumnName=${SPANNER_START_DATE_COLUMN_NAME}" \
      --parameters "endDateColumnName=${SPANNER_END_DATE_COLUMN_NAME}" \
      --parameters "orderByColumnName=${SPANNER_ORDER_BY_COLUMN_NAME}" \
      --parameters "sortOrder=${SPANNER_SORT_ORDER}"
    ```

    Remove any optional pipeline parameters that you do not require. Check the
    `metadata.json` or `dataflow_template_variable.sh` for more details on these
    configuration variables.
