#!/usr/bin/env python3

# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Managed Service for Apache Spark Batch Inference Job:
Product Affinity Re-engagement
This script identifies inactive users, predicts their preferred product category
using a pre-trained SparkML model, and recommends a top-rated product.
"""

import argparse

from pyspark.ml import PipelineModel
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F


def get_spark_session() -> SparkSession:
    # App name for Managed Service For Apache Spark UI tracking
    return SparkSession.builder.appName(
        "Production-Batch-Inference-Reengagement"
    ).getOrCreate()


def main(project_id, bucket_name, model_path):
    # Initialize Spark
    spark = get_spark_session()

    # Define Output Table
    OUTPUT_TABLE = f"{project_id}.reengagement.affinity_leads"

    print(f"Loading Product Affinity Model from {model_path}...")
    model = PipelineModel.load(model_path)

    print("Step 1: Identifying 'Inactive' Users...")
    # Loading tables individually and using Spark SQL for robustness
    df_users_raw = (
        spark.read.format("bigquery")
        .option("table", "bigquery-public-data.thelook_ecommerce.users")
        .load()
    )

    df_orders_raw = (
        spark.read.format("bigquery")
        .option("table", "bigquery-public-data.thelook_ecommerce.order_items")
        .load()
    )

    df_users_raw.createOrReplaceTempView("users")
    df_orders_raw.createOrReplaceTempView("order_items")

    inactive_users_query = """
    SELECT
        u.id as user_id,
        u.age,
        u.gender,
        u.country
    FROM users u
    LEFT JOIN order_items oi ON u.id = oi.user_id
    GROUP BY u.id, u.age, u.gender, u.country
    HAVING MAX(oi.created_at) < current_timestamp() - INTERVAL 90 DAYS
       OR MAX(oi.created_at) IS NULL
    LIMIT 10000
    """

    df_leads = spark.sql(inactive_users_query)

    print(f"Step 2: Running Batch Prediction for {df_leads.count()} leads...")
    # The pipeline model handles demographics encoding and scaling
    # automatically.
    # Note: WARN about missing 'label_category' is expected as we are
    # in prediction (no labels).
    df_predictions = model.transform(df_leads)

    print("Step 3: Finding Top-Rated Products for each predicted category...")
    # Load products to find the best match for the predicted category
    df_products = (
        spark.read.format("bigquery")
        .option("table", "bigquery-public-data.thelook_ecommerce.products")
        .load()
    )

    # Simple recommendation logic: Pick the
    # highest-priced item in each category.
    window_spec = Window.partitionBy("category").orderBy(
        F.col("retail_price").desc()
    )

    df_top_products = (
        df_products.withColumn("rank", F.row_number().over(window_spec))
        .filter(F.col("rank") == 1)
        .select(
            F.col("category").alias("predicted_category"),
            F.col("name").alias("recommended_product"),
            F.col("retail_price"),
        )
    )

    # Join predictions with product recommendations
    # We use 'predicted_category' which was created by
    # IndexToString in the pipeline
    final_output = df_predictions.select(
        "user_id", "age", "gender", "country", "predicted_category"
    ).join(df_top_products, on="predicted_category", how="left")

    print(
        f"Step 4: Writing Actionable leads to BigQuery table: {OUTPUT_TABLE}..."
    )
    # Spark is not an island! Writing back to BigQuery makes
    # results available for SQL and BI tools.
    (
        final_output.write.format("bigquery")
        .mode("overwrite")
        .option("table", OUTPUT_TABLE)
        .option("temporaryGcsBucket", bucket_name)
        .save()
    )

    print("Batch Job Complete. Re-engagement leads are ready in BigQuery.")
    spark.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Managed Service for Apache Spark Batch Inference Job"
    )
    parser.add_argument(
        "--project-id", required=True, help="Google Cloud Project ID"
    )
    parser.add_argument(
        "--bucket-name", required=True, help="GCS Bucket Name for staging"
    )
    parser.add_argument(
        "--model-path",
        required=True,
        help="GCS path to the saved PipelineModel",
    )

    args = parser.parse_args()
    main(args.project_id, args.bucket_name, args.model_path)
