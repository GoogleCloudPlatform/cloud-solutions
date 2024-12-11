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

"""A DAG which archives and prunes data from a database with table configs.

The DAG can run for multiple tables on multiple databases or instances at once.
The configuration is provided and can vary on a per table-level.

The DAG assumes that the there is a live copy of the data on BigQuery. This can
be achieved using Datastream, Dataflow or other means.

The DAG will first archive (copy) the relevant data from the live BigQuery table
to a snapshot-like partition. If the data will be pruned, it will copy only data
that is old than that period. If the data will not be pruned, it will copy all
the data of the table to, effectively, create a snapshot as of the DAG run date.

If the table is marked for pruning, a second snapshot of the data to archive is
taken containing only the primary keys and the pruning status. The data is then
removed from the database (Cloud SQL, AlloyDB or Spanner) and marked as deleted
on the progress / pruning status table.
"""

import airflow
from airflow.operators import empty
from database_archival.dag import config
from database_archival.dag.tasks import table_workflow
from database_archival.dag.utils import config_parser


def set_up_archive_and_prune_dag(dag: airflow.DAG):
    """Sets up and initializes the Archival and Pruning DAG.

    Args:
        dag: The airflow DAG where the pipeline will be set up and run.
    """

    with dag:
        tables_config = config_parser.get_and_parse_config_from_path(
            config.DATA_ARCHIVAL_CONFIG_PATH
        )

        start = empty.EmptyOperator(task_id=f'{config.DAG_NAME}_root')

        for table_config in tables_config:
            # pylint: disable-next=pointless-statement, expression-not-assigned
            start >> table_workflow.create_workflow_for_table(
                database_table_name=table_config.database_table_name,
                table_config=table_config,
            )
