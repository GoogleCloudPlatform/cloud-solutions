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
"""Unit tests for validate_storage_map.py."""

import json
import tempfile
import unittest
from pathlib import Path

from validate_storage_map import (
    extract_pvc_storage_classes,
    extract_required_pvcs,
    find_file_recursively,
    load_json,
)


class TestValidateStorageMap(unittest.TestCase):
    """Test suite for storage map validation functions."""

    def test_extract_required_pvcs_cluster_level(self):
        data = {
            "clusters": [
                {
                    "namespaces": [
                        {
                            "name": "prod",
                            "workloads": [
                                {
                                    "dependencies": {
                                        "storage": {
                                            "pvc_names": [
                                                "data-pvc",
                                                "cache-pvc",
                                            ]
                                        }
                                    }
                                }
                            ],
                        }
                    ]
                }
            ]
        }
        pvcs = extract_required_pvcs(data)
        self.assertEqual(pvcs, {("prod", "data-pvc"), ("prod", "cache-pvc")})

    def test_extract_required_pvcs_namespace_level(self):
        data = {
            "namespace": "staging",
            "workloads": [
                {"dependencies": {"storage": {"pvc_names": ["app-db-pvc"]}}}
            ],
        }
        pvcs = extract_required_pvcs(data)
        self.assertEqual(pvcs, {("staging", "app-db-pvc")})

    def test_extract_required_pvcs_with_volume_claim_templates(self):
        data = {
            "namespace": "prod",
            "workloads": [
                {
                    "dependencies": {
                        "storage": {
                            "pvc_names": ["data-pvc"],
                            "volume_claim_templates": ["stateful-vol"],
                        }
                    }
                }
            ],
        }
        pvcs = extract_required_pvcs(data)
        self.assertEqual(pvcs, {("prod", "data-pvc"), ("prod", "stateful-vol")})

    def test_extract_pvc_storage_classes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "pvc.yaml"
            manifest_content = (
                "apiVersion: v1\n"
                "kind: PersistentVolumeClaim\n"
                "metadata:\n"
                "  name: my-pvc\n"
                "  namespace: prod\n"
                "spec:\n"
                "  storageClassName: gp3\n"
            )
            manifest_path.write_text(manifest_content, encoding="utf-8")
            res = extract_pvc_storage_classes(Path(tmpdir))
            self.assertEqual(res, {("prod", "my-pvc"): "gp3"})

    def test_extract_pvc_storage_classes_statefulset(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "statefulset.yaml"
            manifest_content = (
                "apiVersion: apps/v1\n"
                "kind: StatefulSet\n"
                "metadata:\n"
                "  name: web-app\n"
                "  namespace: prod\n"
                "spec:\n"
                "  volumeClaimTemplates:\n"
                "  - metadata:\n"
                "      name: web-data\n"
                "    spec:\n"
                "      storageClassName: fast-disks\n"
            )
            manifest_path.write_text(manifest_content, encoding="utf-8")
            res = extract_pvc_storage_classes(Path(tmpdir))
            self.assertEqual(res, {("prod", "web-data"): "fast-disks"})

    def test_load_json(self):
        with tempfile.NamedTemporaryFile(
            "w+", delete=False, suffix=".json"
        ) as f:
            json.dump([{"source": "gp2", "target": "standard-rwo"}], f)
            f_path = Path(f.name)
        try:
            data = load_json(f_path)
            self.assertIsInstance(data, list)
            self.assertEqual(data[0]["source"], "gp2")
        finally:
            f_path.unlink()

    def test_load_json_not_found(self):
        with self.assertRaises(FileNotFoundError):
            load_json(Path("/nonexistent/path/for/test/file.json"))

    def test_load_json_invalid_json(self):
        with tempfile.NamedTemporaryFile(
            "w+", delete=False, suffix=".json"
        ) as f:
            f.write("invalid json content {")
            f_path = Path(f.name)
        try:
            with self.assertRaises(json.JSONDecodeError):
                load_json(f_path)
        finally:
            f_path.unlink()

    def test_find_file_recursively_single_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "sub" / "target.json"
            target_file.parent.mkdir()
            target_file.touch()
            found = find_file_recursively(Path(tmpdir), "target.json")
            self.assertEqual(found, target_file)

    def test_find_file_recursively_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            found = find_file_recursively(Path(tmpdir), "missing.json")
            self.assertIsNone(found)

    def test_find_file_recursively_multiple_matches(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / "dir1" / "dup.json"
            file2 = Path(tmpdir) / "dir2" / "dup.json"
            file1.parent.mkdir()
            file2.parent.mkdir()
            file1.touch()
            file2.touch()
            with self.assertRaises(ValueError) as ctx:
                find_file_recursively(Path(tmpdir), "dup.json")
            self.assertIn(
                "Multiple instances of 'dup.json'", str(ctx.exception)
            )


if __name__ == "__main__":
    unittest.main()
