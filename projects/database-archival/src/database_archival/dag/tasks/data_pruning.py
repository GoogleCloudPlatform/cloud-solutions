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

"""Provides tasks to perform data pruning on the database."""

import enum
import time
from airflow.decorators import task
from airflow.decorators import task_group
from airflow.models import expandinput
from airflow.operators import python as airflow_operators
from airflow.providers.google.cloud.operators import bigquery
from airflow.providers.google.common.utils import id_token_credentials
from google.auth.transport import requests
from database_archival.common.models import database
from database_archival.dag.tasks import data_pruning_preparation
from database_archival.dag.utils import task_namer
from database_archival.dag import config
from typing import Iterable, Optional


TASK_GROUP_NAME = 'delete_data_from_database'
TASK_NAME_GET_BATCHES = 'get_batches_for_loop'

TASK_GROUP_NAME_DELETE_BATCH_AND_UPDATE_PROGRESS = (
    'delete_and_update_data_batch'
)
TASK_NAME_DELETE_BATCH = 'delete_data_from_database'

TASK_GROUP_UPDATE_PROGRESS_BATCH = 'update_pruned_rows_status'
TASK_NAME_GET_CONFIG_FOR_STATUS_UPDATE = 'get_update_prune_status_job_config'
TASK_NAME_UPDATE_STATUS = 'update_pruned_rows_status_job'


class _TaskPriority(enum.Enum):
    """Defines Airflow Task priorities.

    The higher, the higher the priority. The actual values are arbitrary, the
    relative value (which is higher) is all it matters.
    """

    DEFAULT = 1
    LOW = 10
    MEDIUM = 100
    HIGH = 1_000


@task_group(group_id=TASK_GROUP_NAME)
def delete_data_from_database(
    *,
    bigquery_location: str,
    database_type: database.DatabaseType,
    database_instance_name: Optional[str] = None,
    database_host: Optional[str] = None,
    database_name: str,
    database_table_name: str,
    table_primary_key_columns: Iterable[str],
    database_username: str,
    database_password: Optional[str] = None,
    database_password_secret: Optional[str] = None,
):
    """Processes batches and requests deletion of data from the database.

    Args:
        bigquery_location: location where BigQuery jobs will be run.
        database_type: type of database where the data is hosted.
        database_instance_name: intance name of the database.
            AlloyDB Format:
                projects/<project_id>/locations/<region_id>/
                clusters/<cluster_id>/instances/<instance_id>
            Cloud SQL Format:
                <project_id>:<region_id>:<instance_name>
        database_host: hostname or IP where the database is located.
        database_name: name of the database where the table is located.
        database_table_name: name of the table that will be pruned. Used also
            for identifying tasks.
        table_primary_key_columns: list of primary keys for the table.
        database_username: username to access the database.
        database_password: password for the username to access the database.
        database_password_secret: password for the username to access the
            database, stored in Secret Manager. Format:
            "projects/<projectId>/secrets/<secretId>/versions/<versionId>".
    """

    @task(task_id=TASK_NAME_GET_BATCHES)
    def get_batches_for_loop():
        context = airflow_operators.get_current_context()
        batches = context['ti'].xcom_pull(
            task_ids=task_namer.get_task_name(
                database_table_name=database_table_name,
                task_group_name=data_pruning_preparation.TASK_GROUP_NAME,
                task_name=data_pruning_preparation.TASK_NAME_GET_BATCH_LIST,
            ),
            key='return_value',
        )
        return batches

    delete_and_update_data_batch.partial(
        database_table_name=database_table_name,
        bigquery_location=bigquery_location,
        database_type=database_type,
        database_instance_name=database_instance_name,
        database_host=database_host,
        database_name=database_name,
        database_username=database_username,
        database_password=database_password,
        database_password_secret=database_password_secret,
        table_primary_key_columns=table_primary_key_columns,
    ).expand(batch_number_expand=get_batches_for_loop())


