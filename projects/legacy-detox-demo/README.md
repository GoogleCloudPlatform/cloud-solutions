# Legacy Detox Demo

The project is "AI-Native - The Legacy Detox", a demo of a solution for running
data science jobs on Google Cloud. It focuses on migrating legacy PySpark jobs
(e.g., from Hadoop, SAS, Netezza) to Managed Service for Apache Spark and
BigQuery, providing a unified environment for Data Engineers and Data Scientists
to collaborate, perform exploratory data analysis with Gemini, and train/deploy
machine learning models using SparkML and Gemini Enterprise Agent Platform.

## Product Definition: AI-Native - The Legacy Detox

### Vision

To provide a compelling demo showcasing how organizations can "detox" from
legacy data systems (Hadoop, SAS, Netezza) by migrating heavy PySpark workloads
to Google Cloud's Managed Service for Apache Spark. The solution bridges the gap
between Data Engineering and Data Science by offering a unified, AI-powered
workspace in BigQuery Studio and Colab Enterprise, enabling frictionless model
training and deployment.

### Prerequisites

- A Google Cloud Project with Billing Enabled
- Terraform

### Target Audience

- **Data Scientists** who need a native AI workspace to explore data and build
  models without infrastructure friction.
- **Data Engineers** who want to move away from manual cluster management to
  serverless, auto-scaling Spark.

### Key Objectives

- **Modernization:** Execute legacy PySpark jobs instantly on serverless
  infrastructure.
- **Unified Collaboration:** Enable engineers and scientists to work on the
  exact same datasets (Lakehouse/Iceberg) without data duplication.
- **Frictionless AI:** Move from raw data to trained models (SparkML/Gemini
  Enterprise Agent Engine) within a single notebook environment.
- **Performance:** Demonstrate high-speed, cost-effective execution using the
  Lightning Engine.

### Reference Material

