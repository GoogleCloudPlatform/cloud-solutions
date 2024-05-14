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

set -u

CURRENT_DIR="$(pwd)"
SCRIPT="$(readlink -f "${0}")"
SCRIPT_DIR="$(dirname "${SCRIPT}")"

cd "${SCRIPT_DIR}/terraform" || exit 1

terraform init && terraform apply

BQ_PROJECT_ID=$(terraform output -raw bq-project-id)
export BQ_PROJECT_ID

BQ_DATASET=$(terraform output -raw bq-dataset)
export BQ_DATASET

SPANNER_PROJECT_ID=$(terraform output -raw spanner-project-id)
export SPANNER_PROJECT_ID

SPANNER_DATABASE=$(terraform output -raw spanner-database)
export SPANNER_DATABASE

SPANNER_INSTANCE=$(terraform output -raw spanner-instance)
export SPANNER_INSTANCE

ORDERS_CHANGE_STREAM=$(terraform output -raw orders_change_stream)
export ORDERS_CHANGE_STREAM

DATAFLOW_TEMP_BUCKET=gs://$(terraform output -raw dataflow-temp-bucket)
export DATAFLOW_TEMP_BUCKET

DATAFLOW_SA=$(terraform output -raw dataflow-sa)
export DATAFLOW_SA

DATAFLOW_PROJECT_ID=$(terraform output -raw dataflow-project-id)
export DATAFLOW_PROJECT_ID

REGION=$(terraform output -raw region)
export REGION

cd "${CURRENT_DIR}" || exit 1
