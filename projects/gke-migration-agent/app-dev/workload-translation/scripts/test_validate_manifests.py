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
"""Unit tests for validate_manifests.py."""

import unittest

from validate_manifests import check_autopilot_compatibility


class TestValidateManifests(unittest.TestCase):
    """Unit tests for validate_manifests.py logic."""

    def test_check_autopilot_compatibility_valid(self):
        manifest = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "valid-app"},
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": "web",
                                "securityContext": {"privileged": False},
                            }
                        ]
                    }
                }
            },
        }
        violations = check_autopilot_compatibility(manifest)
        self.assertEqual(violations, [])

    def test_check_autopilot_compatibility_violations(self):
        manifest = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "invalid-app"},
            "spec": {
                "template": {
                    "spec": {
                        "hostNetwork": True,
                        "volumes": [
                            {
                                "name": "host-vol",
                                "hostPath": {"path": "/tmp"},
                            }
                        ],
                        "containers": [
                            {
                                "name": "web",
                                "securityContext": {
                                    "privileged": True,
                                    "capabilities": {"add": ["CAP_SYS_ADMIN"]},
                                },
                            }
                        ],
                    }
                }
            },
        }
        violations = check_autopilot_compatibility(manifest)
        self.assertEqual(len(violations), 4)
        self.assertTrue(any("hostNetwork" in v for v in violations))
        self.assertTrue(any("hostPath" in v for v in violations))
        self.assertTrue(any("privileged" in v for v in violations))
        self.assertTrue(any("capabilities" in v for v in violations))


if __name__ == "__main__":
    unittest.main()
