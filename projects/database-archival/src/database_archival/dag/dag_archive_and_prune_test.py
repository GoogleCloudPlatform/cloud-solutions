#  Copyright 2024 Google LLC
#
#  Licensed under the Apache License, Version 2.0 (the 'License');
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an 'AS IS' BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""Tests for dag_archive_and_prune."""

import unittest
from unittest import mock

from database_archival.dag.models import config_model
from database_archival.dag.testing import base_test
from database_archival.dag import dag_archive_and_prune


_DAG_TEST_CONFIG = [
    config_model.TableConfig(
        bigquery_location='asia-southeast1',
        bigquery_table_name='project.dataset.mainTable',
        bigquery_days_to_keep=3650,
        database_table_name='mainTable',
        database_prune_data=False,
    ),
    config_model.TableConfig(
        bigquery_location='us-central1',
        bigquery_table_name='project2.dataset2.transactionTable',
        bigquery_days_to_keep=7300,
        database_table_name='transactionTable',
        database_prune_data=True,
        database_prune_batch_size=100,
        table_primary_key_columns=['transaction_id'],
        table_date_column='transaction_date',
        table_date_column_data_type='DATE',
        database_days_to_keep=730,
        database_type='ALLOYDB',
        database_instance_name='project:us-central1:alloydb',
        database_name='database',
        database_username='fake-username',
        database_password_secret=(
            'projects/123/secrets/alloydb-password/versions/1'
        ),
    ),
]


class TestDataPruningPreparation(base_test.DagTestCase):
    """Tests for dag_archive_and_prune."""

    def setUp(self):
        """Sets up tests."""
        super().setUp()

        self.config_mock = self.enter_context(
            mock.patch.object(
                dag_archive_and_prune.config_parser,
                'get_and_parse_config_from_path',
                autospec=True,
                return_value=_DAG_TEST_CONFIG,
            )
        )

    def test_dag_builds(self):
        """Tests that the DAG can be built (i.e. structure is fine)."""
        dag_archive_and_prune.set_up_archive_and_prune_dag(self.dag)

    # TODO: add end to end local integration tests using test containers.
    # Requires having a local BigQuery emulator or fake that need to be injected
    # into the Airflow BigQuery operators.

    def test_dag_produces_expected_task_structure(self):
        """Tests that each DAG tasks has the expected downstream tasks."""
        dag_archive_and_prune.set_up_archive_and_prune_dag(self.dag)

        # pylint: disable=line-too-long
        # Disable line-too-long on this function to facilitate readability.
        # The task names are very long strings. Breaking it out into the 80
        # character limit would make it hard to read and validate the task names
        # and therefore structure.
        self.asssertDagStructure(
            self.dag,
            {
                # Root spins two task groups (aka "workflows"), one for each table.
                'database_archival_dag_root': [
                    'mainTable_workflow.copy_data_to_archive.get_copy_data_job_configuration',
                    'transactionTable_workflow.copy_data_to_archive.get_copy_data_job_configuration',
                ],
                # Main table - DAG archives only.
                'mainTable_workflow.copy_data_to_archive.get_copy_data_job_configuration': [
                    'mainTable_workflow.copy_data_to_archive.copy_data_to_archive',
                ],
                'mainTable_workflow.copy_data_to_archive.copy_data_to_archive': [],
                # Historical (Transactional) table - DAG archives and prunes.
                'transactionTable_workflow.copy_data_to_archive.get_copy_data_job_configuration': [
                    'transactionTable_workflow.copy_data_to_archive.copy_data_to_archive',
                ],
                'transactionTable_workflow.copy_data_to_archive.copy_data_to_archive': [
                    'transactionTable_workflow.batch_primary_keys_to_delete.get_batch_primary_keys_job_config',
                ],
                'transactionTable_workflow.batch_primary_keys_to_delete.get_batch_primary_keys_job_config': [
                    'transactionTable_workflow.batch_primary_keys_to_delete.execute_batch_primary_keys_job',
                ],
                'transactionTable_workflow.batch_primary_keys_to_delete.execute_batch_primary_keys_job': [
                    'transactionTable_workflow.batch_primary_keys_to_delete.get_list_of_pending_batches',
                ],
                'transactionTable_workflow.batch_primary_keys_to_delete.get_list_of_pending_batches': [
                    'transactionTable_workflow.delete_data_from_database.get_batches_for_loop',
                ],
                'transactionTable_workflow.delete_data_from_database.get_batches_for_loop': [
                    'transactionTable_workflow.delete_data_from_database.delete_and_update_data_batch.update_pruned_rows_status.get_update_prune_status_job_config',
                    'transactionTable_workflow.delete_data_from_database.delete_and_update_data_batch.delete_data_from_database',
                ],
                'transactionTable_workflow.delete_data_from_database.delete_and_update_data_batch.delete_data_from_database': [
                    'transactionTable_workflow.delete_data_from_database.delete_and_update_data_batch.update_pruned_rows_status.get_update_prune_status_job_config'
                ],
                'transactionTable_workflow.delete_data_from_database.delete_and_update_data_batch.update_pruned_rows_status.get_update_prune_status_job_config': [
                    'transactionTable_workflow.delete_data_from_database.delete_and_update_data_batch.update_pruned_rows_status.update_pruned_rows_status_job'
                ],
                'transactionTable_workflow.delete_data_from_database.delete_and_update_data_batch.update_pruned_rows_status.update_pruned_rows_status_job': [],
            },
        )
        # pylint: enable=line-too-long


if __name__ == '__main__':
    unittest.main()
