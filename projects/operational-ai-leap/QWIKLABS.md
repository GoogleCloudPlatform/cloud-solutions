# Zero ETL for Operational AI: The Operational AI Leap

## Overview

The Operational AI Leap demonstrates a modern paradigm shift enabling ML
engineers to run real-time vector search and generative LLM inference natively
inside the database engine. By connecting **Google Colab Enterprise** directly
to live **AlloyDB** data and joining **BigQuery** Data Lakes via zero-copy
federation, this demo proves how enterprise-grade AI recommendation agents can
be deployed in hours with _zero data movement overhead_.

- **Zero-ETL Architecture** : Eliminates ETL pipelines by connecting ML
  environments directly to live operational data.
- **In-Database Generative AI** : Invokes Gemini LLM endpoints directly inside
  database SQL via secure IAM integration.
- **Multi-Index Optimization** : Fuses Dense Vectors, Sparse Vectors, and
  Full-Text Search into a single unified plan.
- **Lakehouse Federation** : Executes real-time, zero-copy joins between live
  databases and BigQuery Data Lakes.
- **Compute Isolation** : Offloads high-throughput AI workloads onto dynamically
  scaling Read Pools.

The demo proves that Zero-ETL workflows accelerate AI deployment cycles from
_months to hours_ while protecting primary application performance.

---

## What You'll Need

To complete this lab, you will need:

- Access to a standard internet browser ( _Chrome browser recommended_ ).
- **Time** : Note the lab's **Completion time** in Qwiklabs, which is an
  estimate of the time it should take to complete all steps. Plan your schedule
  so you have time to complete the lab. Once you start the lab, you will not be
  able to pause and return later because _you begin at step 1 every time you
  start a lab_.
- You do NOT need a **Google Cloud Platform** account or project. An account,
  project, and associated resources are provided to you as part of this lab.
- If you already have your own GCP account, make sure you do _not_ use it for
  this lab.
- If your lab prompts you to log into the console, use _only the student account
  provided to you by the lab_. This prevents you from incurring charges for lab
  activities in your personal GCP account.
- Use a new **Incognito window** in Chrome or another browser for the Qwiklabs
  session. Alternatively, you can log out of all other Google and Gmail accounts
  before beginning the lab.

---

## Start Your Lab

When you are ready, click **Start Lab** . You can track your lab's progress with
the status bar at the top of your screen.

_Important: What is happening during this time?_ Your lab is spinning up GCP
resources for you behind the scenes, including an account, a project, resources
within the project, and permissions for you to control the resources you will
need to run the lab. This means that instead of spending time manually setting
up a project and building resources from scratch as part of your lab, you can
begin learning more quickly once provisioning completes.

---

## Sign In to Google Cloud Console

### Locate Your Lab's GCP Username and Password

To access the resources and console for this lab, locate the **Connection
Details** panel in Qwiklabs. Here you will find the account ID and password for
the account you will use to log in to the **Google Cloud Platform** . If your
lab provides other resource identifiers or connection-related information, it
will appear on this panel as well.

### Access the Console in Incognito Mode

1.  Using the Qwiklabs browser tab/window, _preferably in Incognito mode_ , or
    the separate browser you are using for the Qwiklabs session, copy the
    **Username** from the **Connection Details** panel and click **Open Google
    Console** .
1.  Paste in the **Username** and then the **Password** as prompted.
1.  Accept the terms and conditions.
1.  Because this is a temporary account, which you will only have access to for
    this one lab, _do not add recovery options and do not sign up for free
    trials_.

_Note: You can view the menu with a list of GCP Products and Services by
clicking the navigation menu button at the top-left next to Google Cloud
Platform._

---

## Lab Environment Readiness

Welcome to **The Operational AI Leap** Qwiklabs environment!

In this lab, all foundational infrastructure and data readiness tasks have been
automatically provisioned and verified _upon starting the lab session_. You do
not need to run any Terraform commands, data pipelines, or database population
scripts manually.

- **AlloyDB for PostgreSQL** : Pre-loaded with a live eCommerce product catalog
  containing _over 1,000 verified records_ and fully optimized vector search
  indexes including `ScaNN` , `HNSW` , and `GIN` built in parallel—ready for
  instant Zero-ETL querying.
- **Cymbal Shops Demo Application** : A live web storefront application hosted
  on Cloud Run.
- **BigQuery Data Lake** : Cross-region federated copy of historical order and
  transaction data under dataset `thelook_ecommerce` .
- **Colab Enterprise Runtime Template** : Pre-created and peered securely to the
  private database VPC named `demo-vpc` .

---

## Step 1: Locate Your Lab Credentials & Outputs

### Step 1.1: Locate Student Visible Outputs

Once you have signed into the **Google Cloud Console** using your temporary
credentials, return briefly to your Qwiklabs instruction panel on the left side
of your screen and locate the section titled **Student Visible Outputs** ( _or
lab details_ ).

### Step 1.2: Required Lab Outputs Checklist

Make a note of the following exact outputs from the **Student Visible Outputs**
panel:

- **Demo Application URL** ( `demo_app_url` ) : The web URL to view the live
  Cymbal Shops demo storefront.
- **Colab Notebook GCS URI** ( `notebook*gcs_uri` ) : The Cloud Storage path
  where your interactive English lab notebook is stored ( \_e.g.,
  `gs://YOUR_PROJECT_ID/operational-ai-leap.ipynb`\* ).
- **Colab Notebook GCS URI (KR)** ( `notebook*gcs_uri_ko` ) : The Cloud Storage
  path for the Korean translated lab notebook ( \_e.g.,
  `gs://YOUR_PROJECT_ID/operational-ai-leap-ko.ipynb`\* ).
- **AlloyDB Password** ( `alloydb_password` ) : The generated secure password
  for the AlloyDB database connection pool.
