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

"""Provides connections to the database(s)."""

import frozendict
import sqlalchemy
from google.cloud.sql import connector as sql_connector
from google.cloud.alloydb import connector as alloydb_connector
from database_archival.common import config
from database_archival.common.models import database
from database_archival.common.utils import secret_manager
from typing import Callable, Optional


# Mapping between the DatabaseType and their drivers.
_DRIVER_MAPPING = {
    database.DatabaseType.ALLOYDB: 'pg8000',
    database.DatabaseType.MYSQL: 'pymysql',
    database.DatabaseType.POSTGRES: 'pg8000',
    database.DatabaseType.SPANNER: 'pg8000',
    database.DatabaseType.SQL_SERVER: 'pytds',
}

_DATABASE_URL_MAPPING = {
    database.DatabaseType.ALLOYDB: (
        f'postgresql+{_DRIVER_MAPPING[database.DatabaseType.ALLOYDB]}'
    ),
    database.DatabaseType.MYSQL: (
        f'mysql+{_DRIVER_MAPPING[database.DatabaseType.MYSQL]}'
    ),
    database.DatabaseType.POSTGRES: (
        f'postgresql+{_DRIVER_MAPPING[database.DatabaseType.POSTGRES]}'
    ),
    database.DatabaseType.SPANNER: (
        f'postgresql+{_DRIVER_MAPPING[database.DatabaseType.SPANNER]}'
    ),
    database.DatabaseType.SQL_SERVER: (
        f'mssql+{_DRIVER_MAPPING[database.DatabaseType.SQL_SERVER]}'
    ),
}

# Default parameters for all database connections.
_DEFAULT_ENGINE_ARGS = frozendict.frozendict(
    {
        'max_overflow': 0,
        'pool_recycle': 1800,
        'pool_size': 1,
        'pool_timeout': 600,
    }
)


def _get_database_url_prefix(database_type: database.DatabaseType) -> str:
    """Gets the database URL prefix for the engine URL.

    Args:
        database_type: type of database for which to get driver.

    Raises:
        ValueError: database type not supported.

    Returns:
        Database URL prefix for the database URL, with database and driver name.
    """
    if database_type not in _DATABASE_URL_MAPPING:
        raise ValueError(f'Database {database_type} is not supported.')
    return _DATABASE_URL_MAPPING[database_type]


def _get_database_drivername(database_type: database.DatabaseType) -> str:
    """Gets the database drivername.

    Args:
        database_type: type of database for which to get driver.

    Raises:
        ValueError: database type not supported.

    Returns:
        Database driver name.
    """
    if database_type not in _DRIVER_MAPPING:
        raise ValueError(f'Database {database_type} is not supported.')
    return _DRIVER_MAPPING[database_type]


def _get_database_password(
    database_password: Optional[str], database_password_secret: Optional[str]
) -> str:
    """Gets the database password.

    Uses database password or fetches database password secret.

    Args:
        database_password: password for the database.
        database_password_secret: password for the database, stored in Secrets
            Manager.

    Raises:
        ValueError: no password provided.

    Returns:
        Password for the database.
    """
    if not database_password and not database_password_secret:
        raise ValueError('Database password must be provided.')
    elif database_password:
        return database_password
    else:  # if database_password_secret:
        return secret_manager.get_secret(database_password_secret)


def _create_getconn_function(
    database_driver: str,
    database_instance_name: str,
    database_username: str,
    database_password: str,
    database_name: str,
    database_type: database.DatabaseType,
) -> Callable:
    """Creates a getconn function used for connecting to the database.

    Args:
        database_driver: driver (class) to use to get a connection.
        database_instance_name: name of the instance to which to connect.
            AlloyDB Format:
                projects/<project_id>/locations/<region_id>/
                clusters/<cluster_id>/instances/<instance_id>
            Cloud SQL Format:
                <project_id>:<region_id>:<instance_name>
        database_name: name of the database where archiving will happen.
        database_username: username to connect to the database.
        database_password: password for the given user.
        database_type: type of the database.
    """
    if database_type == database.DatabaseType.ALLOYDB:
        db_connector = alloydb_connector.Connector(
            refresh_strategy='lazy',
            ip_type=alloydb_connector.IPTypes.PRIVATE,
        )
        return lambda: db_connector.connect(
            database_instance_name,
            database_driver,
            user=database_username,
            password=database_password,
            db=database_name,
        )
    else:
        db_connector = sql_connector.Connector(
            ip_type=sql_connector.IPTypes.PRIVATE,
            refresh_strategy='lazy',
            timeout=config.DATABASE_TIMEOUT,
        )
        return lambda: db_connector.connect(
            database_instance_name,
            database_driver,
            user=database_username,
            password=database_password,
            db=database_name,
        )


