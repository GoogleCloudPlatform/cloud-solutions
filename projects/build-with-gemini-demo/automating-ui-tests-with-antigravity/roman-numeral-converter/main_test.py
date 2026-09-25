# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for Flask application routes."""

import unittest

try:
    from main import app

    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in environment")
class MainAppTest(unittest.TestCase):
    """Tests for Flask web application."""

    def setUp(self):
        self.client = app.test_client()

    def test_home_page(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Roman Numerals", response.data)

    def test_convert_valid_number(self):
        response = self.client.post("/convert", data={"number": "10"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"The number 10 is X in Roman Numerals.", response.data)

    def test_convert_invalid_number(self):
        response = self.client.post("/convert", data={"number": "invalid"})
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Please enter a valid positive integer.", response.data)


if __name__ == "__main__":
    unittest.main()
