# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.1
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% id="kzcPtSa2FLbr"
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# %% [markdown] id="wYhD473SFLbs"
# # Legacy-Detox: AI-Native ML Pipelines - Spark-Centric Demo
#
# **Before you begin** make sure to click "Connect" on the top right corner, to create or connect to a runtime.
# You might be asked to choose the default network for the runtime. In that case,
# choose the designated `dataproc-vpc` and `dataproc-subnet`.
#
# ## The Modernization Journey: From Legacy Silos to AI-Native Spark
#
# Many organizations struggle with "Legacy Data Debt"—expensive, hard-to-maintain Hadoop/Spark clusters that are siloed from the rest of the cloud ecosystem. Managing infrastructure becomes a full-time job, leaving little room for actual data science.
#
# **This notebook demonstrates the "Detox" process:**
# 1. **Zero Infrastructure Overhead**: We use **Dataproc Serverless** to run Spark. No clusters to provision, no versions to manage, and no idle costs.
# 2. **Lightning-Fast Execution**: We leverage the **Dataproc Lightning Engine**, a high-performance vectorized execution engine that speeds up Spark jobs by up to 3x without code changes.
# 3. **AI-Assisted Development**: Use Gemini Code Assist directly within the notebook to write complex PySpark logic using natural language.
# 4. **Seamless Integration**: Spark isn't an island. We read directly from **BigQuery** and write models to **Cloud Storage**, creating a unified AI-Native pipeline.
#
# ### Our Business Story: Intelligent Re-engagement
# TheLook eCommerce wants to personalize their marketing. Instead of generic "Please come back" emails, they want to predict exactly which **Product Category** an inactive user is most likely to buy from next.
#
# **This demo covers:**
# - Explore customer and order data using Spark and BigQuery.
# - Train a **Multi-class Logistic Regression** model to predict user category affinity.
# - Deploy this model for a **Production Batch Job** on a managed cluster to generate actionable marketing leads in BigQuery.

# %% [markdown] id="ocnfNZpLrBh7"
# ## Step 1: Setup
#
# We initialize our environment variables.

# %% id="eQTRkSItFLbu"
import os

PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
REGION = os.environ["GOOGLE_CLOUD_REGION"]
BUCKET_NAME = f"{PROJECT_ID}-detox-bucket"

# %% [markdown] id="_qJCXP8TrJWO"
# ## Step 2: Modern Spark Sessions with the Lightning Engine
#
# In a legacy world, you'd spend hours tuning `spark-defaults.conf`. Here, we define a Serverless session that automatically uses the **Lightning Engine** for optimized performance.
#
# This engine provides:
# - **Native Execution**: Faster SQL and Dataframe operations.
# - **Auto-Scaling**: Dynamically adjusts to the workload.
# - **BigQuery Optimization**: High-speed data transfer between Spark and BigQuery.

# %% colab={"base_uri": "https://localhost:8080/", "height": 205} id="pnz8zToJFLbu" outputId="dbe7bd6f-b105-4ce8-a22b-31b3c607a3a8"
from google.cloud.dataproc_spark_connect import DataprocSparkSession
from google.cloud.dataproc_v1 import Session
from pyspark.sql import SparkSession


def create_spark_session():
    """Creates a SparkSession with BigQuery and GCS support using Lightning Engine."""
    session = Session()
    session.runtime_config.version = "3.0"

    # The 'lightningEngine' is the key modernization component here
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

# %% [markdown] id="56PNlpUeXQhK"
# ## Step 3: High-Speed Data Access from BigQuery
#
# Load users, orders, and product data. Because we are using the Spark-BigQuery connector on the Lightning engine, this read is significantly faster than standard JDBC connections.

# %% colab={"base_uri": "https://localhost:8080/", "height": 272} id="OmUXjaBlFLbu"
# Load Users
users_df = (
    spark.read.format("bigquery")
    .option("table", "bigquery-public-data.thelook_ecommerce.users")
    .load()
)

# Load Order Items
order_items_df = (
    spark.read.format("bigquery")
    .option("table", "bigquery-public-data.thelook_ecommerce.order_items")
    .load()
)