- **GCP Project ID** ( `gcp_project_id` ) : Your active Google Cloud project ID.
- **GCP Region** ( `gcp*region` ) : The exact Google Cloud region where your lab
  resources and runtime template were deployed ( \_e.g., `us-central1` or
  `us-west1`\* ).
- **AlloyDB Cluster Name** ( `alloydb_cluster_name` ) : Pre-configured cluster
  name which is `stylesearch-cluster` .
- **VPC Network Name** ( `vpc_name` ) : Pre-configured private network which is
  `demo-vpc` .
- **Colab Runtime Template ID** ( `colab_runtime_template_id` ) : Pre-configured
  Agent Platform runtime template which is `stylesearch-colab-template` .

---

## Step 2: Explore the Live Storefront Application

1.  Click or copy the **Demo Application URL** from your Student Visible Outputs
    into your browser.
1.  Explore the Cymbal Shops eCommerce catalog. Notice how semantic vector
    search and generative AI recommendations power product discovery right out
    of the box _without any external ETL replication delays_.

---

## Step 3: Run the Companion Interactive Notebook

To dive deep into the database-native AI architecture, you will run an
interactive Jupyter notebook inside **Google Colab Enterprise** . You may choose
either the English version ( `operational-ai-leap.ipynb` ) or the Korean version
( `operational-ai-leap-ko.ipynb` ).

### Step 3A: Import the Notebook into Colab Enterprise

1.  In the Google Cloud Console top search bar, search for **Colab Enterprise**
    and select **Colab Enterprise** from the results.
1.  In the top-right corner of the Colab Enterprise page, check the **Region**
    dropdown selector. Ensure it is set to your exact **GCP Region** (
    `gcp*region` ) from your Student Visible Outputs ( \_e.g., `us-central1` or
    `us-west1`\* ). If it shows a different region, click the dropdown and
    select your matching **GCP Region** so your runtime and private network
    align.
1.  In the left navigation sidebar, click **My Notebooks** .
1.  Click the **Import notebook** button at the top of the page.
1.  Under **Import source** , select **Cloud Storage** .
1.  In the **Cloud Storage file** field, click **Browse** and navigate into your
    project bucket using your `notebook_gcs_uri` or `notebook_gcs_uri_ko` output
    path, then select your preferred notebook file: `operational-ai-leap.ipynb`
    for English or `operational-ai-leap-ko.ipynb` for Korean.
1.  Click **Import** at the bottom of the dialog. The notebook will open
    directly in your browser.

### Step 3B: Connect to the Pre-Provisioned Runtime Template

To securely connect your notebook to the private AlloyDB database instance, you
must connect to the pre-created VPC-peered runtime template in your matching
region:

1.  In the top-right corner of your imported notebook, click the dropdown arrow
    `▾` next to the **Connect** button.
1.  From the dropdown menu, select **Change runtime type** or **Connect to a
    runtime** .
1.  In the **Connect to Agent Platform Runtime** panel on the right side, verify
    or select your matching **GCP Region** ( `gcp_region` ) if prompted.
1.  Click the **Runtimes** or **Runtime template** dropdown menu.
1.  Select **Cymbal Shops Colab Template** ( `stylesearch-colab-template` ).
1.  Verify that the **Network** field shows `demo-vpc` and **Subnetwork** shows
    `demo-vpc-subnet` .
1.  Click **Connect** at the bottom of the panel.
1.  Wait a few seconds for the runtime instance to start and indicate
    **Connected** in green.

### Step 3C: Execute the Lab Workflows

Once connected, and _before clicking run on all cells_ , follow these steps to
configure and execute your pipeline:

#### Step 3C.1: Configure Connection Variables ( _Required First Step_ )

1.  Locate the code cell directly under the heading
    `Connection Setup & Environment Configuration` ( _around Cell 5_ ).
1.  Update `project_id = "your-project-id"` with your exact **GCP Project ID** (
    `gcp_project_id` ) from your Student Visible Outputs.
1.  Update `alloydb_password = "your-db-password"` with your exact **AlloyDB
    Password** ( `alloydb_password` ) from your Student Visible Outputs.
1.  Run this cell by clicking the play button `▶` or pressing `Shift + Enter` .

#### Step 3C.2: Execute Remaining Pipeline Stages

1.  **Database Connection Pool** : Run the next cell to initialize low-latency
    `asyncpg` connections to AlloyDB with _0ms replication lag_.
1.  **In-Database Generative AI** : Execute SQL queries invoking `ai.generate()`
    and `embedding()` natively inside PostgreSQL using extension
    `google_ml_integration` .
1.  **Reciprocal Rank Fusion (RRF)** : Combine vector similarity, full-text
    keyword search via index `GIN` , and sparse `BM25` ranking into unified
    recommendation cards.
1.  **Zero-Copy Lakehouse Federation** : Run live federated joins using
    `bigquery*fdw` across BigQuery historical order datasets \_without ETL
    pipelines\*.

---

## End Your Lab

When you have completed your lab, click **End** . Qwiklabs removes the resources
you have used and cleans the account for you.

You will be given an opportunity to rate the lab experience. Select the
applicable number of stars, type a comment, and then click **Submit** .

_Note: The number of stars indicates the following:_

- **1 star** = Very dissatisfied
- **2 stars** = Dissatisfied
- **3 stars** = Neutral
- **4 stars** = Satisfied
- **5 stars** = Very satisfied

You may close the dialog if you do not want to provide feedback.

---

## Additional Resources

- For more information about Google Cloud Training and Certification, see
  https://cloud.google.com/training/
- For more Google Cloud Platform Self-Paced Labs, see http://run.qwiklabs.com
- For feedback, suggestions, or corrections, please use the **Support** tab.
