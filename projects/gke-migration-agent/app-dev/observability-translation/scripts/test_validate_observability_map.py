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
"""Unit tests for validate_observability_map.py."""

import json
import tempfile
import unittest
from pathlib import Path

from validate_observability_map import (
    find_file_recursively,
    load_json,
    scan_manifests_for_scraped_workloads,
)


class TestValidateObservabilityMap(unittest.TestCase):
    """Test suite for observability map validation functions."""

    def test_scan_manifests_for_scraped_workloads(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "deployment.yaml"
            manifest_content = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: prod
spec:
  template:
    metadata:
      annotations:
        prometheus.io/scrape: "true"
"""
            manifest_path.write_text(manifest_content, encoding="utf-8")

            scraped = scan_manifests_for_scraped_workloads(Path(tmpdir))
            self.assertEqual(scraped, {("prod", "frontend")})

    def test_find_file_recursively_single_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f1 = Path(tmpdir) / "sub" / "observability-map.json"
            f1.parent.mkdir(parents=True, exist_ok=True)
            f1.write_text("[]", encoding="utf-8")

            res = find_file_recursively(Path(tmpdir), "observability-map.json")
            self.assertEqual(res, f1)

    def test_find_file_recursively_multiple_matches_raises_system_exit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f1 = Path(tmpdir) / "cluster-a" / "observability-map.json"
            f2 = Path(tmpdir) / "cluster-b" / "observability-map.json"
            f1.parent.mkdir(parents=True, exist_ok=True)
            f2.parent.mkdir(parents=True, exist_ok=True)
            f1.write_text("[]", encoding="utf-8")
            f2.write_text("[]", encoding="utf-8")

            with self.assertRaises(SystemExit):
                find_file_recursively(Path(tmpdir), "observability-map.json")

    def test_load_json(self):
        with tempfile.NamedTemporaryFile(
            "w+", delete=False, suffix=".json"
        ) as f:
            json.dump([], f)
            f_path = Path(f.name)
        try:
            data = load_json(f_path)
            self.assertIsInstance(data, list)
        finally:
            f_path.unlink()


if __name__ == "__main__":
    unittest.main()