# Load Products (needed for category labels)
products_df = (
    spark.read.format("bigquery")
    .option("table", "bigquery-public-data.thelook_ecommerce.products")
    .load()
)

users_df.createOrReplaceTempView("users")
order_items_df.createOrReplaceTempView("order_items")
products_df.createOrReplaceTempView("products")

# %% [markdown]
# ## AI-Assisted Exploration with Gemini
#
# BigQuery Studio notebooks include a Gemini-powered code assistant. You can use natural language to explore the data we just loaded. 
#
# **Try creating a new code cell and using these prompts:**
#
# 1. *"Using PySpark, show the top 5 most frequent countries in the users table."*
# 2. *"Using the 'users' table, calculate the average age of users grouped by gender."*
# 3. *"Using PySpark and the 'products' table, list the top 10 most expensive product categories."*
# 4. *"Using the 'order_items' table, show the distribution of order status (e.g. Complete, Returned)."*
# 5. *"Using PySpark, join 'users' and 'order_items' to find the total number of orders per country."*
# 6. *"Generate a matplotlib chart showing the number of users created per year."*

# %% [markdown]
# ## Step 4: AI-Assisted Feature Engineering
#
# We need to build a training set. Our goal is to predict the `category` of the last item a user bought.
#
# **Logic:**
# 1. Join Users, Order Items, and Products.
# 2. Filter for 'Complete' orders.
# 3. Identify the most recent category purchased per user.
# 4. Use demographics (Age, Gender, Country) as features.

# %% id="0MXjHTD2aDaW"
# We use Spark SQL for complex joins, a familiar syntax for legacy users but running on modern infra.
training_data_raw = spark.sql("""
WITH user_category_purchases AS (
  SELECT
    u.id as user_id,
    u.age,
    u.gender,
    u.country,
    p.category,
    ROW_NUMBER() OVER(PARTITION BY u.id ORDER BY oi.created_at DESC) as rank
  FROM users u
  JOIN order_items oi ON u.id = oi.user_id
  JOIN products p ON oi.product_id = p.id
  WHERE oi.status = 'Complete'
)
SELECT
  user_id,
  CAST(age AS DOUBLE) as age,
  gender,
  country,
  category as label_category
FROM user_category_purchases
WHERE rank = 1
""")

training_data_raw.show(5)

# %% [markdown]
# ## Step 5: Multi-class Model Training
#
# Use `StringIndexer` to convert our categorical features and labels into numerical indices, and then train a `LogisticRegression` model.
#
# Unlike the simple "buy/no-buy" model, this is a **Multi-class Classifier**.

# %% id="lxC8L45AsPbN"
from pyspark.ml.classification import LogisticRegression
from pyspark.ml.feature import (
    IndexToString,
    StandardScaler,
    StringIndexer,
    VectorAssembler,
)
from pyspark.ml.pipeline import Pipeline

# 1. Index categorical strings (Gender, Country, Category)
gender_indexer = StringIndexer(
    inputCol="gender", outputCol="gender_index", handleInvalid="keep"
)
country_indexer = StringIndexer(
    inputCol="country", outputCol="country_index", handleInvalid="keep"
)
label_indexer = StringIndexer(inputCol="label_category", outputCol="label")

# 2. Assemble features
assembler = VectorAssembler(
    inputCols=["age", "gender_index", "country_index"], outputCol="features"
)

# 3. Scale features for better convergence
scaler = StandardScaler(inputCol="features", outputCol="scaled_features")

# 4. Multi-class Logistic Regression
lr = LogisticRegression(
    featuresCol="scaled_features", labelCol="label", family="multinomial"
)

# 5. Convert indexed prediction back to string
label_converter = IndexToString(
    inputCol="prediction",
    outputCol="predicted_category",
    labels=label_indexer.fit(training_data_raw).labels,
)

# 6. Build the Pipeline
pipeline = Pipeline(
    stages=[
        gender_indexer,
        country_indexer,
        label_indexer,
        assembler,
        scaler,
        lr,
        label_converter,
    ]
)

# Split and Train
train, test = training_data_raw.randomSplit([0.8, 0.2], seed=42)
pipeline_model = pipeline.fit(train)

print("Model Training Complete.")

