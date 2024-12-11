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

"""Provides common constants and enums for interacting with the database."""

import enum
from typing import Any, Iterable, Mapping


class DatabaseType(enum.Enum):
    """Database type."""

    ALLOYDB = 'alloydb'
    MYSQL = 'mysql'
    POSTGRES = 'postgres'
    SPANNER = 'spanner'
    SQL_SERVER = 'sql_server'


class DateColumnDataType(enum.Enum):
    """BigQuery column types for date-like fields."""

    DATE = 'DATE'
    DATETIME = 'DATETIME'
    TIMESTAMP = 'TIMESTAMP'


# Typing for the list of primary key values per row.
# Each row represents an element (Mapping) on the list. Each mapping contains
# all the primary key field names as keys and their values as the mapping value.
PrimaryKeyFilters = Iterable[Mapping[str, Any]]


# Details for snapshot tables.
FIELD_NAME_SNAPSHOT_DATE = '_snapshot_date'
FIELD_NAME_SNAPSHOT_RUN_ID = '_snapshot_run_id'
FIELD_NAME_PRUNE_BATCH = '_prune_batch_number'
FIELD_NAME_PRUNE_STATUS = '_is_data_pruned'
PRUNE_PROGRESS_TABLE_NAME_SUFFIX = '_prune_progress'
SNAPSHOT_TABLE_NAME_SUFFIX = '_snapshot'
