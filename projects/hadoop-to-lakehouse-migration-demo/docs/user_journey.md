# User Journey: Hadoop to Google Cloud Data Lakehouse Migration

Welcome to the Hadoop to Google Cloud Data Lakehouse Migration demo. This guide
walks you through the end-to-end process of migrating data from a legacy Hadoop
environment to a modern Data Lakehouse on Google Cloud.

## Overview

The demo simulates a migration of MTA subway hourly ridership data from a legacy
Hadoop cluster (using HDFS and Hive) to a Google Cloud Data Lakehouse leveraging
Google Cloud Storage, Managed Service for Apache Spark (formerly Dataproc)
Metastore, and BigQuery.

## Prerequisites

Before you begin, ensure you have:

- **Two** Google Cloud projects with billing enabled:
    - One for the **Source** environment (simulating legacy Hadoop, e.g.
      `project-source`).
    - One for the **Target** environment (modern Data Lakehouse, e.g.
      `project-target`).
- Google Cloud SDK installed and authenticated.
- Terraform installed.
- Set the following shell variables to simplify the process:

    ```bash
    export SOURCE_PROJECT_ID="<YOUR_SOURCE_PROJECT>"
    export TARGET_PROJECT_ID="<YOUR_TARGET_PROJECT>"
    export SOURCE_CLUSTER_NAME="legacy-hadoop"
    export REGION="us-central1"
    export ZONE="us-central1-a"
    ```

> [!NOTE]
> You may need to make the scripts
> executable before running them. You can do this for all scripts in the `scripts`
> directory with:
>
> ```bash
> chmod +x scripts/*.sh
> ```

## Steps

### 1. Enable APIs

Enable the required Google Cloud APIs for both the source and target projects.

```bash
scripts/01.01-enable-source-apis.sh "${SOURCE_PROJECT_ID}"
scripts/01.02-enable-target-apis.sh "${TARGET_PROJECT_ID}"
```

### 2. Provision Infrastructure

The infrastructure is divided into two parts: the source (simulated legacy
Hadoop) and the target (modern Data Lakehouse).

#### Step 2.1: Provision Source Infrastructure

Navigate to the source terraform directory and apply the configuration, passing
your source project ID. This step will take approximately 5 minutes.

```bash
cd terraform/source-environment
terraform init

export TF_VAR_source_project_id="${SOURCE_PROJECT_ID}"
export TF_VAR_cluster_name="${SOURCE_CLUSTER_NAME}"
export TF_VAR_region="${REGION}"
export TF_VAR_zone="${ZONE}"

terraform apply
```

### 3. Load Sample Data (Source)

Populate the source Hadoop environment with sample MTA rider data. This script
copies datasets to HDFS and creates Hive tables for each.

```bash
cd ../.. # or make sure you are on the project root
scripts/03-load_data.sh
```

> [!NOTE]
> This script will automatically read values from your
> `terraform/source-environment` state if run after step 2.1. If you need to
> override, use flags like `--project-id`.

### Checking Work: Viewing Data in the Source System

After loading the data, you can verify it is correctly populated in the source
Hadoop environment.

Submit a Hive job from your terminal using the `gcloud` CLI.

```bash
gcloud dataproc jobs submit hive \
  --cluster=$SOURCE_CLUSTER_NAME \
  --region=$REGION \
  --project=$SOURCE_PROJECT_ID \
  --execute="SELECT * FROM mta_ridership LIMIT 10;"
```

To verify that the files are in HDFS, you can SSH into the master node and use
Hadoop commands.

```bash
gcloud compute ssh ${SOURCE_CLUSTER_NAME}-m \
--project=$SOURCE_PROJECT_ID \
--zone=$ZONE \
--tunnel-through-iap \
--command="hadoop fs -ls -R /data/"
```

_You should see several datasets organized under `/data/mta` and
`/data/staged/`._

### 4. Provision Target Infrastructure

