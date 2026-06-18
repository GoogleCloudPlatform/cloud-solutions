# Legacy Detox Demo

The project is "AI-Native - The Legacy Detox", a demo of a solution for running
data science jobs on Google Cloud. It focuses on migrating legacy PySpark jobs
(e.g., from Hadoop, SAS, Netezza) to Managed Service for Apache Spark and
BigQuery, providing a unified environment for Data Engineers and Data Scientists
to collaborate, perform exploratory data analysis with Gemini, and train/deploy
machine learning models using SparkML and Vertex AI.

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
- **Frictionless AI:** Move from raw data to trained models (SparkML/Vertex AI)
  within a single notebook environment.
- **Performance:** Demonstrate high-speed, cost-effective execution using the
  Lightning Engine.

### Core Features

- **Managed Service for Apache Spark:** Serverless, auto-scaling Spark execution
  with the Lightning Engine.
- **BigQuery Studio / Colab Enterprise:** A unified "single pane of glass" for
  data analysis and machine learning.
- **Apache Iceberg (BigLake):** A shared storage fabric providing zero-copy
  interoperability between Spark and BigQuery.
- **Gemini Integration:** AI-assisted data analysis, code generation, and
  insight discovery.
- **Vertex AI Model Registry:** Centralized governance for models trained via
  Spark or BigQuery ML.

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
- Deployment of a trained model to Vertex AI Registry.
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
1.  Browse to the `src` directory in this project, and select
    `spark_centric_demo.ipynb`.
1.  Upload and open the notebook.
1.  Click "Connect" on the top right to create a runtime.
1.  You might be asked to choose a network. If so, choose the `dataproc-vpc` and
    `dataproc-subnet`.
1.  Click `Create default Runtime`
1.  Follow the instructions in the notebook.

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
> `terraform destroy` will stop and remove the notebooks runtime, but as
> this operation is async, sometimes the `destroy` will fail. You can remove the
> runtime manually, through the Google Cloud Console, under **Colab Enterprise**
> -> **Runtimes**, and try again.