@task_group(group_id=TASK_GROUP_NAME_DELETE_BATCH_AND_UPDATE_PROGRESS)
def delete_and_update_data_batch(
    *,
    bigquery_location: str,
    database_type: database.DatabaseType,
    database_instance_name: Optional[str] = None,
    database_host: Optional[str] = None,
    database_name: str,
    database_table_name: str,
    table_primary_key_columns: Iterable[str],
    database_username: str,
    database_password: Optional[str] = None,
    database_password_secret: Optional[str] = None,
    batch_number_expand: expandinput.MappedArgument,
):
    """Requests to deletes a batch of data from database and updates status.

    Args:
        bigquery_location: location where BigQuery jobs will be run.
        database_type: type of database where the data is hosted.
        database_instance_name: intance name of the database.
            AlloyDB Format:
                projects/<project_id>/locations/<region_id>/
                clusters/<cluster_id>/instances/<instance_id>
            Cloud SQL Format:
                <project_id>:<region_id>:<instance_name>
        database_host: hostname or IP where the database is located.
        database_name: name of the database where the table is located.
        database_table_name: name of the table that will be pruned. Used also
            for identifying tasks.
        table_primary_key_columns: list of primary keys for the table.
        database_username: username to access the database.
        database_password: password for the username to access the database.
        database_password_secret: password for the username to access the
            database, stored in Secrets Manager. Format:
            "projects/<projectId>/secrets/<secretId>/versions/<versionId>".
        batch_number_expand: number of the batch to delete.
    """

    @task(
        task_id=TASK_NAME_DELETE_BATCH,
        # Limit the pruning tasks to run only one batch at a time per table to
        # avoid overloading the database with delete requests in parallel for
        # the same table.
        max_active_tis_per_dagrun=1,
        pre_execute=time.sleep(config.TIME_BETWEEN_DELETE_BATCHES_IN_SECONDS),
    )
    def call_cloud_function_to_prune_data(batch_number):
        """Calls Cloud Function to request deleting batch from the database.

        Args:
            batch_number: batch number that will be pruned.
        """
        context = airflow_operators.get_current_context()
        dag_run_id = context['run_id']
        dag_date = context['ds_nodash']
        snapshot_progress_table_name = context['ti'].xcom_pull(
            task_ids=task_namer.get_task_name(
                database_table_name=database_table_name,
                task_group_name=data_pruning_preparation.TASK_GROUP_NAME,
                task_name=data_pruning_preparation.TASK_NAME_GET_CONFIG,
            ),
            key=data_pruning_preparation.VAR_NAME_PRUNE_PROGRESS_TABLE,
        )

        credentials = id_token_credentials.get_default_id_token_credentials(
            config.CLOUD_FUNCTION_URL_DATA_DELETION
        )
        response = requests.AuthorizedSession(credentials).post(
            url=config.CLOUD_FUNCTION_URL_DATA_DELETION,
            json={
                'bigquery_location': bigquery_location,
                'snapshot_progress_table_name': snapshot_progress_table_name,
                'snapshot_date': dag_date,
                'snapshot_run_id': dag_run_id,
                'snapshot_batch': batch_number,
                'database_type': database_type.value,  # enum to string value.
                'database_instance_name': database_instance_name,
                'database_host': database_host,
                'database_name': database_name,
                'database_username': database_username,
                'database_password': database_password,
                'database_password_secret': database_password_secret,
                'database_table_name': database_table_name,
                'table_primary_key_columns': table_primary_key_columns,
            },
            timeout=config.DATABASE_TIMEOUT,
        )
        if response.status_code != 200:
            raise RuntimeError(
                'Cloud Function call to prune data failed with status code '
                f'{response.status_code}. Response text: {response.text}. '
                'Check Cloud Function logs for more details.'
            )

        return response.json()

    update_batch_status_in_bigquery = update_pruned_rows_status(
        database_table_name=database_table_name,
        bigquery_location=bigquery_location,
        batch_number_expand=batch_number_expand,
    )

    # pylint: disable-next=pointless-statement, expression-not-assigned
    (
        call_cloud_function_to_prune_data(batch_number=batch_number_expand)
        >> update_batch_status_in_bigquery
    )


@task_group(group_id=TASK_GROUP_UPDATE_PROGRESS_BATCH)
def update_pruned_rows_status(
    *,
    database_table_name: str,
    bigquery_location: str,
    batch_number_expand: expandinput.MappedArgument,
):
    """Updates the batch pruning status in BigQuery.

    Args:
        database_table_name: name of the table that was pruned. Used for
            identifying tasks.
        bigquery_location: location where BigQuery jobs will be run.
        batch_number: number of the batch that was pruned.
    """

    @task(
        task_id=TASK_NAME_GET_CONFIG_FOR_STATUS_UPDATE,
        priority_weight=_TaskPriority.MEDIUM.value,  # Prioritize over delete.
    )
    def get_update_prune_status_job_config(batch_number: int):
        """Creates the job config to update pruned rows status.

        Args:
            batch_number: batch number for which to create job config.
        """
        context = airflow_operators.get_current_context()
        dag_date = context['ds_nodash']
        dag_run_id = context['run_id']
        snapshot_progress_table_name = context['ti'].xcom_pull(
            task_ids=task_namer.get_task_name(
                database_table_name=database_table_name,
                task_group_name=data_pruning_preparation.TASK_GROUP_NAME,
                task_name=data_pruning_preparation.TASK_NAME_GET_CONFIG,
            ),
            key=data_pruning_preparation.VAR_NAME_PRUNE_PROGRESS_TABLE,
        )

        set_fields = [
            f'{database.FIELD_NAME_PRUNE_STATUS} = TRUE',
        ]
        parsed_dag_date = f'PARSE_DATE("%Y%m%d", "{dag_date}")'
        condition_fields = [
            f'{database.FIELD_NAME_SNAPSHOT_RUN_ID} = "{dag_run_id}"',
            f'{database.FIELD_NAME_SNAPSHOT_DATE} = {parsed_dag_date}',
            f'{database.FIELD_NAME_PRUNE_BATCH} = {batch_number}',
        ]
        return {
            'query': {
                'query': (
                    f'UPDATE {snapshot_progress_table_name} '
                    f"SET {', '.join(set_fields)} "
                    f"WHERE {' AND '.join(condition_fields)}"
                ),
                'use_legacy_sql': False,
            },
        }

    update_pruned_rows_status_job = bigquery.BigQueryInsertJobOperator(
        task_id=TASK_NAME_UPDATE_STATUS,
        priority_weight=_TaskPriority.HIGH.value,  # Prioritize over config.
        configuration=get_update_prune_status_job_config(
            batch_number=batch_number_expand,
        ),
        location=bigquery_location,
    )

    # pylint: disable-next=pointless-statement, expression-not-assigned
    update_pruned_rows_status_job
