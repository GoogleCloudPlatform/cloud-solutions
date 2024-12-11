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

"""Tests for Cloud Function BigQuery module."""

import unittest
from unittest import mock
from database_archival.pruning_function.workflow import bigquery
from absl.testing import parameterized


class TestBigQuery(parameterized.TestCase):
    """Tests BigQuery workflow helper."""

    def setUp(self):
        """Sets up tests."""
        super().setUp()
        self.bq_client_mock = self.enter_context(
            mock.patch.object(bigquery.bigquery, 'Client', autospec=True)
        )

    def test_get_primary_keys_calls_bigquery_with_expected_values(self):
        """Tests get_primary_keys calls BigQuery with expected values."""
        self.bq_client_mock.return_value.query.return_value.destination = (
            'output_table_name'
        )

        # Must call with list() to force execution since it is only a
        # generator and will not execute othrwise.
        list(
            bigquery.get_primary_keys_to_prune_from_bigquery(
                bigquery_location='asia-southeast1',
                snapshot_progress_table_name='projectA.dataset.table_name',
                table_primary_key_columns=['id', 'key'],
                snapshot_run_id='run_123',
                snapshot_date='19900714',
                snapshot_batch=1,
            )
        )

        self.bq_client_mock.return_value.get_table.assert_called_once_with(
            'output_table_name'
        )
        self.bq_client_mock.return_value.query.assert_called_once_with(
            query=(
                'SELECT id, key '
                'FROM `projectA.dataset.table_name` '
                'WHERE NOT _is_data_pruned '
                'AND _snapshot_run_id = "run_123" '
                'AND _prune_batch_number = 1 '
                'AND _snapshot_date = PARSE_DATE("%Y%m%d", "19900714")'
            ),
            project='projectA',
            location='asia-southeast1',
        )

    def test_get_primary_keys_returns_primary_keys(self):
        """Tests get_primary_keys returns primary keys."""
        self.bq_client_mock.return_value.query.return_value.destination = (
            'output_table_name'
        )
        rows = [
            {
                'id': 1,
                'key': 'abc',
            },
            {
                'id': 2,
                'key': 'xyz',
            },
        ]
        self.bq_client_mock.return_value.list_rows.return_value = rows

        output = list(
            bigquery.get_primary_keys_to_prune_from_bigquery(
                bigquery_location='asia-southeast1',
                snapshot_progress_table_name='projectA.dataset.table_name',
                table_primary_key_columns=['id', 'key'],
                snapshot_run_id='run_123',
                snapshot_date='19900714',
                snapshot_batch=1,
            )
        )

        self.assertEqual(output, rows)

    @parameterized.parameters(None, '', 123)
    def test_get_primary_keys_asserts_bad_bigquery_location(
        self, bigquery_location
    ):
        """Tests get_primary_keys asserts for bad bigquery_location."""
        with self.assertRaisesRegex(ValueError, 'bigquery_location'):
            # Must call with list() to force execution since it is only a
            # generator and will not execute othrwise.
            list(
                bigquery.get_primary_keys_to_prune_from_bigquery(
                    bigquery_location=bigquery_location,
                    snapshot_progress_table_name='project.dataset.table_name',
                    table_primary_key_columns=['id', 'key'],
                    snapshot_run_id='run_123',
                    snapshot_date='19900714',
                    snapshot_batch=1,
                )
            )

    @parameterized.parameters(None, '', 123)
    def test_get_primary_keys_asserts_bad_snapshot_progress_table_name(
        self, snapshot_progress_table_name
    ):
        """Tests get_primary_keys asserts bad snapshot_progress_table_name."""
        with self.assertRaisesRegex(ValueError, 'snapshot_progress_table_name'):
            # Must call with list() to force execution since it is only a
            # generator and will not execute othrwise.
            list(
                bigquery.get_primary_keys_to_prune_from_bigquery(
                    bigquery_location='asia-southeast1',
                    snapshot_progress_table_name=snapshot_progress_table_name,
                    table_primary_key_columns=['id', 'key'],
                    snapshot_run_id='run_123',
                    snapshot_date='19900714',
                    snapshot_batch=1,
                )
            )

    def test_get_primary_keys_asserts_bad_table_format(self):
        """Tests get_primary_keys asserts bad snapshot table format."""
        with self.assertRaisesRegex(
            ValueError, 'format of "<project_id>.<dataset_id>.<table_id>"'
        ):
            # Must call with list() to force execution since it is only a
            # generator and will not execute othrwise.
            list(
                bigquery.get_primary_keys_to_prune_from_bigquery(
                    bigquery_location='asia-southeast1',
                    snapshot_progress_table_name='table_name',  # Tested value.
                    table_primary_key_columns=['id', 'key'],
                    snapshot_run_id='run_123',
                    snapshot_date='19900714',
                    snapshot_batch=1,
                )
            )

    @parameterized.parameters(
        {'table_primary_key_columns': None},
        {'table_primary_key_columns': []},
        {'table_primary_key_columns': 123},
    )
    def test_get_primary_keys_asserts_bad_table_primary_key_columns(
        self, table_primary_key_columns
    ):
        """Tests get_primary_keys asserts for bad table_primary_key_columns."""
        with self.assertRaisesRegex(ValueError, 'table_primary_key_columns'):
            # Must call with list() to force execution since it is only a
            # generator and will not execute othrwise.
            list(
                bigquery.get_primary_keys_to_prune_from_bigquery(
                    bigquery_location='asia-southeast1',
                    snapshot_progress_table_name='project.dataset.table_name',
                    table_primary_key_columns=table_primary_key_columns,
                    snapshot_run_id='run_123',
                    snapshot_date='19900714',
                    snapshot_batch=1,
                )
            )

    @parameterized.parameters(None, '', 123)
    def test_get_primary_keys_asserts_bad_snapshot_run_id(
        self, snapshot_run_id
    ):
        """Tests get_primary_keys asserts for bad snapshot_run_id."""
        with self.assertRaisesRegex(ValueError, 'snapshot_run_id'):
            # Must call with list() to force execution since it is only a
            # generator and will not execute othrwise.
            list(
                bigquery.get_primary_keys_to_prune_from_bigquery(
                    bigquery_location='asia-southeast1',
                    snapshot_progress_table_name='project.dataset.table_name',
                    table_primary_key_columns=['id', 'key'],
                    snapshot_run_id=snapshot_run_id,
                    snapshot_date='19900714',
                    snapshot_batch=1,
                )
            )

    @parameterized.parameters(None, '', 123)
    def test_get_primary_keys_asserts_bad_snapshot_date(self, snapshot_date):
        """Tests get_primary_keys asserts for bad snapshot_date."""
        with self.assertRaisesRegex(ValueError, 'snapshot_date'):
            # Must call with list() to force execution since it is only a
            # generator and will not execute othrwise.
            list(
                bigquery.get_primary_keys_to_prune_from_bigquery(
                    bigquery_location='asia-southeast1',
                    snapshot_progress_table_name='project.dataset.table_name',
                    table_primary_key_columns=['id', 'key'],
                    snapshot_run_id='run_123',
                    snapshot_date=snapshot_date,
                    snapshot_batch=1,
                )
            )

    @parameterized.parameters(None, -1, '4')
    def test_get_primary_keys_asserts_bad_snapshot_batch(self, snapshot_batch):
        """Tests get_primary_keys asserts for bad snapshot_batch."""
        with self.assertRaisesRegex(ValueError, 'snapshot_batch'):
            # Must call with list() to force execution since it is only a
            # generator and will not execute otherwise.
            list(
                bigquery.get_primary_keys_to_prune_from_bigquery(
                    bigquery_location='asia-southeast1',
                    snapshot_progress_table_name='project.dataset.table_name',
                    table_primary_key_columns=['id', 'key'],
                    snapshot_run_id='run_123',
                    snapshot_date='19900714',
                    snapshot_batch=snapshot_batch,
                )
            )


if __name__ == '__main__':
    unittest.main()
