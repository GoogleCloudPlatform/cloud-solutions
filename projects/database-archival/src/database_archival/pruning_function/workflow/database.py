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

"""Connects to database to delete the data during pruning stage."""

import logging
import sqlalchemy
from sqlalchemy import orm

from database_archival.common.models import database
from database_archival.pruning_function.utils import database_connector
from typing import Iterable, Optional


_LOGGER = logging.getLogger(__name__)


def delete_rows_from_database(
    *,
    database_type: database.DatabaseType,
    database_instance_name: Optional[str] = None,
    database_host: Optional[str] = None,
    database_name: str,
    database_username: str,
    database_password: Optional[str] = None,
    database_password_secret: Optional[str] = None,
    database_table_name: str,
    table_primary_key_columns: Iterable[str],
    primary_keys_to_delete: database.PrimaryKeyFilters,
) -> sqlalchemy.engine.CursorResult:
    """Deletes rows from a database table where the condition matches.

    Deletion is done as a transaction. Either all records are deleted or
    none is.

    Args:
        database_type: type of database where data is stored.
        database_instance_name: name of the instance to which to connect.
            AlloyDB Format:
                projects/<project_id>/locations/<region_id>/
                clusters/<cluster_id>/instances/<instance_id>
            Cloud SQL Format:
                <project_id>:<region_id>:<instance_name>
        database_host: host of the database instance where data will be pruned.
        database_name: name of the database where archiving will happen.
        database_username: username to connect to the database.
        database_password: password for the given user.
        database_password_secret: password for the given user, stored in Secrets
            Manager. Format:
            "projects/<projectId>/secrets/<secretId>/versions/<versionId>".
        database_table_name: name of the table from which to remove records.
        table_primary_key_columns: list of primary key field names.
        primary_keys_to_delete: list of primary keys to delete. The format is a
            list, where each entry is for one row, of a map between the
            primary key column name and it's value.
            Example: [
                {"col1": 123, "col2": "abc"},
                {"col1": 456, "col2": "xyz"},
            ]
            This example may remove two rows where the primary keys match
            (123, abc) and (456, xyz).

    Raises:
        ValueError: database password not provided. Provide database_password
            or database_password_secret.

    Returns:
        Delete query results.
    """
    _LOGGER.info('Creating connection to the database.')
    db_engine = database_connector.get_database_engine(
        database_type=database_type,
        database_instance_name=database_instance_name,
        database_host=database_host,
        database_name=database_name,
        database_username=database_username,
        database_password=database_password,
        database_password_secret=database_password_secret,
    )
    _LOGGER.info('Created engine for connecting to the database.')

    where_clause = ' AND '.join(
        [
            f'{field_name}=:{field_name}'
            for field_name in table_primary_key_columns
        ]
    )
    with orm.Session(db_engine) as session:
        _LOGGER.info('Initializing database execution.')
        results = session.execute(
            statement=sqlalchemy.text(
                f'DELETE FROM {database_table_name} WHERE {where_clause}'
            ),
            params=primary_keys_to_delete,
        )
        _LOGGER.info('Created all statements for the database transaction.')
        session.commit()
        _LOGGER.info('Database transaction completed.')
        return results
