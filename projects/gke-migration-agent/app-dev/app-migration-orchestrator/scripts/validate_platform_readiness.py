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
"""Platform and Workload Handoff readiness validation script."""

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

import yaml
from utils import (
    find_any_file_recursively,
    find_file_recursively,
    load_json,
    validate_schema,
)
from validate_gcp_env import (
    configure_gke_context,
    is_active_gke_context,
    verify_gcloud_connection,
    verify_gcp_project,
    verify_gke_cluster,
    verify_kubectl_connection,
)

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("validate_platform_readiness")

CLUSTER_SCOPED_KINDS = {
    "StorageClass",
    "ClusterRole",
    "ClusterRoleBinding",
    "CustomResourceDefinition",
    "Namespace",
    "PersistentVolume",
    "APIService",
}


def parse_yaml_documents(file_path: Path) -> list[tuple[str, str, str]]:
    """Parser to extract (kind, name, namespace) of Kubernetes resources."""
    discovered = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            docs = yaml.safe_load_all(f)
            for doc in docs:
                if not isinstance(doc, dict):
                    continue
                # Handle standard Kubernetes List resources
                if doc.get("kind") == "List" or "items" in doc:
                    items = doc.get("items", [])
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        kind = item.get("kind")
                        metadata = item.get("metadata", {})
                        name = metadata.get("name")
                        namespace = (
                            None
                            if kind in CLUSTER_SCOPED_KINDS
                            else (metadata.get("namespace") or "default")
                        )
                        if kind and name:
                            discovered.append((kind, name, namespace))
                else:
                    kind = doc.get("kind")
                    metadata = doc.get("metadata", {})
                    name = metadata.get("name")
                    namespace = (
                        None
                        if kind in CLUSTER_SCOPED_KINDS
                        else (metadata.get("namespace") or "default")
                    )
                    if kind and name:
                        discovered.append((kind, name, namespace))
    except (OSError, yaml.YAMLError) as e:
        logger.error("Failed to parse manifest file %s: %s", file_path, e)
        raise ValueError(
            f"Failed to parse manifest file {file_path}: {e}"
        ) from e
    return discovered


def validate_raw_manifests(
    workloads: list[dict],
    raw_manifests_dir: Path,
    target_namespaces: set[str] = None,
) -> None:
    """Validates that all workloads listed in the handoff are present.

    Checks the raw manifests directory.
    """
    logger.info(
        "Validating raw manifests in directory '%s'...", raw_manifests_dir
    )
    if not raw_manifests_dir.exists():
        logger.error(
            "Raw manifests directory does not exist: %s", raw_manifests_dir
        )
        raise SystemExit(1)

    # 1. Discover all manifests (kind, name, namespace)
    discovered = set()
    for root, dirs, files in os.walk(raw_manifests_dir):
        # Ignore hidden directories (e.g. .terraform, .git)
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for file in files:
            if file.endswith((".yaml", ".yml")):
                file_path = Path(root) / file
                res = parse_yaml_documents(file_path)
                for kind, name, namespace in res:
                    if target_namespaces is not None:
                        if not namespace or namespace not in target_namespaces:
                            continue
                    discovered.add((kind, name))

    logger.info("Discovered %d resources in raw manifests.", len(discovered))

    # 2. Match with workloads list
    missing = []
    for wl in workloads:
        name = wl.get("name")
        kind = wl.get("kind")
        if (kind, name) not in discovered:
            missing.append(f"{kind}/{name}")

    if missing:
        logger.error(
            "Verification failed! The following workloads listed in the "
            "handoff are missing from raw manifests: %s",
            ", ".join(missing),
        )
        raise SystemExit(1)

    logger.info(
        "✓ All workloads listed in the handoff are present in raw manifests."
    )


