# Agentic Data Cloud & Knowledge Catalog Demo

## Overview

The **Agentic Data Cloud Demo** demonstrates how to build an AI-ready data cloud
infrastructure on Google Cloud and perform advanced data analytics using Google
Cloud Dataplex, BigQuery, and Gemini models.

In this lab, you interact directly with live eCommerce data in BigQuery and run
automated metadata pipelines in Google Colab Enterprise:

- **Automated Data Profiling & Quality**: Execute Dataplex DataScans to profile
  tables and validate data quality rules automatically.
- **Automated Column Insights**: Generate intelligent column descriptions and
  documentation across dataset tables.
- **Relational Business Glossary**: Import structured business taxonomies and
  link glossary terms to physical BigQuery schemas.
- **BigQuery Property Graph Analysis**: Construct property graphs and query
  multi-hop customer relationships natively in SQL using GQL syntax.
- **BigQuery Generative AI & Vector Search**: Connect remote Gemini models to
  BigQuery and generate embeddings for semantic similarity search.
- **BigQuery SQL AI Functions**: Run high-level declarative AI functions
  (`AI.CLASSIFY`, `AI.SIMILARITY`, `AI.IF`, `AI.SEARCH`, and Distillation)
  directly inside SQL.

---

## What You Need

To complete this lab:

- Use a modern internet browser (Google Chrome recommended).
- Note the lab **Duration** in Qwiklabs. Plan your schedule to complete all
  steps within the allotted time. When you start the lab, you cannot pause and
  resume later.
- Do not use your personal Google Cloud account. The lab provides a dedicated
  Google Cloud project and temporary student credentials.
- Open a new **Incognito window** in Google Chrome for the lab session to
  prevent account conflicts.

---

## Start Your Lab

Click **Start Lab** in the Qwiklabs panel. The lab environment provisions
foundational Google Cloud resources automatically:

- An isolated Google Cloud project with all required BigQuery, Dataplex, and
  Vertex AI APIs enabled.
- The `thelook_ecommerce` BigQuery dataset populated with eCommerce tables
  (`distribution_centers`, `events`, `inventory_items`, `order_items`, `orders`,
  `products`, `users`).
- A dedicated Virtual Private Cloud (VPC) network (`adc-demo-vpc`) and private
  subnet.
- A pre-configured **Colab Enterprise Runtime Template** attached to the VPC.
- A Google Cloud Storage bucket containing all 7 interactive lab notebooks and
  glossary resource files.

---

## Sign In to Google Cloud Console

### Locate Your Student Credentials

Locate the **Connection Details** panel in Qwiklabs. Copy the temporary
**Username** and **Password**.

### Access the Console in Incognito Mode

1.  Open a new **Incognito window** in your browser.
1.  Navigate to the [Google Cloud Console](https://console.cloud.google.com).
1.  Enter the assigned student **Username** and click **Next**.
1.  Enter the temporary **Password** and click **Next**.
1.  Accept the terms and conditions. Do not add recovery options or sign up for
    free trials.

---

## Step 1: Review Student Visible Outputs

Return to the Qwiklabs interface and inspect the **Student Visible Outputs**
section. Note the following values:

- **Colab Runtime Template ID**: The pre-configured Colab Enterprise template
  name.
- **Notebooks GCS Bucket**: The Cloud Storage bucket containing the lab
  notebooks.
- **Google Cloud Project ID**: Your assigned temporary Google Cloud Project ID.
- **Google Cloud Region**: The primary deployment region (for example,
  `us-central1`).
- **BigQuery Dataset ID**: The pre-populated eCommerce dataset
  (`thelook_ecommerce`).

> [!NOTE]
>
> All notebooks are provided in both English (base filename) and Korean (`_ko`
> suffix). Choose your preferred language when importing.

---

## Step 2: Open Colab Enterprise

1.  In the Google Cloud Console search bar, search for **Colab Enterprise** and
    select it from the results.
1.  In the top-right toolbar, verify that the **Region** dropdown matches your
    assigned **Google Cloud Region** from the outputs (for example,
    `us-central1`).
1.  In the left navigation menu, click **My Notebooks**.

---

## Step 3: Import Lab Notebooks from Cloud Storage

Import the interactive lab notebooks directly from Cloud Storage using the
import dialog:

1.  Click **Import notebook** in the Colab Enterprise toolbar.
1.  In the import modal, select **Google Cloud Storage** as the source.
1.  Click **Browse** to open the Cloud Storage file selector.
1.  Select your assigned **Notebooks GCS Bucket** from the list.
1.  Select the desired Jupyter notebook file inside the bucket (for example,
    `01_data_profile_quality.ipynb` for English, or
    `01_data_profile_quality_ko.ipynb` for Korean).
1.  Click **Select**, then click **Import**.
1.  Repeat this process for the notebooks you want to explore during your lab
    session.

---

## Step 4: Connect to the Pre-Configured Runtime Template

1.  Open the imported notebook in the Colab Enterprise editor.
1.  In the top-right corner of the notebook editor, click the connection arrow
    next to **Connect** and choose **Connect to a runtime template**.
1.  Select the pre-provisioned runtime template matching your **Colab Runtime
    Template ID** (for example, `adc-demo-template-...`).
1.  Wait for the runtime to allocate and connect.

---

## Step 5: Execute Analytics Exercises

Run the notebooks sequentially:

### Notebook 01: Data Profile & Data Quality

- Open `01_data_profile_quality.ipynb`.
- Step through the cells to configure Dataplex DataScan jobs.
- Run automated profiling against the `users` and `orders` tables.
- Query profiling and rule validation results directly from BigQuery.

### Notebook 02 & 03: Automated Metadata Insights

- Open `02_data_insight.ipynb` and `03_dataset_insights.ipynb`.
- Generate AI-assisted column descriptions using Dataplex DataScans.
- Publish documentation labels into Dataplex Knowledge Catalog.

### Notebook 04: Relational Business Glossary Setup

- Open `04_glossary_setup.ipynb`.
- Load the structured retail glossary taxonomy from
  `resources/business_glossary.json`.
- Link glossary business terms and synonyms to physical BigQuery tables and
  columns.

### Notebook 05: BigQuery Graph Analysis (GQL)

- Open `05_graph_analysis.ipynb`.
- Create a Property Graph over eCommerce customers, orders, products, and
  distribution centers.
- Run SQL queries using GQL graph pattern matching
  (`MATCH (c:Customer)-[:ordered]->(p:Product)`) to identify purchase clusters.

### Notebook 06 & 07: BigQuery AI & Remote Gemini Models

- Open `06_bigquery_ai_ml_demo.ipynb` and
  `07_bigquery_ai_functions.ipynb`.
- Use the pre-configured `vertex-connection` BigQuery connection.
- Invoke Gemini models directly in SQL to classify customer reviews, compute
  semantic vector embeddings, and run cosine similarity search.
- Test high-level SQL AI functions (`AI.CLASSIFY`, `AI.SIMILARITY`,
  `AI.SEARCH`).

---

## Step 6: End Your Lab

When you finish running your experiments:

1.  Return to the Qwiklabs browser tab.
1.  Click **End Lab** and confirm.
1.  The lab environment tears down all temporary resources automatically.
