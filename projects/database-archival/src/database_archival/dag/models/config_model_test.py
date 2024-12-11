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
from database_archival.dag.models import config_model
from absl.testing import parameterized


_BASE_CONFIG_WITHOUT_PRUNE = {
    'bigquery_location': 'asia-southeast1',
    'bigquery_table_name': 'project_id.dataset.table_name',
    'bigquery_days_to_keep': 3650,
    'database_table_name': 'appointment',
    'database_prune_data': False,
}

_BASE_CONFIG_WITH_PRUNE = {
    **_BASE_CONFIG_WITHOUT_PRUNE,
    'database_prune_data': True,
    'table_primary_key_columns': ['transaction_id'],
    'table_date_column': 'created_date',
    'table_date_column_data_type': 'DATE',
    'database_prune_batch_size': 150,
    'database_days_to_keep': 365,
    'database_type': 'ALLOYDB',
    'database_instance_name': 'project:database:instance',
    'database_name': 'database',
    'database_username': 'test-username',
    'database_password': 'fake-test-password',
}


class TestConfigModel(parameterized.TestCase):
    """Tests for config_model."""

    def test_initializes_config_without_prune(self):
        """Tests TableConfig initializes config without pruning."""
        output = config_model.TableConfig(**_BASE_CONFIG_WITHOUT_PRUNE)

        self.assertEqual(output.bigquery_location, 'asia-southeast1')
        self.assertEqual(
            output.bigquery_table_name, 'project_id.dataset.table_name'
        )
        self.assertEqual(output.bigquery_days_to_keep, 3650)
        self.assertEqual(output.database_table_name, 'appointment')
        self.assertFalse(output.database_prune_data)
        self.assertIsNone(output.table_primary_key_columns)
        self.assertIsNone(output.table_date_column)
        self.assertIsNone(output.table_date_column_data_type)
        self.assertIsNone(output.database_prune_batch_size)
        self.assertIsNone(output.database_days_to_keep)
        self.assertIsNone(output.database_type)
        self.assertIsNone(output.database_instance_name)
        self.assertIsNone(output.database_host)
        self.assertIsNone(output.database_name)
        self.assertIsNone(output.database_username)
        self.assertIsNone(output.database_password)
        self.assertIsNone(output.database_password_secret)

    def test_get_config_parses_into_expected_table_config_with_prune(self):
        """Tests TableConfig initializes config with pruning."""
        output = config_model.TableConfig(**_BASE_CONFIG_WITH_PRUNE)

        self.assertEqual(output.bigquery_location, 'asia-southeast1')
        self.assertEqual(
            output.bigquery_table_name, 'project_id.dataset.table_name'
        )
        self.assertEqual(output.bigquery_days_to_keep, 3650)
        self.assertEqual(output.database_table_name, 'appointment')
        self.assertTrue(output.database_prune_data)

        self.assertEqual(output.table_primary_key_columns, ['transaction_id'])
        self.assertEqual(output.table_date_column, 'created_date')
        self.assertEqual(
            output.table_date_column_data_type,
            database.DateColumnDataType.DATE,
        )
        self.assertEqual(output.database_prune_batch_size, 150)
        self.assertEqual(output.database_days_to_keep, 365)
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
                'testcase_name': 'DATE',
                'enum_str_value': 'DATE',
                'expected_output': database.DateColumnDataType.DATE,
            },
            {
                'testcase_name': 'DATETIME',
                'enum_str_value': 'datetime',
                'expected_output': database.DateColumnDataType.DATETIME,
            },
            {
                'testcase_name': 'TIMESTAMP',
                'enum_str_value': 'Timestamp',
                'expected_output': database.DateColumnDataType.TIMESTAMP,
            },
        ]
    )
    def test_sets_table_date_column_data_type(
        self, enum_str_value, expected_output
    ):
        """Tests TableConfig initializes with expected DateColumnDataType."""
        config = {
            **_BASE_CONFIG_WITH_PRUNE,
            'table_date_column_data_type': enum_str_value,
        }

        output = config_model.TableConfig(**config)

        self.assertEqual(output.table_date_column_data_type, expected_output)

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
        """Tests TableConfig initializes with expected DatabaseType."""
        config = {
            **_BASE_CONFIG_WITH_PRUNE,
            'database_type': enum_str_value,
        }

        output = config_model.TableConfig(**config)

        self.assertEqual(output.database_type, expected_output)

    def test_sets_database_host(self):
        """Tests TableConfig initializes with database_host."""
        config = {
            **_BASE_CONFIG_WITH_PRUNE,
            # Cannot set both database_host and database_instance_name.
            'database_instance_name': None,
            'database_host': '127.0.0.1',
        }

        output = config_model.TableConfig(**config)

        self.assertEqual(output.database_host, '127.0.0.1')
        self.assertIsNone(output.database_instance_name)

    @parameterized.named_parameters(
        [
            {
                'testcase_name': 'database_prune_batch_size',
                'field_name': 'database_prune_batch_size',
                'expected_output': 1000,
            },
        ]
    )
    def test_sets_default_values(self, field_name, expected_output):
        """Tests TableConfig initializes with default values."""
        config = {**_BASE_CONFIG_WITH_PRUNE}
        del config[field_name]

        output = config_model.TableConfig(**config)

        self.assertEqual(getattr(output, field_name), expected_output)

    @parameterized.named_parameters(
        [
            # Without prune test cases.
            {
                'testcase_name': 'without_prune_bigquery_location__None',
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'bigquery_location': None,
                },
                'expected_error_message': (
                    'bigquery_location is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'without_prune_bigquery_location__empty',
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'bigquery_location': '',
                },
                'expected_error_message': (
                    'bigquery_location is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'without_prune_bigquery_location_not__string',
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'bigquery_location': 123,
                },
                'expected_error_message': 'bigquery_location must be a string.',
            },
            {
                'testcase_name': 'without_prune_bigquery_table_name__None',
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'bigquery_table_name': None,
                },
                'expected_error_message': (
                    'bigquery_table_name is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'without_prune_bigquery_table_name__empty',
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'bigquery_table_name': '',
                },
                'expected_error_message': (
                    'bigquery_table_name is required and was not provided.'
                ),
            },
            {
                'testcase_name': (
                    'without_prune_bigquery_table_name__not_string'
                ),
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'bigquery_table_name': 123,
                },
                'expected_error_message': (
                    'bigquery_table_name must be a string.'
                ),
            },
            {
                'testcase_name': 'without_prune_bigquery_days_to_keep__None',
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'bigquery_days_to_keep': None,
                },
                'expected_error_message': (
                    'bigquery_days_to_keep is required and was not provided.'
                ),
            },
            {
                'testcase_name': (
                    'without_prune_bigquery_days_to_keep__not_integer'
                ),
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'bigquery_days_to_keep': '123',
                },
                'expected_error_message': (
                    'bigquery_days_to_keep must be an integer.'
                ),
            },
            {
                'testcase_name': 'without_prune_bigquery_days_to_keep__zero',
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'bigquery_days_to_keep': 0,
                },
                'expected_error_message': (
                    'bigquery_days_to_keep must be positive.'
                ),
            },
            {
                'testcase_name': (
                    'without_prune_bigquery_days_to_keep__negative'
                ),
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'bigquery_days_to_keep': -10,
                },
                'expected_error_message': (
                    'bigquery_days_to_keep must be positive.'
                ),
            },
            {
                'testcase_name': 'without_prune__database_table_name__None',
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'database_table_name': None,
                },
                'expected_error_message': (
                    'database_table_name is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'without_prune__database_table_name__empty',
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'database_table_name': '',
                },
                'expected_error_message': (
                    'database_table_name is required and was not provided.'
                ),
            },
            {
                'testcase_name': (
                    'without_prune__database_table_name__not_string'
                ),
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'database_table_name': 123,
                },
                'expected_error_message': (
                    'database_table_name must be a string.'
                ),
            },
            {
                'testcase_name': 'without_prune__database_prune_data__None',
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'database_prune_data': None,
                },
                'expected_error_message': (
                    'database_prune_data is required and was not provided.'
                ),
            },
            {
                'testcase_name': (
                    'without_prune__database_prune_data__not_boolean'
                ),
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'database_prune_data': 'False',
                },
                'expected_error_message': (
                    'database_prune_data must be a boolean.'
                ),
            },
            {
                'testcase_name': 'without_prune__database_days_to_keep__is_set',
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'database_days_to_keep': 3,
                },
                'expected_error_message': (
                    'database_days_to_keep was set but database_prune_data is '
                    'False.'
                ),
            },
            {
                'testcase_name': (
                    'without_prune__database_days_to_keep__is_set_falsy'
                ),
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'database_days_to_keep': 0,
                },
                'expected_error_message': (
                    'database_days_to_keep was set but database_prune_data is '
                    'False.'
                ),
            },
            {
                'testcase_name': (
                    'without_prune__table_primary_key_columns__is_set'
                ),
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'table_primary_key_columns': ['id'],
                },
                'expected_error_message': (
                    'table_primary_key_columns was set but database_prune_data '
                    'is False.'
                ),
            },
            {
                'testcase_name': (
                    'without_prune__table_primary_key_columns__is_set_falsy'
                ),
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'table_primary_key_columns': [],
                },
                'expected_error_message': (
                    'table_primary_key_columns was set but database_prune_data '
                    'is False.'
                ),
            },
            {
                'testcase_name': 'without_prune__table_date_column__is_set',
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'table_date_column': 'date',
                },
                'expected_error_message': (
                    'table_date_column was set but database_prune_data is '
                    'False.'
                ),
            },
            {
                'testcase_name': (
                    'without_prune__table_date_column__is_set_falsy'
                ),
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'table_date_column': '',
                },
                'expected_error_message': (
                    'table_date_column was set but database_prune_data is '
                    'False.'
                ),
            },
            {
                'testcase_name': (
                    'without_prune__table_date_column_data_type__is_set'
                ),
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'table_date_column_data_type': 'DATE',
                },
                'expected_error_message': (
                    'table_date_column_data_type was set but '
                    'database_prune_data is False.'
                ),
            },
            {
                'testcase_name': (
                    'without_prune__table_date_column_data_type__is_set_falsy'
                ),
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'table_date_column_data_type': '',
                },
                'expected_error_message': (
                    'table_date_column_data_type was set but '
                    'database_prune_data is False.'
                ),
            },
            {
                'testcase_name': 'without_prune__database_type__is_set',
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'database_type': 'ALLOYDB',
                },
                'expected_error_message': (
                    'database_type was set but database_prune_data is False.'
                ),
            },
            {
                'testcase_name': 'without_prune__database_type__is_set_falsy',
                'config': {**_BASE_CONFIG_WITHOUT_PRUNE, 'database_type': ''},
                'expected_error_message': (
                    'database_type was set but database_prune_data is False.'
                ),
            },
            {
                'testcase_name': (
                    'without_prune__database_instance_name__is_set'
                ),
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'database_instance_name': 'project:region:instance',
                },
                'expected_error_message': (
                    'database_instance_name was set but database_prune_data is '
                    'False.'
                ),
            },
            {
                'testcase_name': (
                    'without_prune__database_instance_name__is_set_falsy'
                ),
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'database_instance_name': '',
                },
                'expected_error_message': (
                    'database_instance_name was set but database_prune_data is '
                    'False.'
                ),
            },
            {
                'testcase_name': 'without_prune__database_host__is_set',
                'config': {**_BASE_CONFIG_WITHOUT_PRUNE, 'database_host': 'ip'},
                'expected_error_message': (
                    'database_host was set but database_prune_data is False.'
                ),
            },
            {
                'testcase_name': 'without_prune__database_host__is_set_falsy',
                'config': {**_BASE_CONFIG_WITHOUT_PRUNE, 'database_host': ''},
                'expected_error_message': (
                    'database_host was set but database_prune_data is False.'
                ),
            },
            {
                'testcase_name': 'without_prune__database_name__is_set',
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'database_name': 'dbname',
                },
                'expected_error_message': (
                    'database_name was set but database_prune_data is False.'
                ),
            },
            {
                'testcase_name': 'without_prune__database_name__is_set_falsy',
                'config': {**_BASE_CONFIG_WITHOUT_PRUNE, 'database_name': ''},
                'expected_error_message': (
                    'database_name was set but database_prune_data is False.'
                ),
            },
            {
                'testcase_name': 'without_prune__database_username__is_set',
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'database_username': 'user',
                },
                'expected_error_message': (
                    'database_username was set but database_prune_data is '
                    'False.'
                ),
            },
            {
                'testcase_name': (
                    'without_prune__database_username__is_set_falsy'
                ),
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'database_username': '',
                },
                'expected_error_message': (
                    'database_username was set but database_prune_data is '
                    'False.'
                ),
            },
            {
                'testcase_name': 'without_prune__database_password__is_set',
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'database_password': 'pass',
                },
                'expected_error_message': (
                    'database_password was set but database_prune_data is '
                    'False.'
                ),
            },
            {
                'testcase_name': (
                    'without_prune__database_password__is_set_falsy'
                ),
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'database_password': '',
                },
                'expected_error_message': (
                    'database_password was set but database_prune_data is '
                    'False.'
                ),
            },
            # With prune test cases.
            {
                'testcase_name': 'with_prune__bigquery_location__None',
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'bigquery_location': None,
                },
                'expected_error_message': (
                    'bigquery_location is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'with_prune__bigquery_location__empty',
                'config': {**_BASE_CONFIG_WITH_PRUNE, 'bigquery_location': ''},
                'expected_error_message': (
                    'bigquery_location is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'with_prune__bigquery_location__not_string',
                'config': {
                    **_BASE_CONFIG_WITHOUT_PRUNE,
                    'bigquery_location': 123,
                },
                'expected_error_message': 'bigquery_location must be a string.',
            },
            {
                'testcase_name': 'with_prune__bigquery_table_name__None',
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'bigquery_table_name': None,
                },
                'expected_error_message': (
                    'bigquery_table_name is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'with_prune__bigquery_table_name__empty',
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'bigquery_table_name': '',
                },
                'expected_error_message': (
                    'bigquery_table_name is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'with_prune__bigquery_table_name__not_string',
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'bigquery_table_name': 123,
                },
                'expected_error_message': (
                    'bigquery_table_name must be a string.'
                ),
            },
            {
                'testcase_name': 'with_prune__bigquery_days_to_keep__None',
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'bigquery_days_to_keep': None,
                },
                'expected_error_message': (
                    'bigquery_days_to_keep is required and was not provided.'
                ),
            },
            {
                'testcase_name': (
                    'with_prune__bigquery_days_to_keep__not_integer'
                ),
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'bigquery_days_to_keep': '123',
                },
                'expected_error_message': (
                    'bigquery_days_to_keep must be an integer.'
                ),
            },
            {
                'testcase_name': 'with_prune__bigquery_days_to_keep__zero',
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'bigquery_days_to_keep': 0,
                },
                'expected_error_message': (
                    'bigquery_days_to_keep must be positive.'
                ),
            },
            {
                'testcase_name': 'with_prune__bigquery_days_to_keep__negative',
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'bigquery_days_to_keep': -10,
                },
                'expected_error_message': (
                    'bigquery_days_to_keep must be positive.'
                ),
            },
            {
                'testcase_name': 'with_prune__database_table_name__None',
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'database_table_name': None,
                },
                'expected_error_message': (
                    'database_table_name is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'with_prune__table_name__empty',
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'database_table_name': '',
                },
                'expected_error_message': (
                    'database_table_name is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'with_prune__database_table_name__not_string',
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'database_table_name': 123,
                },
                'expected_error_message': (
                    'database_table_name must be a string.'
                ),
            },
            {
                'testcase_name': 'with_prune__database_prune_data__None',
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'database_prune_data': None,
                },
                'expected_error_message': (
                    'database_prune_data is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'with_prune__database_prune_data__not_boolean',
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'database_prune_data': 'True',
                },
                'expected_error_message': (
                    'database_prune_data must be a boolean.'
                ),
            },
            {
                'testcase_name': 'with_prune__database_prune_batch_size__None',
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'database_prune_batch_size': None,
                },
                'expected_error_message': (
                    'database_prune_batch_size is required and was not '
                    'provided.'
                ),
            },
            {
                'testcase_name': (
                    'with_prune__database_prune_batch_size__not_integer'
                ),
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'database_prune_batch_size': '123',
                },
                'expected_error_message': (
                    'database_prune_batch_size must be an integer.'
                ),
            },
            {
                'testcase_name': 'with_prune__database_prune_batch_size__zero',
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'database_prune_batch_size': 0,
                },
                'expected_error_message': (
                    'database_prune_batch_size must be positive.'
                ),
            },
            {
                'testcase_name': (
                    'with_prune__database_prune_batch_size__negative'
                ),
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'database_prune_batch_size': -10,
                },
                'expected_error_message': (
                    'database_prune_batch_size must be positive.'
                ),
            },
            {
                'testcase_name': 'with_prune__table_primary_key_columns__None',
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'table_primary_key_columns': None,
                },
                'expected_error_message': (
                    'table_primary_key_columns is required and was not '
                    'provided.'
                ),
            },
            {
                'testcase_name': 'with_prune__table_primary_key_columns__empty',
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'table_primary_key_columns': [],
                },
                'expected_error_message': (
                    'table_primary_key_columns is required and was not '
                    'provided.'
                ),
            },
            {
                'testcase_name': (
                    'with_prune__table_primary_key_columns__not_list'
                ),
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'table_primary_key_columns': '123',
                },
                'expected_error_message': (
                    'table_primary_key_columns must be a list.'
                ),
            },
            {
                'testcase_name': (
                    'with_prune__table_primary_key_columns_list__None_element'
                ),
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'table_primary_key_columns': [None],
                },
                'expected_error_message': (
                    'Element in table_primary_key_columns is required and was '
                    'not provided.'
                ),
            },
            {
                'testcase_name': (
                    'with_prune__table_primary_key_columns_list__empty_element'
                ),
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'table_primary_key_columns': [''],
                },
                'expected_error_message': (
                    'Element in table_primary_key_columns is required and was '
                    'not provided.'
                ),
            },
            {
                'testcase_name': (
                    'with_prune__table_primary_key_columns_list__'
                    'not_string_element'
                ),
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'table_primary_key_columns': [123],
                },
                'expected_error_message': (
                    'Element in table_primary_key_columns must be a string.'
                ),
            },
            {
                'testcase_name': 'with_prune__table_date_column__None',
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'table_date_column': None,
                },
                'expected_error_message': (
                    'table_date_column is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'with_prune__table_date_column__empty',
                'config': {**_BASE_CONFIG_WITH_PRUNE, 'table_date_column': ''},
                'expected_error_message': (
                    'table_date_column is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'with_prune__table_date_column__not_string',
                'config': {**_BASE_CONFIG_WITH_PRUNE, 'table_date_column': 123},
                'expected_error_message': 'table_date_column must be a string.',
            },
            {
                'testcase_name': (
                    'with_prune__table_date_column_data_type__None'
                ),
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'table_date_column_data_type': None,
                },
                'expected_error_message': (
                    'table_date_column_data_type is required and was not '
                    'provided.'
                ),
            },
            {
                'testcase_name': (
                    'with_prune__table_date_column_data_type__emtpy'
                ),
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'table_date_column_data_type': '',
                },
                'expected_error_message': (
                    'table_date_column_data_type is required and was not '
                    'provided.'
                ),
            },
            {
                'testcase_name': (
                    'with_prune__table_date_column_data_type__not_string'
                ),
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'table_date_column_data_type': 1,
                },
                'expected_error_message': (
                    'table_date_column_data_type must be a string.'
                ),
            },
            {
                'testcase_name': (
                    'with_prune__table_date_column_data_type__'
                    'invalid_enum_value'
                ),
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'table_date_column_data_type': 'NO_MATCH',
                },
                'expected_error_message': (
                    'table_date_column_data_type must be one of DATE'
                ),
            },
            {
                'testcase_name': 'with_prune__database_days_to_keep__None',
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'database_days_to_keep': None,
                },
                'expected_error_message': (
                    'database_days_to_keep is required and was not provided.'
                ),
            },
            {
                'testcase_name': (
                    'with_prune__database_days_to_keep__not_integer'
                ),
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'database_days_to_keep': '123',
                },
                'expected_error_message': (
                    'database_days_to_keep must be an integer.'
                ),
            },
            {
                'testcase_name': 'with_prune__database_days_to_keep__zero',
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'database_days_to_keep': 0,
                },
                'expected_error_message': (
                    'database_days_to_keep must be positive.'
                ),
            },
            {
                'testcase_name': 'with_prune__database_days_to_keep__negative',
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'database_days_to_keep': -10,
                },
                'expected_error_message': (
                    'database_days_to_keep must be positive.'
                ),
            },
            {
                'testcase_name': 'with_prune__database_type__None',
                'config': {**_BASE_CONFIG_WITH_PRUNE, 'database_type': None},
                'expected_error_message': (
                    'database_type is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'with_prune__database_type__emtpy',
                'config': {**_BASE_CONFIG_WITH_PRUNE, 'database_type': ''},
                'expected_error_message': (
                    'database_type is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'with_prune__database_type__not_string',
                'config': {**_BASE_CONFIG_WITH_PRUNE, 'database_type': 1},
                'expected_error_message': 'database_type must be a string.',
            },
            {
                'testcase_name': (
                    'with_prune__database_type__invalid_enum_value'
                ),
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'database_type': 'NO_MATCH',
                },
                'expected_error_message': (
                    'database_type must be one of ALLOYDB'
                ),
            },
            {
                'testcase_name': (
                    'with_prune__database_instance_name_and_host__None'
                ),
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'database_instance_name': None,
                    'database_host': None,
                },
                'expected_error_message': (
                    'database_host or database_instance_name must be provided.'
                ),
            },
            {
                'testcase_name': (
                    'with_prune__database_instance_name_or_host_not_both'
                ),
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'database_instance_name': 'projectId:regionId:instanceName',
                    'database_host': '127.0.0.1',
                },
                'expected_error_message': (
                    'Only database_host or database_instance_name can be used '
                    'at one time. Choose one of the two.'
                ),
            },
            {
                'testcase_name': (
                    'with_prune__database_instance_name__wrong_format'
                ),
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'database_instance_name': 'project-region-instance',
                },
                'expected_error_message': (
                    'database_instance_name must follow '
                    '"<projectId>:<regionId>:<instanceName>" format. '
                    'Got: project-region-instance.'
                ),
            },
            {
                'testcase_name': (
                    'with_prune__database_instance_name__not_string'
                ),
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'database_instance_name': 123,
                },
                'expected_error_message': (
                    'database_instance_name must be a string.'
                ),
            },
            {
                'testcase_name': 'with_prune__database_host__not_string',
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'database_instance_name': None,
                    'database_host': 123,
                },
                'expected_error_message': 'database_host must be a string.',
            },
            {
                'testcase_name': 'with_prune__database_name__None',
                'config': {**_BASE_CONFIG_WITH_PRUNE, 'database_name': None},
                'expected_error_message': (
                    'database_name is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'with_prune__database_name__empty',
                'config': {**_BASE_CONFIG_WITH_PRUNE, 'database_name': ''},
                'expected_error_message': (
                    'database_name is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'with_prune__database_name__not_string',
                'config': {**_BASE_CONFIG_WITH_PRUNE, 'database_name': 123},
                'expected_error_message': 'database_name must be a string.',
            },
            {
                'testcase_name': 'with_prune__database_username__None',
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'database_username': None,
                },
                'expected_error_message': (
                    'database_username is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'with_prune__database_username__empty',
                'config': {**_BASE_CONFIG_WITH_PRUNE, 'database_username': ''},
                'expected_error_message': (
                    'database_username is required and was not provided.'
                ),
            },
            {
                'testcase_name': 'with_prune__database_username__not_string',
                'config': {**_BASE_CONFIG_WITH_PRUNE, 'database_username': 123},
                'expected_error_message': 'database_username must be a string.',
            },
            {
                'testcase_name': 'with_prune__database_password__None',
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'database_password': None,
                    'database_password_secret': None,
                },
                'expected_error_message': (
                    'database_password or database_password_secret must be '
                    'provided.'
                ),
            },
            {
                'testcase_name': 'with_prune__database_password__empty',
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'database_password': '',
                    'database_password_secret': None,
                },
                'expected_error_message': (
                    'database_password or database_password_secret must be '
                    'provided.'
                ),
            },
            {
                'testcase_name': 'with_prune__database_password__not_string',
                'config': {**_BASE_CONFIG_WITH_PRUNE, 'database_password': 123},
                'expected_error_message': 'database_password must be a string.',
            },
            {
                'testcase_name': 'with_prune__database_password_secret__empty',
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'database_password': None,
                    'database_password_secret': '',
                },
                'expected_error_message': (
                    'database_password or database_password_secret must be '
                    'provided.'
                ),
            },
            {
                'testcase_name': (
                    'with_prune__database_password_secret__not_string'
                ),
                'config': {
                    **_BASE_CONFIG_WITH_PRUNE,
                    'database_password': None,
                    'database_password_secret': 123,
                },
                'expected_error_message': (
                    'database_password_secret must be a string.'
                ),
            },
        ]
    )
    def test_raises_bad_config_parameters(self, config, expected_error_message):
        """Tests raises for bad config params."""
        with self.assertRaisesRegex(ValueError, expected_error_message):
            config_model.TableConfig(**config)


if __name__ == '__main__':
    unittest.main()
