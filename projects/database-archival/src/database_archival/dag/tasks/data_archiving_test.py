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

"""Tests for data_archiving."""

import unittest
from unittest import mock
from absl.testing import parameterized

from airflow.decorators import task
from airflow.operators import python as airflow_operators

from database_archival.common.models import database
from database_archival.dag.tasks import data_archiving
from database_archival.dag.testing import base_test


class TestDataArchiving(base_test.DagTestCase):
    """Tests for data_archiving."""

    def setUp(self):
        """Sets up tests."""
        super().setUp()

        self.bigquery_operator_mock = self.enter_context(
            mock.patch.object(
                data_archiving.bigquery,
                'BigQueryInsertJobOperator',
                autospec=True,
            )
        )

    def test_calls_bigquery_operator(self):
        """Tests that the BigQuery operator is called with expected params."""
        # Act.
        with self.dag:
            data_archiving.copy_data_to_archive(
                bigquery_location='asia-southeast5',
                bigquery_table_name='projectA.datasetB.tableC',
                bigquery_days_to_keep=365,
                database_prune_data=False,
                database_days_to_keep=None,
                table_date_column=None,
                table_date_column_data_type=None,
            )
        self.run_test_dag()

        # Assert.
        self.bigquery_operator_mock.assert_called_once_with(
            task_id='copy_data_to_archive',
            configuration=mock.ANY,  # XComArg, evaluate config separately.
            location='asia-southeast5',
        )

    def test_generates_expected_job_config(self):
        """Tests that the query job is generated for the config as expected."""
        # Act.
        with self.dag:
            act = data_archiving.copy_data_to_archive(
                bigquery_location='asia-southeast5',
                bigquery_table_name='projectA.datasetB.tableC',
                bigquery_days_to_keep=365,
                database_prune_data=False,
                database_days_to_keep=None,
                table_date_column=None,
                table_date_column_data_type=None,
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
                                '"manual__2024-01-01T00:00:00+00:00" '
                                'AS _snapshot_run_id, '
                                'PARSE_DATE("%Y%m%d", "20240101") '
                                'AS _snapshot_date, '
                                '* '
                                'FROM `projectA.datasetB.tableC` '
                                'WHERE TRUE'
                            ),
                            'use_legacy_sql': False,
                            'destination_table': {
                                'project_id': 'projectA',
                                'dataset_id': 'datasetB',
                                'table_id': 'tableC_snapshot',
                            },
                            'create_disposition': 'CREATE_IF_NEEDED',
                            'write_disposition': 'WRITE_APPEND',
                            'time_partitioning': {
                                'field': '_snapshot_date',
                                # 365 days in ms.
                                'expiration_ms': 31536000000,
                            },
                        }
                    },
                )

            # pylint: disable-next=pointless-statement, expression-not-assigned
            act >> assert_tests()

        self.run_test_dag()

    @parameterized.named_parameters(
        [
            {
                'testcase_name': 'no_prune_data',
                'bigquery_table_name': 'projectA.datasetB.tableC',
                'database_prune_data': False,
                'database_days_to_keep': None,
                'table_date_column': None,
                'table_date_column_data_type': None,
                'expected_sql_query': (
                    'SELECT '
                    '"manual__2024-01-01T00:00:00+00:00" AS _snapshot_run_id, '
                    'PARSE_DATE("%Y%m%d", "20240101") AS _snapshot_date, '
                    '* '
                    'FROM `projectA.datasetB.tableC` '
                    'WHERE TRUE'
                ),
            },
            {
                'testcase_name': 'updates_table_name',
                'bigquery_table_name': 'projectX.datasetY.tableZ',
                'database_prune_data': False,
                'database_days_to_keep': None,
                'table_date_column': None,
                'table_date_column_data_type': None,
                'expected_sql_query': (
                    'SELECT '
                    '"manual__2024-01-01T00:00:00+00:00" AS _snapshot_run_id, '
                    'PARSE_DATE("%Y%m%d", "20240101") AS _snapshot_date, '
                    '* '
                    'FROM `projectX.datasetY.tableZ` '
                    'WHERE TRUE'
                ),
            },
            {
                'testcase_name': 'updates_date_column_name',
                'bigquery_table_name': 'projectA.datasetB.tableC',
                'database_prune_data': True,
                'database_days_to_keep': 365,
                'table_date_column': 'column_name',
                'table_date_column_data_type': database.DateColumnDataType.DATE,
                'expected_sql_query': (
                    'SELECT '
                    '"manual__2024-01-01T00:00:00+00:00" AS _snapshot_run_id, '
                    'PARSE_DATE("%Y%m%d", "20240101") AS _snapshot_date, '
                    '* '
                    'FROM `projectA.datasetB.tableC` '
                    'WHERE column_name < PARSE_DATE("%Y%m%d", "20230101")'
                ),
            },
            {
                'testcase_name': 'updates_database_days_to_keep_365',
                'bigquery_table_name': 'projectA.datasetB.tableC',
                'database_prune_data': True,
                'database_days_to_keep': 365,
                'table_date_column': 'date_column',
                'table_date_column_data_type': database.DateColumnDataType.DATE,
                'expected_sql_query': (
                    'SELECT '
                    '"manual__2024-01-01T00:00:00+00:00" AS _snapshot_run_id, '
                    'PARSE_DATE("%Y%m%d", "20240101") AS _snapshot_date, '
                    '* '
                    'FROM `projectA.datasetB.tableC` '
                    'WHERE date_column < PARSE_DATE("%Y%m%d", "20230101")'
                ),
            },
            {
                'testcase_name': 'updates_database_days_to_keep_730',
                'bigquery_table_name': 'projectA.datasetB.tableC',
                'database_prune_data': True,
                'database_days_to_keep': 730,
                'table_date_column': 'date_column',
                'table_date_column_data_type': database.DateColumnDataType.DATE,
                'expected_sql_query': (
                    'SELECT '
                    '"manual__2024-01-01T00:00:00+00:00" AS _snapshot_run_id, '
                    'PARSE_DATE("%Y%m%d", "20240101") AS _snapshot_date, '
                    '* '
                    'FROM `projectA.datasetB.tableC` '
                    'WHERE date_column < PARSE_DATE("%Y%m%d", "20220101")'
                ),
            },
            {
                'testcase_name': 'updates_date_column_type_date',
                'bigquery_table_name': 'projectA.datasetB.tableC',
                'database_prune_data': True,
                'database_days_to_keep': 365,
                'table_date_column': 'date_column',
                'table_date_column_data_type': database.DateColumnDataType.DATE,
                'expected_sql_query': (
                    'SELECT '
                    '"manual__2024-01-01T00:00:00+00:00" AS _snapshot_run_id, '
                    'PARSE_DATE("%Y%m%d", "20240101") AS _snapshot_date, '
                    '* '
                    'FROM `projectA.datasetB.tableC` '
                    'WHERE date_column < PARSE_DATE("%Y%m%d", "20230101")'
                ),
            },
            {
                'testcase_name': 'updates_date_column_type_datetime',
                'bigquery_table_name': 'projectA.datasetB.tableC',
                'database_prune_data': True,
                'database_days_to_keep': 365,
                'table_date_column': 'date_column',
                'table_date_column_data_type': (
                    database.DateColumnDataType.DATETIME
                ),
                'expected_sql_query': (
                    'SELECT '
                    '"manual__2024-01-01T00:00:00+00:00" AS _snapshot_run_id, '
                    'PARSE_DATE("%Y%m%d", "20240101") AS _snapshot_date, '
                    '* '
                    'FROM `projectA.datasetB.tableC` '
                    'WHERE date_column < PARSE_DATETIME("%Y%m%d", "20230101")'
                ),
            },
            {
                'testcase_name': 'updates_date_column_type_timestamp',
                'bigquery_table_name': 'projectA.datasetB.tableC',
                'database_prune_data': True,
                'database_days_to_keep': 365,
                'table_date_column': 'date_column',
                'table_date_column_data_type': (
                    database.DateColumnDataType.TIMESTAMP
                ),
                'expected_sql_query': (
                    'SELECT '
                    '"manual__2024-01-01T00:00:00+00:00" AS _snapshot_run_id, '
                    'PARSE_DATE("%Y%m%d", "20240101") AS _snapshot_date, '
                    '* '
                    'FROM `projectA.datasetB.tableC` '
                    'WHERE date_column < PARSE_TIMESTAMP("%Y%m%d", "20230101")'
                ),
            },
        ]
    )
    def test_generates_expected_sql_query(
        self,
        bigquery_table_name,
        database_prune_data,
        database_days_to_keep,
        table_date_column,
        table_date_column_data_type,
        expected_sql_query,
    ):
        """Tests that the SQL query job is as expected."""
        # Act.
        with self.dag:
            act = data_archiving.copy_data_to_archive(
                bigquery_location='asia-southeast5',
                bigquery_table_name=bigquery_table_name,
                bigquery_days_to_keep=365,
                database_prune_data=database_prune_data,
                database_days_to_keep=database_days_to_keep,
                table_date_column=table_date_column,
                table_date_column_data_type=table_date_column_data_type,
            )

            # Assert.
            @task(task_id='test_assertion')
            def assert_tests():
                context = airflow_operators.get_current_context()
                _, mock_kwargs = self.bigquery_operator_mock.call_args
                call_config = mock_kwargs['configuration'].resolve(context)
                sql_query = call_config['query']['query']
                self.assertEqual(sql_query, expected_sql_query)

            # pylint: disable-next=pointless-statement, expression-not-assigned
            act >> assert_tests()

        self.run_test_dag()

    @parameterized.named_parameters(
        [
            {
                'testcase_name': 'table_date_column_data_type_not_specified',
                'table_date_column_data_type': None,
                'expected_error_message': (
                    'table_date_column_data_type is required when specifying '
                    'database_days_to_keep.'
                ),
            },
            {
                'testcase_name': 'table_date_column_data_type_invalid',
                'table_date_column_data_type': 'not_enum_value',
                'expected_error_message': (
                    'Date columns must be one of (.*?). Got: not_enum_value.'
                ),
            },
        ]
    )
    def test_raises_invalid_table_date_column_data_type(
        self,
        table_date_column_data_type,
        expected_error_message,
    ):
        """Tests that task raises for invalid table_date_column_data_type."""
        with self.assertRaisesRegex(ValueError, expected_error_message):
            with self.dag:
                data_archiving.copy_data_to_archive(
                    bigquery_location='asia-southeast5',
                    bigquery_table_name='projectA.datasetB.tableC',
                    bigquery_days_to_keep=365,
                    database_prune_data=True,
                    database_days_to_keep=1000,
                    table_date_column='date_column',
                    table_date_column_data_type=table_date_column_data_type,
                )

            self.run_test_dag()


if __name__ == '__main__':
    unittest.main()
