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

"""Provides tasks to perform data pruning preparation."""

from airflow.decorators import task
from airflow.decorators import task_group
from airflow.operators import python as airflow_operators
from airflow.providers.google.cloud.operators import bigquery
from airflow.providers.google.cloud.hooks import bigquery as bigquery_hook
from database_archival.common.models import database
from database_archival.common.utils import bigquery_utils
from database_archival.dag.tasks import data_archiving
from database_archival.dag.utils import task_namer


TASK_GROUP_NAME = 'batch_primary_keys_to_delete'
TASK_NAME_GET_CONFIG = 'get_batch_primary_keys_job_config'
TASK_NAME_BATCH_PRIMARY_KEYS = 'execute_batch_primary_keys_job'
TASK_NAME_GET_BATCH_LIST = 'get_list_of_pending_batches'

VAR_NAME_PRUNE_PROGRESS_TABLE = 'snapshot_progress_table_name'


@task_group(group_id=TASK_GROUP_NAME)
def batch_primary_keys_to_delete(
    *,
    database_table_name: str,
    bigquery_location: str,
    table_primary_key_columns: list[str],
    database_prune_batch_size: int,
) -> None:
    """Queries and batches data that needs to be pruned from the database.

    Args:
        database_table_name: name of the base table. Used for task names.
        bigquery_location: location where BigQuery jobs will be run.
        table_primary_key_columns: list of primary key columns.
        database_prune_batch_size: how many rows to delete at once.
    """

    @task(task_id=TASK_NAME_GET_CONFIG)
    def get_batch_primary_keys_job_config():
        """Creates the job config to batch primary keys to prune."""
        context = airflow_operators.get_current_context()
        dag_run_id = context['run_id']
        dag_date = context['ds_nodash']
        snapshot_table_name = context['ti'].xcom_pull(
            task_ids=task_namer.get_task_name(
                database_table_name=database_table_name,
                task_group_name=data_archiving.TASK_GROUP_NAME,
                task_name=data_archiving.TASK_NAME_GET_CONFIG,
            ),
            key=data_archiving.VAR_NAME_SNAPSHOT_TABLE,
        )

        snapshot_progress_table_name = (
            snapshot_table_name + database.PRUNE_PROGRESS_TABLE_NAME_SUFFIX
        )
        parsed_dag_date = f'PARSE_DATE("%Y%m%d", "{dag_date}")'
        calculated_batch_number = (
            'CAST(CEIL('
            f'ROW_NUMBER() OVER () / {database_prune_batch_size}'
            ') AS INT64)'
        )
        snapshot_fields = [
            database.FIELD_NAME_SNAPSHOT_RUN_ID,
            database.FIELD_NAME_SNAPSHOT_DATE,
            f'FALSE AS {database.FIELD_NAME_PRUNE_STATUS}',
            f'{calculated_batch_number} AS {database.FIELD_NAME_PRUNE_BATCH}',
        ]
        select_fields = table_primary_key_columns + snapshot_fields
        where_conditions = [
            f'{database.FIELD_NAME_SNAPSHOT_DATE} = {parsed_dag_date}',
            f'{database.FIELD_NAME_SNAPSHOT_RUN_ID} = "{dag_run_id}"',
        ]

        context['ti'].xcom_push(
            key=VAR_NAME_PRUNE_PROGRESS_TABLE,
            value=snapshot_progress_table_name,
        )
        return {
            'query': {
                'query': (
                    f"SELECT {', '.join(select_fields) } "
                    f'FROM `{snapshot_table_name}` '
                    f"WHERE {' AND '.join(where_conditions)}"
                ),
                'use_legacy_sql': False,
                'destination_table': bigquery_utils.split_table_name(
                    snapshot_progress_table_name
                ),
                'create_disposition': 'CREATE_IF_NEEDED',
                'write_disposition': 'WRITE_APPEND',
            },
        }

    get_primary_keys_job = bigquery.BigQueryInsertJobOperator(
        task_id=TASK_NAME_BATCH_PRIMARY_KEYS,
        configuration=get_batch_primary_keys_job_config(),
        location=bigquery_location,
    )

    @task(task_id=TASK_NAME_GET_BATCH_LIST)
    def get_list_of_pending_batches():
        """Get the list of batches not processed yet from the progress table."""
        context = airflow_operators.get_current_context()
        dag_run_id = context['run_id']
        dag_date = context['ds_nodash']
        snapshot_progress_table_name = context['ti'].xcom_pull(
            task_ids=task_namer.get_task_name(
                database_table_name=database_table_name,
                task_group_name=TASK_GROUP_NAME,
                task_name=TASK_NAME_GET_CONFIG,
            ),
            key=VAR_NAME_PRUNE_PROGRESS_TABLE,
        )

        parsed_dag_date = f'PARSE_DATE("%Y%m%d", "{dag_date}")'
        where_conditions = [
            f'NOT {database.FIELD_NAME_PRUNE_STATUS}',  # is False
            f'{database.FIELD_NAME_SNAPSHOT_RUN_ID} = "{dag_run_id}"',
            f'{database.FIELD_NAME_SNAPSHOT_DATE} = {parsed_dag_date}',
        ]

        bq_hook = bigquery_hook.BigQueryHook(use_legacy_sql=False)
        bq_conn = bq_hook.get_conn()
        bq_cursor = bq_conn.cursor()
        bq_cursor.execute(
            f'SELECT DISTINCT {database.FIELD_NAME_PRUNE_BATCH} '
            f'FROM {snapshot_progress_table_name} '
            f"WHERE {' AND '.join(where_conditions)}"
        )
        rows = bq_cursor.fetchall()

        prune_batches = [row[0] for row in rows if row] if rows else []
        return prune_batches

    # pylint: disable-next=pointless-statement, expression-not-assigned
    get_primary_keys_job >> get_list_of_pending_batches()
