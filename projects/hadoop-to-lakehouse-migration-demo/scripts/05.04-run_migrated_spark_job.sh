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

# Script to run migrated Spark job on Managed Spark Serverless

set -e

# Default values from Terraform
if [ -d "terraform/target-environment" ]; then
  CUR_DIR=$(pwd)
  cd terraform/target-environment || exit
  TF_TARGET_PROJECT=$(terraform output -raw project_id 2>/dev/null)
  TF_SILVER_BUCKET=$(terraform output -raw silver_bucket 2>/dev/null)
  TF_METASTORE_ID=$(terraform output -raw metastore_id 2>/dev/null)
  TF_DATAPROC_SA=$(terraform output -raw dataproc_service_account 2>/dev/null)
  TF_SUBNET=$(terraform output -raw subnet_name 2>/dev/null)
  TF_REGION=$(terraform output -raw region 2>/dev/null)
  cd "$CUR_DIR" || exit
fi

# Variables with precedence: Flag -> TF Output -> Default
TARGET_PROJECT="${TF_TARGET_PROJECT}"
SILVER_BUCKET="${TF_SILVER_BUCKET}"
METASTORE_ID="${TF_METASTORE_ID}"
DATAPROC_SA="${TF_DATAPROC_SA}"
SUBNET="${TF_SUBNET}"
REGION="${TF_REGION}"
SCRIPTS_DIR="scripts"

# Parse flags
while [[ $# -gt 0 ]]; do
  case $1 in
  --target-project)
    TARGET_PROJECT="$2"
    shift 2
    ;;
  --silver-bucket)
    SILVER_BUCKET="$2"
    shift 2
    ;;
  --metastore-id)
    METASTORE_ID="$2"
    shift 2
    ;;
  --scripts-dir)
    SCRIPTS_DIR="$2"
    shift 2
    ;;
  --service-account)
    DATAPROC_SA="$2"
    shift 2
    ;;
  --subnet)
    SUBNET="$2"
    shift 2
    ;;
  --region)
    REGION="$2"
    shift 2
    ;;
  *)
    echo "Unknown argument: $1"
    exit 1
    ;;
  esac
done

# Ensure we have required values (either from TF or flags)
if [ -z "$TARGET_PROJECT" ] || [ -z "$SILVER_BUCKET" ] || [ -z "$METASTORE_ID" ] || [ -z "$SUBNET" ] || [ -z "$REGION" ]; then
  echo "Usage: $0 [--target-project <id>] [--silver-bucket <name>] [--metastore-id <id>] [--scripts-dir <path>] [--subnet <name>] [--region <region>]"
  exit 1
fi

echo "Submitting Migrated Spark job to Managed Spark Serverless..."
gcloud dataproc batches submit pyspark "$SCRIPTS_DIR/pyspark/05.04-migrated_spark_job.py" \
  --project="$TARGET_PROJECT" \
  --region="$REGION" \
  --deps-bucket="gs://$SILVER_BUCKET" \
  --metastore-service="$METASTORE_ID" \
  --subnet="$SUBNET" \
  --service-account="$DATAPROC_SA" \
  --version=2.2 \
  --properties="\
spark.sql.defaultCatalog=lakehouse,\
spark.sql.catalog.lakehouse=org.apache.iceberg.spark.SparkCatalog,\
spark.sql.catalog.lakehouse.type=rest,\
spark.sql.catalog.lakehouse.uri=https://biglake.googleapis.com/iceberg/v1/restcatalog,\
spark.sql.catalog.lakehouse.warehouse=gs://$SILVER_BUCKET,\
spark.sql.catalog.lakehouse.io-impl=org.apache.iceberg.hadoop.HadoopFileIO,\
spark.sql.catalog.lakehouse.header.x-goog-user-project=$TARGET_PROJECT,\
spark.sql.catalog.lakehouse.rest.auth.type=org.apache.iceberg.gcp.auth.GoogleAuthManager,\
spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions,\
spark.sql.catalog.lakehouse.rest-metrics-reporting-enabled=false,\
spark.sql.catalog.lakehouse.header.X-Iceberg-Access-Delegation=vended-credentials,\
spark.jars.packages=org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.0"

echo "Job submitted."
