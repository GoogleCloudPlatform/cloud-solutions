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

"""Provides TablePruneConfig to get configuration for database pruning."""

from database_archival.common.utils import config_validator
from database_archival.common.models import database
from typing import Optional


class TablePruneConfig:
    """Data pruning configuration for one table."""

    def __init__(
        self,
        *,
        bigquery_location: str,
        snapshot_progress_table_name: str,
        snapshot_run_id: str,
        snapshot_date: str,
        snapshot_batch: int,
        database_table_name: str,
        table_primary_key_columns: str,
        database_type: str,
        database_instance_name: Optional[str] = None,
        database_host: Optional[str] = None,
        database_name: str,
        database_username: str,
        database_password: Optional[str] = None,
        database_password_secret: Optional[str] = None,
    ):
        """Initializes and validates TablePruneConfig.

        Args:
            bigquery_location: location where the BigQuery tables are located
                and where BigQuery jobs will be run.
            snapshot_progress_table_name: name of the BigQuery table where the
                data to be pruned is stored.
            snapshot_run_id: DAG run id for this batch.
            snapshot_date: date of the run for this batch.
            snapshot_batch: number of the batch to delete.
            database_table_name: table where data will be pruned.
            table_primary_key_columns: list of all the column names that are
                used as the primary key for this table.
            database_type: type of database where data is stored. Must be one
                of the values in DatabaseType in string format.
            database_instance_name: name of the instance where data will be
                pruned.
                AlloyDB Format:
                    projects/<project_id>/locations/<region_id>/
                    clusters/<cluster_id>/instances/<instance_id>
                Cloud SQL Format:
                    <project_id>:<region_id>:<instance_name>
            database_host: host of the database instance where data will be
                pruned.
            database_name: name of the database where archiving will happen.
            database_username: username to connect to the database.
            database_password: password for the given user.
            database_password: password for the given user, stored in Secrets
                Manager. Format:
                "projects/<projectId>/secrets/<secretId>/versions/<versionId>".

        Raises:
            ValueError: database_host or database_instance_name must be set.
            ValueError: database_host and database_instance_name cannot both be
                set.
        """
        config_validator.assert_is_valid_string(
            bigquery_location, 'bigquery_location'
        )
        self.bigquery_location = bigquery_location

        config_validator.assert_is_valid_string(
            snapshot_progress_table_name,
            'snapshot_progress_table_name',
        )
        self.snapshot_progress_table_name = snapshot_progress_table_name

        config_validator.assert_is_valid_string(snapshot_date, 'snapshot_date')
        self.snapshot_date = snapshot_date

        config_validator.assert_is_valid_string(
            snapshot_run_id, 'snapshot_run_id'
        )
        self.snapshot_run_id = snapshot_run_id

        config_validator.assert_is_positive_integer(
            snapshot_batch, 'snapshot_batch'
        )
        self.snapshot_batch = snapshot_batch

        config_validator.assert_is_valid_enum_string(
            database_type, 'database_type', database.DatabaseType
        )
        self.database_type = database.DatabaseType[database_type.upper()]

        if not database_host and not database_instance_name:
            raise ValueError(
                'database_host or database_instance_name must be provided.'
            )
        elif database_host and database_instance_name:
            raise ValueError(
                'Only database_host or database_instance_name can be used at '
                'one time. Choose one of the two.'
            )
        elif database_host:
            config_validator.assert_is_valid_string(
                database_host, 'database_host'
            )
            self.database_host = database_host
            self.database_instance_name = None
        elif database_instance_name:
            config_validator.assert_is_valid_string(
                database_instance_name, 'database_instance_name'
            )
            self.database_instance_name = database_instance_name
            self.database_host = None

        config_validator.assert_is_valid_string(database_name, 'database_name')
        self.database_name = database_name

        config_validator.assert_is_valid_string(
            database_username, 'database_username'
        )
        self.database_username = database_username

        if not database_password and not database_password_secret:
            raise ValueError(
                'database_password or database_password_secret must be '
                'provided.'
            )
        elif database_password and database_password_secret:
            raise ValueError(
                'Only database_password or database_password_secret can be '
                'used at one time. Choose one of the two.'
            )
        elif database_password:
            config_validator.assert_is_valid_string(
                database_password, 'database_password'
            )
            self.database_password = database_password
            self.database_password_secret = None
        elif database_password_secret:
            config_validator.assert_is_valid_string(
                database_password_secret, 'database_password_secret'
            )
            self.database_password_secret = database_password_secret
            self.database_password = None

        config_validator.assert_is_valid_string(
            database_table_name, 'database_table_name'
        )
        self.database_table_name = database_table_name

        config_validator.assert_is_valid_list(
            table_primary_key_columns, 'table_primary_key_columns'
        )
        for field in table_primary_key_columns:
            config_validator.assert_is_valid_string(
                field, 'Element in table_primary_key_columns'
            )
        self.table_primary_key_columns = table_primary_key_columns
