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

"""Tests for config_model."""

import unittest

from database_archival.common.models import database
from database_archival.pruning_function.models import config_model

from absl.testing import parameterized


_BASE_CONFIG = {
    'bigquery_location': 'asia-southeast1',
    'snapshot_progress_table_name': 'project_id.dataset.table_prune_progress',
    'snapshot_run_id': 'manual_run_id',
    'snapshot_date': '20240101',
    'snapshot_batch': 5,
    'database_table_name': 'transactions',
    'table_primary_key_columns': ['transaction_id'],
    'database_type': 'ALLOYDB',
    'database_instance_name': 'project:database:instance',
    'database_name': 'database',
    'database_username': 'test-username',
    'database_password': 'fake-test-password',
}


class TestConfigModel(parameterized.TestCase):
    """Tests for config_model."""

    def test_initializes_config(self):
        """Tests TablePruneConfig initializes with valid config."""
        output = config_model.TablePruneConfig(**_BASE_CONFIG)

        self.assertEqual(output.bigquery_location, 'asia-southeast1')
        self.assertEqual(
            output.snapshot_progress_table_name,
            'project_id.dataset.table_prune_progress',
        )
        self.assertEqual(output.snapshot_run_id, 'manual_run_id')
        self.assertEqual(output.snapshot_date, '20240101')
        self.assertEqual(output.snapshot_batch, 5)
        self.assertEqual(output.database_table_name, 'transactions')
        self.assertEqual(output.database_type, database.DatabaseType.ALLOYDB)
        self.assertEqual(
            output.database_instance_name, 'project:database:instance'
        )
        self.assertIsNone(output.database_host)
        self.assertEqual(output.database_name, 'database')
        self.assertEqual(output.database_username, 'test-username')
        self.assertEqual(output.database_password, 'fake-test-password')
        self.assertIsNone(output.database_password_secret)

    @parameterized.named_parameters(
        [
            {
                'testcase_name': 'ALLOYDB',
                'enum_str_value': 'ALLOYDB',
                'expected_output': database.DatabaseType.ALLOYDB,
            },
            {
                'testcase_name': 'MYSQL',
                'enum_str_value': 'MySQL',
                'expected_output': database.DatabaseType.MYSQL,
            },
            {
                'testcase_name': 'POSTGRES',
                'enum_str_value': 'Postgres',
                'expected_output': database.DatabaseType.POSTGRES,
            },
            {
                'testcase_name': 'SPANNER',
                'enum_str_value': 'spanner',
                'expected_output': database.DatabaseType.SPANNER,
            },
            {
                'testcase_name': 'SQL_SERVER',
                'enum_str_value': 'sql_server',
                'expected_output': database.DatabaseType.SQL_SERVER,
            },
        ]
    )
    def test_sets_database_type(self, enum_str_value, expected_output):
        """Tests TablePruneConfig initializes with expected DatabaseType."""
        config = {
            **_BASE_CONFIG,
            'database_type': enum_str_value,
        }

        output = config_model.TablePruneConfig(**config)

        self.assertEqual(output.database_type, expected_output)

    def test_sets_database_host(self):
        """Tests TablePruneConfig initializes with database_host."""
        config = {
            **_BASE_CONFIG,
            # Cannot set both database_host and database_instance_name.
            'database_instance_name': None,
            'database_host': '127.0.0.1',
        }

        output = config_model.TablePruneConfig(**config)

        self.assertEqual(output.database_host, '127.0.0.1')
        self.assertIsNone(output.database_instance_name)

    def test_sets_database_password_secret(self):
        """Tests TablePruneConfig initializes with database_password_secret."""
        config = {
            **_BASE_CONFIG,
            # Cannot set both database_password and database_password_secret.
            'database_password': None,
            'database_password_secret': '/project/123/secret/version/1',
        }

        output = config_model.TablePruneConfig(**config)

        self.assertEqual(
            output.database_password_secret, '/project/123/secret/version/1'
        )
        self.assertIsNone(output.database_password)

    @parameterized.named_parameters(
        [
            {
                'testcase_name': 'bigquery_location__None',
                'config': {
                    **_BASE_CONFIG,
                    'bigquery_location': None,
                },
                'expected_error_message': (
                    'bigquery_location is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'bigquery_location__empty',
                'config': {
                    **_BASE_CONFIG,
                    'bigquery_location': '',
                },
                'expected_error_message': (
                    'bigquery_location is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'bigquery_location__not_string',
                'config': {
                    **_BASE_CONFIG,
                    'bigquery_location': 123,
                },
                'expected_error_message': 'bigquery_location must be a string.',
            },
            {
                'testcase_name': 'snapshot_progress_table_name__None',
                'config': {
                    **_BASE_CONFIG,
                    'snapshot_progress_table_name': None,
                },
                'expected_error_message': (
                    'snapshot_progress_table_name is required and was not '
                    'provided.'
                ),
            },
            {
                'testcase_name': 'snapshot_progress_table_name__empty',
                'config': {
                    **_BASE_CONFIG,
                    'snapshot_progress_table_name': '',
                },
                'expected_error_message': (
                    'snapshot_progress_table_name is required and was not '
                    'provided.'
                ),
            },
            {
                'testcase_name': 'snapshot_progress_table_name__not_string',
                'config': {
                    **_BASE_CONFIG,
                    'snapshot_progress_table_name': 123,
                },
                'expected_error_message': (
                    'snapshot_progress_table_name must be a string.'
                ),
            },
            {
                'testcase_name': 'snapshot_date__None',
                'config': {
                    **_BASE_CONFIG,
                    'snapshot_date': None,
                },
                'expected_error_message': (
                    'snapshot_date is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'snapshot_date__empty',
                'config': {
                    **_BASE_CONFIG,
                    'snapshot_date': '',
                },
                'expected_error_message': (
                    'snapshot_date is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'snapshot_date__not_string',
                'config': {
                    **_BASE_CONFIG,
                    'snapshot_date': 123,
                },
                'expected_error_message': 'snapshot_date must be a string.',
            },
            {
                'testcase_name': 'snapshot_run_id__None',
                'config': {
                    **_BASE_CONFIG,
                    'snapshot_run_id': None,
                },
                'expected_error_message': (
                    'snapshot_run_id is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'snapshot_run_id__empty',
                'config': {
                    **_BASE_CONFIG,
                    'snapshot_run_id': '',
                },
                'expected_error_message': (
                    'snapshot_run_id is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'snapshot_run_id__not_string',
                'config': {
                    **_BASE_CONFIG,
                    'snapshot_run_id': 123,
                },
                'expected_error_message': 'snapshot_run_id must be a string.',
            },
            {
                'testcase_name': 'snapshot_batch__None',
                'config': {
                    **_BASE_CONFIG,
                    'snapshot_batch': None,
                },
                'expected_error_message': (
                    'snapshot_batch is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'snapshot_batch__not_integer',
                'config': {
                    **_BASE_CONFIG,
                    'snapshot_batch': '123',
                },
                'expected_error_message': 'snapshot_batch must be an integer.',
            },
            {
                'testcase_name': 'snapshot_batch__zero',
                'config': {
                    **_BASE_CONFIG,
                    'snapshot_batch': 0,
                },
                'expected_error_message': 'snapshot_batch must be positive.',
            },
            {
                'testcase_name': ('snapshot_batch__negative'),
                'config': {
                    **_BASE_CONFIG,
                    'snapshot_batch': -10,
                },
                'expected_error_message': 'snapshot_batch must be positive.',
            },
            {
                'testcase_name': 'database_type__None',
                'config': {**_BASE_CONFIG, 'database_type': None},
                'expected_error_message': (
                    'database_type is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'database_type__empty',
                'config': {**_BASE_CONFIG, 'database_type': ''},
                'expected_error_message': (
                    'database_type is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'database_type__not_string',
                'config': {**_BASE_CONFIG, 'database_type': 1},
                'expected_error_message': 'database_type must be a string.',
            },
            {
                'testcase_name': 'database_type__invalid_enum_value',
                'config': {
                    **_BASE_CONFIG,
                    'database_type': 'NO_MATCH',
                },
                'expected_error_message': (
                    'database_type must be one of ALLOYDB'
                ),
            },
            {
                'testcase_name': 'database_instance_name_and_host__None',
                'config': {
                    **_BASE_CONFIG,
                    'database_instance_name': None,
                    'database_host': None,
                },
                'expected_error_message': (
                    'database_host or database_instance_name must be provided.'
                ),
            },
            {
                'testcase_name': 'database_instance_name_or_host_not_both',
                'config': {
                    **_BASE_CONFIG,
                    'database_instance_name': 'projectId:regionId:instanceName',
                    'database_host': '127.0.0.1',
                },
                'expected_error_message': (
                    'Only database_host or database_instance_name can be used '
                    'at one time. Choose one of the two.'
                ),
            },
            {
                'testcase_name': 'database_instance_name__not_string',
                'config': {
                    **_BASE_CONFIG,
                    'database_instance_name': 123,
                },
                'expected_error_message': (
                    'database_instance_name must be a string.'
                ),
            },
            {
                'testcase_name': 'database_host__not_string',
                'config': {
                    **_BASE_CONFIG,
                    'database_instance_name': None,
                    'database_host': 123,
                },
                'expected_error_message': 'database_host must be a string.',
            },
            {
                'testcase_name': 'database_username__None',
                'config': {
                    **_BASE_CONFIG,
                    'database_username': None,
                },
                'expected_error_message': (
                    'database_username is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'database_username__empty',
                'config': {
                    **_BASE_CONFIG,
                    'database_username': '',
                },
                'expected_error_message': (
                    'database_username is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'database_username__not_string',
                'config': {
                    **_BASE_CONFIG,
                    'database_username': 123,
                },
                'expected_error_message': 'database_username must be a string.',
            },
            {
                'testcase_name': 'database_password_and_password_secret__None',
                'config': {
                    **_BASE_CONFIG,
                    'database_password': None,
                    'database_password_secret': None,
                },
                'expected_error_message': (
                    'database_password or database_password_secret must be '
                    'provided.'
                ),
            },
            {
                'testcase_name': (
                    'database_password_or_password_secret_not_both'
                ),
                'config': {
                    **_BASE_CONFIG,
                    'database_password': 'fake-password',
                    'database_password_secret': '/project/7/secret/a/version/1',
                },
                'expected_error_message': (
                    'Only database_password or database_password_secret can be '
                    'used at one time. Choose one of the two.'
                ),
            },
            {
                'testcase_name': 'database_password__not_string',
                'config': {
                    **_BASE_CONFIG,
                    'database_password': 123,
                    'database_password_secret': None,
                },
                'expected_error_message': (
                    'database_password must be a string.'
                ),
            },
            {
                'testcase_name': 'database_password_secret__not_string',
                'config': {
                    **_BASE_CONFIG,
                    'database_password': None,
                    'database_password_secret': 123,
                },
                'expected_error_message': (
                    'database_password_secret must be a string.'
                ),
            },
            {
                'testcase_name': 'database_table_name__None',
                'config': {
                    **_BASE_CONFIG,
                    'database_table_name': None,
                },
                'expected_error_message': (
                    'database_table_name is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'database_table_name__empty',
                'config': {
                    **_BASE_CONFIG,
                    'database_table_name': '',
                },
                'expected_error_message': (
                    'database_table_name is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'database_table_name__not_string',
                'config': {
                    **_BASE_CONFIG,
                    'database_table_name': 123,
                },
                'expected_error_message': (
                    'database_table_name must be a string.'
                ),
            },
            {
                'testcase_name': 'table_primary_key_columns__None',
                'config': {
                    **_BASE_CONFIG,
                    'table_primary_key_columns': None,
                },
                'expected_error_message': (
                    'table_primary_key_columns is required and was not '
                    'provided.'
                ),
            },
            {
                'testcase_name': 'table_primary_key_columns__empty',
                'config': {
                    **_BASE_CONFIG,
                    'table_primary_key_columns': [],
                },
                'expected_error_message': (
                    'table_primary_key_columns is required and was not '
                    'provided.'
                ),
            },
            {
                'testcase_name': 'table_primary_key_columns__not_list',
                'config': {
                    **_BASE_CONFIG,
                    'table_primary_key_columns': '123',
                },
                'expected_error_message': (
                    'table_primary_key_columns must be a list.'
                ),
            },
            {
                'testcase_name': 'table_primary_key_columns_list__None_element',
                'config': {
                    **_BASE_CONFIG,
                    'table_primary_key_columns': [None],
                },
                'expected_error_message': (
                    'Element in table_primary_key_columns is required and was '
                    'not provided.'
                ),
            },
            {
                'testcase_name': (
                    'table_primary_key_columns_list__empty_element'
                ),
                'config': {
                    **_BASE_CONFIG,
                    'table_primary_key_columns': [''],
                },
                'expected_error_message': (
                    'Element in table_primary_key_columns is required and was '
                    'not provided.'
                ),
            },
            {
                'testcase_name': (
                    'table_primary_key_columns_list__not_string_element'
                ),
                'config': {
                    **_BASE_CONFIG,
                    'table_primary_key_columns': [123],
                },
                'expected_error_message': (
                    'Element in table_primary_key_columns must be a string.'
                ),
            },
        ]
    )
    def test_get_config_raises_bad_config_parameters(
        self, config, expected_error_message
    ):
        """Tests raises for bad config params."""
        with self.assertRaisesRegex(ValueError, expected_error_message):
            config_model.TablePruneConfig(**config)


if __name__ == '__main__':
    unittest.main()
