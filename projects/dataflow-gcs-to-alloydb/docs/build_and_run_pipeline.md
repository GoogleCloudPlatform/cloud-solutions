# Build and Run Dataflow Template

## Costs

This tutorial uses billable components of Google Cloud, including the following:

*   [Cloud Storage](https://cloud.google.com/storage/pricing)
*   [Dataflow](https://cloud.google.com/dataflow/pricing)
*   [AlloyDB](https://cloud.google.com/alloydb/pricing)
*   [Artifact Registry](https://cloud.google.com/artifact-registry/pricing)

When you finish the tasks that are described in this document, you can avoid
continued billing by deleting the resources that you created.

## Build and Run the Dataflow Flex Template

### Prepare your project

1.  Create a
    [Google Cloud project](https://console.cloud.google.com/projectselector2/home/dashboard)
    with
    [billing enabled](https://support.google.com/cloud/answer/6293499#enable-billing).

1.  Open the [Cloud Console](https://console.cloud.google.com/).

1.  Activate [Cloud Shell](https://console.cloud.google.com/?cloudshell=true).
    At the bottom of the Cloud Console, a Cloud Shell session starts and
    displays a command-line prompt. Cloud Shell is a shell environment with the
    Cloud SDK already installed, including the gcloud command-line tool, and
    with values already set for your current project. It can take a few seconds
    for the session to initialize.

### Prepare your environment

1.  Clone this repository:

    ```bash
    git clone https://github.com/GoogleCloudPlatform/cloud-solutions.git
    ```

1.  Access this project folder:

    ```bash
    cd cloud-solutions/projects/dataflow-gcs-to-alloydb/
    ```

1.  Set up the project variables.

    ```bash
    PROJECT_ID=""
    REGION=""
    REPOSITORY_NAME=""
    BUCKET_NAME=""
    DATAFLOW_JOB_NAME=""

    ALLOYDB_CLUSTER_NAME=""
    ALLOYDB_INSTANCE_NAME="${ALLOYDB_CLUSTER_NAME}-instance"
    ALLOYDB_PASSWORD=""
    ```

    The variables mean the following:

    *   `PROJECT_ID` is the project id where the Artifact Registry repository
        was created and where the Dataflow job will run.

    *   `REGION` is the region where the resources will run.

    *   `REPOSITORY_NAME` is in the Artifact Repository repository name where
        the image will be created.

    *   `BUCKET_NAME` is the name of the Google Cloud Storage bucket that will
        be used to store the data files and temporary Dataflow data.

    *   `DATAFLOW_JOB_NAME` is a custom job name to identify the template run.

    *   `ALLOYDB_CLUSTER_NAME` is the name of the AlloyDB cluster that will be
        created and to which data will be uploaded.

    *   `ALLOYDB_INSTANCE_NAME` is the name of the (primary) instance within the
        AlloyDB cluster. Leave the variable as is to name it the same as the
        cluster name with `-instance` added after it.

    *   `ALLOYDB_PASSWORD` is password for the AlloyDB instance.

1.  Set the project id.

    ```bash
    gcloud config set project $PROJECT_ID
    ```

1.  Enable the required Google Cloud services.

    ```bash
    gcloud services enable \
      alloydb.googleapis.com \
      artifactregistry.googleapis.com \
      cloudbuild.googleapis.com \
      cloudresourcemanager.googleapis.com \
      compute.googleapis.com \
      dataflow.googleapis.com \
      servicenetworking.googleapis.com \
      storage.googleapis.com
    ```

### Create an AlloyDB cluster, instance, database and table

1.  Create an AlloyDB cluster.

    ```bash
    gcloud alloydb clusters create $ALLOYDB_CLUSTER_NAME \
      --region=$REGION \
      --password=$ALLOYDB_PASSWORD
    ```

1.  Create an AlloyDB instance.

    ```bash
    gcloud alloydb instances create $ALLOYDB_INSTANCE_NAME \
      --cluster=$ALLOYDB_CLUSTER_NAME \
      --region=$REGION \
      --instance-type=PRIMARY \
      --cpu-count=2 \
      --availability-type=ZONAL \
      --ssl-mode=ALLOW_UNENCRYPTED_AND_ENCRYPTED
    ```

    Note: By default, AlloyDB creates a default user and database named
    "postgres". For the purpose of this guide, this default database and user
    will be used.

    Note: For the purpose of this guide, we are allowing unencrypted connections
    to the database to ease the process of connecting and configure it the
    database via command line. For production environments, this might not be
    the recommended set up.

1.  Get the internal AlloyDB instance IP.

    ```bash
    gcloud alloydb instances describe $ALLOYDB_INSTANCE_NAME \
      --cluster=$ALLOYDB_CLUSTER_NAME \
      --region=$REGION \
      --view=BASIC \
    | grep "ipAddress"
    ```

1.  Store the internal IP into a variable.

    ```bash
    ALLOYDB_IP=$(\
      gcloud alloydb instances describe $ALLOYDB_INSTANCE_NAME \
        --cluster=$ALLOYDB_CLUSTER_NAME \
        --region=$REGION \
        --view=BASIC \
      | grep "ipAddress" \
      | sed "s/ipAddress: //"
    )
    ```

1.  Connect to the database.

    ```bash
    psql -h $ALLOYDB_IP -d postgres -U postgres
    ```

1.  Write the AlloyDB password when prompted.

1.  Create a new table by pasting the contents of the
    `src/testdata/test1/schema.sql` file.

1.  Confirm the table was created.

    ```sql
    \dt public.*
    ```

    You should see the following:

    ```text
              List of relations
    Schema |   Name    | Type  |  Owner
    --------+-----------+-------+----------
    public | employees | table | postgres
    (1 row)
    ```

1.  Exit `psql` by typing `exit`.

### Create a GCS bucket and upload data files

1.  Create a Google Cloud Storage bucket.

    ```bash
    gcloud storage buckets create gs://$BUCKET_NAME --location=$REGION
    ```

1.  Upload a data file to the bucket. In this case, a CSV file will be used.

    ```bash
    gsutil cp src/testdata/test1/data.csv gs://$BUCKET_NAME/dataflow-template/data.csv
    ```

### Create an Artifact Registry repository

1.  Create a new Artifact Registry repository.

    ```bash
    gcloud artifacts repositories create $REPOSITORY_NAME \
      --repository-format=docker \
      --location=$REGION
    ```

## Build the Flex Template

1.  Name your container and store it into a variable.

    ```bash
    TEMPLATE_IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY_NAME/dataflow-template-gcs-to-alloydb-$(date +%s):latest"
    ```

1.  Build the Dataflow Flex template using the custom image.

    ```bash
    gcloud builds submit \
      --substitutions=_IMAGE_NAME="$TEMPLATE_IMAGE",_BUCKET_NAME="$BUCKET_NAME" \
      .
    ```

    Before deploying the Dataflow Flex template, tests are run to ensure the
    pipeline code is working as intended.

At this point the custom image for the Dataflow Flex template has been created
in the Artifact Repository. The template metadata has been written to the bucket
as a JSON file (`dataflow_gcs_to_alloydb_template.json`).

Once the template is built, it can be run as many times as desired, and
configured by changing the parameters.

## Run the Flex Template

1.  Run a Dataflow job that uses the Flex Template created in the previous
    steps.

    ```bash
    gcloud dataflow flex-template run dataflow-template-run-test-gcs-alloydb \
      --template-file-gcs-location gs://$BUCKET_NAME/dataflow-template/dataflow_gcs_to_alloydb_template.json \
      --region $REGION \
      --parameters "input_file_format=csv" \
      --parameters "input_file_pattern=gs://$BUCKET_NAME/dataflow-template/data.csv" \
      --parameters 'input_schema=id:int64;first_name:string;last_name:string;deparment:string;salary:float;hire_date:string' \
      --parameters "alloydb_ip=$ALLOYDB_IP" \
      --parameters "alloydb_password=$ALLOYDB_PASSWORD" \
      --parameters "alloydb_table=employees" \
      --parameters "region=$REGION" \
      --parameters "project=$PROJECT_ID" \
      --parameters "job_name=$DATAFLOW_JOB_NAME" \
      --parameters "temp_location=gs://$BUCKET_NAME/dataflow-template/temp" \
      --parameters "staging_location=gs://$BUCKET_NAME/dataflow-template/staging"
    ```

    To learn how to customize these flags, read the
    [Configuration](./configuration.md) section.
