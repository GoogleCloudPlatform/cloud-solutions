#!/bin/bash
#
# Copyright 2023 Google LLC
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

## Description: Templated shell script to Run automatically to generate
# standard machine type PKB results in BigQuery.

TARGET_PROJECT_ID="${TARGET_PROJECT_ID:-unknown-project}"
TARGET_OS_TYPE="${TARGET_OS_TYPE:-ubuntu2004}"
TARGET_OS_IMAGE="${TARGET_OS_IMAGE:-projects/ubuntu-os-cloud/global/images/ubuntu-2004-focal-v20220927}"

TARGET_VM_ZONE="${TARGET_VM_ZONE:-us-central1}"
VM_DATA_DISK_SIZE="${VM_DATA_DISK_SIZE:-100}"
VM_DATA_DISK_TYPE="${VM_DATA_DISK_TYPE:-pd-ssd}"

RESULT_BQ_PROJECT="${RESULT_BQ_PROJECT:-${TARGET_PROJECT_ID}}"
RESULT_BQ_DATASET="${RESULT_BQ_DATASET:-prefkit}"
RESULT_BQ_TABLE="${RESULT_BQ_TABLE:-results}"

TEST_VM_MACHINE_TYPES=(
  "e2-standard-2" "e2-standard-4" "e2-standard-8" "e2-standard-16"
  "e2-highmem-2" "e2-highmem-4" "e2-highmem-8" "e2-highmem-16"
  "e2-highcpu-2" "e2-highcpu-4" "e2-highcpu-8" "e2-highcpu-16"
  "n2-standard-2" "n2-standard-4" "n2-standard-8" "n2-standard-16"
  "n2-highmem-2" "n2-highmem-4" "n2-highmem-8" "n2-highmem-16"
  "n2-highcpu-2" "n2-highcpu-4" "n2-highcpu-8" "n2-highcpu-16"
  "n2d-standard-2" "n2d-standard-4" "n2d-standard-8" "n2d-standard-16"
  "n2d-highmem-2" "n2d-highmem-4" "n2d-highmem-8" "n2d-highmem-16"
  "n2d-highcpu-2" "n2d-highcpu-4" "n2d-highcpu-8" "n2d-highcpu-16"
  "t2d-standard-2" "t2d-standard-4" "t2d-standard-8" "t2d-standard-16"
  "t2a-standard-2" "t2a-standard-4" "t2a-standard-8" "t2a-standard-16"
  "n1-standard-2" "n1-standard-4" "n1-standard-8" "n1-standard-16"
  "n1-highmem-2" "n1-highmem-4" "n1-highmem-8" "n1-highmem-16"
  "n1-highcpu-2" "n1-highcpu-4" "n1-highcpu-8" "n1-highcpu-16"
)

TEST_CLOUDSQL_MACHINE_TYPES=(
  "db-custom-2-7680" "db-custom-4-15360" "db-custom-8-30720" "db-custom-16-61440" "db-custom-32-122880"
  "db-custom-2-13312" "db-custom-4-26624" "db-custom-8-53248" "db-custom-16-106496" "db-custom-32-212992"
)

rm -rf "${LOG_BASE}/*-*-.log"

# Handled by basing the image on this pull
# git clone https://github.com/prakhag2/PerfKitBenchmarker

