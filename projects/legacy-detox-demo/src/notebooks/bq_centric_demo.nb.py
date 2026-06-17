# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.20.0
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %%
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

# %% [markdown]
# # Legacy-Detox: AI-Native ML Pipelines - BigQuery-Centric Demo
#
# ## The Modernization Journey: From Spark to Native BigQuery
#
# In the Spark-centric demo, we modernized legacy Hadoop/Spark workloads using Serverless Spark and the Lightning Engine. While this is a huge step forward for Spark users, Google Cloud offers an even more integrated, "Zero Infrastructure" approach for tabular data: **BigQuery DataFrames (BigFrames)** and **BigQuery ML (BQML)**.
#
# **This notebook demonstrates the ultimate "Detox" process:**
# 1. **Zero Data Movement**: Instead of reading data into a Spark cluster, we keep all data in BigQuery. BigQuery DataFrames allows you to use a familiar pandas-like API (`bigframes.pandas`) and scikit-learn-like API (`bigframes.ml`) while executing the actual computations inside BigQuery.
# 2. **Simplified Architecture**: No Spark sessions to manage, no clusters (even serverless ones) to configure. It is pure Python code that compiles to SQL.
# 3. **Native Model Deployment**: Replaces the complex MLeap/JSON model export and custom FastAPI serving containers with native Google Cloud integrations.
#
# ### Our Business Story: Intelligent Re-engagement
# We solve the same business problem: predicting which **Product Category** an inactive user is most likely to buy from next, using the Looker eCommerce dataset.
#
# **This demo covers:**
# - Explore customer and order data using BigQuery DataFrames.
# - Train a **Multi-class Logistic Regression** model using BQML (via `bigframes.ml`).
# - Run **Native Batch Inference** to generate marketing leads directly in BigQuery.
# - Provide a suggestion for **Native On-Demand Serving** using Vertex AI Model Registry.

# %%
import os

import bigframes.pandas as bpd
import pandas as pd
from bigframes.ml.linear_model import LogisticRegression
from bigframes.ml.model_selection import train_test_split

# Initialize project settings
PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
REGION = os.environ["GOOGLE_CLOUD_REGION"]

# Configure BigQuery DataFrames global options
bpd.options.bigquery.project = PROJECT_ID
bpd.options.bigquery.location = "US"

print(
    f"BigQuery DataFrames initialized for project: {PROJECT_ID} in region: {REGION}"
)

# %% [markdown] id="cc955707"
# ## Step 1: Zero-Movement Data Loading
#
# We load the public dataset tables. Unlike Spark, this does not copy data to a local environment or Spark workers. It creates references to the BigQuery tables.

# %% id="01786a4b"
# Load Users
users_df = bpd.read_gbq("bigquery-public-data.thelook_ecommerce.users")

# Load Order Items
order_items_df = bpd.read_gbq(
    "bigquery-public-data.thelook_ecommerce.order_items"
)

# Load Products
products_df = bpd.read_gbq("bigquery-public-data.thelook_ecommerce.products")

print("BigQuery DataFrames references created successfully.")

# %% [markdown] id="22abd55e"
# ## Step 2: Feature Engineering
#
# We construct our training set. We want to predict the `category` of the last complete purchase per user.
# Instead of writing raw SQL, we use the pandas-like API of BigQuery DataFrames to perform the joins,
# sorting, and deduplication natively in BigQuery.

# %% id="d5749428"
# Filter for complete orders
complete_orders = order_items_df[order_items_df["status"] == "Complete"]

# Join complete orders with users
user_orders = complete_orders.merge(
    users_df, left_on="user_id", right_on="id", suffixes=("_order", "_user")
)

# Join with products to get the category
merged_df = user_orders.merge(
    products_df, left_on="product_id", right_on="id", suffixes=("", "_product")
)

# Identify the most recent purchase per user (sorting by order creation time)
sorted_df = merged_df.sort_values("created_at_order", ascending=False)
latest_purchases = sorted_df.drop_duplicates(subset=["user_id"], keep="first")