Now that the source system is populated and verified, provision the target Data
Lakehouse infrastructure.

#### Step 4.1: Configure Variables

The target environment needs to know about the source environment to set up
cross-project permissions (e.g., for data transfer).

1.  Navigate to the target terraform directory:

    ```bash
    cd terraform/target-environment
    ```

1.  Run the following commands to set up the terraform variables:

    ```sh
    export TF_VAR_target_project_id="$TARGET_PROJECT_ID"
    export TF_VAR_region="$REGION"
    export TF_VAR_zone="$ZONE"
    export TF_VAR_source_project_id="$SOURCE_PROJECT_ID"
    export TF_VAR_source_cluster_name="$SOURCE_CLUSTER_NAME"
    export TF_VAR_source_service_account="dataproc-source-sa@${SOURCE_PROJECT_ID}.iam.gserviceaccount.com"
    ```

#### Step 4.2: Apply Configuration

Initialize and apply the configuration. This may take 30 minutes to complete.

```bash
terraform init
terraform apply
```

> [!NOTE]
> This provisions Cloud Storage buckets, Dataproc Metastore, BigQuery
> datasets, and Dataplex resources.

### 5. Execute Migration

The migration process involves assessment, transfer, and transformation.

#### Step 5.1: Assessment

The assessment step uses Google Cloud's
[`dwh-migration-dumper` tool](https://docs.cloud.google.com/bigquery/docs/generate-metadata)
to extract comprehensive metadata, including table schemas, statistics, and
configuration, from the source Hive system. This tool is part of the official
Google Cloud BigQuery migration assessment suite.

This demo will run an assessment script that will download the tool, and execute
it on the Hadoop master node, capturing the results in the `assessment_output/`
directory. The script will also upload the results to the source staging bucket
for further processing.

The [tools repo](https://github.com/google/dwh-migration-tools) has more tools
to offer, like batch translation tool, and more information about other
connectors you can use, depending on your use-case. Please refer to the repo and
the
[documentation](https://docs.cloud.google.com/bigquery/docs/generate-metadata)
for more details.

Run the assessment script, from the project root:

```bash
cd ../.. # or navigate to the project root
scripts/05.01-assess_source.sh
```

The script will:

1.  Download the `dwh-migration-tools` if not already present in the `tmp/`
    directory.
1.  Upload and execute the `dwh-migration-dumper` on the Managed Service for
    Apache Spark (formerly Dataproc) master node.
1.  Upload the results to the source staging bucket for use in the BigQuery
    migration assessment.

#### Step 5.1.1: Review and Run BigQuery Migration Assessment

After the assessment script completes, you will have a set of metadata files in
the `assessment_output/` directory. These files are designed to be uploaded to
the **BigQuery Migration Assessment** service in the Google Cloud Console.

**Process Outline:**

1.  **Upload to BigQuery**:
    - In the Google Cloud Console, verify your target project is active.
    - Go to the **BigQuery Studio**.
    - In the left navigation menu, under the **Migration** section, click
      **Services**.
    - In the **Assess** box, click **Start Assessment**.
    - Enter any desired **Display name**.
    - For **Data source**, select **Hive**.
    - For **Input metadata**, provide the path to the directory containing the
      results on your Cloud Storage bucket (e.g.,
      `staging-SOURCE_PROJECT_ID/assessment_tool_output/`).
1.  **Wait for Assessment to complete**: you can click the Refresh button in the
    Migration Assessment page to refresh the assessment status. This can take
    several minutes.
1.  **Analyze Results**: BigQuery provides a detailed report of your source
    data, including:
    - **Query Translation**: Identification of potential issues when moving from
      HiveQL to GoogleSQL.
    - **Schema Optimization**: Recommendations for partitioning and clustering
      in BigQuery.
    - **Cost Estimation**: Preliminary estimates for storage and query costs.

For detailed instructions and advanced configuration, refer to the official
documentation:
[Run the BigQuery migration assessment](https://docs.cloud.google.com/bigquery/docs/migration-assessment#run_the_migration_assessment)

#### Step 5.2: Data Transfer

Transfer data from the source HDFS to the target Cloud Storage Bronze layer. For
a large-scale production migration, you have two main options:

- **Hadoop DistCp**: The traditional distributed copy tool using MapReduce.
- **Google Cloud Storage Transfer Service (STS)**: The cloud-native, fully
  managed service recommended for scale.

For this demo, we use **Storage Transfer Service** to demonstrate cloud-native
tooling.

##### Setup and Installation

**Enable APIs and Create Pool**: We have scripted the setup of the agent pool.
Run:

```bash
scripts/05.02-setup_transfer_service.sh \
  --source-project "${SOURCE_PROJECT_ID}" \
  --target-project "${TARGET_PROJECT_ID}"
```

**Install Agents on Cluster**: This step **MUST** be run on the cluster master
node (the namenode) so that the agents have direct access to HDFS. The script
`scripts/05.02-install_transfer_agents.sh` will copy a different script
(`scripts/05.02.01-namenode_install_transfer_agent_script.sh`) that then will be
run on the namenode to install the transfer agents.

> [!NOTE]
> **Authentication**
>
> By default, the `gcloud` command on the cluster, that will be used in this
> script, uses the VM's service account.
>
> To ensure you have the necessary permissions to register agents in the
> target project, you should give the Managed Service for Apache Spark
> (formerly Dataproc) service account on the source cluster, the
> `roles/storagetransfer.admin` role.
>
> This is already done for you with in
> `scripts/05.02-setup_transfer_service.sh`. Another option is to run
> `gcloud auth login` on the name node, and authenticate with your
> credentials.

<!-- Comment to separate 2 blockquotes for MD028 -->

> [!NOTE]
> **Understanding the IAM Requirements**
>
> In a cross-project migration, the data transfer agents require specific
> permissions across both environments:
>
> - **Target Project (STS Admin & Object Admin)**:
>
>     The agents must be registered in the **Target Project's** agent pool and
>     need write access to the Cloud Storage bucket in that same project. Even
>     though the agents run in the source environment, they act as "producers"
>     for the target data lake.
>
> - **Source Project (STS Admin)**:
>
>     The agents need to interact with the Storage Transfer API in the source
>     project to coordinate the data extraction from HDFS.
>
> - **Hadoop GCS Connector**:
>
>     For certain cluster-native operations (like `hadoop fs -cp` using the
>     GCS connector), the source service account may require
>     `roles/storage.admin` in the target project to avoid _403 Forbidden
>     errors_, as `roles/storage.objectAdmin` might not provide
>     sufficient bucket-level metadata permissions for the Hadoop
>     filesystem client.
>
> These cross-project permissions are
> automatically granted to the source Dataproc service account by
> the `05.02-setup_transfer_service.sh` script to simplify the demo
> setup.

**Run the script for installing transfer agents**:

```bash
scripts/05.02-install_transfer_agents.sh
```

_(If you are not using `gcloud auth login`, the command will use the VM's
service account, which must have the required permissions as mentioned above.)_

  <!-- markdownlint-enable MD007 -->

- **Create Transfer Job**: Once agents are running, you can create the transfer
  job using our script:

    ```bash
    scripts/05.02-create_transfer_job.sh
    ```

    This script will read project IDs and bucket names from Terraform state and
    create the job which will run in the background.

    You can check the status in the Target Project's Cloud Console, in the
    [Storage Transfer > Transfer Jobs page](https://console.cloud.google.com/transfer/jobs)

- **Validate Transfer**: After the job completes, verify that the data has
  arrived in the Bronze Cloud Storage bucket:

    ```bash
    gcloud storage ls -R gs://bronze-$TARGET_PROJECT_ID/
    ```

    _You should see all dataset directories (mta/ and staged/) transferred from
    HDFS._

#### Step 5.3: Medallion Lakehouse Conversion

Convert the transferred data to Iceberg format and move it through the Medallion
layers (Silver/Gold) using **Managed Service for Apache Spark Batches (formerly
Dataproc Serverless)**.

We have created a script to submit the job:

```bash
scripts/05.03-run_iceberg_conversion.sh
```

_This script will read project IDs and bucket names from Terraform state and
submit the job to Serverless Batch Jobs. The job converts all migrated datasets
into schema-enforced Iceberg tables in the Silver layer._

#### Step 5.3.1: Verification and BigQuery Integration

You can monitor the status of the Serverless Batch job using the Target
Project's Cloud Console in the
[**Managed Service for Apache Spark -> Serverless Batches** page](https://console.cloud.google.com/dataproc/batches)

After the batch job completes, you can verify the results and query the data in
BigQuery.

1.  **Verify Iceberg Table creation**: The conversion script should have created
    Iceberg tables in the Silver bucket. You can verify this by listing the
    contents of the bucket:

    ```bash
    gcloud storage ls gs://silver-$TARGET_PROJECT_ID/default/**
    ```

1.  **Verify Tables in BigQuery**: With the new
    [Google Cloud Lakehouse Runtime Catalog](https://docs.cloud.google.com/lakehouse/docs/about-lakehouse-catalogs),
    you can get complete interoperability between different processing engine,
    including Apache Spark, Apache Flink, Apache Hive, and BigQuery—share tables
    and metadata without copying files. You can verify that the tables are
    already available in BigQuery, with the tables in BigQuery appearing in the
    format: `PROJECT_ID.DATASET.NAMESPACE.TABLE`; for example:

    ```bash
    bq query --use_legacy_sql=false \
      "SELECT *
      FROM
        \`${TARGET_PROJECT_ID}.silver-${TARGET_PROJECT_ID}.default.mta_ridership\`
      LIMIT 10;"
    ```

#### Step 5.4: Spark Job Migration

In addition to migrating data, you also need to migrate your processing code.
Here we compare the legacy Spark job running on the source cluster with the
migrated version for the target environment, including a complex join across
multiple Iceberg tables.

**Legacy Spark Job (`scripts/pyspark/05.04-legacy_spark_job.py`)** Reads from
Hive:

```python
spark = (
    SparkSession.builder.appName("LegacySparkJob")
    .enableHiveSupport()
    .getOrCreate()
)
mta_df = spark.table("default.mta_ridership")
bus_stations_df = spark.table("default.bus_stations")

joined_df = (
    mta_df.join(bus_stations_df, "borough", "inner")
    .groupBy("borough", "station_complex")
    .agg({"ridership": "sum", "bus_stop_id": "count"})
    .withColumnRenamed("sum(ridership)", "total_ridership")
    .withColumnRenamed("count(bus_stop_id)", "nearby_bus_stops")
    .orderBy("total_ridership", ascending=False)
)
```

**Migrated Spark Job (`scripts/pyspark/05.04-migrated_spark_job.py`)** Reads
from multiple Iceberg tables:

```python
spark = SparkSession.builder.appName("MigratedSparkJob").getOrCreate()
mta_df = spark.table("lakehouse.default.mta_ridership")
bus_stations_df = spark.table("lakehouse.default.bus_stations")

joined_df = (
    mta_df.join(bus_stations_df, "borough", "inner")
    .groupBy("borough", "station_complex")
    .agg({"ridership": "sum", "bus_stop_id": "count"})
    .withColumnRenamed("sum(ridership)", "total_ridership")
    .withColumnRenamed("count(bus_stop_id)", "nearby_bus_stops")
    .orderBy("total_ridership", ascending=False)
)
```

As you can see, the migrated job can now perform cross-table analysis easily
using the Iceberg catalog. Core processing logic remains consistent, but data
access is modernized.

To run the legacy Spark job on the source cluster:

```bash
scripts/05.04-run_spark_job.sh
```

To run the migrated Spark job on Managed Service for Apache Spark (formerly
Dataproc) Serverless:

```bash
scripts/05.04-run_migrated_spark_job.sh
```

#### Step 5.5: SQL Translation

To modernize your analytics, you can use the BigQuery Translation Service to
convert legacy Hive queries to BigQuery SQL. This process highlights idiomatic
differences between HiveQL and GoogleSQL.

**Sample Hive Query (`scripts/05.05-sample_hive_query.sql`)**

This query joins the `mta_ridership` and `bus_stations` tables to calculate the
total number of lines that pass through each bus station.

```sql
WITH exploded_lines AS (
    SELECT
        bus_line_id,
        stop_id
    FROM bus_lines
    LATERAL VIEW explode(stops) exploded_table AS stop_id
)
SELECT
    s.bus_stop_id,
    s.address,
    COUNT(DISTINCT l.bus_line_id) AS total_lines
FROM exploded_lines l
JOIN bus_stations s
    ON l.stop_id = s.bus_stop_id
GROUP BY
    s.bus_stop_id,
    s.address
ORDER BY
    total_lines DESC;
    --hadoop-mod-target-1001.silver-hadoop-mod-target-1001.default
```

To run the hive query on the source cluster, run the following:

```bash
scripts/05.05-run_hive_query.sh
```

##### Translation Process

Translating queries to GoogleSQL can be done either interactively using the
BigQuery Translation Service or programmatically using the BigQuery Translation
API, one at a time, or in batches.

##### Interactive Translation

1.  In the Google Cloud Console, go to **BigQuery** > **Migration services**.
1.  In **Translate SQL** click **Translate** > **Interactive Translation**
1.  Set **Translating From** to **HiveQL**.
1.  Paste a Hive query above into the **Translating from** pane.
1.  Click **Translate**
1.  Review the generated translation.

Make a note to the option of adding a configuration file, under **More** -->
**Translation Settings**. This allows for advanced configuration of the
translation service, and is quite useful to make interactive test runs before
translating in batches.

For more information, have a look at the following links:

- [Interactive SQL translator](https://docs.cloud.google.com/bigquery/docs/interactive-sql-translator)
- [API SQL translator](https://docs.cloud.google.com/bigquery/docs/api-sql-translator)
- [Batch SQL translator](https://docs.cloud.google.com/bigquery/docs/batch-sql-translator)
- [YAML configuration reference](https://docs.cloud.google.com/bigquery/docs/config-yaml-translation)

**Translated BigQuery Query (`scripts/05.05-translated_bigquery_query.sql`)**

```sql
WITH exploded_lines AS (
  SELECT
      bus_lines.bus_line_id,
      stop_id
    FROM
      `__PROJECT_ID__.silver-__PROJECT_ID__.default.bus_lines` AS `bus_lines`,
      UNNEST(stops) stop_id
)
SELECT
    s.bus_stop_id,
    s.address,
    count(DISTINCT l.bus_line_id) AS total_lines
  FROM
    exploded_lines AS l
    INNER JOIN `__PROJECT_ID__.silver-__PROJECT_ID__.default.bus_stations` AS s ON l.stop_id = s.bus_stop_id
  GROUP BY 1, 2
ORDER BY
  total_lines DESC;

```

Note that we are using the `UNNEST` function to explode the `stops` array into
individual rows, which allows us to join it with the `bus_stations` table,
instead of the `explode` function in the equivalent Hive query.

Also note that the `__PROJECT_ID__` placeholders needs to be replaced with your
target project id. To run the query from the command line, you can run the
following:

```bash
sed -e s/__PROJECT_ID__/$TARGET_PROJECT_ID/g scripts/05.05-translated_bigquery_query.sql | \
    bq query --use_legacy_sql=false --project_id=$TARGET_PROJECT_ID
```
