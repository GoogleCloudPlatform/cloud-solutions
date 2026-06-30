# Skill: Zero-Copy Pipeline Generator (Coordinator)

<!--
  Disabling markdownlint MD029 to provide explicit ordering to avoid
  confusing the LLM.
-->
<!-- markdownlint-disable MD029 -->

This is the coordinator skill that orchestrates the end-to-end creation of
Spark-centric and BigQuery-centric data pipelines for a new use case. It manages
the user interview, schema investigation, architecture recommendation, and
delegates code generation to specialized sub-skills.

## Workflow

### 1. User Interview

Prompt the user to understand the new use case. Ask:

1.  **Business Goal**: What is the prediction target? (e.g., churn,
    recommendation).
2.  **Datasets**: What are the input BigQuery tables?
3.  **Features & Label**: What are the features and the target label?
4.  **Data Prep Logic**: How should the data be prepared/joined?
5.  **Model Complexity**: Do they need a simple model (like Logistic Regression)
    or a complex one (like Random Forest or XGBoost)?

### 2. Schema Investigation

Use the `bq` CLI tool to inspect the schemas of the tables provided by the user.

- For each table, run:

    ```bash
    bq show --format=prettyjson <project_id>:<dataset_id>.<table_id>
    ```

- Analyze the schema to confirm column names, types, and nullability. Present a
  summary to the user.

### 3. Solution Recommendation

Based on the interview and schema, propose the architecture:

1.  **Pipeline Options**:
    - **Spark-Centric**: Recommend if the user has existing Spark workloads,
      needs custom PySpark logic, or prefers Spark MLlib.
    - **BigQuery-Centric**: Recommend if the user wants a NoOps, SQL-backed
      pipeline using BigQuery DataFrames.
2.  **Serving Options**:
    - **Lean JSON**: Recommend if using Spark + Simple Model (Logistic
      Regression).
    - **ONNX**: Recommend if using Spark + Complex Model (Random
      Forest/XGBoost).
    - **Native BQML**: Recommend if using BigQuery-Centric pipeline.

Get the user's approval on the recommendation before proceeding.

### 4. Orchestrating Sub-Skills for Code Generation

Once approved, generate the notebooks by activating the relevant sub-skills:

#### Spark-Centric Pipeline Generation

If generating the Spark-centric notebook (`spark_centric_<use_case>.ipynb`),
apply the following sub-skills:

1.  **[spark-lightning-optimization](../spark-lightning-optimization/SKILL.md)**:
    Use to generate the Dataproc Serverless session with Lightning Engine.
2.  **[zero-copy-ingestion](../zero-copy-ingestion/SKILL.md)**: Use to generate
    the BigQuery data loading code using the connector.
3.  **[model-evaluation](../model-evaluation/SKILL.md)**: Use to generate the
    evaluation section (Accuracy or AUC-PR/Confusion Matrix).
4.  **[unified-model-registry](../unified-model-registry/SKILL.md)**: Use to
    generate the model saving and serving code (Lean JSON or ONNX export, Vertex
    AI registration).

#### BigQuery-Centric Pipeline Generation

If generating the BigQuery-centric notebook (`bq_centric_<use_case>.ipynb`),
apply the following sub-skills:

1.  **[zero-copy-ingestion](../zero-copy-ingestion/SKILL.md)**: Use to generate
    the BigFrames data loading code.
2.  **[bigframes-bqml](../bigframes-bqml/SKILL.md)**: Use to generate the
    feature engineering and BQML training code.
3.  **[model-evaluation](../model-evaluation/SKILL.md)**: Use to generate the
    evaluation section.
4.  **[unified-model-registry](../unified-model-registry/SKILL.md)**: Use to
    generate the BQML export and Vertex AI Endpoint deployment code.

#### Batch Prediction Script

Generate `predict_job_<use_case>.py` (PySpark) if the Spark pipeline is chosen,
ensuring it loads the model from GCS and writes predictions back to BigQuery.
