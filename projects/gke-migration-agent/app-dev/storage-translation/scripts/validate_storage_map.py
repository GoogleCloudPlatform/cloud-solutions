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
"""Storage Map validation script."""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import jsonschema
import yaml

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("validate_storage_map")


def load_json(file_path: Path) -> dict | list:
    """Loads JSON file from disk."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_schema(data: dict | list, schema_path: Path) -> None:
    """Validates data against a JSON schema file."""
    schema = load_json(schema_path)
    jsonschema.validate(instance=data, schema=schema)


def extract_required_pvcs(workload_data: dict) -> set[tuple[str, str]]:
    """Extracts all PVCs that are dependencies of active workloads.

    Returns a set of tuples (namespace, pvc_name).
    """
    required_pvcs = set()

    # Determine if it's cluster-level or namespace-level handoff
    if "clusters" in workload_data:
        # Cluster-level handoff
        for cluster in workload_data.get("clusters", []):
            for ns_block in cluster.get("namespaces", []):
                namespace = ns_block.get("name")
                for wl in ns_block.get("workloads", []):
                    storage = wl.get("dependencies", {}).get("storage", {})
                    pvc_names = storage.get("pvc_names", [])
                    for pvc in pvc_names:
                        required_pvcs.add((namespace, pvc))
                    vct_names = storage.get("volume_claim_templates", [])
                    for vct in vct_names:
                        required_pvcs.add((namespace, vct))
    elif "namespace" in workload_data:
        # Namespace-level handoff
        namespace = workload_data.get("namespace")
        for wl in workload_data.get("workloads", []):
            storage = wl.get("dependencies", {}).get("storage", {})
            pvc_names = storage.get("pvc_names", [])
            for pvc in pvc_names:
                required_pvcs.add((namespace, pvc))
            vct_names = storage.get("volume_claim_templates", [])
            for vct in vct_names:
                required_pvcs.add((namespace, vct))

    return required_pvcs


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


def parse_pvc_resource(
    metadata: dict, spec: dict, pvc_classes: dict[tuple[str, str], str]
) -> None:
    """Extracts storageClassName from a PersistentVolumeClaim spec."""
    ns = metadata.get("namespace", "default")
    name = metadata.get("name")
    sc = spec.get("storageClassName", "default")
    if name:
        pvc_classes[(ns, name)] = sc


def parse_statefulset_resource(
    metadata: dict, spec: dict, pvc_classes: dict[tuple[str, str], str]
) -> None:
    """Extracts storageClassName from StatefulSet volumeClaimTemplates."""
    ns = metadata.get("namespace", "default")
    vcts = spec.get("volumeClaimTemplates", [])
    if isinstance(vcts, list):
        for vct in vcts:
            if isinstance(vct, dict):
                vct_meta = vct.get("metadata")
                if not isinstance(vct_meta, dict):
                    vct_meta = {}
                vct_spec = vct.get("spec")
                if not isinstance(vct_spec, dict):
                    vct_spec = {}
                name = vct_meta.get("name")
                sc = vct_spec.get("storageClassName", "default")
                if name:
                    pvc_classes[(ns, name)] = sc


RESOURCE_PARSERS = {
    "PersistentVolumeClaim": parse_pvc_resource,
    "StatefulSet": parse_statefulset_resource,
}


def process_storage_resource(
    item: Any, pvc_classes: dict[tuple[str, str], str]
) -> None:
    """Extracts storage classes from a single Kubernetes resource."""
    if not isinstance(item, dict):
        return
    kind = item.get("kind")
    metadata = item.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    spec = item.get("spec")
    if not isinstance(spec, dict):
        spec = {}

    parser = RESOURCE_PARSERS.get(kind)
    if parser:
        parser(metadata, spec, pvc_classes)


def extract_pvc_storage_classes(
    raw_manifests_dir: Path,
) -> dict[tuple[str, str], str]:
    """Scans raw manifests for PVCs and StatefulSets to extract
    storageClassName.
    """
    pvc_classes = {}
    for root, dirs, files in os.walk(raw_manifests_dir):
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

                            if doc.get("kind") == "List" or "items" in doc:
                                for item in doc.get("items", []):
                                    process_storage_resource(item, pvc_classes)
                            else:
                                process_storage_resource(doc, pvc_classes)
                except (OSError, yaml.YAMLError) as e:
                    logger.warning("Failed to parse %s: %s", file_path, e)
    return pvc_classes


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate Storage Mapping completeness"
    )
    parser.add_argument(
        "--handoff-dir",
        type=Path,
        required=True,
        help=(
            "Path to directory containing handoff files "
            "(workload-handoff.json and storage-map.json)"
        ),
    )
    parser.add_argument(
        "--raw-manifests-dir",
        type=Path,
        default=None,
        help=(
            "Path to raw Kubernetes manifests/YAML files "
            "to extract PVC storageClasses"
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

        storage_map_file = find_file_recursively(
            args.handoff_dir, "storage-map.json"
        )

        if not workload_file:
            raise FileNotFoundError(
                f"Workload handoff file not found recursively in "
                f"{args.handoff_dir}"
            )
        if not storage_map_file:
            raise FileNotFoundError(
                f"storage-map.json not found recursively in {args.handoff_dir}"
            )

        workload_data = load_json(workload_file)
        raw_storage_map = load_json(storage_map_file)

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

        # 3. Validate storage-map.json against JSON schema
        storage_schema_file = find_file_recursively(
            skill_root, "storage-map.schema.json"
        )
        if not storage_schema_file:
            raise FileNotFoundError(
                "Schema file 'storage-map.schema.json' not found"
            )
        validate_schema(raw_storage_map, storage_schema_file)
        logger.info("✓ storage-map.json conforms to schema.")

    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        logger.error("%s", e)
        sys.exit(1)
    except jsonschema.ValidationError as e:
        logger.error("Failed schema validation: %s", e.message)
        sys.exit(1)

    storage_map = {
        item["source"]: item["target"]
        for item in raw_storage_map
        if isinstance(item, dict) and "source" in item and "target" in item
    }

    # 2. Extract PVCs requiring mapping
    required_pvcs = extract_required_pvcs(workload_data)
    logger.info(
        "Found %d PVC dependency(ies) in workload handoff.", len(required_pvcs)
    )

    # 3. Extract PVC storage classes from raw manifests if provided
    pvc_classes = {}
    if args.raw_manifests_dir:
        pvc_classes = extract_pvc_storage_classes(args.raw_manifests_dir)

    # 4. Verify mappings exist in storage-map.json
    missing_mappings = []
    for namespace, pvc in required_pvcs:
        eks_class = pvc_classes.get((namespace, pvc))
        if eks_class:
            if eks_class not in storage_map:
                missing_mappings.append(
                    f"PVC '{namespace}/{pvc}' requires "
                    f"StorageClass '{eks_class}'"
                )
        else:
            # Check if default storage mapping exists in storage_map
            if "default" in storage_map:
                logger.warning(
                    "PVC '%s/%s' does not specify an explicit StorageClass; "
                    "using 'default' target mapping in storage-map.json.",
                    namespace,
                    pvc,
                )
            else:
                missing_mappings.append(
                    f"PVC '{namespace}/{pvc}' does not specify an explicit "
                    "StorageClass and no 'default' mapping exists in "
                    "storage-map.json"
                )

    if missing_mappings:
        logger.error(
            "Verification failed! The following PVCs require "
            "StorageClasses that are missing valid target mappings "
            "in storage-map.json:\n%s",
            "\n".join(f" - {m}" for m in missing_mappings),
        )
        sys.exit(1)

    logger.info(
        "✓ All PVC dependencies have valid storage class mappings "
        "in storage-map.json."
    )


if __name__ == "__main__":
    main()