# %% [markdown]
# ## Step 6: Evaluation & Accuracy
#
# We evaluate how well we can predict the category affinity.

# %%
from pyspark.ml.evaluation import MulticlassClassificationEvaluator

predictions = pipeline_model.transform(test)
evaluator = MulticlassClassificationEvaluator(metricName="accuracy")
accuracy = evaluator.evaluate(predictions)

print(f"Model Accuracy: {accuracy:.2%}")

# %% [markdown]
# ## Step 7: Saving the AI Asset
#
# We save the trained pipeline (including the indexers) to Cloud Storage. This allows our production batch job to load the model and apply the same transformations to new, unseen data.

# %%
MODEL_PATH = f"gs://{BUCKET_NAME}/models/product_affinity_model"
pipeline_model.write().overwrite().save(MODEL_PATH)
print(f"Model successfully exported to {MODEL_PATH}")

# %% [markdown]
# ## Transition: From Notebook to Production Batch Inference
#
# We've "detoxed" our development environment by moving to Serverless Spark and the Lightning Engine. However, a notebook is not a production environment.
#
# **The Next Step:**
# Our production system needs to identify **Inactive Users** and run this model against them to generate re-engagement recommendations.
#
# We have a production PySpark script ready: `predict_job.py`. It queries for users who have not made a purchase
# in the last 90 days, runs the model for those users, finds a high likelihood of product affinity for those users,
# and writes the results back to a BigQuery table (`reengagement.affinity_leads`). This enables our company to send
# out emails and reach out to re-engage with customers.
#
# You can review the code in this repository.
#
# ### Triggering the Batch Job:
# In a real environment, you would use **Cloud Composer (Airflow)** or **Vertex AI Pipelines**. For this demo, we've provided a simple bash runner that submits this job to a persistent Dataproc cluster.
#
# This shows how to deploy the developed model in a robust, automated production pipeline.

# %% [markdown]
# ### Run the Production Batch Inference Job
#
# The following cell executes our rendered `run_predict_job.sh` script. This script:
# 1. Starts the managed Dataproc cluster (if stopped).
# 2. Submits the `predict_job.py` Spark job.
# 3. Passes the model path and data sources as arguments.

# %%
# Call the shell script that triggers a batch PySpark job.
# Review the shell script in this repository.

# !gcloud storage cp gs://{BUCKET_NAME}/run_predict_job.sh ./run_predict_job.sh
# !chmod +x ./run_predict_job.sh
# !./run_predict_job.sh --project-id {PROJECT_ID} --region {REGION} --bucket-name {BUCKET_NAME}

# %% [markdown]
# ### Step 9: Final Results in BigQuery
#
# Our modernized Spark pipeline has successfully integrated with the Google Cloud ecosystem. The re-engagement leads are now available directly in BigQuery, making them accessible to SQL developers, BI tools, and downstream automation.
#
# Let's verify the results using BigQuery SQL.

# %%
# %%bigquery
SELECT * FROM `reengagement.affinity_leads` LIMIT 20

# %% [markdown]
# ## Conclusion: The Legacy-Detox Recap
#
# Congratulations! You have successfully journeyed from a "Legacy" mindset to an **AI-Native Spark Pipeline**. 
#
# ### Key Takeaways:
# 1.  **Serverless Agility**: We used **Dataproc Serverless** for exploration and training. This gave us "Immediate Spark"—zero clusters to manage, zero idle costs, and instant scaling. This is perfect for the "Experimentation Phase" of Data Science.
# 2.  **Persistent Reliability**: We ran our production batch inference on a **Persistent Managed Spark Cluster**. While we want serverless for agility, a persistent cluster for production provides a stable "Production Anchor" where we can track long-term metrics, monitor job health, and centralize our evaluation logs.
# 3.  **Modern Performance**: The **Lightning Engine** ensured that our BigQuery reads and complex joins execute with vectorized performance, bridging the gap between Big Data and AI.
# 4.  **Business Value**: We didn't just build a model; we solved a business problem. By identifying **Inactive Users** and predicting their **Product Affinity**, we generate actionable leads and write them directly into **BigQuery** for the marketing team to use immediately.
#
# This architecture represents the "New Normal" for Spark on Google Cloud: fast, integrated, and business-focused.