for vm_machine_type in "${TEST_VM_MACHINE_TYPES[@]}"; do

  bash "${DIR}/aerospike.sh"

  bash "${DIR}/cassandra_stress.sh"

  /PerfKitBenchmarker/pkb.py \
    --benchmarks=tomcat_wrk \
    --os_type="${TARGET_OS_TYPE}" \
    --machine_type="${vm_machine_type}" \
    --image="${TARGET_OS_IMAGE}" \
    --data_disk_size="${VM_DATA_DISK_SIZE}" \
    --data_disk_type="${VM_DATA_DISK_TYPE}" \
    --bq_project="${RESULT_BQ_PROJECT}" \
    --bigquery_table="${RESULT_BQ_DATASET}.${RESULT_BQ_TABLE}" \
    --zone="${TARGET_VM_ZONE}" 2> >(tee "${LOG_BASE}/tomcat-${vm_machine_type}.log")

  ./PerfKitBenchmarker/pkb.py \
    --benchmarks=apachebench \
    --os_type="${TARGET_OS_TYPE}" \
    --machine_type="${vm_machine_type}" \
    --image="${TARGET_OS_IMAGE}" \
    --data_disk_size="${VM_DATA_DISK_SIZE}" \
    --data_disk_type="${VM_DATA_DISK_TYPE}" \
    --bq_project="${RESULT_BQ_PROJECT}" \
    --bigquery_table="${RESULT_BQ_DATASET}.${RESULT_BQ_TABLE}" \
    --zone="${TARGET_VM_ZONE}" 2> >(tee "${LOG_BASE}/apachebench-${vm_machine_type}.log")

  sed -i -e "s/\[machine_type\]/$vm_machine_type/g" redis.yml
  ./PerfKitBenchmarker/pkb.py \
    --benchmarks=redis_memtier \
    --memtier_protocol=redis \
    --benchmark_config_file=redis.yml \
    --os_type="${TARGET_OS_TYPE}" \
    --image="${TARGET_OS_IMAGE}" \
    --bq_project="${RESULT_BQ_PROJECT}" \
    --bigquery_table="${RESULT_BQ_DATASET}.${RESULT_BQ_TABLE}" \
    --zone="${TARGET_VM_ZONE}" 2> >(tee "${LOG_BASE}/redis-${vm_machine_type}.log")
  sed -i -e "s/$vm_machine_type/\[machine_type\]/g" redis.yml

  sed -i -e "s/\[machine_type\]/$vm_machine_type/g" k8s-redis.yml
  ./PerfKitBenchmarker/pkb.py \
    --benchmarks=kubernetes_redis_memtier \
    --memtier_protocol=redis \
    --benchmark_config_file=k8s-redis.yml \
    --bq_project="${RESULT_BQ_PROJECT}" \
    --bigquery_table="${RESULT_BQ_DATASET}.${RESULT_BQ_TABLE}" \
    --zone="${TARGET_VM_ZONE}" 2> >(tee "${LOG_BASE}/k8s-redis-${vm_machine_type}.log")
  sed -i -e "s/$vm_machine_type/\[machine_type\]/g" k8s-redis.yml

  sed -i -e "s/\[machine_type\]/$vm_machine_type/g" nginx.yml
  ./PerfKitBenchmarker/pkb.py \
    --benchmarks=nginx \
    --benchmark_config_file=nginx.yml \
    --bq_project="${RESULT_BQ_PROJECT}" \
    --bigquery_table="${RESULT_BQ_DATASET}.${RESULT_BQ_TABLE}" \
    --zone="${TARGET_VM_ZONE}" 2> >(tee "${LOG_BASE}/nginx-${vm_machine_type}.log")
  sed -i -e "s/$vm_machine_type/\[machine_type\]/g" nginx.yml

  sed -i -e "s/\[machine_type\]/$vm_machine_type/g" k8s-nginx.yml
  ./PerfKitBenchmarker/pkb.py \
    --benchmarks=kubernetes_nginx \
    --benchmark_config_file=k8s-nginx.yml \
    --bq_project="${RESULT_BQ_PROJECT}" \
    --bigquery_table="${RESULT_BQ_DATASET}.${RESULT_BQ_TABLE}" \
    --zone="${TARGET_VM_ZONE}" 2> >(tee "${LOG_BASE}/k8s-nginx-${vm_machine_type}.log")
  sed -i -e "s/$vm_machine_type/\[machine_type\]/g" k8s-nginx.yml

  ./PerfKitBenchmarker/pkb.py \
    --benchmarks=mongodb_ycsb \
    --os_type="${TARGET_OS_TYPE}" \
    --machine_type="${vm_machine_type}" \
    --image="${TARGET_OS_IMAGE}" \
    --data_disk_size="${VM_DATA_DISK_SIZE}" \
    --data_disk_type="${VM_DATA_DISK_TYPE}" \
    --bq_project="${RESULT_BQ_PROJECT}" \
    --bigquery_table="${RESULT_BQ_DATASET}.${RESULT_BQ_TABLE}" \
    --zone="${TARGET_VM_ZONE}" 2> >(tee "${LOG_BASE}/mongodb-${vm_machine_type}.log")

  ./PerfKitBenchmarker/pkb.py \
    --benchmarks=coremark \
    --os_type="${TARGET_OS_TYPE}" \
    --machine_type="${vm_machine_type}" \
    --image="${TARGET_OS_IMAGE}" \
    --data_disk_size="${VM_DATA_DISK_SIZE}" \
    --data_disk_type="${VM_DATA_DISK_TYPE}" \
    --bq_project="${RESULT_BQ_PROJECT}" \
    --bigquery_table="${RESULT_BQ_DATASET}.${RESULT_BQ_TABLE}" \
    --zone="${TARGET_VM_ZONE}" 2> >(tee "${LOG_BASE}/coremark-${vm_machine_type}.log")

  ./PerfKitBenchmarker/pkb.py \
    --benchmarks=multichase \
    --os_type="${TARGET_OS_TYPE}" \
    --machine_type="${vm_machine_type}" \
    --image="${TARGET_OS_IMAGE}" \
    --data_disk_size="${VM_DATA_DISK_SIZE}" \
    --data_disk_type="${VM_DATA_DISK_TYPE}" \
    --bq_project="${RESULT_BQ_PROJECT}" \
    --bigquery_table="${RESULT_BQ_DATASET}.${RESULT_BQ_TABLE}" \
    --zone="${TARGET_VM_ZONE}" 2> >(tee "${LOG_BASE}/multichase-${vm_machine_type}.log")

  ./PerfKitBenchmarker/pkb.py \
    --benchmarks=iperf \
    --os_type="${TARGET_OS_TYPE}" \
    --machine_type="${vm_machine_type}" \
    --image="${TARGET_OS_IMAGE}" \
    --data_disk_size="${VM_DATA_DISK_SIZE}" \
    --data_disk_type="${VM_DATA_DISK_TYPE}" \
    --bq_project="${RESULT_BQ_PROJECT}" \
    --bigquery_table="${RESULT_BQ_DATASET}.${RESULT_BQ_TABLE}" \
    --zone="${TARGET_VM_ZONE}" 2> >(tee "${LOG_BASE}/iperf-${vm_machine_type}.log")

  ./PerfKitBenchmarker/pkb.py \
    --benchmarks=fio \
    --os_type="${TARGET_OS_TYPE}" \
    --machine_type="${vm_machine_type}" \
    --image="${TARGET_OS_IMAGE}" \
    --data_disk_size="${VM_DATA_DISK_SIZE}" \
    --data_disk_type="${VM_DATA_DISK_TYPE}" \
    --bq_project="${RESULT_BQ_PROJECT}" \
    --bigquery_table="${RESULT_BQ_DATASET}.${RESULT_BQ_TABLE}" \
    --zone="${TARGET_VM_ZONE}" 2> >(tee "${LOG_BASE}/fio-${vm_machine_type}.log")
