# Skill: Serverless Spark & Lightning Engine Optimization

<!--
  Disabling markdownlint MD029 to provide explicit ordering to avoid
  confusing the LLM.
-->
<!-- markdownlint-disable MD029 -->

## 1. Description & Rationale

This skill establishes the configuration practices for executing PySpark
workloads on Managed Service for Apache Spark Serverless. To achieve optimal
performance, workloads should leverage the **Spark Lightning Engine**
(vectorized execution) and **Spark Connect** for decoupled session management.

## 2. Environment Prerequisites

- **Execution Engine**: Managed Service for Apache Spark Serverless.
- **Tier**: Premium (required for Lightning Engine).
- **SDK**: `google-cloud-dataproc` (specifically for Spark Connect).

## 3. Agent Execution Guidelines (System Prompts)

When configuring Spark sessions:

1.  **Enforce Lightning Engine**: Always configure the session to use
    `lightningEngine`.
2.  **Enforce Premium Tier**: Set the runtime to `premium`.
3.  **Use Spark Connect**: Prefer `DataprocSparkSession` over standard
    `SparkSession` when working with Serverless Spark to support modern
    decoupled execution.

## 4. Opinionated Code Patterns

### A. Creating the Optimized Spark Session

The agent must use the following pattern to initialize the Spark session:

```python
from google.cloud.dataproc_spark_connect import DataprocSparkSession
from google.cloud.dataproc_v1 import Session

def create_spark_session():
    """Creates a SparkSession with BigQuery and GCS support using Lightning Engine."""
    session = Session()
    session.runtime_config.version = "3.0" # Adjust version if needed

    # Enable premium tier and lightning engine
    session.runtime_config.properties = {
        "dataproc.runtime": "premium",
        "spark.dataproc.engine": "lightningEngine",
        "spark.dynamicAllocation.maxExecutors": "8",
    }

    spark = (
        DataprocSparkSession.builder.appName("Detox-Spark-Demo")
        .dataprocSessionConfig(session)
        .getOrCreate()
    )
    return spark

spark = create_spark_session()
print("AI-Native Spark Session Created with Lightning Engine")
```

## 5. Verification Checklist

- [ ] **Premium Tier**: Verify `"dataproc.runtime": "premium"` is in the
      properties.
- [ ] **Lightning Engine**: Verify `"spark.dataproc.engine": "lightningEngine"`
      is set.
- [ ] **Spark Connect**: Ensure `DataprocSparkSession` is used instead of
      `pyspark.sql.SparkSession`.
