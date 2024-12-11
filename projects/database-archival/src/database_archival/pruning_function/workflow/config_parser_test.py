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

import unittest
import json
import flask
import werkzeug
from absl.testing import parameterized
from database_archival.common.models import database
from database_archival.pruning_function.models import config_model
from database_archival.pruning_function.workflow import config_parser
from typing import Any, Mapping, Optional


def _create_request_with_data(
    method: Optional[str] = None,
    headers: Optional[Mapping[str, Any]] = None,
    data: Optional[Mapping[str, Any]] = None,
) -> flask.Request:
    """Creates a flask request with headers, data and method.

    Args:
        method: HTTP request method.
        headers: headers for the HTTP Request.
        data: data for the HTTP request.
    """
    return flask.Request.from_values(
        headers=headers or {'Content-Type': 'application/json'},
        data=data or None,
        method=method or 'POST',
    )


class TestConfigParser(parameterized.TestCase):
    """Tests for config_parser."""

    def test_parse_and_validate_request_data_parses_data_to_table_prune_config(
        self,
    ):
        """Tests that parse_and_validate_request_data parses Request."""
        http_request = _create_request_with_data(
            data=json.dumps(
                {
                    'bigquery_location': 'asia-southeast1',
                    'snapshot_progress_table_name': (
                        'project_id.dataset.table_prune_progress'
                    ),
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
            ),
        )

        table_config = config_parser.parse_and_validate_request_data(
            http_request
        )

        self.assertIsInstance(table_config, config_model.TablePruneConfig)
        self.assertEqual(table_config.bigquery_location, 'asia-southeast1')
        self.assertEqual(
            table_config.snapshot_progress_table_name,
            'project_id.dataset.table_prune_progress',
        )
        self.assertEqual(table_config.snapshot_run_id, 'manual_run_id')
        self.assertEqual(table_config.snapshot_date, '20240101')
        self.assertEqual(table_config.snapshot_batch, 5)
        self.assertEqual(table_config.database_table_name, 'transactions')
        self.assertEqual(
            table_config.table_primary_key_columns, ['transaction_id']
        )
        self.assertEqual(
            table_config.database_type, database.DatabaseType.ALLOYDB
        )
        self.assertEqual(table_config.database_name, 'database')
        self.assertEqual(
            table_config.database_instance_name, 'project:database:instance'
        )
        self.assertEqual(table_config.database_username, 'test-username')
        self.assertEqual(table_config.database_password, 'fake-test-password')

    @parameterized.named_parameters(
        [
            {
                'testcase_name': 'no_json_data',
                'http_request': _create_request_with_data(
                    data='raw-text-body',
                ),
                'expected_error_message': (
                    'Unable to parse request body as JSON.'
                ),
            },
            {
                'testcase_name': 'no_data',
                'http_request': _create_request_with_data(data=json.dumps({})),
                'expected_error_message': 'No request data detected.',
            },
        ]
    )
    def test_parse_and_validate_request_data_raises_bad_request(
        self, http_request, expected_error_message
    ):
        """Tests that parse_and_validate_request_data raises BadRequest."""
        with self.assertRaisesRegex(
            werkzeug.exceptions.BadRequest, expected_error_message
        ):
            config_parser.parse_and_validate_request_data(http_request)


if __name__ == '__main__':
    unittest.main()