- **Serverless Spark Quickstart**: Refer to the
  [Managed Service for Apache Spark Serverless Lab Manual](https://github.com/GoogleCloudPlatform/lakehouse-solutions/blob/main/solutions/spark-serverless-quickstart/lab-manuals/ts2-manual.md)
  for environment setup and Spark Lightning Engine configuration.
- **Data Science Notebook**: Adopted the flow and code samples found in the
  [Spark Data Science Notebook](https://github.com/chmstimoteo/devrel-demos/blob/main/data-analytics/qwiklabs/Spark_Data_Science.ipynb).
- **Dataproc Examples**:
  [Dataproc examples notebooks](https://github.com/statmike/vertex-ai-mlops/blob/main/data%2Bai/dataproc/examples/readme.md).
- **BigQuery Notebooks Guide**: Get up and running with
  [PySpark in BigQuery Notebook documentation](https://docs.cloud.google.com/bigquery/docs/use-spark#dataproc_serverless_bq_notebook-Wordcount).
- **Data Science Agent in BigQuery Notebooks**: Guides in the
  [BigQuery Notebook documentation](https://docs.cloud.google.com/bigquery/docs/colab-data-science-agent).
- **BigQuery DataFrames**: Refer to the
  [BigQuery DataFrame guides](https://docs.cloud.google.com/bigquery/docs/bigquery-dataframes-introduction)
  to implement transformations done in Spark DataFrames.

### Core Features

- **Managed Service for Apache Spark:** Serverless, auto-scaling Spark execution
  with the Lightning Engine.
- **BigQuery Studio / Colab Enterprise:** A unified "single pane of glass" for
  data analysis and machine learning.
- **Apache Iceberg (BigLake):** A shared storage fabric providing zero-copy
  interoperability between Spark and BigQuery.
- **Gemini Integration:** AI-assisted data analysis, code generation, and
  insight discovery.
- **Gemini Enterprise Agent Platform Model Registry:** Centralized governance
  for models trained via Spark or BigQuery ML.

### Modules

- **Spark-Centric Workflow:** This module consists of a BigQuery Studio
  notebook, which allows users to seamlessly transition legacy PySpark workflows
  to serverless Spark execution with the Lightning Engine. It allows users to
  prepare and explore data using a serverless Spark interactive session, train a
  linear regression model using a batch serverless Spark job, and run batch
  inference on a persistent Spark cluster.
- **BigQuery ML Workflow:** This module reproduces the equivalent process of the
  Spark-Centric Workflow, but implements it entirely within BigQuery using
  BigFrames and BQML.

### Success Criteria

- A compelling end-to-end narrative that clearly demonstrates the "Legacy Detox"
  journey.
- Successful execution of a legacy-style PySpark job on serverless
  infrastructure.
- Deployment of a trained model to Gemini Enterprise Agent Platform Registry.
- Demonstrable performance benefits of the Lightning Engine.

## 🚀 Getting Started

### 1. Initialize the Project

Run the following script to configure your Google Cloud project, enable required
APIs, and set up your Terraform variables:

```bash
./scripts/init.sh
```

### 2. Deploy Infrastructure

Navigate to the `terraform` directory and deploy the solution:

```bash
cd terraform
terraform init
terraform apply
```

### 3. Upload the Spark-Centric Notebook

1.  Open your cloud console, and navigate to BigQuery Studio.
1.  If this is your first time in BigQuery Studio, select a code region.
1.  On the left panel, make sure you are on the "Files" tab.
1.  Click "+ Add" -> upload -> Notebook
1.  Browse to the `src/notebooks` directory in this project, and select
    `spark_centric_demo.ipynb`.
1.  Upload the notebook.
1.  Repeat the process for the `src/notebooks/bq_centric_demo.ipynb`
1.  Open each of the notebooks in any order your would like.
1.  Click "Connect" on the top right to create a runtime.
1.  You might be asked to choose a network. If so, choose the `legacy-detox-vpc`
    and `legacy-detox-subnet`.
1.  Click `Create default Runtime`
1.  Follow the instructions in the notebooks.

## Use Skills: Bring your own use-case

We have created a set of AI Agent Skills that allow you to easily replicate this
"Zero-Copy" architecture for your own datasets and use cases. Instead of
manually writing the notebooks, you can use a coding agent (like Antigravity) to
interview you, investigate your schemas, and generate the pipelines.

### How it Works

The architecture is split into a coordinator skill and several specialized
sub-skills:

1.  **`pipeline-generator` (Coordinator)**: Conducts the user interview,
    inspects BigQuery schemas using the `bq` CLI, recommends the best
    architecture, and orchestrates the other skills.
1.  **`zero-copy-ingestion`**: Handles loading data from BigQuery (Spark
    connector & BigFrames).
1.  **`spark-lightning-optimization`**: Configures optimized Serverless Spark
    sessions.
1.  **`bigframes-bqml`**: Handles BigQuery-centric training and feature
    engineering.
1.  **`model-evaluation`**: Generates evaluation code (Accuracy, AUC-PR,
    Confusion Matrix).
1.  **`unified-model-registry`**: Handles model serving (Lean JSON, ONNX, or
    Vertex AI Endpoints).

### Installation & Registration

These skills are registered locally in the project. If you are using a
compatible agent (like Antigravity), they will be automatically discovered via
the `.agents/skills.json` file.

To ensure they are active in your workspace:

1.  Make sure the `.agents/skills.json` file exists in the project root (it is
    configured to point to `skills/`).
1.  The agent will automatically load them upon startup.

### Example: Running with Antigravity

You can invoke the coordinator skill using the `antigravity` CLI or in an
interactive chat session.

#### Option 1: Interactive Chat

Start a chat session with the agent in this directory:

```bash
antigravity chat
```

Then, ask the agent to start the process:

> **User**: I want to create a new pipeline for a new use case. Please use the
> `pipeline-generator` skill.

#### Option 2: Direct Command

You can also trigger it directly:

```bash
antigravity run --prompt "Use the pipeline-generator skill to build a zero-copy pipeline for my new dataset."
```

The agent will then start the interview:

1.  It will ask you about your business goal and table names.
1.  It will run `bq show` to inspect the schemas.
1.  It will propose the design and, upon your approval, generate the new
    notebooks under `src/notebooks/`.

## Cleanup

To avoid costs, after finishing the demo, you can cleanup the resources by the
following steps:

1.  Open your **Google Cloud Console**
1.  Navigate to **Colab Enterprise** -> **Runtimes**
1.  Find the runtime that was used with the notebooks, select it and click
    "Delete".
1.  Confirm the deletion
1.  Go to your `terraform` directory and run the `destroy` command

```bash
cd terraform
terraform destroy
```

> [!NOTE]
>
> `terraform destroy` will stop and remove the notebooks runtime, but as this
> operation is async, sometimes the `destroy` will fail. You can remove the
> runtime manually, through the Google Cloud Console, under **Colab Enterprise**
> -> **Runtimes**, and try again.
