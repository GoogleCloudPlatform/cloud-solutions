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

"""Tests for data_pruning."""

import unittest
from unittest import mock

from airflow.decorators import task
from airflow.decorators import task_group
from airflow.operators import python as airflow_operators

from database_archival.common.models import database as database_model
from database_archival.dag.tasks import data_pruning
from database_archival.dag.testing import base_test


class TestDataPruningPreparation(base_test.DagTestCase):
    """Tests for data_pruning."""

    def setUp(self):
        """Sets up tests."""
        super().setUp()

        self.bigquery_operator_mock = self.enter_context(
            mock.patch.object(
                data_pruning.bigquery,
                'BigQueryInsertJobOperator',
                autospec=True,
            )
        )

        self.requests_mock = self.enter_context(
            mock.patch.object(
                data_pruning.requests,
                'AuthorizedSession',
                autospec=True,
            )
        )
        response = self.requests_mock.return_value.post.return_value
        response.json.return_value = {}
        response.status_code = 200

        self.batch_number_mapping_mock = self.enter_context(
            mock.patch.object(
                data_pruning.expandinput,
                'MappedArgument',
                autospec=True,
            )
        )
        self.batch_number_mapping_mock.return_value.resolve = 5  # batch_number

        snapshot_progress_task_id = (
            'data_table_workflow.batch_primary_keys_to_delete.'
            'get_batch_primary_keys_job_config'
        )
        batches_task_id = (
            'data_table_workflow.batch_primary_keys_to_delete.'
            'get_list_of_pending_batches'
        )
        self.xcom_task_data = {
            snapshot_progress_task_id: {
                'snapshot_progress_table_name': (
                    'projectA.datasetB.data_table_snapshot_prune_progress'
                ),
            },
            batches_task_id: {
                'return_value': [1, 2, 3],
            },
        }

    # TODO: Test through delete_data_from_database expansion.
    # This requires supporting dynamically expanding Dynamic Mapped tasks on
    # tests. At the moment, our DAG harness fails to run tasks when expansion
    # is needed. This requires further work to be solved. After which, the
    # tests below can be changed to be run directly from
    # delete_data_from_database. An additional test to verify the expansion
    # would be recommended.

    def disable_test_data_pruning_calls_cloud_function(self):
        """Tests that delete_and_update_data_batch calls the Cloud Function."""
        with self.dag:
            # Arrange.
            xcom_push_tasks = self.create_xcom_push_task_group(
                self.xcom_task_data
            )

            # Act.
            @task_group(group_id='delete_and_update_data_batch')
            def act():
                data_pruning.delete_and_update_data_batch(
                    database_table_name='data_table',
                    bigquery_location='asia-southeast5',
                    database_type=database_model.DatabaseType.POSTGRES,
                    database_instance_name='connection/instance-name',
                    database_name='database',
                    table_primary_key_columns=['id', 'other_column'],
                    database_username='fake-username',
                    database_password='fake-password',
                    batch_number_expand=5,
                )

            # pylint: disable-next=pointless-statement, expression-not-assigned
            xcom_push_tasks >> act()
            self.run_test_dag()

            # Assert
            self.requests_mock.assert_called_once()
            self.requests_mock.return_value.post.assert_called_once_with(
                url='',
                json={
                    'bigquery_location': 'asia-southeast5',
                    'snapshot_progress_table_name': (
                        'projectA.datasetB.data_table_snapshot_prune_progress'
                    ),
                    'snapshot_date': '20240101',
                    'snapshot_run_id': 'manual__2024-01-01T00:00:00+00:00',
                    'snapshot_batch': 5,
                    'database_type': 'postgres',
                    'database_instance_name': 'connection/instance-name',
                    'database_host': None,
                    'database_name': 'database',
                    'database_username': 'fake-username',
                    'database_password': 'fake-password',
                    'database_password_secret': None,
                    'database_table_name': 'data_table',
                    'table_primary_key_columns': ['id', 'other_column'],
                },
                timeout=3000,
            )

    def disable_test_data_pruning_raises_for_non_200_response(self):
        """Tests that data_pruning workflow raises when status code != 200."""
        # Response.status_code = 500
        self.requests_mock.return_value.post.return_value.status_code = 500
        with self.dag:
            # Arrange.
            xcom_push_tasks = self.create_xcom_push_task_group(
                self.xcom_task_data
            )

            # Act.
            @task_group(group_id='delete_and_update_data_batch')
            def act():
                data_pruning.delete_and_update_data_batch(
                    database_table_name='data_table',
                    bigquery_location='asia-southeast5',
                    database_type=database_model.DatabaseType.POSTGRES,
                    database_instance_name='connection/instance-name',
                    database_name='database',
                    table_primary_key_columns=['id', 'other_column'],
                    database_username='fake-username',
                    database_password='fake-password',
                    batch_number_expand=5,
                )

            # Assert
            with self.assertRaisesRegex(
                RuntimeError,
                'Cloud Function call to prune data failed with status code 500',
            ):
                # pylint: disable-next=pointless-statement, expression-not-assigned
                xcom_push_tasks >> act()
                self.run_test_dag()

    def disable_test_data_pruning_updates_bigquery_metadata_table(self):
        """Tests that data_pruning creates job to update BigQuery metadata."""
        with self.dag:
            # Arrange.
            xcom_push_tasks = self.create_xcom_push_task_group(
                self.xcom_task_data
            )

            # Act.
            @task_group(group_id='delete_and_update_data_batch')
            def act():
                data_pruning.delete_and_update_data_batch(
                    database_table_name='data_table',
                    bigquery_location='asia-southeast5',
                    database_type=database_model.DatabaseType.POSTGRES,
                    database_instance_name='connection/instance-name',
                    database_name='database',
                    table_primary_key_columns=['id', 'other_column'],
                    database_username='fake-username',
                    database_password='fake-password',
                    batch_number_expand=5,
                )

            # pylint: disable-next=pointless-statement, expression-not-assigned
            xcom_push_tasks >> act()
            self.run_test_dag()

            # Assert.
            self.bigquery_operator_mock.assert_called_once_with(
                task_id='update_pruned_rows_status_job',
                priority_weight=1000,
                configuration=mock.ANY,  # XComArg, evaluate config separately.
                location='asia-southeast5',
            )

    def test_data_pruning_creates_expected_bigquery_config_job_for_update(self):
        """Tests that data_pruning creates BigQuery job with expected config."""
        with self.dag:
            # Arrange
            xcom_push_tasks = self.create_xcom_push_task_group(
                self.xcom_task_data
            )

            # Act.
            act = data_pruning.delete_and_update_data_batch(
                database_table_name='data_table',
                bigquery_location='asia-southeast5',
                database_type=database_model.DatabaseType.POSTGRES,
                database_instance_name='connection/instance-name',
                database_name='database',
                table_primary_key_columns=['id', 'other_column'],
                database_username='fake-username',
                database_password='fake-password',
                batch_number_expand=5,
            )

            # Assert.
            @task(task_id='test_assertion')
            def assert_tests():
                context = airflow_operators.get_current_context()
                _, mock_kwargs = self.bigquery_operator_mock.call_args
                call_config = mock_kwargs['configuration'].resolve(context)
                self.assertEqual(
                    call_config,
                    {
                        'query': {
                            'query': (
                                'UPDATE '
                                'projectA.datasetB.'
                                'data_table_snapshot_prune_progress '
                                'SET _is_data_pruned = TRUE '
                                'WHERE '
                                '_snapshot_run_id = '
                                '"manual__2024-01-01T00:00:00+00:00" '
                                'AND _snapshot_date = '
                                'PARSE_DATE("%Y%m%d", "20240101") '
                                'AND _prune_batch_number = 5'
                            ),
                            'use_legacy_sql': False,
                        },
                    },
                )

            # pylint: disable-next=pointless-statement, expression-not-assigned
            xcom_push_tasks >> act >> assert_tests()

        dagrun = self.run_test_dag()

        # Verify the assertion task run successfully to avoid false positives.
        self.assertDagTaskRunSuccessfully(dagrun, 'test_assertion')


if __name__ == '__main__':
    unittest.main()
