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

"""Tests for table_workflow."""

import unittest
from unittest import mock
from absl.testing import parameterized

from airflow.utils import task_group

from database_archival.dag.models import config_model
from database_archival.dag.tasks import table_workflow
from database_archival.dag.testing import base_test


_DAG_TEST_CONFIG_WITHOUT_PRUNE = config_model.TableConfig(
    bigquery_location='asia-southeast1',
    bigquery_table_name='project.dataset.mainTable',
    bigquery_days_to_keep=3650,
    database_table_name='mainTable',
    database_prune_data=False,
)

_DAG_TEST_CONFIG_WITH_PRUNE = config_model.TableConfig(
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
    database_password_secret='projects/123/secrets/alloydb-password/versions/1',
)


class TestTableWorkflow(base_test.DagTestCase):
    """Tests for table_workflow."""

    def setUp(self):
        super().setUp()

        self.data_archiving_mock = self.enter_context(
            mock.patch.object(
                table_workflow.data_archiving,
                'copy_data_to_archive',
                autospec=True,
            )
        )

        self.data_pruning_preparation_mock = self.enter_context(
            mock.patch.object(
                table_workflow.data_pruning_preparation,
                'batch_primary_keys_to_delete',
                autospec=True,
            )
        )

        self.data_pruning_mock = self.enter_context(
            mock.patch.object(
                table_workflow.data_pruning,
                'delete_data_from_database',
                autospec=True,
            )
        )

    @parameterized.named_parameters(
        [
            {
                'testcase_name': 'without_prune',
                'config': _DAG_TEST_CONFIG_WITHOUT_PRUNE,
                'expected_group_id': 'mainTable_workflow',
            },
            {
                'testcase_name': 'with_prune',
                'config': _DAG_TEST_CONFIG_WITH_PRUNE,
                'expected_group_id': 'transactionTable_workflow',
            },
        ]
    )
    def test_create_workflow_returns_task_group(
        self, config, expected_group_id
    ):
        """Tests that a TaskGroup is created without errors."""
        with self.dag:
            table_task_group = table_workflow.create_workflow_for_table(
                database_table_name=config.database_table_name,
                table_config=config,
            )

        self.assertIsInstance(table_task_group, task_group.TaskGroup)
        self.assertEqual(table_task_group.group_id, expected_group_id)

    # Note: task_workflow only provides structure of tasks. This is tested
    # end to end on the DAG tests on dag_archive_and_prune_test.py.

    def test_create_workflow_without_prune(self):
        """Tests that without-prune config only creates archive tasks."""
        config = _DAG_TEST_CONFIG_WITHOUT_PRUNE

        with self.dag:
            table_workflow.create_workflow_for_table(
                database_table_name=config.database_table_name,
                table_config=config,
            )

        self.data_archiving_mock.assert_called_once()
        self.data_pruning_preparation_mock.assert_not_called()
        self.data_pruning_mock.assert_not_called()

    def test_create_workflow_with_prune(self):
        """Tests that with-prune config creates archive and pruning tasks."""
        config = _DAG_TEST_CONFIG_WITH_PRUNE

        with self.dag:
            table_workflow.create_workflow_for_table(
                database_table_name=config.database_table_name,
                table_config=config,
            )

        self.data_archiving_mock.assert_called_once()
        self.data_pruning_preparation_mock.assert_called_once()
        self.data_pruning_mock.assert_called_once()


if __name__ == '__main__':
    unittest.main()
