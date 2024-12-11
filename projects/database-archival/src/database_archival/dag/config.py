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

"""Basic configuration for the Archival and Pruning DAG."""

import os
from database_archival.common import config

# Name of the DAG.
DAG_NAME = database_url = os.environ.get('DAG_NAME', 'database_archival_dag')

# DAG schedule interval.
DAG_SCHEDULE_INTERVAL = os.environ.get('DAG_SCHEDULE_INTERVAL', None)

# Google Cloud Storage file path to the configuration file.
DATA_ARCHIVAL_CONFIG_PATH = os.environ.get(
    'DATA_ARCHIVAL_CONFIG_PATH', 'gs://bucket/file.json'
)

# Time to wait between deletes of batches.
TIME_BETWEEN_DELETE_BATCHES_IN_SECONDS = int(os.environ.get(
    'TIME_BETWEEN_DELETE_BATCHES_IN_SECONDS', 120  # 2min
))

# URL for the Cloud Function which performs the data deletion.
CLOUD_FUNCTION_URL_DATA_DELETION = os.environ.get(
    'CLOUD_FUNCTION_URL_DATA_DELETION', ''
)

# Timeout to the Cloud Function that performs database deletion.
DATABASE_TIMEOUT = int(os.environ.get(
    'DATABASE_TIMEOUT', config.DATABASE_TIMEOUT
))