def _create_engine_for_database_instance(
    database_type: database.DatabaseType,
    database_instance_name: str,
    database_name: str,
    database_username: str,
    database_password: str,
) -> sqlalchemy.engine.base.Engine:
    """Creates the database engine for a given database instance.

    Args:
        database_type: type of database for which get or create engine.
        database_instance_name: instance name for which to create engine.
        database_username: username for the database.
        database_password: password for the database user.

    Raises:
        ValueError: unsupported database type.

    Returns:
        Database engine to connect to the given database instance.
    """
    database_driver = _get_database_drivername(database_type)
    database_driver_url = _get_database_url_prefix(database_type)
    getconn_provider = _create_getconn_function(
        database_driver=database_driver,
        database_instance_name=database_instance_name,
        database_name=database_name,
        database_username=database_username,
        database_password=database_password,
        database_type=database_type,
    )
    engine_args = {
        **_DEFAULT_ENGINE_ARGS,
        'creator': getconn_provider,
    }
    return sqlalchemy.create_engine(
        f'{database_driver_url}://',
        **engine_args,
    )


def _create_engine_for_database_host(
    database_type: database.DatabaseType,
    database_host: str,
    database_username: str,
    database_password: str,
    database_name: str,
) -> sqlalchemy.engine.base.Engine:
    """Creates the database engine for a given database host.

    Args:
        database_type: type of database for which get or create engine.
        database_host: host of the database. Accepts with and without port.
        database_username: username for the database.
        database_password: password for the database user.

    Raises:
        ValueError: unsupported database type.

    Returns:
        Database engine for connecting to the given database host.
    """
    if ':' in database_host:
        database_hostname, database_port = database_host.split(':')
    else:
        database_hostname = database_host
        database_port = None

    database_url = sqlalchemy.engine.url.URL.create(
        drivername=_get_database_url_prefix(database_type),
        username=database_username,
        password=database_password,
        database=database_name,
        host=database_hostname,
        port=database_port,
    )

    return sqlalchemy.create_engine(
        database_url,
        **_DEFAULT_ENGINE_ARGS,
    )


def get_database_engine(
    *,
    database_type: database.DatabaseType,
    database_instance_name: Optional[str] = None,
    database_host: Optional[str] = None,
    database_name: str,
    database_username: str,
    database_password: Optional[str] = None,
    database_password_secret: Optional[str] = None,
) -> sqlalchemy.engine.base.Engine:
    """Creates a connection pool/engine for the database instance.

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
        database_password_secret: password secret for the given user.

    Raises:
        ValueError: database_host or database_instance_name must be provided.
        ValueError: database_host and database_instance_name cannot both be set.

    Returns:
        Connection engine to interact with the database.
    """
    database_password = _get_database_password(
        database_password=database_password,
        database_password_secret=database_password_secret,
    )

    if database_host and database_instance_name:
        raise ValueError(
            'Only database_host or database_instance_name must be set.'
        )

    elif not database_host and not database_instance_name:
        raise ValueError('Database host or instance name must be provided.')

    elif database_host:  # Connect via TCP.
        return _create_engine_for_database_host(
            database_type=database_type,
            database_host=database_host,
            database_name=database_name,
            database_username=database_username,
            database_password=database_password,
        )

    else:  # if database_instance_name:  # Connect via Python connector.
        return _create_engine_for_database_instance(
            database_type=database_type,
            database_instance_name=database_instance_name,
            database_name=database_name,
            database_username=database_username,
            database_password=database_password,
        )
