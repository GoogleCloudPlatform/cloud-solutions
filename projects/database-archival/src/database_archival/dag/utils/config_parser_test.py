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

"""Tests for config_parser."""

import json
import unittest
from database_archival.common.models import database
from database_archival.dag.models import config_model
from database_archival.dag.utils import config_parser
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
    'database_username': '88513c06c0bf28e26b52a14dd13bb8ec',
    'database_password': '0a68e2ea2093561a9accc8277a47dc4b',
}


class TestConfigValidator(parameterized.TestCase):
    """Tests for config_parser."""

    def setUp(self):
        super().setUp()
        self.gcs_uri = 'gs://bucket/file.json'
        self.config = [{**_BASE_CONFIG_WITHOUT_PRUNE}]

        self.blob_mock = self.enter_context(
            unittest.mock.patch.object(
                config_parser.storage.blob, 'Blob', autospec=True
            )
        )
        self.blob_mock.download_as_bytes.side_effect = lambda: json.dumps(
            self.config
        )

        self.bucket_mock = self.enter_context(
            unittest.mock.patch.object(
                config_parser.storage.bucket, 'Bucket', autospec=True
            )
        )
        self.bucket_mock.blob.return_value = self.blob_mock

        self.storage_client_mock = self.enter_context(
            unittest.mock.patch.object(
                config_parser.storage, 'Client', autospec=True
            )
        )
        self.storage_client_mock.return_value.bucket.return_value = (
            self.bucket_mock
        )

    @parameterized.named_parameters(
        {
            'testcase_name': 'at_root',
            'gcs_uri': 'gs://bucket-name/file.json',
            'expected_bucket': 'bucket-name',
            'expected_path': 'file.json',
        },
        {
            'testcase_name': 'with_path',
            'gcs_uri': 'gs://my-bucket/path/to/file/config.json',
            'expected_bucket': 'my-bucket',
            'expected_path': 'path/to/file/config.json',
        },
        {
            'testcase_name': 'without_extension',
            'gcs_uri': 'gs://bucket-name/filename',
            'expected_bucket': 'bucket-name',
            'expected_path': 'filename',
        },
        {
            'testcase_name': 'with_multiple_extensions',
            'gcs_uri': 'gs://bucket/path-file/to/filename.ext1.ext2',
            'expected_bucket': 'bucket',
            'expected_path': 'path-file/to/filename.ext1.ext2',
        },
    )
    def test_get_config_fetches_from_gs(
        self, gcs_uri, expected_bucket, expected_path
    ):
        """Tests that get_and_parse_config_from_path fetches GCS blob."""
        config_parser.get_and_parse_config_from_path(gcs_uri)

        self.storage_client_mock.return_value.bucket.assert_called_once_with(
            bucket_name=expected_bucket,
        )
        self.bucket_mock.blob.assert_called_once_with(
            blob_name=expected_path,
        )

    @parameterized.named_parameters(
        {
            'testcase_name': 'no_gs_prefix',
            'gcs_uri': 'https://bucket-name/file.json',
        },
        {
            'testcase_name': 'only_bucket_name',
            'gcs_uri': 'gs://my-bucket/',
        },
        {
            'testcase_name': 'no_bucket_name',
            'gcs_uri': 'gs://filename.json',
        },
        {
            'testcase_name': 'bad_format',
            'gcs_uri': 'gs:///',
        },
    )
    def test_get_config_raises_invalid_gcs_path(self, gcs_uri):
        """Tests get_and_parse_config_from_path raises for invalid gcs_uri."""
        with self.assertRaisesRegex(
            ValueError,
            'Config file should be on Google Cloud Storage with the format: '
            'gs://bucket-name/file-path/file.json.',
        ):
            config_parser.get_and_parse_config_from_path(gcs_uri)

    @parameterized.named_parameters(
        [
            {
                'testcase_name': 'base_without_prune',
                'config': [{**_BASE_CONFIG_WITHOUT_PRUNE}],
            },
            {
                'testcase_name': 'base_with_prune',
                'config': [{**_BASE_CONFIG_WITH_PRUNE}],
            },
            {
                'testcase_name': 'multiple_values',
                'config': [
                    {**_BASE_CONFIG_WITH_PRUNE},
                    {**_BASE_CONFIG_WITHOUT_PRUNE},
                ],
            },
        ]
    )
    def test_get_config_parses_configs(self, config):
        """Tests that get_and_parse_config_from_path parses valid configs."""
        self.config = config

        output = config_parser.get_and_parse_config_from_path(self.gcs_uri)

        self.assertEqual(len(output), len(config))
        for output_config in output:
            self.assertIsInstance(output_config, config_model.TableConfig)

    def test_get_config_parses_into_expected_table_config_without_prune(self):
        """Tests get_and_parse_config_from_path parses without prune configs."""
        self.config = [{**_BASE_CONFIG_WITHOUT_PRUNE}]

        output = config_parser.get_and_parse_config_from_path(self.gcs_uri)

        first_config = output[0]
        self.assertEqual(first_config.bigquery_location, 'asia-southeast1')
        self.assertEqual(
            first_config.bigquery_table_name, 'project_id.dataset.table_name'
        )
        self.assertEqual(first_config.bigquery_days_to_keep, 3650)
        self.assertEqual(first_config.database_table_name, 'appointment')
        self.assertFalse(first_config.database_prune_data)

    def test_get_config_parses_into_expected_table_config_with_prune(self):
        """Tests get_and_parse_config_from_path parses with prune configs."""
        self.config = [{**_BASE_CONFIG_WITH_PRUNE}]

        output = config_parser.get_and_parse_config_from_path(self.gcs_uri)

        first_config = output[0]
        self.assertEqual(first_config.bigquery_location, 'asia-southeast1')
        self.assertEqual(
            first_config.bigquery_table_name, 'project_id.dataset.table_name'
        )
        self.assertEqual(first_config.bigquery_days_to_keep, 3650)
        self.assertEqual(first_config.database_table_name, 'appointment')
        self.assertTrue(first_config.database_prune_data)

        self.assertEqual(
            first_config.table_primary_key_columns, ['transaction_id']
        )
        self.assertEqual(first_config.table_date_column, 'created_date')
        self.assertEqual(
            first_config.table_date_column_data_type,
            database.DateColumnDataType.DATE,
        )
        self.assertEqual(first_config.database_prune_batch_size, 150)
        self.assertEqual(first_config.database_days_to_keep, 365)
        self.assertEqual(
            first_config.database_type, database.DatabaseType.ALLOYDB
        )
        self.assertEqual(
            first_config.database_instance_name, 'project:database:instance'
        )
        self.assertEqual(first_config.database_name, 'database')
        self.assertEqual(
            first_config.database_username, '88513c06c0bf28e26b52a14dd13bb8ec'
        )
        self.assertEqual(
            first_config.database_password, '0a68e2ea2093561a9accc8277a47dc4b'
        )

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
    def test_get_config_parses_table_date_column_data_type(
        self, enum_str_value, expected_output
    ):
        """Tests get_and_parse_config_from_path parses DateColumnDataType."""
        self.config = [
            {
                **_BASE_CONFIG_WITH_PRUNE,
                'table_date_column_data_type': enum_str_value,
            }
        ]

        output = config_parser.get_and_parse_config_from_path(self.gcs_uri)

        first_config = output[0]
        self.assertEqual(
            first_config.table_date_column_data_type, expected_output
        )

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
    def test_get_config_parses_database_type(
        self, enum_str_value, expected_output
    ):
        """Tests get_and_parse_config_from_path parses DatabaseType."""
        self.config = [
            {**_BASE_CONFIG_WITH_PRUNE, 'database_type': enum_str_value}
        ]

        output = config_parser.get_and_parse_config_from_path(self.gcs_uri)

        first_config = output[0]
        self.assertEqual(first_config.database_type, expected_output)

    def test_get_config_parses_database_host(self):
        """Tests get_and_parse_config_from_path sets database_host."""
        self.config = [{**_BASE_CONFIG_WITH_PRUNE}]
        # Cannot set both database_host and database_instance_name.
        self.config[0]['database_instance_name'] = None
        self.config[0]['database_host'] = '127.0.0.1'

        output = config_parser.get_and_parse_config_from_path(self.gcs_uri)

        first_config = output[0]
        self.assertEqual(first_config.database_host, '127.0.0.1')
        self.assertIsNone(first_config.database_instance_name)

    def test_get_config_parses_database_password_secret(self):
        """Tests get_and_parse_config_from_path sets db password secret."""
        self.config = [{**_BASE_CONFIG_WITH_PRUNE}]
        # Cannot set both database_password and database_password_secret.
        self.config[0]['database_password'] = None
        self.config[0][
            'database_password_secret'
        ] = '/project/123/secret/abc/version/1'

        output = config_parser.get_and_parse_config_from_path(self.gcs_uri)

        first_config = output[0]
        self.assertEqual(
            first_config.database_password_secret,
            '/project/123/secret/abc/version/1',
        )
        self.assertIsNone(first_config.database_password)

    @parameterized.named_parameters(
        [
            {
                'testcase_name': 'database_prune_batch_size',
                'field_name': 'database_prune_batch_size',
                'expected_output': 1000,
            },
        ]
    )
    def test_get_config_parses_sets_default_values(
        self, field_name, expected_output
    ):
        """Tests get_and_parse_config_from_path sets default values."""
        self.config = [{**_BASE_CONFIG_WITH_PRUNE}]
        del self.config[0][field_name]

        output = config_parser.get_and_parse_config_from_path(self.gcs_uri)

        first_config = output[0]
        self.assertEqual(getattr(first_config, field_name), expected_output)

    def test_get_config_raises_bad_config_single_config(self):
        """Tests get_and_parse_config_from_path raises for single config."""
        self.config = {**_BASE_CONFIG_WITH_PRUNE}  # Single config, no list.

        with self.assertRaisesRegex(
            ValueError, 'Unable to parse configuration file. Expected a list.'
        ):
            config_parser.get_and_parse_config_from_path(self.gcs_uri)


if __name__ == '__main__':
    unittest.main()
