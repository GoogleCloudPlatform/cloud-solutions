# Copyright 2023 Google LLC
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

"""Functions for interacting with BigQuery."""

import asyncio
import logging
import multiprocessing
import time
import typing

from google.cloud import bigquery
from google.cloud import storage

from state import ScriptState

logger = logging.getLogger(__name__)


def truncate_table(target_table: bigquery.Table):
    """Truncate a table."""
    logger.info("Truncating table %s", target_table)
    query = f"TRUNCATE TABLE {target_table}"
    query_job = ScriptState.bq_client().query(query)
    return query_job


def delete_partition_worker(
    queue: multiprocessing.Queue, worker_name: str, bucket_name: str
):
    """Async worker function to poll for partition info and Delete it."""
    count = 0
    gcs_client = storage.Client()
    bucket = gcs_client.get_bucket(bucket_name)

    while not queue.empty():
        blob_name = queue.get()  # type: str
        if blob_name is None:
            continue
        blob = bucket.get_blob(blob_name)
        blob.delete()
        count += 1
    logger.info("%s deleted %s blobs", worker_name, count)


def logging_callback(partition: str, short_table_name: str):
    def future_log(_: asyncio.Future):
        logger.info(
            "extracted partition %s from table %s", partition, short_table_name
        )

    return future_log


def export_partitioned_table(table_name: str, bucket_name: str):
    """Export a partitioned table to GCS."""
    table = ScriptState.bq_client().get_table(table_name)
    short_table_name = table.table_id
    partition_field = table.time_partitioning.field.replace("_at", "_date")
    partitions = ScriptState.bq_client().list_partitions(table)
    all_jobs = []
    bucket = ScriptState.gcs_client().get_bucket(bucket_name)
    logger.info(
        "Cleaning path gs://%s/data/%s and " "cleaning path gs://%s/backup/%s",
        bucket_name,
        short_table_name,
        bucket_name,
        short_table_name,
    )

    delete_queue = multiprocessing.Queue()

    blobs = list(bucket.list_blobs(prefix=f"data/{short_table_name}")) + list(
        bucket.list_blobs(prefix=f"backup/{short_table_name}")
    )
    logger.info("Found %s blobs to delete", len(blobs))
    if blobs:
        for b in blobs:
            delete_queue.put(b.name)
        workers = []
        for i in range(ScriptState.processes()):
            p = multiprocessing.Process(
                target=delete_partition_worker,
                args=(delete_queue, f"worker-{i}", bucket_name),
            )
            workers.append(p)
            p.start()
        for p in workers:
            p.join()

    # No need for concurrency here - this is mostly handled by bq
    for partition in partitions:
        target_partition = f"{partition[:4]}-{partition[4:6]}-{partition[6:]}"

        dest_path = [
            f"gs://{bucket_name}/data/{short_table_name}/{partition_field}="
            f"{target_partition}/*.parquet",
            f"gs://{bucket_name}/backup/{short_table_name}/{partition_field}="
            f"{target_partition}/*.parquet",
        ]
        extract_job = ScriptState.bq_client().extract_table(
            f"{table_name}${partition}",
            dest_path,
            job_id_prefix=f"extract-table-{short_table_name}-" f"{partition}",
            location="US",
            job_config=bigquery.ExtractJobConfig(
                destination_format="PARQUET",
            ),
        )
        extract_job.add_done_callback(
            logging_callback(partition, short_table_name)
        )
        all_jobs.append(extract_job)
    logger.info("Waiting for all jobs to finish")
    while not all(map(lambda job: job.done(), all_jobs)):
        time.sleep(1)
    error_jobs = list(
        filter(lambda job: job.error_result is not None, all_jobs)
    )
    if any(error_jobs):
        logger.info("One or more jobs have failed. Here's one of them:")
        logger.info(error_jobs[0].error_result)
        raise RuntimeError(error_jobs[0].job_result["message"])
    logger.info(
        "Finished extraction of table %s to partition destinations", table_name
    )
    return f"gs://{bucket_name}/data/{short_table_name}/"


def extract_table(table_name: str, bucket_name: str):
    """Extract a table to GCS."""
    table = ScriptState.bq_client().get_table(table_name)
    short_table_name = table.table_id
    dest_path = [
        f"gs://{bucket_name}/data/{short_table_name}/*.parquet",
        f"gs://{bucket_name}/backup/{short_table_name}/*.parquet",
    ]
    bucket = ScriptState.gcs_client().get_bucket(bucket_name)
    for blob in bucket.list_blobs(prefix=f"data/{short_table_name}"):
        blob.delete()
    for blob in bucket.list_blobs(prefix=f"backup/{short_table_name}"):
        blob.delete()
    logger.info("Extracting of table %s to %s", table_name, dest_path[0])
    job = ScriptState.bq_client().extract_table(
        table,
        dest_path,
        job_id_prefix=f"extract-table-{short_table_name}",
        location="US",
        job_config=bigquery.ExtractJobConfig(
            destination_format="PARQUET",
        ),
    )
    while not job.done():
        time.sleep(1)
    if job.error_result is not None:
        logger.info("Mounting partitioned table failed. %s", job.error_result)
        raise RuntimeError(job.error_result["message"])
    logger.info(
        "Finished extraction of table %s to %s", table_name, dest_path[0]
    )
    return dest_path[0]


