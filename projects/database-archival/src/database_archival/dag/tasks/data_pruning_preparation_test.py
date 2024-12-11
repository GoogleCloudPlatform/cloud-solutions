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

"""Tests for data_pruning_preparation."""


import unittest
from unittest import mock

from airflow.decorators import task
from airflow.decorators import task_group
from airflow.operators import python as airflow_operators

from database_archival.dag.tasks import data_pruning_preparation
from database_archival.dag.testing import base_test


class TestDataPruningPreparation(base_test.DagTestCase):
    """Tests for data_pruning_preparation."""

    def setUp(self):
        """Sets up tests."""
        super().setUp()

        self.bigquery_operator_mock = self.enter_context(
            mock.patch.object(
                data_pruning_preparation.bigquery,
                'BigQueryInsertJobOperator',
                autospec=True,
            )
        )

        self.bigquery_hook_mock = self.enter_context(
            mock.patch.object(
                data_pruning_preparation.bigquery_hook,
                'BigQueryHook',
                autospec=True,
            )
        )

        xcom_task_prefix = 'data_table_workflow.copy_data_to_archive'
        self.xcom_task_data = {
            f'{xcom_task_prefix}.get_copy_data_job_configuration': {
                'snapshot_table_name': 'projectA.datasetB.data_table_snapshot',
            },
        }

    def test_calls_bigquery_operator(self):
        """Tests that the BigQuery operator is called with expected params."""
        with self.dag:
            # Arrange.
            xcom_push_tasks = self.create_xcom_push_task_group(
                self.xcom_task_data
            )

            # Act.
            @task_group(group_id='data_table_workflow')
            def act():
                data_pruning_preparation.batch_primary_keys_to_delete(
                    database_table_name='data_table',
                    bigquery_location='asia-southeast5',
                    table_primary_key_columns=['id', 'other_column'],
                    database_prune_batch_size=99,
                )

            # pylint: disable-next=pointless-statement, expression-not-assigned
            xcom_push_tasks >> act()

        self.run_test_dag()

        # Assert.
        self.bigquery_operator_mock.assert_called_once_with(
            task_id='execute_batch_primary_keys_job',
            configuration=mock.ANY,  # XComArg, evaluate config separately.
            location='asia-southeast5',
        )

    def test_calls_bigquery_operator_with_expected_job_config(self):
        """Tests that the BigQuery operator is called with job config."""
        with self.dag:
            # Arrange.
            xcom_push_tasks = self.create_xcom_push_task_group(
                self.xcom_task_data
            )

            # Act.
            @task_group(group_id='data_table_workflow')
            def act():
                data_pruning_preparation.batch_primary_keys_to_delete(
                    database_table_name='data_table',
                    bigquery_location='asia-southeast5',
                    table_primary_key_columns=['id', 'other_column'],
                    database_prune_batch_size=99,
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
                                'SELECT '
                                'id, other_column, '
                                '_snapshot_run_id, _snapshot_date, '
                                'FALSE AS _is_data_pruned, '
                                'CAST(CEIL(ROW_NUMBER() OVER () / 99) '
                                'AS INT64) '
                                'AS _prune_batch_number '
                                'FROM `projectA.datasetB.data_table_snapshot` '
                                'WHERE '
                                '_snapshot_date = '
                                'PARSE_DATE("%Y%m%d", "20240101") '
                                'AND _snapshot_run_id = '
                                '"manual__2024-01-01T00:00:00+00:00"'
                            ),
                            'use_legacy_sql': False,
                            'destination_table': {
                                'project_id': 'projectA',
                                'dataset_id': 'datasetB',
                                'table_id': (
                                    'data_table_snapshot_prune_progress'
                                ),
                            },
                            'create_disposition': 'CREATE_IF_NEEDED',
                            'write_disposition': 'WRITE_APPEND',
                        },
                    },
                )

            # pylint: disable-next=pointless-statement, expression-not-assigned
            xcom_push_tasks >> act() >> assert_tests()

        self.run_test_dag()

    def test_calls_bigquery_connector_with_expected_query(self):
        """Tests that the BigQuery Hook connector executes expected query."""
        with self.dag:
            # Arrange.
            xcom_push_tasks = self.create_xcom_push_task_group(
                self.xcom_task_data
            )

            # Act.
            @task_group(group_id='data_table_workflow')
            def act():
                data_pruning_preparation.batch_primary_keys_to_delete(
                    database_table_name='data_table',
                    bigquery_location='asia-southeast5',
                    table_primary_key_columns=['id', 'other_column'],
                    database_prune_batch_size=99,
                )

            # pylint: disable-next=pointless-statement, expression-not-assigned
            xcom_push_tasks >> act()

        self.run_test_dag()

        # Assert.
        cursor_mock = (
            # pylint: disable-next=line-too-long
            self.bigquery_hook_mock.return_value.get_conn.return_value.cursor.return_value
        )
        cursor_mock.execute.assert_called_once_with(
            'SELECT DISTINCT _prune_batch_number '
            'FROM projectA.datasetB.data_table_snapshot_prune_progress '
            'WHERE '
            'NOT _is_data_pruned '
            'AND _snapshot_run_id = "manual__2024-01-01T00:00:00+00:00" '
            'AND _snapshot_date = PARSE_DATE("%Y%m%d", "20240101")'
        )


if __name__ == '__main__':
    unittest.main()