# Select and prepare final features and label
training_data_raw = latest_purchases[
    ["user_id", "age", "gender", "country", "category"]
].rename(columns={"category": "label_category"})

# Ensure age is float64 (double)
training_data_raw["age"] = training_data_raw["age"].astype("Float64")

training_data_raw.head(5)

# %% [markdown] id="d0d32395"
# ## Step 3: Train-Test Split
#
# We split our featurized data into training and evaluation sets natively using BigFrames ML.

# %% id="7994c9fd"
# Split features and label
X = training_data_raw[["age", "gender", "country"]]
y = training_data_raw[["label_category"]]

# Split into 80% train and 20% test
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

print(f"Training set size: {len(X_train)} rows")
print(f"Evaluation set size: {len(X_test)} rows")

# %% [markdown] id="5022171f"
# ## Step 4: Model Training
#
# We train a multinomial `LogisticRegression` model natively in BigQuery.
# BigQuery ML automatically handles categorical features (like `gender` and `country`) by one-hot encoding them natively,
# and standardizes numerical features (like `age`). This eliminates the need for manual preprocessing pipelines.

# %% id="e1726419"
# Initialize the BQML Logistic Regression model
model = LogisticRegression()

print("Training BQML Logistic Regression model...")
# Train the model (this executes a CREATE MODEL statement in BigQuery)
model.fit(X_train, y_train)
print("Model training complete.")

# %% [markdown] id="2b3a511f"
# ## Step 5: Model Evaluation
#
# We evaluate the model's accuracy on the test set.

# %% id="01971d98"
# Score the model
accuracy = model.score(X_test, y_test)
# The score method returns a DataFrame with metrics.
print("Evaluation Metrics:")
print(accuracy)

# %% [markdown] id="ec85a419"
# ## Step 6: Saving the Model Natively
#
# We save our trained model as a native BigQuery ML model.

# %% id="ccd90219"
# Save the model to a BigQuery dataset
# Note: This assumes the 'reengagement' dataset exists in your project
MODEL_NAME = f"{PROJECT_ID}.reengagement.bq_product_affinity_model"

# Save the model to BigQuery
model.to_gbq(MODEL_NAME, replace=True)
print(f"Model successfully saved to BigQuery as: {MODEL_NAME}")

# %% [markdown] id="65801fb7"
# ## Step 7: Native Batch Inference
#
# Instead of launching a Spark batch job, we run batch inference natively in BigQuery.
# We identify inactive users (no purchase in 90 days) and predict their product affinity.
# We use the BigQuery DataFrames API to perform this filtering natively.

# %% id="7c5966b5"
# Calculate cutoff date (90 days ago)
cutoff_date = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=90)

# Find active users in the last 90 days
active_user_ids = order_items_df[order_items_df["created_at"] > cutoff_date][
    "user_id"
].unique()

# Filter for inactive users
inactive_users = users_df[~users_df["id"].isin(active_user_ids)]

# Prepare final DataFrame for prediction
inactive_users = inactive_users[["id", "age", "gender", "country"]].rename(
    columns={"id": "user_id"}
)
inactive_users["age"] = inactive_users["age"].astype("Float64")

print(f"Found {len(inactive_users)} inactive users. Running predictions...")

# Run prediction using the trained model
predictions = model.predict(inactive_users)

# Select relevant columns for the marketing team
leads = predictions[
    ["user_id", "age", "gender", "country", "predicted_label_category"]
]

# Write the leads directly to a BigQuery table
LEADS_TABLE = f"{PROJECT_ID}.reengagement.bq_affinity_leads"
leads.to_gbq(LEADS_TABLE, if_exists="replace")

print(f"Batch inference complete. Leads written to: {LEADS_TABLE}")

# %% [markdown] id="71156ce1"
# ## Step 8: Verify Batch Results
#
# We verify the generated leads using BigQuery SQL.

# %% id="e22901bd"
# %%bigquery
SELECT * FROM `reengagement.bq_affinity_leads` LIMIT 20

