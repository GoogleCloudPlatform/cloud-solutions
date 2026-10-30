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
"""Unit tests for validate_network_map.py."""

import json
import tempfile
import unittest
from pathlib import Path

from validate_network_map import (
    find_file_recursively,
    load_json,
    scan_manifests_for_network_dependencies,
    validate_schema,
)


class TestValidateNetworkMap(unittest.TestCase):
    """Test suite for network map validation functions."""

    def test_scan_manifests_ingress(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "ingress.yaml"
            manifest_content = """apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: shop-ingress
  namespace: prod
  annotations:
    alb.ingress.kubernetes.io/certificate-arn: "arn:aws:acm:us-west-2:123456789012:certificate/abc-123, arn:aws:acm:us-west-2:123456789012:certificate/xyz-789"
spec:
  ingressClassName: alb
  rules:
  - host: shop.example.com
  tls:
  - secretName: shop-tls
"""
            manifest_path.write_text(manifest_content, encoding="utf-8")

            classes, certs, cidrs, domains = (
                scan_manifests_for_network_dependencies(Path(tmpdir))
            )
            self.assertEqual(classes, {"alb"})
            self.assertEqual(
                certs,
                {
                    "shop-tls",
                    "arn:aws:acm:us-west-2:123456789012:certificate/abc-123",
                    "arn:aws:acm:us-west-2:123456789012:certificate/xyz-789",
                },
            )
            self.assertEqual(cidrs, set())
            self.assertEqual(domains, {"shop.example.com"})

    def test_scan_manifests_gateway_and_httproute(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "gateway.yaml"
            manifest_content = """apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: edge-gw
spec:
  gatewayClassName: eg-gateway
  listeners:
  - hostname: api.example.com
    tls:
      certificateRefs:
      - name: api-cert
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: api-route
spec:
  hostnames:
  - api.example.com
"""
            manifest_path.write_text(manifest_content, encoding="utf-8")

            classes, certs, cidrs, domains = (
                scan_manifests_for_network_dependencies(Path(tmpdir))
            )
            self.assertEqual(classes, {"eg-gateway"})
            self.assertEqual(certs, {"api-cert"})
            self.assertEqual(cidrs, set())
            self.assertEqual(domains, {"api.example.com"})

    def test_scan_manifests_service_and_network_policy(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "net.yaml"
            manifest_content = """apiVersion: v1
kind: Service
metadata:
  name: lb-svc
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-type: nlb
    service.beta.kubernetes.io/aws-load-balancer-ssl-cert: "arn:aws:acm:us-west-2:123456789012:certificate/nlb-cert"
spec:
  type: LoadBalancer
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny
spec:
  ingress:
  - from:
    - ipBlock:
        cidr: 10.0.0.0/16
"""
            manifest_path.write_text(manifest_content, encoding="utf-8")

            classes, certs, cidrs, domains = (
                scan_manifests_for_network_dependencies(Path(tmpdir))
            )
            self.assertEqual(classes, {"nlb"})
            self.assertEqual(
                certs,
                {"arn:aws:acm:us-west-2:123456789012:certificate/nlb-cert"},
            )
            self.assertEqual(cidrs, {"10.0.0.0/16"})
            self.assertEqual(domains, set())

    def test_find_file_recursively_single_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f1 = Path(tmpdir) / "sub" / "network-map.json"
            f1.parent.mkdir(parents=True, exist_ok=True)
            f1.write_text("{}", encoding="utf-8")

            res = find_file_recursively(Path(tmpdir), "network-map.json")
            self.assertEqual(res, f1)

    def test_find_file_recursively_multiple_matches(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f1 = Path(tmpdir) / "cluster-a" / "network-map.json"
            f2 = Path(tmpdir) / "cluster-b" / "network-map.json"
            f1.parent.mkdir(parents=True, exist_ok=True)
            f2.parent.mkdir(parents=True, exist_ok=True)
            f1.write_text("{}", encoding="utf-8")
            f2.write_text("{}", encoding="utf-8")

            with self.assertRaises(ValueError):
                find_file_recursively(Path(tmpdir), "network-map.json")

    def test_validate_schema(self):
        schema_path = (
            Path(__file__).resolve().parent.parent
            / "assets"
            / "schemas"
            / "network-map.schema.json"
        )
        valid_map = {
            "class_mappings": {"alb": "gke-l7-global-external-managed"},
            "certificates": {"cert-arn": "gcp-cert"},
            "domain_mappings": {"shop.example.com": "shop.gke.com"},
            "cidr_mappings": {"10.0.0.0/16": "172.16.0.0/16"},
        }
        if schema_path.exists():
            validate_schema(valid_map, schema_path)
        else:
            with tempfile.NamedTemporaryFile("w+", suffix=".json") as f:
                json.dump({"type": "object", "required": ["class_mappings"]}, f)
                f.flush()
                validate_schema(valid_map, Path(f.name))

    def test_load_json(self):
        with tempfile.NamedTemporaryFile(
            "w+", delete=False, suffix=".json"
        ) as f:
            json.dump({"key": "value"}, f)
            f_path = Path(f.name)
        try:
            data = load_json(f_path)
            self.assertEqual(data, {"key": "value"})
        finally:
            f_path.unlink()


if __name__ == "__main__":
    unittest.main()
