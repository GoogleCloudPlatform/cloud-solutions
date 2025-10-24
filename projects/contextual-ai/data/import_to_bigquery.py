#!/usr/bin/env python3

# Copyright 2025 Google LLC
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
Import ecommerce demo data to BigQuery.
Creates tables and loads the generated CSV data.
"""

import os

import pandas as pd
from google.cloud import bigquery

# Configuration
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
DATASET_ID = "ecommerce_data"

if not PROJECT_ID:
    raise ValueError("GOOGLE_CLOUD_PROJECT environment variable not set.")


def create_dataset_and_tables():
    """Create BigQuery dataset and tables"""
    client = bigquery.Client(project=PROJECT_ID)

    # Create dataset
    dataset_id = f"{PROJECT_ID}.{DATASET_ID}"
    dataset = bigquery.Dataset(dataset_id)
    dataset.location = "US"
    dataset.description = "Ecommerce IT Operations Demo Data"

    try:
        dataset = client.create_dataset(dataset, exists_ok=True)
        print(f"Created dataset {dataset_id}")
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Dataset creation error: {e}")

    # Define table schemas
    schemas = {
        "revenue_metrics": [
            bigquery.SchemaField("timestamp", "TIMESTAMP"),
            bigquery.SchemaField("hourly_revenue", "FLOAT"),
            bigquery.SchemaField("transaction_count", "INTEGER"),
            bigquery.SchemaField("avg_order_value", "FLOAT"),
        ],
        "system_performance": [
            bigquery.SchemaField("timestamp", "TIMESTAMP"),
            bigquery.SchemaField("avg_response_time_ms", "FLOAT"),
            bigquery.SchemaField("error_rate_percent", "FLOAT"),
            bigquery.SchemaField("requests_per_second", "FLOAT"),
        ],
        "user_activity": [
            bigquery.SchemaField("timestamp", "TIMESTAMP"),
            bigquery.SchemaField("active_users", "INTEGER"),
            bigquery.SchemaField("page_views", "INTEGER"),
            bigquery.SchemaField("bounce_rate_percent", "FLOAT"),
            bigquery.SchemaField("conversion_rate_percent", "FLOAT"),
        ],
        "infrastructure_health": [
            bigquery.SchemaField("timestamp", "TIMESTAMP"),
            bigquery.SchemaField("service_name", "STRING"),
            bigquery.SchemaField("cpu_percent", "FLOAT"),
            bigquery.SchemaField("memory_percent", "FLOAT"),
            bigquery.SchemaField("api_response_time_ms", "FLOAT"),
        ],
    }

    # Create tables
    for table_name, schema in schemas.items():
        table_id = f"{dataset_id}.{table_name}"
        table = bigquery.Table(table_id, schema=schema)

        try:
            table = client.create_table(table, exists_ok=True)
            print(f"Created table {table_id}")
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"Table creation error for {table_name}: {e}")


def load_data():
    """Load CSV data into BigQuery tables"""
    client = bigquery.Client(project=PROJECT_ID)

    tables = [
        "revenue_metrics",
        "system_performance",
        "user_activity",
        "infrastructure_health",
    ]

    for table_name in tables:
        print(f"Loading {table_name}...")

        # Read CSV
        df = pd.read_csv(f"{table_name}.csv")

        # Convert timestamp column to datetime
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        # Upload to BigQuery
        table_id = f"{PROJECT_ID}.{DATASET_ID}.{table_name}"

        job_config = bigquery.LoadJobConfig(
            write_disposition="WRITE_TRUNCATE"  # Overwrite existing data
        )

        try:
            job = client.load_table_from_dataframe(
                df, table_id, job_config=job_config
            )
            job.result()  # Wait for job to complete

            table = client.get_table(table_id)
            print(f"Loaded {table.num_rows} rows into {table_id}")

        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"Error loading {table_name}: {e}")


def verify_data():
    """Verify data was loaded correctly"""
    client = bigquery.Client(project=PROJECT_ID)

    print("\n=== Data Verification ===")

    # Check row counts
    tables = [
        "revenue_metrics",
        "system_performance",
        "user_activity",
        "infrastructure_health",
    ]

    for table_name in tables:
        query = f"""
        SELECT COUNT(*) as row_count,
               MIN(timestamp) as earliest_date,
               MAX(timestamp) as latest_date
        FROM `{PROJECT_ID}.{DATASET_ID}.{table_name}`
        """

        result = client.query(query).result()
        for row in result:
            log_message = (
                f"{table_name}: "
                f"{row.row_count} rows, "
                f"{row.earliest_date} to {row.latest_date}"
            )
            print(log_message)

    # Show incident periods
    print("\n=== Incident Verification ===")

    # Payment gateway outage (Day 7, hours 14-17)
    query = f"""
    SELECT
        r.timestamp,
        hourly_revenue,
        error_rate_percent,
        avg_response_time_ms
    FROM `{PROJECT_ID}.{DATASET_ID}.revenue_metrics` r
    JOIN `{PROJECT_ID}.{DATASET_ID}.system_performance` s
        ON r.timestamp = s.timestamp
    WHERE EXTRACT(HOUR FROM r.timestamp) BETWEEN 14 AND 17
    ORDER BY r.timestamp
    LIMIT 5
    """

    print("Payment Gateway Outage Sample:")
    result = client.query(query).result()
    for row in result:
        print(
            (
                f"  {row.timestamp}: Revenue=${row.hourly_revenue:,.0f},"
                f" Errors={row.error_rate_percent:.1f}%, "
                f"RT={row.avg_response_time_ms:.0f}ms"
            )
        )


def main():
    """Main execution"""
    print("Importing ecommerce demo data to BigQuery...")
    print(f"Project: {PROJECT_ID}")
    print(f"Dataset: {DATASET_ID}")
    print()

    # Check if CSV files exist
    required_files = [
        "revenue_metrics.csv",
        "system_performance.csv",
        "user_activity.csv",
        "infrastructure_health.csv",
    ]

    missing_files = [f for f in required_files if not os.path.exists(f)]
    if missing_files:
        print(f"Error: Missing CSV files: {missing_files}")
        print("Run generate_ecommerce_data.py first to create the data files.")
        return

    # Create dataset and tables
    create_dataset_and_tables()
    print()

    # Load data
    load_data()
    print()

    # Verify data
    verify_data()

    print("\n✅ Data import complete!")
    print("\nYou can now query the data in BigQuery:")
    print(f"Dataset: {PROJECT_ID}.{DATASET_ID}")
    print("\nExample queries:")
    print(
        f"- SELECT * FROM `{PROJECT_ID}.{DATASET_ID}.revenue_metrics` LIMIT 10"
    )
    print(
        f"""- SELECT * FROM `{PROJECT_ID}.{DATASET_ID}.infrastructure_health`
        WHERE service_name = 'payment-api' LIMIT 10"""
    )


if __name__ == "__main__":
    main()
