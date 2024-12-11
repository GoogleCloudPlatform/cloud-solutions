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

"""Tests for secret_manager."""

import unittest
from unittest import mock
from absl.testing import absltest

from database_archival.common.utils import secret_manager


class TestSecretManager(absltest.TestCase):
    """Unit tests for secret_manager."""

    def setUp(self):
        """Sets up mocks for unit tests."""
        super().setUp()
        self.secret_manager_client_mock = self.enter_context(
            mock.patch.object(
                secret_manager.secretmanager,
                'SecretManagerServiceClient',
                autospec=True,
            )
        )

    def test_get_secret(self):
        """Tests get_secret returns the decoded secret."""
        # Arrange.
        mock_secret_payload = secret_manager.secretmanager.SecretPayload()
        mock_secret_payload.data = 'secret-password'.encode('utf-8')

        mock_secret_response = (
            secret_manager.secretmanager.AccessSecretVersionResponse()
        )
        mock_secret_response.name = 'my_secret'
        mock_secret_response.payload = mock_secret_payload

        mock_client = self.secret_manager_client_mock.return_value
        mock_client.access_secret_version.return_value = mock_secret_response

        # Act.
        output = secret_manager.get_secret('my_secret')

        # Assert.
        mock_client.access_secret_version.assert_called_once_with(
            name='my_secret'
        )
        self.assertEqual(output, 'secret-password')


if __name__ == '__main__':
    unittest.main()
