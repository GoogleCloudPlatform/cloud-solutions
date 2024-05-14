#!/usr/bin/env bash
#
# Copyright 2024 Google LLC
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
#

set -e
set -u

JOB_NAME="spanner-to-bigquery-cdc-ingestion"

# EXPERIMENTS=enable_recommendations,enable_google_cloud_profiler,enable_google_cloud_heap_sampling
EXPERIMENTS=enable_recommendations,use_runner_v2

set -x
./gradlew run --args="--jobName=${JOB_NAME} \
  --region=${REGION} \
  --maxNumWorkers=2 \
  --runner=DataflowRunner \
  --spannerProjectId=${SPANNER_PROJECT_ID} \
  --spannerInstanceId=${SPANNER_INSTANCE} \
  --spannerDatabaseId=${SPANNER_DATABASE} \
  --spannerOrdersStreamId=${ORDERS_CHANGE_STREAM} \
  --bigQueryProjectId=${BQ_PROJECT_ID} \
  --bigQueryDataset=${BQ_DATASET} \
  --experiments=${EXPERIMENTS} \
  --enableStreamingEngine \
  --serviceAccount=${DATAFLOW_SA} \
  --project='${DATAFLOW_PROJECT_ID}' \
  --tempLocation=${DATAFLOW_TEMP_BUCKET}/temp \
  --diskSizeGb=30"
