#!/bin/bash
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

# Script to load data into HDFS on the source cluster and create Hive table

set -e

# Default values from Terraform
if [ -d "terraform/source-environment" ]; then
  # Save current dir
  CUR_DIR=$(pwd)
  cd terraform/source-environment || exit
  TF_PROJECT_ID=$(terraform output -raw project_id 2>/dev/null)
  TF_CLUSTER_NAME=$(terraform output -raw cluster_name 2>/dev/null)
  TF_REGION=$(terraform output -raw cluster_region 2>/dev/null)
  TF_ZONE=$(terraform output -raw cluster_zone 2>/dev/null)
  TF_BUCKET_NAME=$(terraform output -raw staging_bucket 2>/dev/null)
  cd "$CUR_DIR" || exit
fi

# Parse arguments
while [[ "$#" -gt 0 ]]; do
  case $1 in
  --project-id)
    PROJECT_ID="$2"
    shift
    ;;
  --cluster-name)
    CLUSTER_NAME="$2"
    shift
    ;;
  --region)
    REGION="$2"
    shift
    ;;
  --zone)
    ZONE="$2"
    shift
    ;;
  --bucket-name)
    BUCKET_NAME="$2"
    shift
    ;;
  *)
    echo "Unknown parameter passed: $1"
    exit 1
    ;;
  esac
  shift
done

# Use defaults if not overridden
PROJECT_ID=${PROJECT_ID:-$TF_PROJECT_ID}
CLUSTER_NAME=${CLUSTER_NAME:-$TF_CLUSTER_NAME}
REGION=${REGION:-$TF_REGION}
ZONE=${ZONE:-$TF_ZONE}
BUCKET_NAME=${BUCKET_NAME:-$TF_BUCKET_NAME}

if [ -z "$PROJECT_ID" ] || [ -z "$CLUSTER_NAME" ] || [ -z "$REGION" ] || [ -z "$ZONE" ] || [ -z "$BUCKET_NAME" ]; then
  echo "Usage: $0 [--project-id <project_id>] [--cluster-name <cluster_name>] [--region <region>] [--zone <zone>] [--bucket-name <bucket_name>]"
  echo "If flags are omitted, script will try to read values from terraform/source-environment outputs."
  exit 1
fi

PUBLIC_SOURCE_BUCKET="gs://data-lakehouse-demo-data-assets"
SOURCE_FILE="mta-raw/mta-manual-downloaded-data_MTA_Subway_Hourly_Ridership.csv"

echo "Copying subway ridership data from public source bucket to HDFS..."
gcloud compute ssh "$CLUSTER_NAME"-m \
  --project="$PROJECT_ID" \
  --zone="$ZONE" \
  --tunnel-through-iap \
  --command="hadoop fs -mkdir -p /data/mta && hadoop fs -cp -f $PUBLIC_SOURCE_BUCKET/$SOURCE_FILE /data/mta/"

echo "Copying additional staged datasets from public source bucket to HDFS..."
gcloud compute ssh "$CLUSTER_NAME"-m \
  --project="$PROJECT_ID" \
  --zone="$ZONE" \
  --tunnel-through-iap \
  --command="
    hadoop fs -mkdir -p /data/staged/ridership && \
    hadoop fs -cp -f $PUBLIC_SOURCE_BUCKET/staged-data/ridership/*.parquet /data/staged/ridership/ && \
    hadoop fs -mkdir -p /data/staged/bus_lines && \
    hadoop fs -cp -f $PUBLIC_SOURCE_BUCKET/staged-data/bus_lines/*.parquet /data/staged/bus_lines/ && \
    hadoop fs -mkdir -p /data/staged/bus_stations && \
    hadoop fs -cp -f $PUBLIC_SOURCE_BUCKET/staged-data/bus_stations.csv /data/staged/bus_stations/
  "

echo "Creating Hive tables..."
# Subway Ridership (CSV)
gcloud dataproc jobs submit hive \
  --cluster="$CLUSTER_NAME" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --execute="CREATE EXTERNAL TABLE IF NOT EXISTS mta_ridership (
    transit_timestamp STRING,
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
  )
  ROW FORMAT DELIMITED
  FIELDS TERMINATED BY ','
  STORED AS TEXTFILE
  LOCATION '/data/mta/'
  TBLPROPERTIES (\"skip.header.line.count\"=\"1\");"

# Staged Ridership (Parquet)
gcloud dataproc jobs submit hive \
  --cluster="$CLUSTER_NAME" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --execute="CREATE EXTERNAL TABLE IF NOT EXISTS staged_ridership (
    transit_timestamp TIMESTAMP,
    station_id BIGINT,
    ridership BIGINT
  )
  STORED AS PARQUET
  LOCATION '/data/staged/ridership/';"

# Bus Lines (Parquet)
gcloud dataproc jobs submit hive \
  --cluster="$CLUSTER_NAME" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --execute="CREATE EXTERNAL TABLE IF NOT EXISTS bus_lines (
    bus_line_id BIGINT,
    bus_line STRING,
    number_of_stops BIGINT,
    stops ARRAY<BIGINT>,
    frequency_minutes BIGINT
  )
  STORED AS PARQUET
  LOCATION '/data/staged/bus_lines/';"

# Bus Stations (CSV)
gcloud dataproc jobs submit hive \
  --cluster="$CLUSTER_NAME" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --execute="CREATE EXTERNAL TABLE IF NOT EXISTS bus_stations (
    bus_stop_id INT,
    address STRING,
    school_zone STRING,
    seating STRING,
    borough STRING,
    latitude DOUBLE,
    longitude DOUBLE
  )
  ROW FORMAT DELIMITED
  FIELDS TERMINATED BY ','
  STORED AS TEXTFILE
  LOCATION '/data/staged/bus_stations/'
  TBLPROPERTIES (\"skip.header.line.count\"=\"1\");"
