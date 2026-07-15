# Skill: Zero-Copy Data Exploration & Ingestion

<!--
  Disabling markdownlint MD029 to provide explicit ordering to avoid
  confusing the LLM.
-->
<!-- markdownlint-disable MD029 -->

## 1. Description & Rationale

This skill enforces the **Zero-Copy Architecture** of the modern Google Cloud
Lakehouse. It eliminates the overhead of copying data to external compute
engines or creating intermediate files (CSVs/JSONs) on GCS.

It standardizes:

1.  Reading from BigQuery directly into Spark DataFrames using the
    Spark-BigQuery connector.
2.  Reading from BigQuery using BigQuery DataFrames (`bigframes.pandas`) for
    in-warehouse processing.

## 2. Environment Prerequisites

- **Spark**: Managed Service for Apache Spark Serverless (Runtime 3.0+
  recommended) with the Spark BigQuery Connector pre-bundled.
- **BigQuery**: `bigframes` Python package installed.

## 3. Agent Execution Guidelines (System Prompts)

When generating data loading or exploration code:

1.  **Never export to GCS first**: Do not write code that exports BigQuery
    tables to GCS as CSV/Avro/Parquet before loading them into Spark or Pandas.
2.  **Use BigQuery Storage API**: Ensure Spark reads use the `"bigquery"`
    format, which utilizes the high-speed BigQuery Storage Read API.
3.  **Use BigFrames for BQ**: Ensure BigQuery-centric pipelines use
    `bigframes.pandas.read_gbq` to create references to the tables.

## 4. Opinionated Code Patterns

### A. Spark-Centric Zero-Copy Load

Use the Spark-BigQuery connector to load tables directly.

```python
# Load BigQuery table directly into Spark DataFrame
users_df = (
    spark.read.format("bigquery")
    .option("table", "bigquery-public-data.thelook_ecommerce.users")
    .load()
)

# Create temporary view for Spark SQL queries
users_df.createOrReplaceTempView("users")
```

### B. BigQuery-Centric Zero-Copy Load

Use BigQuery DataFrames to create a virtual DataFrame.

```python
import bigframes.pandas as bpd

# Configure BigQuery DataFrames global options
bpd.options.bigquery.project = PROJECT_ID
bpd.options.bigquery.location = "US"  # Or your dataset location

# Load table reference (zero data movement)
users_df = bpd.read_gbq("bigquery-public-data.thelook_ecommerce.users")
```

## 5. Verification Checklist

- [ ] **No GCS Export**: Verify the code does not contain `bq extract` or GCS
      export steps before loading.
- [ ] **Spark Format**: Ensure the Spark read format is explicitly `"bigquery"`.
- [ ] **BigFrames Config**: Ensure `bpd.options.bigquery.project` is set before
      calling `read_gbq`.
