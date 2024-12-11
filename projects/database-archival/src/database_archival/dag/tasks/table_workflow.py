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

"""Provides the tasks performed for each table to archive and/or prune data."""

from airflow.utils import task_group
from database_archival.dag.tasks import data_archiving
from database_archival.dag.tasks import data_pruning
from database_archival.dag.tasks import data_pruning_preparation
from database_archival.dag.models import config_model
from database_archival.dag.utils import task_namer


def create_workflow_for_table(
    *,
    database_table_name: str,
    table_config: config_model.TableConfig,
):
    """Creates the archival and/or pruning workflow for a single table.

    Args:
        database_table_name: name of the table for which the task group is
            created.
        table_config: configuration for this table.
    """
    table_workflow_name = task_namer.get_table_task_group_name(
        database_table_name
    )

    with task_group.TaskGroup(group_id=table_workflow_name) as table_workflow:

        copy_archival_data = data_archiving.copy_data_to_archive(
            bigquery_location=table_config.bigquery_location,
            bigquery_table_name=table_config.bigquery_table_name,
            bigquery_days_to_keep=table_config.bigquery_days_to_keep,
            database_prune_data=table_config.database_prune_data,
            database_days_to_keep=table_config.database_days_to_keep,
            table_date_column=table_config.table_date_column,
            table_date_column_data_type=(
                table_config.table_date_column_data_type
            ),
        )

        if not table_config.database_prune_data:
            return table_workflow

        batch_primary_keys_to_delete = (
            data_pruning_preparation.batch_primary_keys_to_delete(
                database_table_name=table_config.database_table_name,
                bigquery_location=table_config.bigquery_location,
                table_primary_key_columns=(
                    table_config.table_primary_key_columns
                ),
                database_prune_batch_size=(
                    table_config.database_prune_batch_size
                ),
            )
        )

        delete_data_from_database = data_pruning.delete_data_from_database(
            database_table_name=table_config.database_table_name,
            bigquery_location=table_config.bigquery_location,
            database_type=table_config.database_type,
            database_instance_name=table_config.database_instance_name,
            database_host=table_config.database_host,
            database_name=table_config.database_name,
            database_username=table_config.database_username,
            database_password=table_config.database_password,
            database_password_secret=table_config.database_password_secret,
            table_primary_key_columns=table_config.table_primary_key_columns,
        )

        # pylint: disable-next=pointless-statement, expression-not-assigned
        (
            copy_archival_data
            >> batch_primary_keys_to_delete
            >> delete_data_from_database
        )

        return table_workflow
