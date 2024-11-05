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

"""Tests the GCS to AlloyDB Dataflow template."""

import datetime
from typing import Sequence
import unittest
from unittest import mock

from absl.testing import parameterized
import dataflow_gcs_to_alloydb
import sqlalchemy
from testcontainers import postgres


_TEST_POSTGRES_CONTAINER = 'postgres:15'
_POSTGRES_INTERNAL_PORT = 5432


class TestPipelineBase(parameterized.TestCase):
    """Base TestPipeline for all unit tests."""

    def _get_flags_as_argv(self) -> Sequence[str]:
        """Gets self.flags in argv[] format.

        When passed to run(), this allows to pass argument flags to the
        pipeline. Each test can change self.test_pipeline_flags before calling
        this method for testing with different flags.

        Returns:
          Arguments in list format.
          E.g. ['--flags_name', 'value', '--next_flag', 'next_value, ...]
        """
        argv_flags = []
        for flag_name, flag_value in self.test_pipeline_flags.items():
            argv_flags.extend((f'--{flag_name}', flag_value))
        return argv_flags


class TestPipelineSetUp(TestPipelineBase):
    """Tests pipeline setup."""

    def setUp(self):
        super().setUp()
        self.test_pipeline_flags = {
            # Must specify input_file_pattern on your test.
            # 'input_file_pattern': './testadata/*.csv',
            # Unused for pipeline validation tests.
            'input_file_format': 'csv',
            'input_schema': 'id:int64;first_name:string',
            'input_csv_file_delimiter': ',',
            'input_file_contains_headers': '1',
            'alloydb_ip': '127.0.0.1',
            'alloydb_port': '5432',
            'alloydb_database': 'postgres',
            'alloydb_user': 'postgres',
            'alloydb_password': '',
            'alloydb_table': 'test_table',
        }

        self.storage_client_mock = self.enter_context(
            mock.patch.object(
                dataflow_gcs_to_alloydb.storage, 'Client', autospec=True
            )
        )
        self.bucket_mock = self.enter_context(
            mock.patch.object(
                dataflow_gcs_to_alloydb.storage.bucket, 'Bucket', autospec=True
            )
        )
        self.storage_client_mock.return_value.bucket.return_value = (
            self.bucket_mock
        )

        # Prevent the pipeline for running.
        # The pipeline is tested in the TestPipelineRun suite.
        self.enter_context(
            mock.patch.object(
                dataflow_gcs_to_alloydb.beam, 'Pipeline', autospec=True
            )
        )
        self.enter_context(
            mock.patch.object(
                dataflow_gcs_to_alloydb.beam.io, 'ReadFromText', autospec=True
            )
        )

    def test_validate_options_skips_for_local_file(self):
        """Tests that validate options ignore local files."""
        self.test_pipeline_flags.update(
            {
                'input_file_pattern': './testdata/test1/data.csv',
            }
        )

        dataflow_gcs_to_alloydb.run(argv=self._get_flags_as_argv())

        self.assertFalse(self.storage_client_mock.called)

    def test_validate_options_raises_if_bucket_name_not_found(self):
        self.test_pipeline_flags.update(
            {
                'input_file_pattern': 'gs://',
            }
        )

        with self.assertRaisesRegex(
            ValueError, 'GCS path must be in the form gs://<bucket>/<object>.'
        ):
            dataflow_gcs_to_alloydb.run(argv=self._get_flags_as_argv())

    @parameterized.named_parameters(
        {
            'testcase_name': 'glob_only',
            'input_file_pattern': 'gs://my-bucket/*.avro',
            'expected_prefix': '',
            'expected_glob': '*.avro',
        },
        {
            'testcase_name': 'filename_only',
            'input_file_pattern': 'gs://my-bucket/file.avro',
            'expected_prefix': '',
            'expected_glob': 'file.avro',
        },
        {
            'testcase_name': 'path_and_filename',
            'input_file_pattern': 'gs://my-bucket/file-path/file.avro',
            'expected_prefix': 'file-path/',
            'expected_glob': 'file.avro',
        },
        {
            'testcase_name': 'path_and_glob',
            'input_file_pattern': 'gs://my-bucket/abc/def/g-h_i/*.csv',
            'expected_prefix': 'abc/def/g-h_i/',
            'expected_glob': '*.csv',
        },
        {
            'testcase_name': 'mixed_path_and_glob',
            'input_file_pattern': 'gs://my-bucket/abc/*/def/file.csv',
            'expected_prefix': 'abc/',
            'expected_glob': '*/def/file.csv',
        },
        {
            'testcase_name': 'square_glob',
            'input_file_pattern': 'gs://my-bucket/[abc]/def/file.csv',
            'expected_prefix': '',
            'expected_glob': '[abc]/def/file.csv',
        },
        {
            'testcase_name': 'question_glob',
            'input_file_pattern': 'gs://my-bucket/a-b-c/?/*.avro',
            'expected_prefix': 'a-b-c/',
            'expected_glob': '?/*.avro',
        },
    )
    def test_validate_options_checks_gcs_expected_paths(
        self, input_file_pattern, expected_prefix, expected_glob
    ):
        self.bucket_mock.list_blobs.return_value = ['file1.csv']
        self.test_pipeline_flags.update(
            {
                'input_file_pattern': input_file_pattern,
            }
        )

        dataflow_gcs_to_alloydb.run(argv=self._get_flags_as_argv())

        self.storage_client_mock.return_value.bucket.assert_called_once_with(
            'my-bucket'
        )
        self.bucket_mock.list_blobs.assert_called_once_with(
            prefix=expected_prefix, match_glob=expected_glob, max_results=1
        )

    def test_validate_options_continues_when_files_are_matched(self):
        self.bucket_mock.list_blobs.return_value = ['file1.csv', 'file2.csv']
        self.test_pipeline_flags.update(
            {
                'input_file_pattern': 'gs://bucket-name/file-path/subdir/*',
            }
        )

        dataflow_gcs_to_alloydb.run(argv=self._get_flags_as_argv())

        self.storage_client_mock.return_value.bucket.assert_called_once_with(
            'bucket-name'
        )
        self.bucket_mock.list_blobs.assert_called_once_with(
            prefix='file-path/subdir/', match_glob='*', max_results=1
        )

    def test_validate_options_raises_if_no_files_found(self):
        self.bucket_mock.list_blobs.return_value = []
        self.test_pipeline_flags.update(
            {
                'input_file_pattern': 'gs://my-bucket/file-path/no-match/*',
            }
        )

        with self.assertRaisesRegex(ValueError, 'No files matching pattern'):
            dataflow_gcs_to_alloydb.run(argv=self._get_flags_as_argv())


