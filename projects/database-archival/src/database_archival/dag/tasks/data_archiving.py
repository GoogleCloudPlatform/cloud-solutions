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

"""Provides tasks to perform data archival (copy) within BigQuery."""

import datetime
from airflow.decorators import task
from airflow.decorators import task_group
from airflow.operators import python as airflow_operators
from airflow.providers.google.cloud.operators import bigquery
from database_archival.common.utils import bigquery_utils
from database_archival.common.models import database
from typing import Mapping, Optional

TASK_GROUP_NAME = 'copy_data_to_archive'
TASK_NAME_GET_CONFIG = 'get_copy_data_job_configuration'
TASK_NAME_COPY_DATA = 'copy_data_to_archive'

VAR_NAME_SNAPSHOT_TABLE = 'snapshot_table_name'

_SUPPORTED_DATE_FORMATS = ('DATE', 'DATETIME', 'TIMESTAMP')


def _create_copy_sql_condition(
    execution_date: str,
    database_prune_data: bool,
    database_days_to_keep: Optional[str] = None,
    table_date_column: Optional[str] = None,
    table_date_column_data_type: Optional[database.DateColumnDataType] = None,
) -> str:
    """Generates the WHERE clause to use to copy data.

    Args:
        execution_date: date when the workflow is run (in YYYYMMDD format).
        database_prune_data: whether the data will be pruned.
        database_days_to_keep: for how many days the data should be kept
            in the database.
        table_date_column: name of the column which contains the date.
        table_date_column_data_type: data type of the date column.

    Returns:
        Condition to use on the where clause for copying data.
    """
    if not database_prune_data:
        return 'TRUE'  # Copy all the data.

    initial_query_date = (
        datetime.datetime.strptime(execution_date, '%Y%m%d')
        - datetime.timedelta(days=database_days_to_keep)
    ).strftime('%Y%m%d')

    if not table_date_column_data_type:
        raise ValueError(
            'table_date_column_data_type is required when specifying '
            'database_days_to_keep.'
        )

    if table_date_column_data_type == database.DateColumnDataType.DATE:
        parsed_date_value = f'PARSE_DATE("%Y%m%d", "{initial_query_date}")'
    elif table_date_column_data_type == database.DateColumnDataType.DATETIME:
        parsed_date_value = f'PARSE_DATETIME("%Y%m%d", "{initial_query_date}")'
    elif table_date_column_data_type == database.DateColumnDataType.TIMESTAMP:
        parsed_date_value = f'PARSE_TIMESTAMP("%Y%m%d", "{initial_query_date}")'
    else:
        raise ValueError(
            f'Date columns must be one of {_SUPPORTED_DATE_FORMATS}. '
            f'Got: {table_date_column_data_type}.'
        )

    return f'{table_date_column} < {parsed_date_value}'


@task_group(group_id=TASK_GROUP_NAME)
def copy_data_to_archive(
    *,
    bigquery_location: str,
    bigquery_table_name: str,
    bigquery_days_to_keep: int,
    database_prune_data: bool,
    database_days_to_keep: Optional[int] = None,
    table_date_column: Optional[str] = None,
    table_date_column_data_type: Optional[database.DateColumnDataType] = None,
) -> None:
    """Copies data that needs to be archived to a BigQuery partitioned table.

    Args:
        bigquery_location: location where BigQuery jobs will be run.
        bigquery_table_name: name of the BigQuery table where the data is.
        bigquery_days_to_keep: for how long to keep the data copied.
        database_prune_data: whether the data will be pruned.
        database_days_to_keep: for how many days the data should be kept
            in the database.
        table_date_column: name of the column which contains the date.
        table_date_column_data_type: data type of the date column.
    """

    @task(task_id=TASK_NAME_GET_CONFIG)
    def get_copy_job_configuration() -> Mapping[str, str]:
        """Creates the job configuration to copy archival data."""
        context = airflow_operators.get_current_context()
        dag_run_id = context['run_id']
        dag_date = context['ds_nodash']
        snapshot_table_name = (
            bigquery_table_name + database.SNAPSHOT_TABLE_NAME_SUFFIX
        )

        context['ti'].xcom_push(
            key=VAR_NAME_SNAPSHOT_TABLE,
            value=snapshot_table_name,
        )

        parsed_dag_date = f'PARSE_DATE("%Y%m%d", "{dag_date}")'
        select_fields = [
            f'"{dag_run_id}" AS {database.FIELD_NAME_SNAPSHOT_RUN_ID}',
            f'{parsed_dag_date} AS {database.FIELD_NAME_SNAPSHOT_DATE}',
            '*',
        ]
        where_condition = _create_copy_sql_condition(
            database_prune_data=database_prune_data,
            table_date_column=table_date_column,
            table_date_column_data_type=table_date_column_data_type,
            execution_date=dag_date,
            database_days_to_keep=database_days_to_keep,
        )
        return {
            'query': {
                'query': (
                    f"SELECT {', '.join(select_fields)} "
                    f'FROM `{bigquery_table_name}` '
                    f'WHERE {where_condition}'
                ),
                'use_legacy_sql': False,
                'destination_table': bigquery_utils.split_table_name(
                    snapshot_table_name
                ),
                'create_disposition': 'CREATE_IF_NEEDED',
                'write_disposition': 'WRITE_APPEND',
                'time_partitioning': {
                    'field': database.FIELD_NAME_SNAPSHOT_DATE,
                    'expiration_ms': bigquery_days_to_keep
                    * (24 * 60 * 60 * 1000),  # days to ms.
                },
            },
        }

    bigquery.BigQueryInsertJobOperator(
        task_id=TASK_NAME_COPY_DATA,
        configuration=get_copy_job_configuration(),
        location=bigquery_location,
    )
