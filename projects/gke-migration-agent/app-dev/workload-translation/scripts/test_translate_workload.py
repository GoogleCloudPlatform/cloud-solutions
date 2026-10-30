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
"""Unit tests for translate_workload.py."""

import json
import tempfile
import unittest
from pathlib import Path

from translate_workload import (
    load_target_namespaces,
    translate_image,
    translate_pvc,
    translate_service_account,
)


class TestTranslateWorkload(unittest.TestCase):
    """Unit tests for EKS to GKE workload translation functions."""

    def test_translate_image(self):
        container = {
            "name": "web",
            "image": "123456789012.dkr.ecr.us-east-1.amazonaws.com/my-app:v1",
        }
        image_map = {
            "123456789012.dkr.ecr.us-east-1.amazonaws.com/my-app:v1": (
                "us-docker.pkg.dev/gke-migration/my-app:v1"
            )
        }
        translate_image(container, image_map)
        self.assertEqual(
            container["image"], "us-docker.pkg.dev/gke-migration/my-app:v1"
        )

    def test_translate_service_account(self):
        sa = {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {
                "name": "frontend-sa",
                "namespace": "production",
                "annotations": {
                    "eks.amazonaws.com/role-arn": (
                        "arn:aws:iam::123456789012:role/eks-pod-role"
                    ),
                    "eks.amazonaws.com/sts-regional-endpoints": "true",
                },
            },
        }
        identity_map = {
            "production/frontend-sa": {
                "gsa_email": "my-gsa@project.iam.gserviceaccount.com"
            }
        }
        translate_service_account(sa, identity_map)
        annotations = sa["metadata"]["annotations"]
        self.assertNotIn("eks.amazonaws.com/role-arn", annotations)
        self.assertNotIn(
            "eks.amazonaws.com/sts-regional-endpoints", annotations
        )
        self.assertEqual(
            annotations["iam.gke.io/gcp-service-account"],
            "my-gsa@project.iam.gserviceaccount.com",
        )

    def test_translate_pvc(self):
        pvc = {
            "apiVersion": "v1",
            "kind": "PersistentVolumeClaim",
            "metadata": {
                "name": "data-volume",
                "namespace": "production",
                "annotations": {
                    "volume.beta.kubernetes.io/storage-provisioner": (
                        "kubernetes.io/aws-ebs"
                    )
                },
            },
            "spec": {"storageClassName": "gp2"},
        }
        storage_map = {"gp2": {"target": "standard-rwo"}}
        translate_pvc(pvc, storage_map)
        self.assertEqual(pvc["spec"]["storageClassName"], "standard-rwo")
        self.assertNotIn(
            "volume.beta.kubernetes.io/storage-provisioner",
            pvc["metadata"]["annotations"],
        )

    def test_load_target_namespaces_namespace_scoped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            target = tmp_path / "workload-handoff-namespace.json"
            with open(target, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "run_id": "run-1",
                        "source_cluster_name": "cluster-1",
                        "namespace": "test-ns",
                        "workloads": [],
                    },
                    f,
                )

            namespaces = load_target_namespaces(tmp_path)
            self.assertEqual(namespaces, {"test-ns"})

    def test_load_target_namespaces_cluster_scoped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            target = tmp_path / "workload-handoff.json"
            with open(target, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "run_id": "run-1",
                        "clusters": [
                            {
                                "source_cluster_name": "cluster-1",
                                "namespaces": [
                                    {"name": "ns-1", "workloads": []},
                                    {"name": "ns-2", "workloads": []},
                                ],
                            }
                        ],
                    },
                    f,
                )

            namespaces = load_target_namespaces(tmp_path)
            self.assertEqual(namespaces, {"ns-1", "ns-2"})

    def test_load_target_namespaces_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            namespaces = load_target_namespaces(tmp_path)
            self.assertIsNone(namespaces)


if __name__ == "__main__":
    unittest.main()
