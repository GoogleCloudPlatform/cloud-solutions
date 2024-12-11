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

"""Deletes data from the database. Acts as entrypoint for Cloud Function."""

import logging
import flask
import functions_framework
from database_archival.pruning_function.workflow import bigquery
from database_archival.pruning_function.workflow import database
from database_archival.pruning_function.workflow import config_parser

_LOGGER = logging.getLogger(__name__)


@functions_framework.http
def request_handler(request: flask.Request):
    """Handles the Cloud Function request, and triggers the data removal.

    Args:
      request: The HTTP request object.

    Returns:
      HTTP Response with a confirmation on whether the rows were deleted.
    """
    try:
        table_config = config_parser.parse_and_validate_request_data(request)

        primary_keys_to_delete = list(
            bigquery.get_primary_keys_to_prune_from_bigquery(
                bigquery_location=table_config.bigquery_location,
                snapshot_progress_table_name=(
                    table_config.snapshot_progress_table_name
                ),
                table_primary_key_columns=(
                    table_config.table_primary_key_columns
                ),
                snapshot_run_id=table_config.snapshot_run_id,
                snapshot_date=table_config.snapshot_date,
                snapshot_batch=table_config.snapshot_batch,
            )
        )

        if not primary_keys_to_delete:
            warning_message = (
                'No primary keys found to delete. '
                'Is this an issue or was the data already deleted?'
            )
            _LOGGER.warning(warning_message)
            return flask.jsonify(
                {
                    'success': True,
                    'rows_retrieved': 0,
                    'rows_deleted': 0,
                    'full_delete': True,
                    'warning': warning_message,
                }
            )

        delete_results = database.delete_rows_from_database(
            database_type=table_config.database_type,
            database_instance_name=table_config.database_instance_name,
            database_host=table_config.database_host,
            database_name=table_config.database_name,
            database_username=table_config.database_username,
            database_password=table_config.database_password,
            database_password_secret=table_config.database_password_secret,
            database_table_name=table_config.database_table_name,
            table_primary_key_columns=table_config.table_primary_key_columns,
            primary_keys_to_delete=primary_keys_to_delete,
        )
        _LOGGER.info(
            'Deleted %s from the database.', str(delete_results.rowcount)
        )

        return flask.jsonify(
            {
                'success': True,
                'rows_retrieved': len(primary_keys_to_delete),
                'rows_deleted': delete_results.rowcount,
                'full_delete': (
                    delete_results.rowcount == len(primary_keys_to_delete)
                ),
            }
        )

    # pylint: disable-next=broad-exception-caught
    except Exception as e:
        _LOGGER.error('Exception: %s', str(e))
        return flask.make_response(
            (
                flask.jsonify({'success': False}),
                400,  # Status code.
            )
        )
