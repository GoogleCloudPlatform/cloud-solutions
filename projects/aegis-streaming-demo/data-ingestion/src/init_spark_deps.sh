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

# Dataproc Cluster Initialization Action: Pre-bakes Spark SQL Kafka 0-10 and
# Google Cloud Managed Kafka OAuth Login Handler JARs into /usr/lib/spark/jars/
# so PySpark Structured Streaming jobs submitted using JobControllerClient start
# in ~5-10 seconds without runtime Maven downloads.

set -o errexit
set -o nounset
set -o pipefail

SPARK_JARS_DIR="/usr/lib/spark/jars"
MAVEN_BASE="https://repo1.maven.org/maven2"

mkdir -p "${SPARK_JARS_DIR}"

JAR_SPECS=(
  "${MAVEN_BASE}/com/google/auth/google-auth-library-credentials/1.19.0/google-auth-library-credentials-1.19.0.jar|095984b0594888a47f311b3c9dcf6da9ed86feeea8f78140c55e14c27b0593e5"
  "${MAVEN_BASE}/com/google/auth/google-auth-library-oauth2-http/1.19.0/google-auth-library-oauth2-http-1.19.0.jar|01bdf5c5cd85e10b794e401775d9909b56a38ffce313fbd39510a5d87ed56f58"
  "${MAVEN_BASE}/com/google/cloud/hosted/kafka/managed-kafka-auth-login-handler/1.0.5/managed-kafka-auth-login-handler-1.0.5.jar|feaaca7e9eac7593d9ad89d45311046d6ca3a3640823b647001ba76c795edef0"
  "${MAVEN_BASE}/com/google/code/gson/gson/2.10.1/gson-2.10.1.jar|4241c14a7727c34feea6507ec801318a3d4a90f070e4525681079fb94ee4c593"
  "${MAVEN_BASE}/com/google/http-client/google-http-client-apache-v2/1.39.2/google-http-client-apache-v2-1.39.2.jar|52d39209f65abf6f577e1cab466adb99f12d1cd2ba4e98d86e501f75d7f850cf"
  "${MAVEN_BASE}/com/google/http-client/google-http-client-gson/1.43.3/google-http-client-gson-1.43.3.jar|e31a4edcb9c83954a2587e14fa2f3f8f4aad56152381b3321a3bd0bcae03fa26"
  "${MAVEN_BASE}/com/google/http-client/google-http-client/1.43.3/google-http-client-1.43.3.jar|60aca7428c5a1ff3655b70541a98ff3d70dded48ac1324dae1af39f1b61914af"
  "${MAVEN_BASE}/com/google/oauth-client/google-oauth-client/1.31.5/google-oauth-client-1.31.5.jar|f827130fb11f8d4be9cd4a3a34167fe1b83071b6096d26a51a9f79494393ea8d"
  "${MAVEN_BASE}/io/grpc/grpc-context/1.27.2/grpc-context-1.27.2.jar|bcbf9055dff453fd6508bd7cca2a0aa2d5f059a9c94beed1f5fda1dc015607b8"
  "${MAVEN_BASE}/io/opencensus/opencensus-api/0.31.1/opencensus-api-0.31.1.jar|f1474d47f4b6b001558ad27b952e35eda5cc7146788877fc52938c6eba24b382"
  "${MAVEN_BASE}/io/opencensus/opencensus-contrib-http-util/0.31.1/opencensus-contrib-http-util-0.31.1.jar|3ea995b55a4068be22989b70cc29a4d788c2d328d1d50613a7a9afd13fdd2d0a"
  "${MAVEN_BASE}/org/apache/commons/commons-pool2/2.11.1/commons-pool2-2.11.1.jar|ea0505ee7515e58b1ac0e686e4d1a5d9f7d808e251a61bc371aa0595b9963f83"
  "${MAVEN_BASE}/org/apache/kafka/kafka-clients/3.5.0/kafka-clients-3.5.0.jar|75efe70fd99b4120cb00c683fbdea8d542fd69096477a0105bf4de768479c7fa"
  "${MAVEN_BASE}/org/apache/spark/spark-sql-kafka-0-10_2.12/3.5.3/spark-sql-kafka-0-10_2.12-3.5.3.jar|195a2bb70a614d75cf81530ead790b20d9c1e7d4ae5b424048d0e0c41c14dc9c"
  "${MAVEN_BASE}/org/apache/spark/spark-token-provider-kafka-0-10_2.12/3.5.3/spark-token-provider-kafka-0-10_2.12-3.5.3.jar|bcdeb0839671c9032d07be21d19b02faaa556369a7b3ab1a568ce34071b6ce53"
)

for spec in "${JAR_SPECS[@]}"; do
  url="${spec%%|*}"
  expected_sha256="${spec##*|}"
  jar_name="$(basename "${url}")"
  target_path="${SPARK_JARS_DIR}/${jar_name}"
  tmp_path="${target_path}.tmp"
  if [[ ! -f "${target_path}" ]]; then
    echo "Downloading ${jar_name} to ${SPARK_JARS_DIR}..."
    curl -fsSL --retry 3 --retry-delay 2 -o "${tmp_path}" "${url}"
    echo "${expected_sha256}  ${tmp_path}" | sha256sum -c -
    chmod 0644 "${tmp_path}"
    mv "${tmp_path}" "${target_path}"
  fi
done

echo "All Spark Kafka and Managed Kafka OAuth JARs installed in ${SPARK_JARS_DIR}."
