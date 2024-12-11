#  Copyright 2024 Google LLC
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""Provides access to BigQuery to get primary keys to prune."""

from google.cloud import bigquery
from database_archival.common.utils import bigquery_utils
from database_archival.common.utils import config_validator
from database_archival.common.models import database
from typing import Iterable


def get_primary_keys_to_prune_from_bigquery(
    *,
    bigquery_location: str,
    snapshot_progress_table_name: str,
    table_primary_key_columns: Iterable[str],
    snapshot_run_id: str,
    snapshot_date: str,
    snapshot_batch: int,
) -> database.PrimaryKeyFilters:
    """Queries the primary keys that must be deleted from the database.

    Args:
        bigquery_location: location where BigQuery job will be run.
        snapshot_progress_table_name: BigQuery table name where primary keys to
            be pruned are stored.
        table_primary_key_columns: list of primary key field names.
        snapshot_run_id: DAG run id where snapshot was created.
        snapshot_date: date of the snapshot (YYYYMMDD).
        snapshot_batch: numbe of the batch to delete.

    Yields:
        BigQuery row with the primary keys. Each row is in dict format.
    """
    config_validator.assert_is_valid_string(
        bigquery_location, 'bigquery_location'
    )
    config_validator.assert_is_valid_string(
        snapshot_progress_table_name, 'snapshot_progress_table_name'
    )
    config_validator.assert_is_valid_list(
        table_primary_key_columns, 'table_primary_key_columns'
    )
    for field in table_primary_key_columns:
        config_validator.assert_is_valid_string(
            field, 'Element in table_primary_key_columns'
        )
    config_validator.assert_is_valid_string(snapshot_run_id, 'snapshot_run_id')
    config_validator.assert_is_valid_string(snapshot_date, 'snapshot_date')
    config_validator.assert_is_positive_integer(
        snapshot_batch, 'snapshot_batch'
    )

    client = bigquery.Client()
    parsed_snapshot_date = f'PARSE_DATE("%Y%m%d", "{snapshot_date}")'
    where_conditions = [
        f'NOT {database.FIELD_NAME_PRUNE_STATUS}',
        f'{database.FIELD_NAME_SNAPSHOT_RUN_ID} = "{snapshot_run_id}"',
        f'{database.FIELD_NAME_PRUNE_BATCH} = {snapshot_batch}',
        f'{database.FIELD_NAME_SNAPSHOT_DATE} = {parsed_snapshot_date}',
    ]
    # TODO: reduce risk of SQL injection.
    table_parts = bigquery_utils.split_table_name(snapshot_progress_table_name)
    query_job = client.query(
        query=(
            f"SELECT {', '.join(table_primary_key_columns)} "
            f'FROM `{snapshot_progress_table_name}` '
            f"WHERE {' AND '.join(where_conditions)}"
        ),
        project=table_parts['project_id'],
        location=bigquery_location,
    )
    query_job.result()  # Waits for job to complete.
    temp_results_table = client.get_table(query_job.destination)
    rows = client.list_rows(temp_results_table)

    for row in rows:
        yield {
            field_name: field_value for field_name, field_value in row.items()
        }