def mount_partitioned_table(
    table_name: str,
    extracted_path: str,
    partition_col: str,
    table_cols: [str],
    connection_location: str,
    connection_id: str,
):
    """Mount a partitioned table to BigQuery."""
    full_table_name = (
        f"{ScriptState.dataset().project}"
        f".{ScriptState.dataset().dataset_id}.{table_name}"
    )
    query = f"""
    CREATE OR REPLACE EXTERNAL TABLE `{full_table_name}`
    (
    {", ".join(table_cols)}
    )
    WITH PARTITION COLUMNS
    WITH CONNECTION `{connection_location}.{connection_id}`
    OPTIONS (
    format = 'PARQUET',
    uris = ['{extracted_path}{partition_col}=*'],
    hive_partition_uri_prefix = '{extracted_path}',
    require_hive_partition_filter = false);
    """
    job = ScriptState.bq_client().query(
        query, job_id_prefix=f"mount-partition-table-" f"{table_name}"
    )
    while not job.done():
        time.sleep(1)
    if job.error_result is not None:
        logger.info("Mounting partitioned table failed. %s", job.error_result)
        raise RuntimeError(job.error_result["message"])
    logger.info("Mounted partitioned table %s", table_name)
    return ScriptState.bq_client().get_table(
        f"{ScriptState.dataset().project}."
        f"{ScriptState.dataset().dataset_id}.{table_name}"
    )


def copy_table(
    full_source_table_name: str, partitioned: typing.Optional[str] = None
) -> bigquery.Table:
    """Copy a table to BigQuery."""

    source_table = ScriptState.bq_client().get_table(full_source_table_name)
    cols = [
        f"CAST({c.name} AS DATETIME) AS {c.name}"
        if c.field_type == "TIMESTAMP"
        else c.name
        for c in source_table.schema
    ]
    target_table_short_name = source_table.table_id
    ref = bigquery.TableReference(
        ScriptState.dataset().reference, target_table_short_name
    )
    partitioned = (
        "" if partitioned is None else (f"PARTITION BY DATE(" f"{partitioned})")
    )
    query = f"""CREATE TABLE
    `{ScriptState.dataset().project}.{ScriptState.dataset().dataset_id}.{
  target_table_short_name}`
    {partitioned}
    AS SELECT {",".join(cols)} FROM {source_table}"""
    job = ScriptState.bq_client().query(query)
    while not job.done():
        time.sleep(1)
    if job.error_result is not None:
        logger.info("Copying table failed. %s", job.error_result)
        raise RuntimeError(job.error_result["message"])
    logger.info("Created a copy of %s", target_table_short_name)
    return ScriptState.bq_client().get_table(ref)


def mount_table(
    table_name: str,
    extracted_path: str,
    connection_location: str,
    connection_id: str,
):
    """Mount a table to BigQuery."""

    query = f"""
    CREATE OR REPLACE EXTERNAL TABLE `{ScriptState.dataset().project}.{
  ScriptState.dataset().dataset_id}.{table_name}`
    WITH CONNECTION `{connection_location}.{connection_id}`
    OPTIONS (
    format = 'PARQUET',
    uris = ['{extracted_path}']);
    """
    job = ScriptState.bq_client().query(query)
    while not job.done():
        time.sleep(1)
    if job.error_result is not None:
        logger.info("Mounting table failed. %s", job.error_result)
        raise RuntimeError(job.error_result["message"])
    logger.info("Mounted table %s", table_name)
    return ScriptState.bq_client().get_table(
        f"{ScriptState.dataset().project}."
        f"{ScriptState.dataset().dataset_id}."
        f"{table_name}"
    )


def handle_users():
    copy_table("bigquery-public-data.thelook_ecommerce.users")


def handle_products():
    copy_table("bigquery-public-data.thelook_ecommerce.products")
    extract_table("ecommerce.products", ScriptState.tf_state().staging_bucket)
    ScriptState.bq_client().delete_table("ecommerce.products")


def handle_orders():
    copy_table(
        "bigquery-public-data.thelook_ecommerce.orders",
        partitioned="created_at",
    )


def handle_order_items():
    copy_table("bigquery-public-data.thelook_ecommerce.order_items")
    extracted_path = extract_table(
        "ecommerce.order_items", ScriptState.tf_state().warehouse_bucket
    )
    ScriptState.bq_client().delete_table("ecommerce.order_items")
    mount_table(
        "order_items",
        extracted_path,
        ScriptState.tf_state().bq_connection_location,
        ScriptState.tf_state().bq_connection_id,
    )


def handle_events():
    events_table = copy_table(
        "bigquery-public-data.thelook_ecommerce.events",
        partitioned="created_at",
    )  # type: bigquery.Table
    extracted_path = export_partitioned_table(
        str(events_table), ScriptState.tf_state().warehouse_bucket
    )
    table_cols = [f"{c.name} {c.field_type}" for c in events_table.schema]
    ScriptState.bq_client().delete_table(events_table)
    mount_partitioned_table(
        "events",
        extracted_path,
        "created_date",
        table_cols,
        ScriptState.tf_state().bq_connection_location,
        ScriptState.tf_state().bq_connection_id,
    )


def handle_distribution_center():
    source_table = "bigquery-public-data.thelook_ecommerce.distribution_centers"
    copy_table(source_table)
    extract_table(
        "ecommerce.distribution_centers", ScriptState.tf_state().staging_bucket
    )
    ScriptState.bq_client().delete_table("ecommerce.distribution_centers")


def handle_inventory_items():
    copy_table("bigquery-public-data.thelook_ecommerce.inventory_items")
