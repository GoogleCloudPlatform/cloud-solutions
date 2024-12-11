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

"""Tests database module."""

import unittest
from unittest import mock
from absl.testing import parameterized

from testcontainers import mysql
from testcontainers import postgres
from testcontainers import mssql
import sqlalchemy
from sqlalchemy import orm

from database_archival.common.models import database as database_model
from database_archival.pruning_function.workflow import database


_BASE_CALL_PARAMS = {
    'database_type': database.database.DatabaseType.ALLOYDB,
    'database_instance_name': 'project:region:instanceName',
    'database_name': 'database',
    'database_username': 'test-username',
    'database_password': 'fake-test-password',
    'database_table_name': 'test_table',
    'table_primary_key_columns': ['id'],
    'primary_keys_to_delete': [
        {'id': 1},
        {'id': 2},
    ],
}


class DatabaseUnitTest(parameterized.TestCase):
    """Unit tests for database module."""

    def setUp(self):
        super().setUp()

        self.db_engine_mock = self.enter_context(
            mock.patch.object(
                database.database_connector,
                'get_database_engine',
                autospec=True,
            )
        )

        self.db_session = self.enter_context(
            mock.patch.object(
                database.orm,
                'Session',
                autospec=True,
            )
        )

    def test_delete_rows_from_database_executes_expected_delete_query(self):
        """Tests that delete_rows_from_database runs expected query."""
        database.delete_rows_from_database(**_BASE_CALL_PARAMS)

        self.db_session.assert_called_once()
        # Session is called within a with statement, so we must use __enter__.
        sesion_mock = self.db_session.return_value.__enter__.return_value
        sesion_mock.execute.assert_called_once_with(
            # Must validate statement separately as it compares address.
            statement=mock.ANY,
            params=[{'id': 1}, {'id': 2}],
        )
        _, execute_kwargs = sesion_mock.execute.call_args
        self.assertEqual(
            str(execute_kwargs['statement'].compile()),
            'DELETE FROM test_table WHERE id=:id',
        )
        sesion_mock.commit.assert_called_once()


class DatabaseLocalIntegrationTest(parameterized.TestCase):
    """Integration tests for database module using a local database.

    These are not completely end to end, but handle database interaction.
    """

    def _create_test_table(self, database_engine):
        """Creates table in the database.

        Args:
            database_engine: database engine to perform operations.

        Returns:
            Table ORM model.
        """
        Base = orm.declarative_base()

        class Row(Base):
            """Test table for local integration tests."""

            __tablename__ = 'test_table'
            id = sqlalchemy.Column('id', sqlalchemy.Integer, primary_key=True)
            active = sqlalchemy.Column(
                'active', sqlalchemy.Boolean, primary_key=True
            )
            name = sqlalchemy.Column('name', sqlalchemy.String(100))

        Base.metadata.create_all(database_engine)

        return Row

    def _insert_data_in_table(self, database_engine, data_model):
        """Inserts data into the database.

        Asserts that the expected number or rows was inserted in the database.

        Args:
            database_engine: database engine to perform operations.
            data_model: ORM table model to use for data insertion.
        """
        with orm.Session(database_engine) as session:
            rows = [
                data_model(
                    id=1,
                    active=True,
                    name='Row1',
                ),
                data_model(
                    id=1,
                    active=False,
                    name='ToDeleteRow1',
                ),
                data_model(
                    id=2,
                    active=True,
                    name='Row2',
                ),
                data_model(
                    id=2,
                    active=False,
                    name='ToDeleteRow2',
                ),
            ]
            session.add_all(rows)
            session.commit()

            results = self._query_test_table(session, data_model)
            self.assertLen(results, 4)
            self.assertCountEqual(
                results,
                [
                    {'id': 1, 'active': True, 'name': 'Row1'},
                    {'id': 1, 'active': False, 'name': 'ToDeleteRow1'},
                    {'id': 2, 'active': True, 'name': 'Row2'},
                    {'id': 2, 'active': False, 'name': 'ToDeleteRow2'},
                ],
            )

    def _query_test_table(self, database_session, data_model):
        """Gets all the results for the test table.

        The schema is fixed to the test table.

        Args:
            database_session: database session to use for querying.
            database_model: ORM model of the table to query.

        Returns:
            List of dictionaries. Each dictionary represents a row with all the
            relevant columns. Schema is fixed to test table.
        """
        query_statement = sqlalchemy.select(data_model)
        query = database_session.scalars(query_statement)
        results = query.all()
        return [
            {
                'id': result.id,
                'active': result.active,
                'name': result.name,
            }
            for result in results
        ]

    @parameterized.named_parameters(
        [
            {
                'testcase_name': 'alloydb',
                'database_type': database_model.DatabaseType.ALLOYDB,
                'test_container': postgres.PostgresContainer(
                    'postgres:16',
                    driver='pg8000',
                ),
            },
            {
                'testcase_name': 'mysql',
                'database_type': database_model.DatabaseType.MYSQL,
                'test_container': mysql.MySqlContainer('mysql:8.4'),
            },
            {
                'testcase_name': 'postgres',
                'database_type': database_model.DatabaseType.POSTGRES,
                'test_container': postgres.PostgresContainer(
                    'postgres:16',
                    driver='pg8000',
                ),
            },
            {
                'testcase_name': 'sqlserver',
                'database_type': database_model.DatabaseType.SQL_SERVER,
                'test_container': (
                    mssql.SqlServerContainer(
                        'mcr.microsoft.com/mssql/server:2022-CU12-ubuntu-22.04',
                        dialect='mssql+pymssql',
                    )
                ),
            },
            {
                'testcase_name': 'spanner',
                'database_type': database_model.DatabaseType.SPANNER,
                'test_container': postgres.PostgresContainer(
                    'postgres:16',
                    driver='pg8000',
                ),
            },
        ]
    )
    def test_delete_rows_from_database_deletes_data_from_database(
        self,
        database_type,
        test_container,
    ):
        """Tests that delete_rows_from_database deletes data from database."""
        # Arrange.
        with test_container as database_container:
            database_engine = sqlalchemy.create_engine(
                database_container.get_connection_url()
            )
            Row = self._create_test_table(database_engine)
            self._insert_data_in_table(database_engine, Row)  # Inserts 4 rows.

            database_ip = database_container.get_container_host_ip()
            database_port = database_container.get_exposed_port(
                database_container.port
            )
            database_host = f'{database_ip}:{database_port}'

            # Act.
            database.delete_rows_from_database(
                database_type=database_type,
                database_host=database_host,
                database_name=database_container.dbname,
                database_username=database_container.username,
                database_password=database_container.password,
                database_table_name='test_table',
                table_primary_key_columns=['id', 'active'],
                primary_keys_to_delete=[
                    {'id': 1, 'active': False},
                    {'id': 2, 'active': False},
                ],
            )

            # Assert.
            with orm.Session(database_engine) as session:
                results = self._query_test_table(session, Row)
                self.assertLen(results, 2)
                self.assertCountEqual(
                    results,
                    [
                        {'id': 1, 'active': True, 'name': 'Row1'},
                        {'id': 2, 'active': True, 'name': 'Row2'},
                    ],
                )


if __name__ == '__main__':
    unittest.main()