class TestPipelineRun(TestPipelineBase):
    """Tests Dataflow template."""

    def setUp(self):
        super().setUp()
        self.postgres_container = postgres.PostgresContainer(
            image=_TEST_POSTGRES_CONTAINER,
            port=_POSTGRES_INTERNAL_PORT,
            driver='pg8000',
            username='postgres_user',
            password='strong_and_safe_password',
            dbname='postgres_db',
        )
        self.postgres_container.start()
        self.addCleanup(self.postgres_container.stop)

        db_url = self.postgres_container.get_connection_url()
        self.db_connection = sqlalchemy.create_engine(db_url).connect()
        self.addCleanup(self.db_connection.close)

        self.test_pipeline_flags = {
            # Must specify input_file_format on your test.
            # 'input_file_format': 'csv',
            # Must specify input_file_pattern on your test.
            # 'input_file_pattern': './testadata/*.csv',
            # Must speficy input_file_schema on your test.
            # 'input_schema': 'id:int64;first_name:string',
            'input_csv_file_delimiter': ',',
            'input_file_contains_headers': '1',
            'alloydb_ip': self.postgres_container.get_container_host_ip(),
            'alloydb_port': str(
                self.postgres_container.get_exposed_port(
                    _POSTGRES_INTERNAL_PORT
                )
            ),
            'alloydb_database': self.postgres_container.dbname,
            'alloydb_user': self.postgres_container.username,
            'alloydb_password': self.postgres_container.password,
            # Must specify alloydb_table.
            # Example: 'alloydb_table': 'test_table',
        }

    def _run_query_on_test_db(
        self, sql_query: str
    ) -> Sequence[sqlalchemy.engine.Row]:
        """Runs a SQL query in the test DB.

        Args:
          sql_query: SQL query in string format.

        Returns:
          Results from the query.
        """
        results = self.db_connection.execute(sqlalchemy.text(sql_query))
        return results.fetchall()

    def _create_schema_from_file(self, sql_file_path: str):
        """Runs a query to create schema stored in a SQL file.

        Args:
          sql_file_path: SQL file with the schema for the test.
        """
        with open(sql_file_path, mode='r', encoding='utf-8') as sql_file:
            self.db_connection.execute(sqlalchemy.text(sql_file.read()))
            self.db_connection.commit()

    @parameterized.named_parameters(
        {'testcase_name': 'csv', 'file_format': 'csv'},
        {'testcase_name': 'avro', 'file_format': 'avro'},
    )
    def test_pipeline_runs(self, file_format):
        """Tests that the pipeline runs without errors."""
        self._create_schema_from_file('testdata/test1/schema.sql')
        self.test_pipeline_flags.update(
            {
                'alloydb_table': 'employees',
                'input_file_format': file_format,
                'input_file_pattern': f'./testdata/test1/data.{file_format}',
                'input_schema': ';'.join(
                    [
                        'id:int64',
                        'first_name:string',
                        'last_name:string',
                        'department:string',
                        'salary:float',
                        'hire_date:string',
                    ]
                ),
            }
        )

        dataflow_gcs_to_alloydb.run(argv=self._get_flags_as_argv())

    @parameterized.named_parameters(
        {'testcase_name': 'csv', 'file_format': 'csv'},
        {'testcase_name': 'avro', 'file_format': 'avro'},
    )
    def test_pipeline_writes_data_to_database(self, file_format):
        """Tests that the pipeline writes data to the database."""
        self._create_schema_from_file('testdata/test1/schema.sql')
        self.test_pipeline_flags.update(
            {
                'alloydb_table': 'employees',
                'input_file_format': file_format,
                'input_file_pattern': f'./testdata/test1/data.{file_format}',
                'input_schema': ';'.join(
                    [
                        'id:int64',
                        'first_name:string',
                        'last_name:string',
                        'department:string',
                        'salary:float',
                        'hire_date:string',
                    ]
                ),
            }
        )

        dataflow_gcs_to_alloydb.run(argv=self._get_flags_as_argv())

        count_results = self._run_query_on_test_db(
            'SELECT COUNT(*) AS count_rows FROM employees'
        )
        num_rows = count_results[0][0]
        self.assertEqual(num_rows, 20)

        result_id_1 = self._run_query_on_test_db(
            """
            SELECT
              id, first_name, last_name, department, salary, hire_date
            FROM
              employees
            WHERE
              id = 1
            """
        )[0]
        self.assertEqual(result_id_1[0], 1)  # id
        self.assertEqual(result_id_1[1], 'John')  # first_name
        self.assertEqual(result_id_1[2], 'Doe')  # last_name
        self.assertEqual(result_id_1[3], 'Sales')  # department
        self.assertEqual(result_id_1[4], 75000.00)  # salary
        self.assertEqual(
            result_id_1[5], datetime.date(2023, 1, 15)
        )  # hire_date

    @parameterized.named_parameters(
        {'testcase_name': 'csv', 'file_format': 'csv'},
        {'testcase_name': 'avro', 'file_format': 'avro'},
    )
    def test_pipeline_writes_data_from_multiple_csv_files(self, file_format):
        """Tests that the pipeline writes data from multiple files."""
        self._create_schema_from_file('testdata/test2/schema.sql')
        self.test_pipeline_flags.update(
            {
                'alloydb_table': 'employees',
                'input_file_format': file_format,
                'input_file_pattern': f'./testdata/test2/*.{file_format}',
                'input_schema': ';'.join(
                    [
                        'id:int64',
                        'first_name:string',
                        'last_name:string',
                        'department:string',
                        'salary:float',
                        'hire_date:string',
                    ]
                ),
            }
        )

        dataflow_gcs_to_alloydb.run(argv=self._get_flags_as_argv())

        count_results = self._run_query_on_test_db(
            'SELECT COUNT(*) AS count_rows FROM employees'
        )
        num_rows = count_results[0][0]
        self.assertEqual(num_rows, 15)

    @parameterized.named_parameters(
        {'testcase_name': 'csv', 'file_format': 'csv'},
        {'testcase_name': 'avro', 'file_format': 'avro'},
    )
    def test_pipeline_writes_data_for_different_data_types(self, file_format):
        """Tests that the pipeline writes data for all/most data types."""
        self._create_schema_from_file('testdata/test3/schema.sql')
        self.test_pipeline_flags.update(
            {
                'alloydb_table': 'data_types_test',
                'input_file_format': file_format,
                'input_file_pattern': f'./testdata/test3/*.{file_format}',
                'input_schema': ';'.join(
                    [
                        'integer_field:int32',
                        'bigint_field:int64',
                        'boolean_field:bool',
                        'char_field:string',
                        'varchar_field:string',
                        'date_field:string',
                        'double_field:float64',
                        'macaddr_field:string',
                        'numeric_field:float64',
                        'point_field:string',
                        'real_field:float32',
                        'smallint_field:int16',
                        'text_field:string',
                        'timestamp_field:string',
                    ]
                ),
            }
        )

        dataflow_gcs_to_alloydb.run(argv=self._get_flags_as_argv())

        count_results = self._run_query_on_test_db(
            'SELECT COUNT(*) AS count_rows FROM data_types_test'
        )
        num_rows = count_results[0][0]
        self.assertEqual(num_rows, 5)
        sample_row = self._run_query_on_test_db(
            """
            SELECT
              integer_field, bigint_field, boolean_field, char_field,
              varchar_field, date_field, double_field, macaddr_field,
              numeric_field, point_field, real_field, smallint_field,
              text_field, timestamp_field
            FROM
              data_types_test
            ORDER BY
              integer_field
            """
        )[0]
        self.assertEqual(sample_row[0], 1)  # integer_field
        self.assertEqual(sample_row[1], 9223372036854775807)  # bigint_field
        self.assertEqual(sample_row[2], False)  # boolean_field
        self.assertEqual(sample_row[3], 'abcdefghij')  # char_field
        self.assertEqual(sample_row[4], 'vwxyz12345')  # varchar_field
        self.assertEqual(
            sample_row[5], datetime.date(2023, 11, 28)
        )  # date_field
        self.assertEqual(sample_row[6], 3.14159)  # double_field
        self.assertEqual(sample_row[7], '08:00:2b:01:02:03')  # macaddr_field
        self.assertEqual(sample_row[8], 123)  # numeric_field
        self.assertEqual(sample_row[9], (1, 2))  # point_field
        self.assertEqual(sample_row[10], 2.71828)  # real_field
        self.assertEqual(sample_row[11], 32767)  # smallint_field
        self.assertEqual(
            sample_row[12], 'This is some sample text'
        )  # text_field
        self.assertEqual(
            sample_row[13], datetime.datetime(2024, 6, 10, 12, 17)
        )  # timestamp_field

    @parameterized.named_parameters(
        {'testcase_name': 'csv', 'file_format': 'csv'},
        {'testcase_name': 'avro', 'file_format': 'avro'},
    )
    def test_pipeline_can_run_with_empty_data(self, file_format):
        """Tests that the pipeline can run with empty data.

        Note that it won't write any data to the database, but it won't fail.
        """
        self._create_schema_from_file('testdata/test4/schema.sql')
        self.test_pipeline_flags.update(
            {
                'alloydb_table': 'empty_table',
                'input_file_format': file_format,
                'input_file_pattern': f'./testdata/test4/*.{file_format}',
                'input_schema': ';'.join(['name:string']),
            }
        )

        dataflow_gcs_to_alloydb.run(argv=self._get_flags_as_argv())

        count_results = self._run_query_on_test_db(
            'SELECT COUNT(*) AS count_rows FROM empty_table'
        )
        num_rows = count_results[0][0]
        self.assertEqual(num_rows, 0)

    @parameterized.named_parameters(
        dict(
            testcase_name='without_headers',
            csv_file='data_without_headers.csv',
            input_file_contains_headers='0',
        ),
        dict(
            testcase_name='with_headers',
            csv_file='data_with_headers.csv',
            input_file_contains_headers='1',
        ),
    )
    def test_pipeline_reads_and_writes_data_with_header_settings(
        self, csv_file, input_file_contains_headers
    ):
        """Tests that the pipeline supports CSVs with/without headers."""
        self._create_schema_from_file('testdata/test5/schema.sql')
        self.test_pipeline_flags.update(
            {
                'input_file_contains_headers': input_file_contains_headers,
                'alloydb_table': 'employees',
                'input_file_format': 'csv',
                'input_file_pattern': f'./testdata/test5/{csv_file}',
                'input_schema': ';'.join(
                    [
                        'id:int64',
                        'first_name:string',
                        'last_name:string',
                        'department:string',
                        'salary:float',
                        'hire_date:string',
                    ]
                ),
            }
        )

        dataflow_gcs_to_alloydb.run(argv=self._get_flags_as_argv())

        count_results = self._run_query_on_test_db(
            'SELECT COUNT(*) AS count_rows FROM employees'
        )
        num_rows = count_results[0][0]
        self.assertEqual(num_rows, 2)
        result_id_1 = self._run_query_on_test_db(
            """
            SELECT
              id, first_name, last_name, department, salary, hire_date
            FROM
              employees
            WHERE
              id = 21
            """
        )[0]
        self.assertEqual(result_id_1[0], 21)  # id
        self.assertEqual(result_id_1[1], 'Nito')  # first_name
        self.assertEqual(result_id_1[2], 'Buendia')  # last_name
        self.assertEqual(result_id_1[3], 'Cloud')  # department
        self.assertEqual(result_id_1[4], 999.00)  # salary
        self.assertEqual(
            result_id_1[5], datetime.date(1990, 7, 14)
        )  # hire_date


if __name__ == '__main__':
    unittest.main()
