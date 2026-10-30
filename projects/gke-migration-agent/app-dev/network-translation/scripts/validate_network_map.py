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
"""Network Map validation script."""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import jsonschema
import yaml

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("validate_network_map")


def load_json(file_path: Path) -> dict:
    """Loads JSON file from disk."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("File not found: %s", file_path)
        raise
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JSON in %s: %s", file_path, e)
        raise


def validate_schema(data: dict, schema_path: Path) -> None:
    """Validates data dictionary against a JSON schema file."""
    schema = load_json(schema_path)
    jsonschema.validate(instance=data, schema=schema)


def parse_ingress(
    spec: dict,
    metadata: dict,
    classes: set[str],
    certs: set[str],
    domains: set[str],
) -> None:
    """Extracts network dependencies from Ingress manifests."""
    ing_class = spec.get("ingressClassName")
    if ing_class:
        classes.add(ing_class)
    annotations = metadata.get("annotations", {})
    legacy_class = annotations.get("kubernetes.io/ingress.class")
    if legacy_class:
        classes.add(legacy_class)

    for rule in spec.get("rules", []):
        host = rule.get("host")
        if host:
            domains.add(host)

    for tls in spec.get("tls", []):
        secret_name = tls.get("secretName")
        if secret_name:
            certs.add(secret_name)

    acm_arn = annotations.get("alb.ingress.kubernetes.io/certificate-arn")
    if acm_arn:
        for arn in acm_arn.split(","):
            arn_cleaned = arn.strip()
            if arn_cleaned:
                certs.add(arn_cleaned)


def parse_gateway(
    spec: dict, classes: set[str], certs: set[str], domains: set[str]
) -> None:
    """Extracts network dependencies from Gateway manifests."""
    gw_class = spec.get("gatewayClassName")
    if gw_class:
        classes.add(gw_class)

    for l in spec.get("listeners", []):
        hostname = l.get("hostname")
        if hostname:
            domains.add(hostname)
        tls = l.get("tls", {})
        for ref in tls.get("certificateRefs", []):
            name = ref.get("name")
            if name:
                certs.add(name)


def parse_http_route(spec: dict, domains: set[str]) -> None:
    """Extracts network dependencies from HTTPRoute manifests."""
    for host in spec.get("hostnames", []):
        if host:
            domains.add(host)


def parse_service(
    spec: dict, metadata: dict, classes: set[str], certs: set[str]
) -> None:
    """Extracts network dependencies from Service (LoadBalancer) manifests."""
    if spec.get("type") == "LoadBalancer":
        annotations = metadata.get("annotations", {})
        lb_type = annotations.get(
            "service.beta.kubernetes.io/aws-load-balancer-type"
        )
        if lb_type:
            classes.add(lb_type)

        ssl_cert = annotations.get(
            "service.beta.kubernetes.io/aws-load-balancer-ssl-cert"
        )
        if ssl_cert:
            for arn in ssl_cert.split(","):
                arn_cleaned = arn.strip()
                if arn_cleaned:
                    certs.add(arn_cleaned)


def parse_network_policy(spec: dict, cidrs: set[str]) -> None:
    """Extracts network dependencies from NetworkPolicy manifests."""
    for rule_type in ["ingress", "egress"]:
        rules = spec.get(rule_type, [])
        for rule in rules:
            targets = rule.get("from" if rule_type == "ingress" else "to", [])
            for t in targets:
                ip_block = t.get("ipBlock", {})
                cidr = ip_block.get("cidr")
                if cidr:
                    cidrs.add(cidr)


KIND_PARSERS = {
    "Ingress": (
        lambda spec, meta, classes, certs, cidrs, domains: parse_ingress(
            spec, meta, classes, certs, domains
        )
    ),
    "Gateway": (
        lambda spec, meta, classes, certs, cidrs, domains: parse_gateway(
            spec, classes, certs, domains
        )
    ),
    "HTTPRoute": (
        lambda spec, meta, classes, certs, cidrs, domains: parse_http_route(
            spec, domains
        )
    ),
    "Service": (
        lambda spec, meta, classes, certs, cidrs, domains: parse_service(
            spec, meta, classes, certs
        )
    ),
    "NetworkPolicy": (
        lambda spec, meta, classes, certs, cidrs, domains: parse_network_policy(
            spec, cidrs
        )
    ),
}


def scan_manifests_for_network_dependencies(
    manifests_dir: Path,
) -> tuple[set[str], set[str], set[str], set[str]]:
    """Scans all YAML files in manifests_dir and returns:
    1. A set of Ingress/Gateway Classes found in manifests.
    2. A set of Certificate references (ACM ARNs or secrets) found in manifests.
    3. A set of CIDRs used in NetworkPolicies.
    4. A set of hostnames/domains used in Ingresses/Gateways/HTTPRoutes.
    """
    classes = set()
    certs = set()
    cidrs = set()
    domains = set()

    if not manifests_dir.exists():
        return classes, certs, cidrs, domains

    for root, dirs, files in os.walk(manifests_dir):
        # Ignore hidden directories (e.g. .terraform, .git)
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for file in files:
            if file.endswith((".yaml", ".yml")):
                file_path = Path(root) / file
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        docs = yaml.safe_load_all(f)
                        for doc in docs:
                            if not isinstance(doc, dict):
                                continue

                            kind = doc.get("kind")
                            parser = KIND_PARSERS.get(kind)
                            if parser:
                                parser(
                                    doc.get("spec", {}),
                                    doc.get("metadata", {}),
                                    classes,
                                    certs,
                                    cidrs,
                                    domains,
                                )

                except (OSError, yaml.YAMLError) as e:
                    logger.warning("Failed to parse %s: %s", file_path, e)

    return classes, certs, cidrs, domains


def find_file_recursively(directory: Path, filename: str) -> Path | None:
    """Recursively searches for a file in the directory and subdirectories.

    Ensures exactly one matching file is found within the specified handoff
    directory.

    Raises:
        ValueError: If multiple matching files are found.
    """
    matches = []
    for root, dirs, files in os.walk(directory):
        # Ignore hidden directories (e.g. .terraform, .git)
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        if filename in files:
            matches.append(Path(root) / filename)

    if len(matches) > 1:
        matches_formatted = "\n".join(f" - {m}" for m in matches)
        raise ValueError(
            f"Multiple instances of '{filename}' found in '{directory}':\n"
            f"{matches_formatted}\n"
            "Please specify a --handoff-dir specific to a single migration run."
        )

    return matches[0] if matches else None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate Network Mapping completeness"
    )
    parser.add_argument(
        "--handoff-dir",
        type=Path,
        required=True,
        help=(
            "Path to directory containing handoff files "
            "(workload-handoff.json and network-map.json)"
        ),
    )
    parser.add_argument(
        "--raw-manifests-dir",
        type=Path,
        default=None,
        help=(
            "Path to raw Kubernetes manifests/YAML files to check "
            "for EKS network dependencies"
        ),
    )

    args = parser.parse_args()

    try:
        workload_file = find_file_recursively(
            args.handoff_dir, "workload-handoff.json"
        )
        if not workload_file:
            workload_file = find_file_recursively(
                args.handoff_dir, "workload-handoff-namespace.json"
            )

        network_map_file = find_file_recursively(
            args.handoff_dir, "network-map.json"
        )

        if not workload_file:
            raise FileNotFoundError(
                f"Workload handoff file not found recursively in "
                f"{args.handoff_dir}"
            )
        if not network_map_file:
            raise FileNotFoundError(
                f"network-map.json not found recursively in {args.handoff_dir}"
            )

        workload_data = load_json(workload_file)
        network_map = load_json(network_map_file)

        # 2. Validate workload handoff against JSON schema
        skill_root = Path(__file__).resolve().parent.parent
        if "clusters" in workload_data:
            workload_schema_name = "workload-handoff.schema.json"
        elif "namespace" in workload_data:
            workload_schema_name = "workload-handoff-namespace.schema.json"
        else:
            raise ValueError(
                f"Invalid workload handoff JSON structure in "
                f"'{workload_file}': Root must contain 'clusters' or "
                "'namespace' keys."
            )

        workload_schema_file = find_file_recursively(
            skill_root, workload_schema_name
        )
        if not workload_schema_file:
            raise FileNotFoundError(
                f"Schema file '{workload_schema_name}' not found"
            )
        validate_schema(workload_data, workload_schema_file)

        # 3. Validate network-map.json against JSON schema
        network_schema_file = find_file_recursively(
            skill_root, "network-map.schema.json"
        )
        if not network_schema_file:
            raise FileNotFoundError(
                "Schema file 'network-map.schema.json' not found"
            )
        validate_schema(network_map, network_schema_file)
        logger.info("✓ network-map.json conforms to schema.")

    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        logger.error("%s", e)
        sys.exit(1)
    except jsonschema.ValidationError as e:
        logger.error("Failed schema validation: %s", e.message)
        sys.exit(1)

    classes = set()
    certs = set()
    cidrs = set()
    domains = set()

    # 3. Extract network dependencies from raw manifests if provided
    if args.raw_manifests_dir and args.raw_manifests_dir.exists():
        (
            classes,
            certs,
            cidrs,
            domains,
        ) = scan_manifests_for_network_dependencies(args.raw_manifests_dir)
    else:
        logger.warning(
            "No raw manifests directory provided or found. Skipping scan for "
            "EKS network dependencies. Validating only basic map properties."
        )

    # 4. Verify mappings exist in network-map.json
    failed = False

    class_mappings = network_map.get("class_mappings", {})
    missing_classes = [c for c in classes if c not in class_mappings]
    if missing_classes:
        logger.error(
            "Verification failed! The following EKS network/ingress "
            "classes are missing mappings under 'class_mappings' in "
            "network-map.json:\n%s",
            "\n".join(f" - {c}" for c in missing_classes),
        )
        failed = True

    cert_mappings = network_map.get("certificates", {})
    missing_certs = [cert for cert in certs if cert not in cert_mappings]
    if missing_certs:
        logger.error(
            "Verification failed! The following AWS certificate "
            "references are missing mappings under 'certificates' in "
            "network-map.json:\n%s",
            "\n".join(f" - {cert}" for cert in missing_certs),
        )
        failed = True

    cidr_mappings = network_map.get("cidr_mappings", {})
    missing_cidrs = [cidr for cidr in cidrs if cidr not in cidr_mappings]
    if missing_cidrs:
        logger.error(
            "Verification failed! The following NetworkPolicy CIDRs "
            "are missing mappings under 'cidr_mappings' in "
            "network-map.json:\n%s",
            "\n".join(f" - {cidr}" for cidr in missing_cidrs),
        )
        failed = True

    domain_mappings = network_map.get("domain_mappings", {})
    if domain_mappings:
        for domain, target_domain in domain_mappings.items():
            if not isinstance(target_domain, str) or not target_domain:
                logger.error(
                    "Invalid domain mapping for '%s': "
                    "target must be a non-empty string",
                    domain,
                )
                failed = True

    if domains:
        logger.info(
            "Discovered %d unique hostnames in manifests: %s",
            len(domains),
            ", ".join(sorted(domains)),
        )
        if domain_mappings:
            unmapped = [d for d in domains if d not in domain_mappings]
            if unmapped:
                logger.info(
                    "Note: The following hostnames do not have domain_mappings "
                    "and will retain original names:\n%s",
                    "\n".join(f" - {d}" for d in unmapped),
                )

    if failed:
        sys.exit(1)

    logger.info(
        "✓ All active EKS network classes, certificates, and CIDRs "
        "have valid mappings in network-map.json."
    )


if __name__ == "__main__":
    main()
