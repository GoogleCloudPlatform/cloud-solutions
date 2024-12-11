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

"""Tests for main pruning function."""

import json
import collections
import flask
import sqlalchemy
from sqlalchemy import orm

import unittest
from unittest import mock
from absl.testing import parameterized
from testcontainers import mysql
from testcontainers import postgres
from testcontainers import mssql


from database_archival.pruning_function import main


# Represents fake results returned from database query.
_FakeResults = collections.namedtuple('FakeResults', ['rowcount'])


_SAMPLE_REQUEST = flask.Request.from_values(
    headers={'Content-Type': 'application/json'},
    data=json.dumps(
        {
            'bigquery_location': 'asia-southeast1',
            'snapshot_progress_table_name': (
                'project_id.dataset.table_prune_progress'
            ),
            'snapshot_run_id': 'manual_run_id',
            'snapshot_date': '20240101',
            'snapshot_batch': 5,
            'database_table_name': 'transactions',
            'table_primary_key_columns': ['transaction_id'],
            'database_type': 'ALLOYDB',
            'database_instance_name': 'project:database:instance',
            'database_name': 'database',
            'database_username': 'test-username',
            'database_password': 'fake-test-password',
        }
    ),
    method='POST',
)


class MainTest(parameterized.TestCase):
    """Tests for main pruning function."""

    def setUp(self):
        """Sets up tests."""
        super().setUp()

        self.bigquery_mock = self.enter_context(
            mock.patch.object(
                main.bigquery,
                'get_primary_keys_to_prune_from_bigquery',
                autospec=True,
            )
        )

        self.database_mock = self.enter_context(
            mock.patch.object(
                main.database,
                'delete_rows_from_database',
                autospec=True,
            )
        )

    @parameterized.named_parameters(
        [
            {
                'testcase_name': 'success_full_delete',
                'bigquery_mock_return': [{'id': 1}, {'id': 2}],
                'database_mock_return': _FakeResults(2),
                'expected_response_body': {
                    'full_delete': True,
                    'rows_deleted': 2,
                    'rows_retrieved': 2,
                    'success': True,
                },
                'expected_response_status_code': 200,
            },
            {
                'testcase_name': 'success_partial_delete',
                'bigquery_mock_return': [{'id': 1}, {'id': 2}],
                # Only one delete instead of expected 2.
                'database_mock_return': _FakeResults(1),
                'expected_response_body': {
                    'full_delete': False,
                    'rows_deleted': 1,
                    'rows_retrieved': 2,
                    'success': True,
                },
                'expected_response_status_code': 200,
            },
            {
                'testcase_name': 'success_no_primary_keys_retrieved',
                'bigquery_mock_return': [],
                'database_mock_return': _FakeResults(0),
                'expected_response_body': {
                    'full_delete': True,
                    'rows_deleted': 0,
                    'rows_retrieved': 0,
                    'success': True,
                    'warning': (
                        'No primary keys found to delete. '
                        'Is this an issue or was the data already deleted?'
                    ),
                },
                'expected_response_status_code': 200,
            },
        ]
    )
    def test_request_handler_returns_expected_response(
        self,
        bigquery_mock_return,
        database_mock_return,
        expected_response_body,
        expected_response_status_code,
    ):
        self.bigquery_mock.return_value = bigquery_mock_return
        self.database_mock.return_value = database_mock_return
        app = flask.Flask(__name__)

        with app.app_context():
            output = main.request_handler(_SAMPLE_REQUEST)

        self.assertEqual(output.get_json(), expected_response_body)
        self.assertEqual(output.status_code, expected_response_status_code)

    def test_request_handler_returns_400_response_when_errors_are_raised(self):
        bad_request = flask.Request.from_values(
            headers={'Content-Type': 'application/json'},
            data='',  # Intentionally putting empty data to cause a ValueError.
            method='POST',
        )
        app = flask.Flask(__name__)

        with app.app_context():
            output = main.request_handler(bad_request)

        self.assertEqual(output.get_json(), {'success': False})
        self.assertEqual(output.status_code, 400)