done

# CloudSQL benchmarks
for cloudsql_machine_type in "${TEST_CLOUDSQL_MACHINE_TYPES[@]}"; do

  sed -i -e "s/\[machine_type\]/$cloudsql_machine_type/g" sysbench.yml
  ./PerfKitBenchmarker/pkb.py \
    --benchmarks=sysbench \
    --benchmark_config_file=sysbench.yml \
    --bq_project="${RESULT_BQ_PROJECT}" \
    --bigquery_table="${RESULT_BQ_DATASET}.${RESULT_BQ_TABLE}" \
    --zone="${TARGET_VM_ZONE}" 2> >(tee "${LOG_BASE}/sysbench-${cloudsql_machine_type}.log")
  sed -i -e "s/$cloudsql_machine_type/\[machine_type\]/g" sysbench.yml

  sed -i -e "s/\[machine_type\]/$cloudsql_machine_type/g" pgbench.yml
  ./PerfKitBenchmarker/pkb.py \
    --benchmarks=pgbench \
    --benchmark_config_file=pgbench.yml \
    --bq_project="${RESULT_BQ_PROJECT}" \
    --bigquery_table="${RESULT_BQ_DATASET}.${RESULT_BQ_TABLE}" \
    --zone="${TARGET_VM_ZONE}" 2> >(tee "${LOG_BASE}/pgbench-${cloudsql_machine_type}.log")
  sed -i -e "s/$cloudsql_machine_type/\[machine_type\]/g" pgbench.yml
done
