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
"""Unit tests for validate_identity_map.py."""

import json
import tempfile
import unittest
from pathlib import Path

import jsonschema
from validate_identity_map import (
    extract_required_service_accounts,
    find_file_recursively,
    is_valid_gsa_email,
    load_json,
    parse_identity_map,
    validate_mappings,
    validate_schema,
)


class TestValidateIdentityMap(unittest.TestCase):
    """Test suite for identity map validation functions."""

    def test_extract_required_service_accounts_cluster_level(self):
        data = {
            "clusters": [
                {
                    "namespaces": [
                        {
                            "name": "prod",
                            "workloads": [
                                {
                                    "dependencies": {
                                        "service_account": "app-sa",
                                        "irsa_role_arn": (
                                            "arn:aws:iam::123:role/role-a"
                                        ),
                                    }
                                }
                            ],
                        }
                    ]
                }
            ]
        }
        sas = extract_required_service_accounts(data)
        self.assertEqual(
            sas, {("prod", "app-sa"): "arn:aws:iam::123:role/role-a"}
        )

    def test_extract_required_service_accounts_conflict_raises_value_error(
        self,
    ):
        data = {
            "namespace": "prod",
            "workloads": [
                {
                    "dependencies": {
                        "service_account": "shared-sa",
                        "irsa_role_arn": "arn:aws:iam::123:role/role-a",
                    }
                },
                {
                    "dependencies": {
                        "service_account": "shared-sa",
                        "irsa_role_arn": "arn:aws:iam::123:role/role-b",
                    }
                },
            ],
        }
        with self.assertRaises(ValueError):
            extract_required_service_accounts(data)

    def test_find_file_recursively_single_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f1 = Path(tmpdir) / "sub" / "identity-map.json"
            f1.parent.mkdir(parents=True, exist_ok=True)
            f1.write_text("[]", encoding="utf-8")

            res = find_file_recursively(Path(tmpdir), "identity-map.json")
            self.assertEqual(res, f1)

    def test_find_file_recursively_multiple_matches_raises_value_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f1 = Path(tmpdir) / "cluster-a" / "identity-map.json"
            f2 = Path(tmpdir) / "cluster-b" / "identity-map.json"
            f1.parent.mkdir(parents=True, exist_ok=True)
            f2.parent.mkdir(parents=True, exist_ok=True)
            f1.write_text("[]", encoding="utf-8")
            f2.write_text("[]", encoding="utf-8")

            with self.assertRaises(ValueError):
                find_file_recursively(Path(tmpdir), "identity-map.json")

    def test_parse_identity_map_success(self):
        raw = [
            {
                "source": "arn:aws:iam::123:role/role-1",
                "target": "sa-1@proj.iam.gserviceaccount.com",
            },
            {
                "source": "arn:aws:iam::123:role/role-2",
                "target": "sa-2@proj.iam.gserviceaccount.com",
            },
        ]
        parsed = parse_identity_map(raw)
        self.assertEqual(
            parsed,
            {
                "arn:aws:iam::123:role/role-1": (
                    "sa-1@proj.iam.gserviceaccount.com"
                ),
                "arn:aws:iam::123:role/role-2": (
                    "sa-2@proj.iam.gserviceaccount.com"
                ),
            },
        )

    def test_parse_identity_map_conflicting_duplicate_raises_value_error(self):
        raw = [
            {
                "source": "arn:aws:iam::123:role/role-1",
                "target": "sa-1@proj.iam.gserviceaccount.com",
            },
            {
                "source": "arn:aws:iam::123:role/role-1",
                "target": "different-sa@proj.iam.gserviceaccount.com",
            },
        ]
        with self.assertRaises(ValueError):
            parse_identity_map(raw)

    def test_load_json(self):
        with tempfile.NamedTemporaryFile(
            "w+", delete=False, suffix=".json"
        ) as f:
            json.dump(
                [
                    {
                        "source": "arn:aws:iam::123:role/r",
                        "target": "gsa@proj.iam.gserviceaccount.com",
                    }
                ],
                f,
            )
            f_path = Path(f.name)
        try:
            data = load_json(f_path)
            self.assertIsInstance(data, list)
            self.assertEqual(data[0]["source"], "arn:aws:iam::123:role/r")
        finally:
            f_path.unlink()

    def test_load_json_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            load_json(Path("/path/does/not/exist.json"))

    def test_load_json_invalid_json(self):
        with tempfile.NamedTemporaryFile(
            "w+", delete=False, suffix=".json"
        ) as f:
            f.write("not valid json")
            f_path = Path(f.name)
        try:
            with self.assertRaises(json.JSONDecodeError):
                load_json(f_path)
        finally:
            f_path.unlink()

    def test_extract_required_service_accounts_namespace_level(self):
        data = {
            "namespace": "backend",
            "workloads": [
                {
                    "dependencies": {
                        "service_account": "backend-sa",
                        "irsa_role_arn": "arn:aws:iam::123:role/role-backend",
                    }
                }
            ],
        }
        sas = extract_required_service_accounts(data)
        self.assertEqual(
            sas,
            {("backend", "backend-sa"): "arn:aws:iam::123:role/role-backend"},
        )

    def test_extract_required_service_accounts_ignores_workloads_without_irsa(
        self,
    ):
        data = {
            "namespace": "frontend",
            "workloads": [
                {
                    "dependencies": {
                        "service_account": "frontend-sa",
                    }
                },
                {"dependencies": {}},
                {},
            ],
        }
        sas = extract_required_service_accounts(data)
        self.assertEqual(sas, {})

    def test_is_valid_gsa_email(self):
        self.assertTrue(
            is_valid_gsa_email("user-sa@my-proj.iam.gserviceaccount.com")
        )
        self.assertTrue(
            is_valid_gsa_email(
                "123456789-compute@developer.gserviceaccount.com"
            )
        )
        self.assertFalse(is_valid_gsa_email("user@example.com"))
        self.assertFalse(is_valid_gsa_email(""))
        self.assertFalse(is_valid_gsa_email(None))

    def test_validate_mappings_success(self):
        required_sas = {
            ("prod", "sa-1"): "arn:aws:iam::123:role/role-1",
            ("prod", "sa-2"): "arn:aws:iam::123:role/role-2",
        }
        identity_map = {
            "arn:aws:iam::123:role/role-1": (
                "sa-1@proj.iam.gserviceaccount.com"
            ),
            "arn:aws:iam::123:role/role-2": (
                "123-compute@developer.gserviceaccount.com"
            ),
        }
        with self.assertLogs(
            "validate_identity_map", level="WARNING"
        ) as log_cm:
            missing = validate_mappings(required_sas, identity_map)
            self.assertEqual(missing, [])
            self.assertTrue(
                any(
                    "default Compute Engine service account" in msg
                    for msg in log_cm.output
                )
            )

    def test_validate_mappings_invalid_email(self):
        required_sas = {
            ("prod", "sa-1"): "arn:aws:iam::123:role/role-1",
        }
        identity_map = {
            "arn:aws:iam::123:role/role-1": "invalid-email@gmail.com",
        }
        missing = validate_mappings(required_sas, identity_map)
        self.assertEqual(
            missing, ["prod/sa-1 (requires: arn:aws:iam::123:role/role-1)"]
        )

    def test_validate_mappings_missing_mapping(self):
        required_sas = {
            ("prod", "sa-1"): "arn:aws:iam::123:role/role-1",
        }
        identity_map = {}
        missing = validate_mappings(required_sas, identity_map)
        self.assertEqual(
            missing, ["prod/sa-1 (requires: arn:aws:iam::123:role/role-1)"]
        )

    def test_validate_schema_success(self):
        schema_path = (
            Path(__file__).resolve().parent.parent
            / "assets"
            / "schemas"
            / "identity-map.schema.json"
        )
        self.assertTrue(
            schema_path.is_file(), f"Schema file not found at {schema_path}"
        )
        valid_data = [
            {
                "source": "arn:aws:iam::123:role/r",
                "target": "sa@proj.iam.gserviceaccount.com",
            }
        ]
        validate_schema(valid_data, schema_path)

    def test_validate_schema_invalid_data(self):
        schema_path = (
            Path(__file__).resolve().parent.parent
            / "assets"
            / "schemas"
            / "identity-map.schema.json"
        )
        self.assertTrue(
            schema_path.is_file(), f"Schema file not found at {schema_path}"
        )
        invalid_data = [{"source": 123}]
        with self.assertRaises(jsonschema.ValidationError):
            validate_schema(invalid_data, schema_path)

    def test_validate_schema_missing_file(self):
        non_existent_path = Path("/path/does/not/exist/schema.json")
        with self.assertRaises(FileNotFoundError):
            validate_schema([], non_existent_path)

    def test_validate_schema_workload_handoff_cluster_level_success(self):
        schema_path = (
            Path(__file__).resolve().parent.parent
            / "assets"
            / "schemas"
            / "workload-handoff.schema.json"
        )
        self.assertTrue(
            schema_path.is_file(), f"Schema file not found at {schema_path}"
        )
        valid_cluster_handoff = {
            "run_id": "run-001",
            "clusters": [
                {
                    "source_cluster_name": "prod-cluster",
                    "namespaces": [
                        {
                            "name": "prod",
                            "workloads": [
                                {
                                    "name": "web-app",
                                    "kind": "Deployment",
                                    "dependencies": {
                                        "images": ["nginx:latest"],
                                        "irsa_role_arn": (
                                            "arn:aws:iam::123:role/web"
                                        ),
                                        "service_account": "web-sa",
                                        "storage": {
                                            "pvc_names": [],
                                            "volume_claim_templates": [],
                                            "rwx_file_shares": [],
                                        },
                                        "ingresses": [],
                                        "http_routes": [],
                                        "secrets": [],
                                        "configmaps": [],
                                        "services": [],
                                        "data_dependencies": [],
                                    },
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        validate_schema(valid_cluster_handoff, schema_path)

    def test_validate_schema_workload_handoff_namespace_level_success(self):
        schema_path = (
            Path(__file__).resolve().parent.parent
            / "assets"
            / "schemas"
            / "workload-handoff-namespace.schema.json"
        )
        self.assertTrue(
            schema_path.is_file(), f"Schema file not found at {schema_path}"
        )
        valid_ns_handoff = {
            "run_id": "run-002",
            "source_cluster_name": "prod-cluster",
            "namespace": "backend",
            "workloads": [
                {
                    "name": "api-server",
                    "kind": "StatefulSet",
                    "dependencies": {
                        "images": ["api:v1"],
                        "irsa_role_arn": "arn:aws:iam::123:role/api",
                        "service_account": "api-sa",
                        "storage": {
                            "pvc_names": ["data-pvc"],
                            "volume_claim_templates": [],
                            "rwx_file_shares": [],
                        },
                        "ingresses": [],
                        "http_routes": [],
                        "secrets": [],
                        "configmaps": [],
                        "services": [],
                        "data_dependencies": [],
                    },
                }
            ],
        }
        validate_schema(valid_ns_handoff, schema_path)

    def test_validate_schema_workload_handoff_missing_required_fields(self):
        schema_path = (
            Path(__file__).resolve().parent.parent
            / "assets"
            / "schemas"
            / "workload-handoff.schema.json"
        )
        # Missing required 'run_id' and 'dependencies'
        invalid_data = {
            "clusters": [
                {
                    "source_cluster_name": "prod-cluster",
                    "namespaces": [
                        {
                            "name": "prod",
                            "workloads": [
                                {
                                    "name": "web-app",
                                    "kind": "Deployment",
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        with self.assertRaises(jsonschema.ValidationError):
            validate_schema(invalid_data, schema_path)


if __name__ == "__main__":
    unittest.main()