# %% [markdown] id="f6e7d6a9"
# ## Step 9: Native On-Demand Serving (Vertex AI Integration)
#
# In a production environment, you may need to serve predictions in real-time (on-demand) to a web application.
#
# ### The Modern, Lean Approach
# Rather than exporting the model to GCS, downloading weights, and writing custom FastAPI containers (as required by Spark), BigQuery ML integrates natively with the **Vertex AI Model Registry**.
#
# #### How it works:
# 1. **Native Registration:** We register our BQML model to the Vertex AI Model Registry using the `ALTER MODEL` SQL statement, executed via the BigQuery client.
# 2. **Zero-Code Deployment:** We deploy the model from the Vertex AI Model Registry to a **Vertex AI Endpoint** using the Vertex AI SDK.
# 3. **Live Prediction:** We send a sample request to the deployed endpoint to get a real-time prediction.

# %% id="5c3c21dd"
from google.cloud import aiplatform

# Initialize Vertex AI SDK
aiplatform.init(project=PROJECT_ID, location=REGION)

# Get the BigQuery client from the BigFrames session
session = bpd.get_global_session()
bq_client = session.bqclient

# Define GCS bucket and export path
BUCKET_NAME = os.environ.get("BUCKET_NAME", f"{PROJECT_ID}-detox-bucket")
EXPORT_PATH = f"gs://{BUCKET_NAME}/models/bq_product_affinity_model"

# %% id="6fe1dc87"
print(f"1. Exporting BQML model to GCS at {EXPORT_PATH}...")
# Export the BQML model as a TensorFlow SavedModel
export_sql = f"""
EXPORT MODEL `{MODEL_NAME}`
OPTIONS(URI = '{EXPORT_PATH}')
"""
query_job = bq_client.query(export_sql)
query_job.result()
print("✅ Model exported successfully to GCS.")

# %% id="_MOLGqS4ex4l"
print("2. Uploading model to Vertex AI Model Registry...")
# Use the pre-built TensorFlow serving container
serving_container_image_uri = (
    "us-docker.pkg.dev/vertex-ai/prediction/tf2-cpu.2-15:latest"
)

uploaded_model = aiplatform.Model.upload(
    display_name="bq_product_affinity_model",
    artifact_uri=EXPORT_PATH,
    serving_container_image_uri=serving_container_image_uri,
)
print(
    f"✅ Model uploaded successfully. Resource name: {uploaded_model.resource_name}"
)

# %% id="f4ploGZ6exd5"
print("3. Deploying model to Vertex AI Endpoint...")
# This provisions the serving infrastructure (takes 10-15 minutes)
# We set replica count to 1 to minimize cost
endpoint = uploaded_model.deploy(
    machine_type="n1-standard-2",
    min_replica_count=1,
    max_replica_count=1,
)
print(f"✅ Model successfully deployed to endpoint: {endpoint.resource_name}")

# %% [markdown] id="a45b91cd"
# ## Step 10: Live Prediction Demo
#
# We test our deployed endpoint with a sample user record. This demonstrates how Vertex AI can serve BQML predictions with low latency, without needing any custom serving code.

# %% id="841db5db"
# Define a sample user record matching our training schema:
# age (float64), gender (string), country (string)
test_instance = {"age": 28.0, "gender": "M", "country": "United States"}

print(f"Sending prediction request for: {test_instance}")

# Send the request to the Vertex AI endpoint
# Note: BQML models expect the instance keys to match the feature column names
response = endpoint.predict(instances=[test_instance])

# Parse and display the results
# BQML prepends 'predicted_' to the target column name ('label_category')
for prediction in response.predictions:
    # The response is a dictionary containing the predicted label and probabilities
    predicted_category = prediction.get("predicted_label_category")
    print(f"\n✅ Predicted Product Affinity: {predicted_category}")
    print(f"Full Prediction Output: {prediction}")


# %% id="-Y0ncn6ylcVC"
