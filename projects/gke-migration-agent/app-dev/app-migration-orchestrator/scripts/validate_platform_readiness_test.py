#!/usr/bin/env python3
# Copyright 2026 Google LLC
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
"""Unit tests for validate_platform_readiness.py."""

import tempfile
import unittest
from pathlib import Path

from validate_platform_readiness import parse_yaml_documents


class TestValidatePlatformReadiness(unittest.TestCase):
    """Unit tests for validate_platform_readiness logic."""

    def test_parse_valid_manifest(self) -> None:
        manifest_content = (
            "apiVersion: apps/v1\n"
            "kind: Deployment\n"
            "metadata:\n"
            "  name: app\n"
            "  namespace: test-ns\n"
        )
        with tempfile.NamedTemporaryFile(
            "w+", suffix=".yaml", delete=False
        ) as f:
            f.write(manifest_content)
            f_path = Path(f.name)

        try:
            discovered = parse_yaml_documents(f_path)
            self.assertEqual(discovered, [("Deployment", "app", "test-ns")])
        finally:
            f_path.unlink(missing_ok=True)

    def test_parse_invalid_manifest(self) -> None:
        with tempfile.NamedTemporaryFile(
            "w+", suffix=".yaml", delete=False
        ) as f:
            f.write("invalid: yaml: [")
            f_path = Path(f.name)

        try:
            with self.assertRaises(ValueError):
                parse_yaml_documents(f_path)
        finally:
            f_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
