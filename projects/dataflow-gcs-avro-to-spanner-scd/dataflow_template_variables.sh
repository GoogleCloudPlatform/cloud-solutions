#!/bin/bash
# Copyright 2024 Google LLC
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

# VARIABLES FOR THE DATAFLOW TEMPLATE.
# The following variables are required for building the Dataflow Flex template.

## Required variables.

### The Google Cloud project id where the resources will be created and run.
export PROJECT_ID="<my-project>"

### The Google Cloud region where the resources will be created and run.
export REGION="<cloud-region>"

### The Google Cloud Storage bucket where which will be used for creating and
### running Dataflow artifacts.
export BUCKET_NAME="<bucket-name>"

### The name of the Artifacts Registry repository where the Dataflow Flex
### template will be built.
export REPOSITORY_NAME="<repository-name>"

## Required variables, which do not require configuration.

### Name of the image that will be created for the Dataflow Flex template.
export IMAGE_NAME="gcs-avro-to-spanner-scd"

### Google Cloud Storage path where the image metadata will be created.
export DATAFLOW_TEMPLATE_GCS_PATH="gs://${BUCKET_NAME}/${IMAGE_NAME}"

### Artifacts Registry where the Dataflow Flex template will be created.
DATAFLOW_TEMPLATE_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}/${IMAGE_NAME}-$(date +%s):latest"
export DATAFLOW_TEMPLATE_IMAGE

# VARIABLES FOR THE DATAFLOW JOB.
# The following variables are required for running the template as a job.
# For more information on these parameters, check `metadata.json`.

## Required parameters.

### The Dataflow job name that will be used for the next run.
JOB_NAME="${IMAGE_NAME}-$(date +%Y%m%d-%H%M%S-%N)"
export JOB_NAME

### The Cloud Storage file pattern where the Avro files are imported from.
export INPUT_FILE_PATTERN="<inputFilePattern>"

### The instance ID of the Cloud Spanner database.
export SPANNER_INSTANCE_ID="<instanceId>"

### The database ID of the Cloud Spanner database.
export SPANNER_DATABASE_ID="<databaseId>"

### Name of the Cloud Spanner table where to upsert data.
export SPANNER_TABLE_NAME="<tableName>"

## Optional parameters.

### The ID of the Google Cloud project that contains the Cloud Spanner database.
### If not set, the default Google Cloud project is used.
export SPANNER_PROJECT_ID="<spannerProjectId>"

### The request priority for Cloud Spanner calls. Possible values are `HIGH`,
### `MEDIUM`, and `LOW`. The default value is `MEDIUM`.
export SPANNER_PRIORITY="<spannerPriority>"

### How many rows to process on each batch. The default value is 100.
export SPANNER_BATCH_SIZE="<batchSize>"

### Type of SCD which will be applied when writing to Cloud Spanner. Possible
### values are TYPE_1 and TYPE_2. The default value is SCD TYPE_1.
export SCD_TYPE="<scdType>"

### Name of column that will be used to order when there are multiple updates
### for the same primary key within the same file. If not set, and there are
### multiple updates to the same primary keys, the update order may be random.
export SPANNER_ORDER_BY_COLUMN_NAME="<orderByColumnName>"

### Whether to use ASC or DESC when sorting the records by order by column name.
### Possible values are ASC and DESC. Default value: Ascending (ASC).
export SPANNER_SORT_ORDER="<sortOrder>"

## Required parameters when using SCD Type TYPE_2.

### Name of column(s) for the primary key(s). If more than one, enter as CSV
### with no spaces (e.g. column1,column2).
export SPANNER_PRIMARY_KEY_COLUMN_NAMES="<primaryKeyColumnName>"

### Name of column name for the end date (TIMESTAMP).
export SPANNER_END_DATE_COLUMN_NAME="<startDateColumnName>"

## Optional parameters, only used when using SCD TYPE_2.

### Name of column name for the start date (TIMESTAMP).
export SPANNER_START_DATE_COLUMN_NAME="<startDateColumnName>"
