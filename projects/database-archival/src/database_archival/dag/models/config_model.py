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

"""Provides the TableConfig syntax for the DAG."""

from database_archival.common.utils import config_validator
from database_archival.common.models import database
from typing import Any, Iterable, Optional


def _assert_value_is_set_but_prune_is_false(field_value: Any, field_name: str):
    """Validates that the field is not set or raises error.

    Args:
        field_value: value of the field to validate.
        field_name: name of the field to validate.

    Raises:
        ValueError: field is set (i.e. not None).
    """
    if field_value is not None:
        raise ValueError(
            f'{field_name} was set but database_prune_data is False. '
            'This setting will be ignored. '
            'Did you mean to enable data pruning?'
        )


class TableConfig:
    """Data archival configuration for one table."""

    def __init__(
        self,
        bigquery_location: str,
        bigquery_table_name: str,
        bigquery_days_to_keep: int,
        database_table_name: str,
        database_prune_data: bool,
        table_primary_key_columns: Iterable[str] = None,
        table_date_column: Optional[str] = None,
        table_date_column_data_type: Optional[str] = None,
        database_prune_batch_size: Optional[int] = 1000,
        database_days_to_keep: Optional[int] = None,
        database_type: Optional[str] = None,
        database_instance_name: Optional[str] = None,
        database_host: Optional[str] = None,
        database_name: Optional[str] = None,
        database_username: Optional[str] = None,
        database_password: Optional[str] = None,
        database_password_secret: Optional[str] = None,
    ):
        """Initializes and validates TableConfig.

        Args:
            bigquery_location: location where the BigQuery tables are located
                and where BigQuery jobs will be run.
            bigquery_table_name: name of the BigQuery table where the data is
                currently copied via Datastream. Data to be archived will be
                copied from this table.
            bigquery_days_to_keep: for how many days the archived data should be
                kept. The table copy/snapshot will be kept for this amount of
                time.
            database_table_name: Table name in the database from which the data
                will be pruned (if database_prune_data is True). Required even
                when data is not pruned to differentiate tasks within the DAG.
            database_prune_data: Whether to prune the data on the database.
            table_primary_key_columns: list of all the column names that are
                used as the primary key for this table. Required only if
                database_prune_data is True.
            table_date_column: name of the column which contains the date that
                will be used to determine whether the data will be archived.
                Required only if database_prune_data is True.
            table_date_column_data_type: format of the date column. Must use
                one of these BigQuery data types on DateColumnDataType in string
                format. Required only if database_prune_data is True.
            database_prune_batch_size: how many rows to delete on each
                iteration. Using larger numbers may speed up the overall
                process, but may put additional pressure on the database.
                Recommended to keep between 100 and 1,000 rows. Only used when
                database_prune_data is True.
            database_days_to_keep: for how many days the data should be kept
                in the database. Rows whose date_column is older than this
                number of days will be pruned. Required only if
                database_prune_data is True.
            database_type: type of database where data is stored. Must be one
                of the values in DatabaseType in string format. Required only if
                database_prune_data is True.
            database_instance_name: database instance name where data will be
                pruned. Required only if database_prune_data is True.
                AlloyDB Format:
                    projects/<project_id>/locations/<region_id>/
                    clusters/<cluster_id>/instances/<instance_id>
                Cloud SQL Format:
                    <project_id>:<region_id>:<instance_name>
            database_host: host of the database instance where data will be
                pruned. Required only if database_prune_data is True.
            database_name: name of the database where archiving will happen.
                Required only if database_prune_data is True.
            database_username: username to connect to the database.
                Required only if database_prune_data is True.
            database_password: password for the given user.
                Required only if database_prune_data is True.
            database_password_secret: password for the given user, stored in
                Secret Manager. Format:
                "projects/<projectId>/secrets/<secretId>/versions/<versionId>".
                Required only if database_prune_data is True.

        Raises:
            ValueError: bigquery_location is not a valid string.
            ValueError: bigquery_table_name is not a valid string.
            ValueError: bigquery_days_to_keep is not a positive integer.
            ValueError: database_table_name is not a valid string.
            ValueError: database_prune_data is not a valid boolean.

            ValueError: database_prune_batch_size is not a positive integer
                when database_prune_data is True.
            ValueError: table_primary_key_columns is not a valid list of
                strings when database_prune_data is True.
            ValueError: table_date_column is not a valid string when
                database_prune_data is True.
            ValueError: table_date_column_data_type is not a valid
                DateColumnDataType when database_prune_data is True.
            ValueError: database_days_to_keep is not a positive integer when
                database_prune_data is True.
            ValueError: database_type is not a valid DatabaseType when
                database_prune_data is True.
            ValueError: database_host or database_instance_name are required.
            ValueError: database_host and database_instance_name cannot be both
                set.
            ValueError: database_instance_name is not a valid string when
                database_prune_data is True.
            ValueError: database_host is not a valid string when
                database_prune_data is True.
            ValueError: database_name is not a valid string when
                database_prune_data is True.
            ValueError: database_username is not a valid string when
                database_prune_data is True.
            ValueError: database_password or database_password_secret are
                required.
            ValueError: database_password and database_password_secret cannot be
                both set.
            ValueError: database_password is not a valid string when
                database_prune_data is True.
            ValueError: database_password_secret is not a valid string when
                database_prune_data is True.

            ValueError: database_days_to_keep is set when database_prune_data is
                False.
            ValueError: table_primary_key_columns is set when
                database_prune_data is False.
            ValueError: table_date_column is set when database_prune_data is
                False.
            ValueError: table_date_column_data_type is set when
                database_prune_data is False.
            ValueError: database_type is set when database_prune_data is False.
            ValueError: database_instance_name is set when database_prune_data
                is False.
            ValueError: database_host is set when database_prune_data is False.
            ValueError: database_name is set when database_prune_data is False.
            ValueError: database_username is set when database_prune_data is
                False.
            ValueError: database_password is set when database_prune_data is
                False.
            ValueError: database_password_secret is set when database_prune_data
                is False.
        """
        config_validator.assert_is_valid_string(
            bigquery_location, 'bigquery_location'
        )
        self.bigquery_location = bigquery_location

        config_validator.assert_is_valid_string(
            bigquery_table_name, 'bigquery_table_name'
        )
        self.bigquery_table_name = bigquery_table_name

        config_validator.assert_is_positive_integer(
            bigquery_days_to_keep, 'bigquery_days_to_keep'
        )
        self.bigquery_days_to_keep = bigquery_days_to_keep

        config_validator.assert_is_valid_string(
            database_table_name, 'database_table_name'
        )
        self.database_table_name = database_table_name

        config_validator.assert_is_valid_boolean(
            database_prune_data, 'database_prune_data'
        )
        self.database_prune_data = database_prune_data

        if database_prune_data:
            config_validator.assert_is_positive_integer(
                database_prune_batch_size, 'database_prune_batch_size'
            )
            self.database_prune_batch_size = database_prune_batch_size

            config_validator.assert_is_valid_list(
                table_primary_key_columns, 'table_primary_key_columns'
            )
            for field in table_primary_key_columns:
                config_validator.assert_is_valid_string(
                    field, 'Element in table_primary_key_columns'
                )
            self.table_primary_key_columns = table_primary_key_columns

            config_validator.assert_is_valid_string(
                table_date_column, 'table_date_column'
            )
            self.table_date_column = table_date_column

            config_validator.assert_is_valid_enum_string(
                table_date_column_data_type,
                'table_date_column_data_type',
                database.DateColumnDataType,
            )
            self.table_date_column_data_type = database.DateColumnDataType[
                table_date_column_data_type.upper()
            ]

            config_validator.assert_is_positive_integer(
                database_days_to_keep, 'database_days_to_keep'
            )
            self.database_days_to_keep = database_days_to_keep

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
                    'Only database_host or database_instance_name can be used '
                    'at one time. Choose one of the two.'
                )
            elif database_instance_name:
                config_validator.assert_is_valid_string(
                    database_instance_name, 'database_instance_name'
                )
                if len(database_instance_name.split(':')) != 3:
                    raise ValueError(
                        'database_instance_name must follow '
                        '"<projectId>:<regionId>:<instanceName>" format. '
                        f'Got: {database_instance_name}.'
                    )
                self.database_instance_name = database_instance_name
                self.database_host = None
            elif database_host:
                config_validator.assert_is_valid_string(
                    database_host, 'database_host'
                )
                self.database_host = database_host
                self.database_instance_name = None

            config_validator.assert_is_valid_string(
                database_name, 'database_name'
            )
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

        else:
            # Raises error even if value could be ignored. This is because this
            # program deals with data deletion which is a sensitive topic. As a
            # result, conflicting information shall result in a hard error to
            # ensure the user has configured the parameters as intended.

            # Do not raise for database_prune_batch_size since we are setting a
            # default value even when None is passed.
            self.database_prune_batch_size = None

            _assert_value_is_set_but_prune_is_false(
                database_days_to_keep, 'database_days_to_keep'
            )
            self.database_days_to_keep = None

            _assert_value_is_set_but_prune_is_false(
                table_primary_key_columns, 'table_primary_key_columns'
            )
            self.table_primary_key_columns = None

            _assert_value_is_set_but_prune_is_false(
                table_date_column, 'table_date_column'
            )
            self.table_date_column = None

            _assert_value_is_set_but_prune_is_false(
                table_date_column_data_type, 'table_date_column_data_type'
            )
            self.table_date_column_data_type = None

            _assert_value_is_set_but_prune_is_false(
                database_type, 'database_type'
            )
            self.database_type = None

            _assert_value_is_set_but_prune_is_false(
                database_instance_name, 'database_instance_name'
            )
            self.database_instance_name = None

            _assert_value_is_set_but_prune_is_false(
                database_host, 'database_host'
            )
            self.database_host = None

            _assert_value_is_set_but_prune_is_false(
                database_name, 'database_name'
            )
            self.database_name = None

            _assert_value_is_set_but_prune_is_false(
                database_username, 'database_username'
            )
            self.database_username = None

            _assert_value_is_set_but_prune_is_false(
                database_password, 'database_password'
            )
            self.database_password = None

            _assert_value_is_set_but_prune_is_false(
                database_password_secret, 'database_password_secret'
            )
            self.database_password_secret = None
