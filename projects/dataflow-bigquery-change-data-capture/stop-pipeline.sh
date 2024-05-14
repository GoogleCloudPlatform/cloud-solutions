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

JOB_NAME_PATTERN="spanner-to-bigquery-cdc-ingestion"

JOB_IDS=$(gcloud dataflow jobs list --region "$REGION" --filter="NAME:${JOB_NAME_PATTERN} AND STATE:Running" --format="get(JOB_ID)")

IFS=$'\n'
# shellcheck disable=SC2206
id_array=($JOB_IDS)
for ((i = 0; i < ${#id_array[@]}; i++)); do
  gcloud dataflow jobs drain --region "$REGION" "${id_array[$i]}"
done
