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

"""Parses and validates the request body for the pruning Cloud Function."""

import flask
import werkzeug  # Flask dependency.
from database_archival.pruning_function.models import config_model

# Redefining it to simplify code as this will be commonly used.
BadRequest = werkzeug.exceptions.BadRequest


def parse_and_validate_request_data(
    request: flask.Request,
) -> config_model.TablePruneConfig:
    """Parses and validates that the request data is as expected.

    Args:
        request: Request received from the HTTP endpoint.

    Raises:
        BadRequest: unable to parse JSON body.
        BadRequest: missing body.

    Returns:
        Parsed table configuration.
    """
    try:
        request_data = request.get_json()
    except Exception as e:
        raise werkzeug.exceptions.BadRequest(
            'Unable to parse request body as JSON.'
        ) from e

    if not request_data:
        raise werkzeug.exceptions.BadRequest('No request data detected.')

    return config_model.TablePruneConfig(
        bigquery_location=request_data.get('bigquery_location'),
        snapshot_progress_table_name=request_data.get(
            'snapshot_progress_table_name'
        ),
        snapshot_date=request_data.get('snapshot_date'),
        snapshot_batch=request_data.get('snapshot_batch'),
        snapshot_run_id=request_data.get('snapshot_run_id'),
        database_table_name=request_data.get('database_table_name'),
        table_primary_key_columns=request_data.get('table_primary_key_columns'),
        database_type=request_data.get('database_type'),
        database_instance_name=request_data.get('database_instance_name'),
        database_host=request_data.get('database_host'),
        database_name=request_data.get('database_name'),
        database_username=request_data.get('database_username'),
        database_password=request_data.get('database_password'),
        database_password_secret=request_data.get('database_password_secret'),
    )
