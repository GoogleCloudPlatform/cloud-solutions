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

"""Handles (gets, parses and validates) configuration data."""

import json
import re

from google.api_core import client_info
from google.cloud import storage
from database_archival.dag.models import config_model


_ERROR_MESSAGE_INVALID_GCS_PATH = (
    'Config file should be on Google Cloud Storage with the format: '
    'gs://bucket-name/file-path/file.json.'
)


def get_and_parse_config_from_path(
    gcs_uri: str,
) -> list[config_model.TableConfig]:
    """Gets, parses and validates the file from the given Cloud Storage path.

    Args:
        gcs_uri: Google Cloud Storage URI (path) to the config file.

    Raises:
        ValueError: gcs_uri does not match expected GCS format.
        ValueError: file contents does not contain a list.

    Returns:
        List of table configurations in TableConfig format.
    """
    # TODO: add other versioned data sources for the config other than GCS.
    gcs_uri_matches = re.match('gs://(.*?)/(.*)', gcs_uri)
    if not gcs_uri_matches:
        raise ValueError(f'{_ERROR_MESSAGE_INVALID_GCS_PATH} Got: {gcs_uri}')

    bucket_name, object_name = gcs_uri_matches.groups()
    if not bucket_name or not object_name:
        raise ValueError(f'{_ERROR_MESSAGE_INVALID_GCS_PATH} Got: {gcs_uri}')

    gcs_client = storage.Client(
        client_info=client_info.ClientInfo(
            user_agent='cloud-solutions/database-archival-v1'
        )
    )
    config_file = gcs_client.bucket(bucket_name=bucket_name).blob(
        blob_name=object_name,
    )

    config_data = json.loads(config_file.download_as_bytes())

    if not isinstance(config_data, list):
        raise ValueError(
            'Unable to parse configuration file. '
            f'Expected a list. Got: {type(config_data)}.'
        )

    return [
        config_model.TableConfig(**table_config) for table_config in config_data
    ]