class MainLocalIntegrationTest(parameterized.TestCase):
    """Integration tests for using a local database.

    These are not completely end to end.
    """

    def setUp(self):
        """Sets up tests."""
        super().setUp()
        self.bq_client_mock = self.enter_context(
            mock.patch.object(main.bigquery.bigquery, 'Client', autospec=True)
        )

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
            snapshot_batch = sqlalchemy.Column(  # Only used for BigQuery fake.
                'snapshot_batch', sqlalchemy.Integer
            )
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
                    snapshot_batch=4,
                    id=1,
                    active=True,
                    name='Row1',
                ),
                data_model(
                    snapshot_batch=5,
                    id=1,
                    active=False,
                    name='ToDeleteRow1',
                ),
                data_model(
                    snapshot_batch=4,
                    id=2,
                    active=True,
                    name='Row2',
                ),
                data_model(
                    snapshot_batch=5,
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
                    # snapshot_batch is ignored on _query_test_table.
                    {'id': 1, 'active': True, 'name': 'Row1'},
                    {'id': 2, 'active': True, 'name': 'Row2'},
                    {'id': 1, 'active': False, 'name': 'ToDeleteRow1'},
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

    # TODO: create a local emulator or full fake for BigQuery.
    def _mock_bigquery_list_rows(
        self, data_model, database_engine, snapshot_batch
    ):
        """Mocks the return value of list_rows from BigQuery.

        As an alternative to a fully functional BigQuery local emulator, the
        same local database is also used as a BigQuery backend.

        Args:
            data_model: the data to be queried.
            database_engine: the database engine to use.
            snapshot_batch: the batch to return for delete.
        """

        def _fake_list_rows():
            """Returns rows of results from the database.

            Used as a fake result (side effect) for BigQuery.
            """
            with orm.Session(database_engine) as session:
                query_statement = sqlalchemy.select(data_model).where(
                    data_model.snapshot_batch == snapshot_batch
                )
                query = session.scalars(query_statement)
                results = query.all()
                return [
                    {
                        'id': result.id,
                        'active': result.active,
                        'name': result.name,
                    }
                    for result in results
                ]

        self.bq_client_mock.return_value.list_rows.side_effect = _fake_list_rows

    @parameterized.named_parameters(
        [
            {
                'testcase_name': 'alloydb',
                'database_type': 'ALLOYDB',
                'test_container': postgres.PostgresContainer(
                    'postgres:16',
                    driver='pg8000',
                ),
            },
            {
                'testcase_name': 'mysql',
                'database_type': 'MYSQL',
                'test_container': mysql.MySqlContainer('mysql:8.4'),
            },
            {
                'testcase_name': 'postgres',
                'database_type': 'POSTGRES',
                'test_container': postgres.PostgresContainer(
                    'postgres:16',
                    driver='pg8000',
                ),
            },
            {
                'testcase_name': 'sqlserver',
                'database_type': 'SQL_SERVER',
                'test_container': (
                    mssql.SqlServerContainer(
                        'mcr.microsoft.com/mssql/server:2022-CU12-ubuntu-22.04',
                        dialect='mssql+pymssql',
                    )
                ),
            },
            {
                'testcase_name': 'spanner',
                'database_type': 'SPANNER',
                'test_container': postgres.PostgresContainer(
                    'postgres:16',
                    driver='pg8000',
                ),
            },
        ]
    )
    def test_request_handler_deletes_database_data(
        self,
        database_type,
        test_container,
    ):
        """Tests that request_handler deletes data from database."""
        # Arrange.
        with test_container as database_container:
            database_engine = sqlalchemy.create_engine(
                database_container.get_connection_url()
            )
            Row = self._create_test_table(database_engine)
            self._insert_data_in_table(database_engine, Row)  # Inserts 4 rows.

            self._mock_bigquery_list_rows(
                data_model=Row,
                database_engine=database_engine,
                snapshot_batch=5,
            )

            database_ip = database_container.get_container_host_ip()
            database_port = database_container.get_exposed_port(
                database_container.port
            )
            database_host = f'{database_ip}:{database_port}'
            app = flask.Flask(__name__)

            # Act.
            with app.app_context():
                main.request_handler(
                    flask.Request.from_values(
                        headers={'Content-Type': 'application/json'},
                        data=json.dumps(
                            {
                                'bigquery_location': 'asia-southeast1',
                                'snapshot_progress_table_name': (
                                    'project_id.dataset.table_prune_progress'
                                ),
                                'snapshot_run_id': 'manual_run_id',
                                'snapshot_date': '20240101',
                                'snapshot_batch': 5,
                                'database_table_name': 'test_table',
                                'table_primary_key_columns': ['id', 'active'],
                                'database_type': database_type,
                                'database_host': database_host,
                                'database_name': database_container.dbname,
                                'database_username': (
                                    database_container.username
                                ),
                                'database_password': (
                                    database_container.password
                                ),
                            }
                        ),
                        method='POST',
                    )
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
