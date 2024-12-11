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

"""Tests database_connector module."""

import unittest
from unittest import mock
from absl.testing import parameterized

import sqlalchemy
from typing import Callable

from database_archival.common.models import database
from database_archival.pruning_function.utils import database_connector


_BASE_CALL_PARAMS = {
    'database_type': database.DatabaseType.ALLOYDB,
    'database_instance_name': 'project:region:instanceName',
    'database_name': 'database',
    'database_username': 'test-username',
    'database_password': 'fake-test-password',
}


class DatabaseUnitTest(parameterized.TestCase):
    """Unit tests for database connector module."""

    def setUp(self):
        super().setUp()

        self.secret_manager_mock = self.enter_context(
            mock.patch.object(
                database_connector.secret_manager,
                'get_secret',
                autospec=True,
                return_value='secret-password',
            )
        )

        self.db_engine_mock = self.enter_context(
            mock.patch.object(
                database_connector.sqlalchemy,
                'create_engine',
                autospec=True,
            )
        )

        self.sql_connector_mock = self.enter_context(
            mock.patch.object(
                database_connector.sql_connector,
                'Connector',
                autospec=True,
            ),
        )

        self.alloydb_connector_mock = self.enter_context(
            mock.patch.object(
                database_connector.alloydb_connector,
                'Connector',
                autospec=True,
            ),
        )

    def test_get_database_engine_fetches_password_secret(self):
        """Tests that get_database_engine fetches password secret."""
        kwargs = {
            **_BASE_CALL_PARAMS,
            'database_password': None,
            'database_password_secret': 'project/123/secret/x/version/1',
        }

        database_connector.get_database_engine(**kwargs)

        self.secret_manager_mock.assert_called_once_with(
            'project/123/secret/x/version/1'
        )

    @parameterized.parameters(
        [
            {
                'database_type': database.DatabaseType.ALLOYDB,
                'drivername': 'postgresql+pg8000',
            },
            {
                'database_type': database.DatabaseType.MYSQL,
                'drivername': 'mysql+pymysql',
            },
            {
                'database_type': database.DatabaseType.POSTGRES,
                'drivername': 'postgresql+pg8000',
            },
            {
                'database_type': database.DatabaseType.SPANNER,
                'drivername': 'postgresql+pg8000',
            },
            {
                'database_type': database.DatabaseType.SQL_SERVER,
                'drivername': 'mssql+pytds',
            },
        ]
    )
    def test_get_database_engine_creates_database_host(
        self,
        database_type,
        drivername,
    ):
        """Tests that get_database_engine creates engine for db host."""
        kwargs = {
            **_BASE_CALL_PARAMS,
            'database_type': database_type,
            'database_host': '127.0.0.1',
            'database_instance_name': None,
        }

        database_connector.get_database_engine(**kwargs)

        self.db_engine_mock.assert_called_once_with(
            sqlalchemy.engine.url.URL.create(
                drivername=drivername,
                username='test-username',
                password='fake-test-password',
                host='127.0.0.1',
                database='database',
            ),
            max_overflow=0,
            pool_recycle=1800,
            pool_size=1,
            pool_timeout=600,
        )

    def test_get_database_engine_creates_database_host_and_port(self):
        """Tests that get_database_engine creates engine with db port."""
        kwargs = {
            **_BASE_CALL_PARAMS,
            'database_type': database.DatabaseType.ALLOYDB,
            'database_host': '127.0.0.1:5432',
            'database_instance_name': None,
        }

        database_connector.get_database_engine(**kwargs)

        self.db_engine_mock.assert_called_once_with(
            sqlalchemy.engine.url.URL.create(
                drivername='postgresql+pg8000',
                username='test-username',
                password='fake-test-password',
                host='127.0.0.1',
                port='5432',
                database='database',
            ),
            max_overflow=0,
            pool_recycle=1800,
            pool_size=1,
            pool_timeout=600,
        )

    @parameterized.parameters(
        [
            {
                'database_type': database.DatabaseType.MYSQL,
                'database_url': 'mysql+pymysql://',
                'database_driver': 'pymysql',
            },
            {
                'database_type': database.DatabaseType.POSTGRES,
                'database_url': 'postgresql+pg8000://',
                'database_driver': 'pg8000',
            },
            {
                'database_type': database.DatabaseType.SPANNER,
                'database_url': 'postgresql+pg8000://',
                'database_driver': 'pg8000',
            },
            {
                'database_type': database.DatabaseType.SQL_SERVER,
                'database_url': 'mssql+pytds://',
                'database_driver': 'pytds',
            },
        ]
    )
    def test_get_database_engine_creates_database_instance_name(
        self, database_type, database_url, database_driver
    ):
        """Tests that get_database_engine creates engine for db instance."""
        kwargs = {
            **_BASE_CALL_PARAMS,
            'database_type': database_type,
            'database_instance_name': 'project:region:instanceName',
            'database_host': None,
        }

        database_connector.get_database_engine(**kwargs)

        self.db_engine_mock.assert_called_once_with(
            database_url,
            max_overflow=0,
            pool_recycle=1800,
            pool_size=1,
            pool_timeout=600,
            creator=mock.ANY,
        )
        # Call through the connection creation.
        # This is normally done by create_engine(), but since the engine is
        # mocked, the connection creator is not going to be executed. This
        # forces the connection to be created, so we can validate that the
        # connection parameters are correct.
        _, engine_kwargs = self.db_engine_mock.call_args
        connection_creator_fn = engine_kwargs.get('creator')
        self.assertIsInstance(connection_creator_fn, Callable)
        connection_creator = connection_creator_fn()
        connection_creator.connect()
        self.sql_connector_mock.assert_called_once()
        self.sql_connector_mock.return_value.connect.assert_called_once_with(
            'project:region:instanceName',
            database_driver,
            user='test-username',
            password='fake-test-password',
            db='database',
        )

    @parameterized.parameters(
        [
            {
                'database_type': database.DatabaseType.ALLOYDB,
                'database_url': 'postgresql+pg8000://',
                'database_driver': 'pg8000',
            },
        ]
    )
    def test_get_database_engine_creates_database_instance_name_alloydb(
        self, database_type, database_url, database_driver
    ):
        """Tests get_database_engine creates engine for AlloyDB instance."""
        kwargs = {
            **_BASE_CALL_PARAMS,
            'database_type': database_type,
            'database_instance_name': (
                'projects/<project_id>/locations/<region_id>/clusters/'
                '<cluster_id>/instances/<instance_id>'
            ),
            'database_host': None,
        }

        database_connector.get_database_engine(**kwargs)

        self.db_engine_mock.assert_called_once_with(
            database_url,
            max_overflow=0,
            pool_recycle=1800,
            pool_size=1,
            pool_timeout=600,
            creator=mock.ANY,
        )
        # Call through the connection creation.
        # This is normally done by create_engine(), but since the engine is
        # mocked, the connection creator is not going to be executed. This
        # forces the connection to be created, so we can validate that the
        # connection parameters are correct.
        _, engine_kwargs = self.db_engine_mock.call_args
        connection_creator_fn = engine_kwargs.get('creator')
        self.assertIsInstance(connection_creator_fn, Callable)
        connection_creator = connection_creator_fn()
        connection_creator.connect()
        self.alloydb_connector_mock.assert_called_once()
        connect_mock = self.alloydb_connector_mock.return_value.connect
        connect_mock.assert_called_once_with(
            (
                'projects/<project_id>/locations/<region_id>/clusters/'
                '<cluster_id>/instances/<instance_id>'
            ),
            database_driver,
            user='test-username',
            password='fake-test-password',
            db='database',
        )

    @parameterized.named_parameters(
        [
            {
                'testcase_name': 'no_password',
                'call_args': {
                    **_BASE_CALL_PARAMS,
                    'database_password': None,
                    'database_password_secret': None,
                },
                'expected_error_message': 'Database password must be provided.',
            },
            {
                'testcase_name': 'no_instance_name_or_host',
                'call_args': {
                    **_BASE_CALL_PARAMS,
                    'database_host': None,
                    'database_instance_name': None,
                },
                'expected_error_message': (
                    'Database host or instance name must be provided.'
                ),
            },
            {
                'testcase_name': 'both_instance_name_and_password',
                'call_args': {
                    **_BASE_CALL_PARAMS,
                    'database_host': '127.0.0.1',
                    'database_instance_name': 'project:region:instanceName',
                },
                'expected_error_message': (
                    'Only database_host or database_instance_name must be set.'
                ),
            },
            {
                'testcase_name': 'unsupported_database_type_with_database_host',
                'call_args': {
                    **_BASE_CALL_PARAMS,
                    'database_type': 'unsupported',
                    'database_host': '127.0.0.1',
                    'database_instance_name': None,
                },
                'expected_error_message': (
                    'Database unsupported is not supported.'
                ),
            },
            {
                'testcase_name': (
                    'unsupported_database_type_with_database_instance_name'
                ),
                'call_args': {
                    **_BASE_CALL_PARAMS,
                    'database_type': 'unsupported',
                    'database_host': None,
                    'database_instance_name': 'project:region:instanceName',
                },
                'expected_error_message': (
                    'Database unsupported is not supported.'
                ),
            },
        ]
    )
    def test_get_database_engine_raises_value_error_bad_params(
        self,
        call_args,
        expected_error_message,
    ):
        """Tests that get_database_engine raises ValueError."""
        with self.assertRaisesRegex(ValueError, expected_error_message):
            database_connector.get_database_engine(**call_args)


# Integration tests are run through the database module on:
# /src/database_archival/pruning_function/workflow/database.py

if __name__ == '__main__':
    unittest.main()