def main() -> None:
    """Main entrypoint for validation."""
    parser = argparse.ArgumentParser(
        description="GKE Migration Agent Platform Readiness Validator"
    )
    parser.add_argument(
        "--handoff-dir",
        type=Path,
        required=True,
        help=(
            "Path to directory containing handoff files "
            "(platform-handoff.json, image-map.json, and "
            "workload-handoff.json or workload-handoff-namespace.json)"
        ),
    )
    parser.add_argument(
        "--raw-manifests-dir",
        type=Path,
        default=None,
        help="Path to raw Kubernetes manifests/YAML files",
    )
    parser.add_argument(
        "--skip-cloud-checks",
        action="store_true",
        help=(
            "Skip active cloud resources connectivity checks "
            "(useful for offline mode/testing)"
        ),
    )

    args = parser.parse_args()
    script_dir = Path(__file__).resolve().parent

    # Path to schemas
    schemas_dir = script_dir.parent / "assets" / "schemas"
    platform_schema = schemas_dir / "platform-handoff.schema.json"
    workload_schema = schemas_dir / "workload-handoff.schema.json"
    workload_ns_schema = schemas_dir / "workload-handoff-namespace.schema.json"
    image_map_schema = schemas_dir / "image-map.schema.json"

    # 1. Resolve and Load files
    logger.info(
        "Resolving and loading handoff files from %s...", args.handoff_dir
    )
    platform_file = find_file_recursively(
        args.handoff_dir, "platform-handoff.json"
    )
    image_map_file = find_file_recursively(args.handoff_dir, "image-map.json")
    workload_file = find_any_file_recursively(
        args.handoff_dir,
        ["workload-handoff.json", "workload-handoff-namespace.json"],
    )

    identity_map_file = find_file_recursively(
        args.handoff_dir, "identity-map.json"
    )
    storage_map_file = find_file_recursively(
        args.handoff_dir, "storage-map.json"
    )
    network_map_file = find_file_recursively(
        args.handoff_dir, "network-map.json"
    )
    observability_map_file = find_file_recursively(
        args.handoff_dir, "observability-map.json"
    )

    missing = []
    if not platform_file:
        missing.append("platform-handoff.json")
    if not image_map_file:
        missing.append("image-map.json")
    if not workload_file:
        missing.append(
            "workload-handoff.json or workload-handoff-namespace.json"
        )
    if not identity_map_file:
        missing.append("identity-map.json")
    if not storage_map_file:
        missing.append("storage-map.json")
    if not network_map_file:
        missing.append("network-map.json")
    if not observability_map_file:
        missing.append("observability-map.json")

    if missing:
        logger.error(
            "Missing required handoff file(s) in directory '%s': %s",
            args.handoff_dir,
            ", ".join(missing),
        )
        raise SystemExit(1)

    platform_data = load_json(platform_file)
    workload_data = load_json(workload_file)
    image_map_data = load_json(image_map_file)

    # 2. Validate Platform Handoff
    logger.info("Validating platform-handoff.json against schema...")
    validate_schema(platform_data, platform_schema)
    logger.info("✓ platform-handoff.json is valid.")

    # Validate Image Map
    logger.info("Validating image-map.json against schema...")
    validate_schema(image_map_data, image_map_schema)
    logger.info("✓ image-map.json is valid.")

    required_maps = {
        "identity-map.json": (identity_map_file, "identity-map.schema.json"),
        "storage-map.json": (storage_map_file, "storage-map.schema.json"),
        "network-map.json": (network_map_file, "network-map.schema.json"),
        "observability-map.json": (
            observability_map_file,
            "observability-map.schema.json",
        ),
    }

    for filename, (file_path, schema_name) in required_maps.items():
        logger.info("Loading %s for validation...", filename)
        map_data = load_json(file_path)
        schema_path = schemas_dir / schema_name
        if schema_path.exists():
            logger.info("Validating %s against schema...", filename)
            validate_schema(map_data, schema_path)
            logger.info("✓ %s is valid against schema.", filename)
        else:
            logger.warning(
                "Schema %s not found. Skipping schema validation for %s.",
                schema_name,
                filename,
            )

    # Validate Image Map content and Registry availability via separate script
    logger.info("Calling validate_images.py to perform image validation...")
    cmd = [
        sys.executable,
        str(script_dir / "validate_images.py"),
        "--workload-file",
        str(workload_file),
        "--image-map-file",
        str(image_map_file),
    ]
    if args.raw_manifests_dir:
        cmd.extend(["--raw-manifests-dir", str(args.raw_manifests_dir)])
    if args.skip_cloud_checks:
        cmd.append("--skip-cloud-checks")

    try:
        subprocess.run(cmd, check=True)
        logger.info(
            "✓ Image mapping and target registry verification complete."
        )
    except subprocess.CalledProcessError as e:
        logger.error("Image and registry validation failed.")
        raise SystemExit(1) from e

    # Validate GCP Project, Clusters, and Configure Kubectl Context
    if not args.skip_cloud_checks and verify_gcloud_connection():
        target_project = platform_data.get("target_project")
        verify_gcp_project(target_project)
        for cluster in platform_data.get("clusters", []):
            cluster_name = cluster.get("name")
            location = cluster.get("location")
            # Verify cluster exists
            verify_gke_cluster(cluster_name, location, target_project)
            # Check and auto-configure kubectl context
            if not is_active_gke_context(cluster_name):
                configure_gke_context(cluster_name, location, target_project)

    # 3. Detect and Validate Workload Schema
    logger.info("Detecting workload handoff schema type...")
    if "clusters" in workload_data:
        logger.info("Detected cluster-level handoff. Validating...")
        validate_schema(workload_data, workload_schema)
    elif "namespace" in workload_data:
        logger.info("Detected namespace-scoped handoff. Validating...")
        validate_schema(workload_data, workload_ns_schema)
    else:
        logger.error(
            "Invalid workload handoff JSON structure: Root must contain "
            "'clusters' or 'namespace' keys."
        )
        raise SystemExit(1)
    logger.info("✓ workload-handoff.json is valid.")

    # Resolve target namespaces
    target_namespaces = None
    if "namespace" in workload_data:
        target_namespaces = {workload_data["namespace"]}
    elif "clusters" in workload_data:
        target_namespaces = set()
        for c in workload_data.get("clusters", []):
            for ns in c.get("namespaces", []):
                if ns.get("name"):
                    target_namespaces.add(ns["name"])

    # 3b. Validate Raw Manifest coverage if --raw-manifests-dir is provided
    if args.raw_manifests_dir:
        workloads = []
        if "clusters" in workload_data:
            for c in workload_data.get("clusters", []):
                for ns in c.get("namespaces", []):
                    workloads.extend(ns.get("workloads", []))
        elif "workloads" in workload_data:
            workloads.extend(workload_data.get("workloads", []))

        validate_raw_manifests(
            workloads, args.raw_manifests_dir, target_namespaces
        )

    # 4. Perform smoke tests / Verify kubectl connection
    if not args.skip_cloud_checks:
        verify_kubectl_connection()

    logger.info(
        "Platform and Workload handoff verification complete. "
        "Environment is ready."
    )


if __name__ == "__main__":
    main()
