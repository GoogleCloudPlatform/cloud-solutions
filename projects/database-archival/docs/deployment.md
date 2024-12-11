# Deployment and Configuration of Database Archival and Pruning

## Deployment

These instructions and Terraform code are for a demo deployment to test the
Database Archival solution. For Production-ready deployment, check our
recommendations on the Productionization section.

### Costs

This demo uses billable components of Google Cloud, including the following:

*   [Composer](https://cloud.google.com/composer/pricing)
*   [Cloud Run Functions](https://cloud.google.com/run/pricing)
*   [Cloud Storage](https://cloud.google.com/storage/pricing)
*   [Cloud SQL for MySQL](https://cloud.google.com/sql/docs/mysql/pricing)

Consider cleaning up the resources when you no longer need them.

### Steps to Deploy the demo

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

1.  Set the active project to your desired project.

    ```bash
    gcloud config set project $PROJECT_ID
    ```

    Where `$PROJECT_ID` is the name of the project you just created.

1.  Set the Application Default Credentials.

    ```bash
    gcloud auth application-default login
    ```

1.  Update Organization Policy, these constraints must be allowed:

    *   compute.restrictVpcPeering - Allowed All
    *   compute.requireShieldedVm - Not enforced:

        ```bash
        gcloud resource-manager org-policies disable-enforce \
        constraints/compute.requireShieldedVm \
        --project=<PROJECT_ID>
        ```

    *   cloudbuild.disableCreateDefaultServiceAccount - Not enforced:

        ```bash
        gcloud resource-manager org-policies disable-enforce \
        constraints/cloudbuild.disableCreateDefaultServiceAccount \
        --project=<PROJECT_ID>
        ```

1.  Manually add roles/iam.serviceAccountTokenCreator to the user that runs
    this script.

1.  Enable cloudresourcemanager.googleapis.com manually:

    ```bash
    gcloud services enable cloudresourcemanager.googleapis.com
    ```

1.  Clone this repository.

    ```bash
    git clone https://github.com/GoogleCloudPlatform/cloud-solutions.git
    ```

1.  Go to the project Terraform folder for the Demo deployment.

    ```bash
    cd projects/database-archival/terraform/
    ```

1.  Run the Terraform script.

    ```bash
    terraform init
    terraform apply \
      -var "project_id=<project_id>" \
      -var "region=<region>" \
      -var "service_account_name=<service_account_name>" \
      -var "database_user_name=<sql_user_name>" \
      -var "database_user_password=<sql_user_password>"
    ```

    Where:

    *   `project_id` is the project where the resources will be created.
        Example: `my-database-archival-project`.
    *   `region` is the Cloud region where the resources will be created.
        Example: `asia-southeast1`.
    *   `service_account_name` is the name of the service account that will be
        used to run this database archival project. Example:
        `database-archival-service-account`.
    *   `database_user_name` is the name of the user which will be created as
        admin of the Cloud SQL instance.
    *   `database_user_password` is the password of the user which will be
        created as admin of the Cloud SQL instance.

1.  If needed, edit the configuration file that was created on the bucket
    called `<project-id>_database_archival_config`. See the
    [Configuration](#configuration) section below for more details.

1.  Once you are done with the demo, consider removing the resources.

    ```bash
    terraform destroy \
      -var "project_id=<project_id>" \
      -var "region=<region>" \
      -var "service_account_name=<service_account_name>" \
      -var "database_user_name=<sql_user_name>" \
      -var "database_user_password=<sql_user_password>"
    ```

    Use the same variables than on the previous step.

### Next steps after deployment

After running the Terraform, the following main components will be created:

1.  A Cloud SQL MySQL database with sample data.

1.  A BigQuery dataset, which contains a live copy of the Cloud SQL data.

1.  A Datastream job which continuously copies the Cloud SQL data to BigQuery.

1.  A Cloud Run Function, which can prune the required data from the Cloud SQL
    database.

1.  A Cloud Storage bucket to host the Composer Directed Acyclic Graph (DAGs),
    and the configuration file.

1.  A secret on Secret Manager to store the database password.

1.  A configuration file, stored on Google Cloud Storage, which configures two
    jobs (in the same Composer pipeline):

    1.  An archival and pruning job for the Cloud SQL Historical Data table
        called `Transaction`.

    1.  An archival-only job for the Cloud SQL Main Data table called `User`.

1.  A Composer instance, and its DAG (pipeline) using the above configuration.
    The Composer DAG is set to run manually only.

1.  Networking and IAM to allow all these components to interact with each
    other.

In order to run the Database Archival solution:

1.  Access your Cloud Console on the project where the solution was deployed.

1.  (Optional) Verify the data on Cloud SQL and BigQuery to see the data state
    before running the solution. You should see:

    1.  Two Cloud SQL tables called `Transaction` and `User`.

    1.  Two BigQuery tables called `db_archival_demo.Transaction` and
        `db_archival_demo.User` with the same data.

1.  Run Composer DAG manually:

    1.  Go to Composer UI.

    1.  Click the name of the Composer instance
        (e.g. `db-archival-composer-env`).

    1.  Click `DAGS`.

    1.  Click the name of the DAG (`database_archival_dag`).

    1.  Click `Trigger DAG`.

1.  The DAG will start running. Monitor the progress on the `Run History` until
    the newly created run has a green checkmark indicating its successful
    completion.

1.  After the DAG has completed its run, verify the data on Cloud SQL and
    BigQuery to see the data state after running the solution. You should see:

    1.  Two Cloud SQL tables:

        *   `User` table will contain the same amount of rows as it originally
            had, as it was set to archive only.

        *   `Transaction` table will contain a smaller amount of rows as the
            row whose `transaction_date` was older than 730 days were pruned.

    1.  Five BigQuery tables:

        *   `db_archival_demo.Transaction` and `db_archival_demo.User` will have
            the same data as in Cloud SQL with the changes described above.

        *   `db_archival_demo.User_snapshot` will contain a full copy of the
            data of the `User` table.

        *   `db_archival_demo.Transaction_snapshot` will contain the data from
            `Transaction` that was marked for deletion - this is, the data
            whose `transaction_date` was older than 730 days.

        *   `db_archival_demo.Transaction_snapshot_prune_progress` will contain
            the primary keys of the data that was deleted, plus metadata
            indicating the run, date and its confirmed pruned status.

If you want to to move the solution to work on your own data and on a schedule:

1.  Read how to [configure](#configuration) Database Archival own data,
    including how to run it on a schedule and other variables.

1.  Read how to [productionize](#productionization) the solution.

## Configuration

### Composer per-table workflow configuration

The configuration for the tables is created as a list of JSON objects and stored
in Google Cloud Storage. Each object contains the following elements:

#### For both Historical and Main Data

*   `database_table_name`: string, the name of the table that will be archived
    and, if required, pruned. Example: `flight`.

*   `bigquery_location`: string, the Google Cloud location where the BigQuery
    data is located and jobs will be created. Example: `us-central1`.

*   `bigquery_table_name`: string, the name of the table in BigQuery that is a
    copy of the `database_table_name` created by Datastream. Example:
    `project.dataset.flight`.

*   `bigquery_days_to_keep`: number, the number of days for which the newly
    copied data will be stored in BigQuery. The partitions get deleted after
    this amount of days. Example: `3650` days = ~10 years.

*   `database_prune_data`:  boolean, whether the data in the database needs to
    be pruned (deleted). Set to `true` if this is a Historical Data table which
    needs pruning, otherwise set to `false`.

#### For Historical Data only

*   `database_prune_batch_size`: number, the size of the batches for data
    pruning. When deleting data from the database, each transaction of the
    database will delete this amount of rows. Example: `1000`. Recommended to
    be kept between `100` and `10000` rows. This field is optional. Default:
    `1000` rows.

*   `table_primary_key_columns`: list of strings, the names of the columns of
    all the primary keys for this table. Must have at least one primary key, but
    can have as many as required by the schema. Example: `["flight_id"]`.

*   `table_date_column`: string, the name of the date column which determines
    when the data should be pruned. When the date in this column is older than
    `database_days_to_keep`, the data gets archived and pruned. Example:
    `flight_date`.

*   `table_date_column_data_type`: enum, as a string, the type of column that
    `table_date_column` is. Must be one of `DATE`, `DATETIME` or `TIMESTAMP`.

*   `database_days_to_keep`: number, the number of days for which the data
    should be stored in the database. Data older than this will be archived
    and pruned (deleted). Example: `365` for one year.

*   `database_type`: enum, as a string, the type of the database where this
    table is located. Must be one of the following: `MYSQL`, `POSTGRES`,
    `SQL_SERVER`, `ALLOY_DB` or `SPANNER`. See
    [Database Support](./index.md#database-support) for the list of supported
    databases.

*   `database_host`: string, the database host (or IP) where the database is
    located. Example: `10.8.0.32`. It can be an internal or external IP,
    provided that the right networking is configured. We recommend using
    internal IP where possible. If the database uses non-standard port numbers,
    the port must be added to the `database_host`. Example: `10.8.0.32:9432`.
    Only `database_host` or `database_instance_name` must be provided. When
    `database_host` is provided, the connection to the database is done via TCP.

*   `database_instance_name`: string, the database connection name, which
    represents the instance. Only `database_host` or `database_instance_name`
    must be provided. When `database_instance_name` is provided, the connection
    to the database is done via Python connector using the Private IP. If you
    must use the Public IP, use `database_host` instead.

    *   AlloyDB example:
        `projects/<project_id>/locations/<region_id>/clusters/<cluster_id>/instances/<instance_id>`.

    *   Cloud SQL example: `project:region:database-sample`.

*   `database_name`: string, the name of the database where the table is
    located. Example: `dataset`.

*   `database_username`: string, the name of the user to use to connect to the
    database. Example: `user`. The user must have permission to read and remove
    records on the given database and table.

*   `database_password`: string, the password for the user which will be used to
    connect to the database. Only `database_password` or
    `database_password_secret` must be provided. We recommend using
    `database_password_secret` instead.

*   `database_password_secret`: string, the full name of the secret stored in
    Secret Manager, which contains the password for the user which will be used
    to connect to the database. Example:
    `projects/project-id/secrets/secret-key-db-password/versions/1`.
    Only `database_password` or `database_password_secret` must be provided.

### Sample per-table workflow configuration

```json
[
  {
    "bigquery_location": "us-central1",
    "bigquery_table_name": "project.dataset.flight",
    "bigquery_days_to_keep": 3000,
    "database_table_name": "flight",
    "database_prune_data": true,
    "database_prune_batch_size": 1000,
    "table_primary_key_columns": ["flight_id"],
    "table_date_column": "departure",
    "table_date_column_data_type": "DATE",
    "database_days_to_keep": 365,
    "database_type": "MYSQL",
    "database_instance_name": "project:region:database-sample",
    "database_name": "dataset",
    "database_username": "user",
    "database_password_secret": "projects/project-id/secrets/secret-key-db-password/versions/1"
  },
  {
    "bigquery_location": "us-central1",
    "bigquery_table_name": "project.dataset.airline",
    "bigquery_days_to_keep": 3000,
    "database_table_name": "airline",
    "database_prune_data": false
  },
]
```

The first example (`flight`) represents a Historical Data table, which needs to
be archived and pruned. The data has been continuously replicated by Datastream
into `project.dataset.flight` which is a dataset located in `us-central1`. The
archived data and metadata will be kept for `3000` days. The data needs to be
pruned (`true`) and will be pruned in batches of size `1000`. The table has one
primary key (`flight_id`) and needs to be pruned in the basis of the column
`departure` which is a `DATE` column. Data older than `365` days will be
archived and deleted from the database. The database is a `MYSQL` database on
Cloud SQL (instance: `project:region:database-sample`). The tables are hosted
on the database `dataset` which can be accessed using user `user` whose password
is stored on Secret Manager under the secret
`projects/project-id/secrets/secret-key-db-password/versions/1`.

The second example (`airline`) represents a Main Data table, which needs to be
archived but does not need to be pruned. The data has been continuously
replicated by Datastream into `project.dataset.airline` which is a dataset
located in `us-central1`.

The tables in the configuration can belong to multiple databases, instances
and database types, hosted in Cloud SQL or self-hosted - provided that the
right permissions (IAM) and networking are configured to enable access from
Composer and the Cloud Run Function to the database.

### Validate the configuration

If the JSON configuration file is not succesfully parsed or contains wrong
values, the DAG will not be built and none of the tables will run. In order to
avoid any issues, validate your configuration file before uploading a new
version to Google Cloud Storage. There is a tool on this repository to achive
that. In order to validate your configuration:

1.  [Install Python >= 3.9](https://www.python.org/downloads/)

1.  Access this project repository.

    ```bash
    git clone https://github.com/GoogleCloudPlatform/cloud-solutions.git
    cd cloud-solutions/projects/database-archival
    ```

1.  Install the project and its required dependencies.

    ```bash
    python3 -m venv .venv
    . .venv/bin/activate
    python3 -m pip install --upgrade pip
    python3 -m pip install -r requirements.txt --require-hashes --no-deps
    python3 -m pip install -e . --no-deps
    ```

1.  Run the configuration tool.

    ```bash
    python3 tools/config_validator/config_validator.py \
      --filename <path_to_config_file_to_validate>.json
    ```

    Where:

    *   `<path_to_config_file_to_validate>.json` is the path to the JSON
        config file that you want to validate.

### Other variables and configuration

When deploying the Composer pipeline (also referred as Directed Acyclic Graph or
DAG), you must configure some variables. These can be configured as environment
or by editing `src/database_archival/dag/config.py` directly.

#### Required configuration variables

*   `DATA_ARCHIVAL_CONFIG_PATH`: string, the Google Cloud Storage URI of the
    JSON file which contains the per-table configuration. Example:
    `gs://bucket/file.json`.

*   `CLOUD_FUNCTION_URL_DATA_DELETION`: string, the URL to the Cloud Run
    Function deployed to prune the data. Example:
    `https://region-project.cloudfunctions.net/prune-data`.

#### Optional configuration variables

These are optional variables, you may configure them, but it is not required to
run the pipeline (DAG):

*   `DAG_NAME`: string, name of the DAG. This will be used in the Airflow and
    Composer UI. Default: `database_archival`.

*   `DAG_SCHEDULE_INTERVAL`: string, the schedule interval for the DAG. See
    [Scheduling & Triggers](https://airflow.apache.org/docs/apache-airflow/1.10.10/scheduler.html)
    for more details. Default: `None`, which means that the pipeline must be run
    manually.

*   `TIME_BETWEEN_DELETE_BATCHES_IN_SECONDS`: number, the time in seconds to
    wait in between the deletion of two batches for the same table. Default
    value: `120` seconds (2 minutes).

*   `DATABASE_TIMEOUT`: number, the timeout in seconds for the Cloud Run
    Function to to establish a database connection and perform data deletion.
    Default: `3000` seconds.

#### Common Troubleshooting Issues

1.  Error on `private_vpc_connection` Terraform resource step. Solution: run
    manually `gcloud` command to update VPC peerings after private-ip-alloc is created.
    Follow this
    [article](https://www.googlecloudcommunity.com/gc/Databases/Create-a-database-instance-by-adding-a-private-ip/m-p/552244)
    for the command to be used.

## Productionization

The following steps are recommended for productionizing deployment of the
Database Archival solution:

*   Begin by deploying the demo, moving towards a dev/test environment and
    progress your use of Database ARchival safely towards your Production
    environments.

    *   As you are testing the solution, run it first on test instances and
        databases.

    *   Ensure you have backups and point in time recovery of the data while you
        use Database Archival to minimize any accidental data loss.

*   Incorporate the relevant portions of the supplied Terraform demo
    configuration into your own Terraform codebase. You may choose to use part
    of the supplied modules with the relevant changes, or select portions of the
    modules to use in your own projects. For more details, check the Terraform
    code and/or read the [Architecture section](architecture.md). For a full
    deployment, you will require to:

    *   Have an existing Cloud SQL or AlloyDB database.

    *   Have or deploy a live copy of the data, with continuous Change Data
        Capture (CDC), to BigQuery. You may choose to use Datastream or an
        alternative solution for this.

    *   Deploy the Database Archival Cloud Run Function which deletes/prunes
        data from the Database.

    *   Deploy the Composer pipeline which coordinates the pipeline, including
        the Google Cloud Storage bucket where the code lives.

    *   [Configure](#configuration) the Composer pipeline to act on your desired
        instances, databases and tables. Host the file on Google Cloud Storage
        (GCS), and create a new GCS bucket if necessary.

    *   Configure networking and IAM so that:

        *   Cloud Run Function can connect to the database to read and remove
            rows.

        *   Cloud Run Function can connect to the BigQuery dataset to read and
            update rows.

        *   Composer can connect to the BigQuery dataset to read and update
            rows, and create new tables.

        *   Composer can connect to the Cloud Run Function.

*   Decouple the lifecycle of the Database Archival components from the
    lifecycles of the Memorystore instances being scaled. In particular, it
    should be possible to completely tear down and redeploy all components of
    the Database Archival solution without affecting your database instances.

*   Pay particular attention to the management and permissions of the service
    accounts you configure the Database to use. We recommend assigning
    [minimally permissioned service accounts](https://cloud.google.com/iam/docs/service-account-overview#service-account-permissions).

*   Store your Database Archival configuration files in your source control
    system, along with the Terraform and application codebase.

*   Automate updating the Database Archival configuration using a deployment
    pipeline separate from deploying the solution itself. This will allow you to
    incorporate policy and other checks according to your organizational
    requirements (e.g. change freeze periods), as well as decoupling updates to
    the configuration from updates to the code solution itself.

*   Define [alerts](https://cloud.google.com/monitoring/alerts) to be notified
    of archival and pruning events that may affect your platform or your
    application. You can use
    [log-based-alerts](https://cloud.google.com/logging/docs/alerting/log-based-alerts)
    to configure alerts that will notify you whenever a specific message appears
    in the logs.
