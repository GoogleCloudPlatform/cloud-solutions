# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Test fetch_and_set_username_and_token."""

import json
import unittest
from unittest import mock

import sqlalchemy_gcp_sa_auth

URLBASE = ("http://metadata.google.internal/computeMetadata/"
           "v1/instance/service-accounts/default")


class TestSqlalchemyGcpSaAuth(unittest.TestCase):
    """Tests for sqlalchemy_gcp_sa_auth."""

    def setUp(self):
        """Sets up mock for tests"""
        super().setUp()
        urlopen_patcher = mock.patch("urllib.request.urlopen")
        self.addCleanup(urlopen_patcher.stop)
        self.mock_urlopen = urlopen_patcher.start()
        self.mock_urlopen.return_value.read.side_effect = [
            "some@prj.iam.gserviceaccount.com".encode("utf8"),
            json.dumps(dict(access_token="an-access-token")).encode("utf8"),
        ]

    def test_fetch_and_set_username_and_token_returns_expected_dict(self):
        """Test if fetch_and_set_username_and_token correctly sets
        user and password.
        """
        output = {}

        sqlalchemy_gcp_sa_auth.fetch_and_set_username_and_token(output)

        self.assertDictEqual(
            output,
            dict(
                user="some@prj.iam",
                password="an-access-token"
            ),
            "Seen user and password correct in output"
        )

    def test_fetch_and_set_username_and_token_makes_expected_requests(self):
        """Test if fetch_and_set_username_and_token makes expected
        requests.
        """
        sqlalchemy_gcp_sa_auth.fetch_and_set_username_and_token({})

        call_request1, call_request2 = (self.mock_urlopen.call_args_list)
        request1, *_ = call_request1.args


        self.assertEqual(
            request1.get_full_url(),
            ("http://metadata.google.internal/computeMetadata/"
             "v1/instance/service-accounts/default/email"),
            "Accessed correct url for email."
        )
        self.assertEqual("Google",
                         request1.headers.get("Metadata-Flavor".capitalize()))

        request2, *_ = call_request2.args

        self.assertEqual(
            request2.get_full_url(),
            ("http://metadata.google.internal/computeMetadata/"
             "v1/instance/service-accounts/default/token"),
            "Accessed correct url for email."
        )
        self.assertEqual("Google",
                         request2.headers.get("Metadata-Flavor".capitalize()))


if __name__ == "__main__":
    unittest.main()
