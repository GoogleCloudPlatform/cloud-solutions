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
Module to convert Bronze data to Iceberg Silver tables.
"""

import sys

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, to_timestamp

if len(sys.argv) < 3:
    print("Usage: iceberg_conversion.py <bronze_bucket> <silver_bucket>")
    sys.exit(1)

bronze_bucket = sys.argv[1]
silver_bucket = sys.argv[2]

# Initialize Spark session
spark = SparkSession.builder.appName("IcebergConversion").getOrCreate()

print("Creating namespace if not exists...")
spark.sql("CREATE NAMESPACE IF NOT EXISTS lakehouse.default")


def convert_table(
    target_table_name, source_path, schema_sql, transform_fn=None, is_csv=True
):
    """Utility to convert a single table to Iceberg."""
    print(f"--- Processing {target_table_name} ---")

    print(f"Reading data from {source_path}")
    if is_csv:
        df = spark.read.option("header", "true").csv(source_path)
    else:
        df = spark.read.parquet(source_path)

    if transform_fn:
        df = transform_fn(df)

    print(f"Dropping table lakehouse.default.{target_table_name}...")
    spark.sql(f"DROP TABLE IF EXISTS lakehouse.default.{target_table_name}")

    # Path format: gs://{bucket}/{namespace}/{table}
    expected_location = f"gs://{silver_bucket}/default/{target_table_name}"

    print(f"Creating Iceberg table at {expected_location}")
    spark.sql(f"""
    CREATE TABLE lakehouse.default.{target_table_name} (
        {schema_sql}
    )
    USING iceberg
    LOCATION '{expected_location}'
    """)

    print(f"Inserting data into {target_table_name}...")
    df.writeTo(f"lakehouse.default.{target_table_name}").append()

    print(f"Table {target_table_name} converted.")
    return target_table_name


# 1. Subway Ridership (CSV)
def transform_mta(df):
    """Cast MTA columns."""
    ts_fmt = "MM/dd/yyyy hh:mm:ss a"
    return (
        df.withColumn(
            "transit_timestamp", to_timestamp(col("transit_timestamp"), ts_fmt)
        )
        .withColumn("ridership", col("ridership").cast("integer"))
        .withColumn("transfers", col("transfers").cast("integer"))
        .withColumn("latitude", col("latitude").cast("double"))
        .withColumn("longitude", col("longitude").cast("double"))
    )


mta_schema = """
    transit_timestamp TIMESTAMP,
    transit_mode STRING,
    station_complex_id STRING,
    station_complex STRING,
    borough STRING,
    payment_method STRING,
    fare_class_category STRING,
    ridership INT,
    transfers INT,
    latitude DOUBLE,
    longitude DOUBLE,
    georeference STRING
"""

# 2. Bus Stations (CSV)
bus_stations_schema = """
    bus_stop_id INT,
    address STRING,
    school_zone STRING,
    seating STRING,
    borough STRING,
    latitude DOUBLE,
    longitude DOUBLE
"""


def transform_bus_stations(df):
    """Cast Bus Station columns."""
    return (
        df.withColumn("bus_stop_id", col("bus_stop_id").cast("integer"))
        .withColumn("latitude", col("latitude").cast("double"))
        .withColumn("longitude", col("longitude").cast("double"))
    )


# 3. Bus Lines (Parquet)
bus_lines_schema = """
    bus_line_id BIGINT,
    bus_line STRING,
    number_of_stops BIGINT,
    stops ARRAY<BIGINT>,
    frequency_minutes BIGINT
"""


def transform_bus_lines(df):
    """Cast Bus Line columns."""
    return (
        df.withColumn("bus_line_id", col("bus_line_id").cast("long"))
        .withColumn("number_of_stops", col("number_of_stops").cast("long"))
        .withColumn("frequency_minutes", col("frequency_minutes").cast("long"))
    )


# 4. Staged Ridership (Parquet)
staged_ridership_schema = """
    transit_timestamp TIMESTAMP,
    station_id BIGINT,
    ridership BIGINT
"""


def transform_staged_ridership(df):
    """Cast Staged Ridership columns."""
    return (
        df.withColumn(
            "transit_timestamp", col("transit_timestamp").cast("timestamp")
        )
        .withColumn("station_id", col("station_id").cast("long"))
        .withColumn("ridership", col("ridership").cast("long"))
    )


results = []
results.append(
    convert_table(
        "mta_ridership",
        f"gs://{bronze_bucket}/mta/*.csv",
        mta_schema,
        transform_mta,
    )
)
results.append(
    convert_table(
        "bus_stations",
        f"gs://{bronze_bucket}/staged/bus_stations/*.csv",
        bus_stations_schema,
        transform_bus_stations,
    )
)
results.append(
    convert_table(
        "bus_lines",
        f"gs://{bronze_bucket}/staged/bus_lines/*.parquet",
        bus_lines_schema,
        transform_bus_lines,
        is_csv=False,
    )
)
results.append(
    convert_table(
        "staged_ridership",
        f"gs://{bronze_bucket}/staged/ridership/*.parquet",
        staged_ridership_schema,
        transform_staged_ridership,
        is_csv=False,
    )
)

print("\n" + "=" * 80)
print("BIGQUERY VALIDATION QUERIES")
print("=" * 80)
print(
    "Since we are using BigLake Iceberg REST Catalog, tables are automatically"
)
print("available in BigQuery. Run these commands to verify the data:")
project_id = silver_bucket.replace("silver-", "")
for t_name in results:
    bq_cmd = f"""
bq query --use_legacy_sql=false \\
"SELECT * FROM \`{project_id}.{silver_bucket}.default.{t_name}\` LIMIT 10;"
"""
    print(f"\n--- {t_name} ---")
    print(bq_cmd)

print("=" * 80 + "\n")

spark.stop()
