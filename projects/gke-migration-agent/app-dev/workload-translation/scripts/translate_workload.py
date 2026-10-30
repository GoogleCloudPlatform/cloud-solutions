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
"""GKE Workload Translation Engine."""

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
logger = logging.getLogger("translate_workload")


def load_target_namespaces(handoff_dir: Path) -> set[str] | None:
    """Resolves target namespaces from the workload handoff file.

    Checks workload-handoff.json and workload-handoff-namespace.json.
    """
    workload_file = find_file_recursively(handoff_dir, "workload-handoff.json")
    schema_name = "workload-handoff.schema.json"
    if not workload_file:
        workload_file = find_file_recursively(
            handoff_dir, "workload-handoff-namespace.json"
        )
        schema_name = "workload-handoff-namespace.schema.json"

    if workload_file:
        data = load_and_validate_json(workload_file, schema_name, handoff_dir)
        if data and isinstance(data, dict):
            if "namespace" in data:
                return {data["namespace"]}
            elif "clusters" in data:
                namespaces = set()
                for c in data.get("clusters", []):
                    for ns in c.get("namespaces", []):
                        if ns.get("name"):
                            namespaces.add(ns["name"])
                return namespaces
    return None


def load_json(file_path: Path) -> dict:
    """Loads JSON file from disk."""
    if not file_path or not file_path.exists():
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to parse JSON in %s: %s", file_path, e)
        raise


def load_and_validate_json(
    file_path: Path | None, schema_name: str, handoff_dir: Path
) -> dict | list:
    """Loads a JSON file and validates it against its schema if available."""
    if not file_path or not file_path.exists():
        return {}
    data = load_json(file_path)
    if not data:
        return {}

    schema_file = find_file_recursively(handoff_dir, schema_name)
    if not schema_file:
        script_dir = Path(__file__).resolve().parent
        schema_file = find_file_recursively(script_dir.parent, schema_name)

    if schema_file and schema_file.exists():
        schema_data = load_json(schema_file)
        if schema_data:
            try:
                jsonschema.validate(instance=data, schema=schema_data)
                logger.info(
                    "✓ Validated %s against schema %s",
                    file_path.name,
                    schema_name,
                )
            except jsonschema.ValidationError as e:
                logger.error(
                    "Schema validation failed for %s against %s: %s",
                    file_path.name,
                    schema_name,
                    e.message,
                )
                raise SystemExit(1) from e
    return data


def load_yaml_manifests(file_path: Path) -> list[dict]:
    """Loads all YAML documents from a file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return list(yaml.safe_load_all(f))
    except (yaml.YAMLError, OSError) as e:
        logger.error("Failed to parse YAML in %s: %s", file_path, e)
        raise


def save_yaml_manifests(manifests: list[dict], file_path: Path) -> None:
    """Saves multiple YAML documents to a file."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.safe_dump_all(
                manifests, f, default_flow_style=False, sort_keys=False
            )
    except (yaml.YAMLError, OSError) as e:
        logger.error("Failed to write YAML to %s: %s", file_path, e)
        raise


def translate_image(container: dict, image_map: dict) -> None:
    """Translates container image referencing ECR to GCP Artifact Registry."""
    img = container.get("image")
    if img in image_map:
        new_img = image_map[img]
        logger.info("  Translating image: '%s' -> '%s'", img, new_img)
        container["image"] = new_img


def translate_service_account(sa_manifest: dict, identity_map: dict) -> None:
    """Translates ServiceAccount annotations."""
    metadata = sa_manifest.get("metadata", {})
    namespace = metadata.get("namespace", "default")
    name = metadata.get("name")
    key = f"{namespace}/{name}"

    # Strip AWS annotations
    annotations = metadata.get("annotations", {})
    aws_role_arn = annotations.get("eks.amazonaws.com/role-arn")
    aws_keys = [k for k in annotations if k.startswith("eks.amazonaws.com/")]
    for k in aws_keys:
        logger.info("  Stripping AWS annotation: %s", k)
        annotations.pop(k)

    # Inject GSA annotation if mapped
    gsa_email = None
    if aws_role_arn and aws_role_arn in identity_map:
        gsa_email = identity_map[aws_role_arn]
    elif key in identity_map:
        mapping = identity_map[key]
        gsa_email = (
            mapping.get("gsa_email") if isinstance(mapping, dict) else mapping
        )

    if gsa_email:
        logger.info(
            "  Mapping SA identity to GSA: '%s' -> '%s'", key, gsa_email
        )
        annotations["iam.gke.io/gcp-service-account"] = gsa_email

    if annotations:
        metadata["annotations"] = annotations
    elif "annotations" in metadata:
        metadata.pop("annotations")


def translate_pvc(pvc_manifest: dict, storage_map: dict) -> None:
    """Translates PVC storageClassName and resource requests."""
    metadata = pvc_manifest.get("metadata", {})
    spec = pvc_manifest.get("spec", {})
    current_sc = spec.get("storageClassName")

    if current_sc in storage_map:
        target_sc = storage_map[current_sc].get("target")
        if target_sc:
            logger.info(
                "  Mapping PVC StorageClass: '%s' -> '%s'",
                current_sc,
                target_sc,
            )
            spec["storageClassName"] = target_sc

    # Strip dynamic volume provisioner annotations if present
    annotations = metadata.get("annotations", {})
    provisioner_keys = [
        k
        for k in annotations
        if "volume.beta.kubernetes.io" in k or "provisioner" in k
    ]
    for k in provisioner_keys:
        annotations.pop(k)


def translate_storage_class(sc_manifest: dict, storage_map: dict) -> None:
    """Translates StorageClass provisioner and parameters dynamically."""
    metadata = sc_manifest.get("metadata", {})
    name = metadata.get("name")
    provisioner = sc_manifest.get("provisioner")

    mapping = None
    if name in storage_map:
        mapping = storage_map[name]
    else:
        # Fallback: find any mapping matching the source_provisioner
        for m in storage_map.values():
            if m.get("source_provisioner") == provisioner:
                mapping = m
                break

    if mapping:
        target_name = mapping.get("target")
        target_provisioner = mapping.get("target_provisioner")
        target_type = mapping.get("target_type")

        logger.info(
            "  Translating StorageClass '%s': name -> '%s', "
            "provisioner -> '%s'",
            name,
            target_name,
            target_provisioner,
        )
        metadata["name"] = target_name
        sc_manifest["provisioner"] = target_provisioner

        # Translate parameters if present
        if "parameters" in sc_manifest:
            parameters = sc_manifest.get("parameters", {})
            if "type" in parameters and target_type:
                parameters["type"] = target_type


def translate_workload_manifests(
    manifests: list[dict],
    image_map: dict,
    identity_map: dict,
    storage_map: dict,
    target_mode: str,
    target_namespaces: set[str] | None = None,
) -> list[dict]:
    """Iterates and mutates Kubernetes resources to match GKE conventions."""
    # Flatten any List resources first
    flat_manifests = []

    def flatten(items):
        for item in items:
            if not item or not isinstance(item, dict):
                continue
            if item.get("kind") == "List" or "items" in item:
                flatten(item.get("items", []))
            else:
                flat_manifests.append(item)

    flatten(manifests)

    translated = []

    for manifest in flat_manifests:
        kind = manifest.get("kind")
        metadata = manifest.get("metadata", {})
        name = metadata.get("name", "unnamed")
        namespace = metadata.get("namespace", "default")

        if kind == "Namespace":
            if target_namespaces is not None and name not in target_namespaces:
                logger.info(
                    "Skipping Namespace %s (not targeted)",
                    name,
                )
                continue
        elif target_namespaces is not None:
            if namespace not in target_namespaces:
                logger.info(
                    "Skipping resource %s/%s (namespace '%s' not targeted)",
                    kind,
                    name,
                    namespace,
                )
                continue

        logger.info("Processing resource: %s/%s", kind, name)

        if kind == "ServiceAccount":
            translate_service_account(manifest, identity_map)
            translated.append(manifest)

        elif kind == "PersistentVolumeClaim":
            translate_pvc(manifest, storage_map)
            translated.append(manifest)

        elif kind == "StorageClass":
            translate_storage_class(manifest, storage_map)
            translated.append(manifest)

        elif kind in [
            "Deployment",
            "StatefulSet",
            "DaemonSet",
            "Job",
            "CronJob",
        ]:
            # 1. Translate image references in containers
            spec = manifest.get("spec", {})
            template = (
                spec.get("template", {})
                if kind != "CronJob"
                else spec.get("jobTemplate", {})
                .get("spec", {})
                .get("template", {})
            )
            pod_spec = template.get("spec", {})

            # Standard containers
            containers = pod_spec.get("containers", [])
            for c in containers:
                translate_image(c, image_map)

            # Init containers
            init_containers = pod_spec.get("initContainers", [])
            for c in init_containers:
                translate_image(c, image_map)

            # 2. GKE Autopilot compatibility checks and mutation
            if target_mode == "autopilot":
                # Remove node selectors or tolerations that target specific
                # AWS instances.
                if "nodeSelector" in pod_spec:
                    pod_spec.pop("nodeSelector")
                    logger.info("  Autopilot mode: Stripping spec.nodeSelector")

            translated.append(manifest)
        else:
            # Leave other manifests (Services, ConfigMaps, Secrets,
            # Namespaces, Ingresses) unchanged.
            translated.append(manifest)

    return translated


def find_file_recursively(directory: Path, filename: str) -> Path | None:
    """Recursively search for a file in the directory."""
    for root, dirs, files in os.walk(directory):
        # Ignore hidden directories (e.g. .terraform, .git)
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        if filename in files:
            return Path(root) / filename
    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="GKE Workload Translation Engine"
    )
    parser.add_argument(
        "--handoff-dir",
        type=Path,
        required=True,
        help="Path to directory containing handoff and map files",
    )
    parser.add_argument(
        "--manifests-dir",
        type=Path,
        required=True,
        help="Directory containing source EKS manifests",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory to save translated GKE manifests",
    )
    parser.add_argument(
        "--target-mode",
        type=str,
        default="autopilot",
        choices=["autopilot", "standard"],
        help="GKE target operation mode",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only run validations without writing output manifests",
    )
    parser.add_argument(
        "--namespace",
        type=str,
        action="append",
        help=(
            "Target namespace(s) to translate (overrides "
            "workload-handoff-namespace)"
        ),
    )

    args = parser.parse_args()

    # Resolve workload file (required)
    workload_file = find_file_recursively(
        args.handoff_dir, "workload-handoff.json"
    )
    if not workload_file:
        workload_file = find_file_recursively(
            args.handoff_dir, "workload-handoff-namespace.json"
        )

    if not workload_file:
        logger.error(
            "Workload handoff file not found recursively in %s",
            args.handoff_dir,
        )
        sys.exit(1)

    # Resolve target namespaces
    target_namespaces = load_target_namespaces(args.handoff_dir)
    if args.namespace:
        target_namespaces = set(args.namespace)
    if target_namespaces is not None:
        logger.info(
            "Target namespaces for restricted translation: %s",
            target_namespaces,
        )
    else:
        logger.info("No namespace restriction. Translating all resources.")

    # 1. Load mappings from handoff directory (optional, empty dict if
    # not present)
    raw_image_map = load_and_validate_json(
        find_file_recursively(args.handoff_dir, "image-map.json"),
        "image-map.schema.json",
        args.handoff_dir,
    )
    if isinstance(raw_image_map, list):
        image_map = {
            item["source"]: item["target"]
            for item in raw_image_map
            if isinstance(item, dict) and "source" in item and "target" in item
        }
    else:
        image_map = raw_image_map
    raw_identity_map = load_and_validate_json(
        find_file_recursively(args.handoff_dir, "identity-map.json"),
        "identity-map.schema.json",
        args.handoff_dir,
    )
    if isinstance(raw_identity_map, list):
        identity_map = {
            item["source"]: item["target"]
            for item in raw_identity_map
            if isinstance(item, dict) and "source" in item and "target" in item
        }
    else:
        identity_map = raw_identity_map

    raw_storage_map = load_and_validate_json(
        find_file_recursively(args.handoff_dir, "storage-map.json"),
        "storage-map.schema.json",
        args.handoff_dir,
    )
    storage_map = {}
    if isinstance(raw_storage_map, list):
        for item in raw_storage_map:
            if isinstance(item, dict) and "source" in item:
                storage_map[item["source"]] = item

    # 2. Scan source directory for manifests
    if not args.manifests_dir.exists():
        logger.error(
            "Source manifests directory does not exist: %s", args.manifests_dir
        )
        sys.exit(1)

    all_source_files = []
    for root, dirs, files in os.walk(args.manifests_dir):
        # Ignore hidden directories (e.g. .terraform, .git)
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for file in files:
            if file.endswith((".yaml", ".yml")):
                all_source_files.append(Path(root) / file)

    logger.info("Found %d source manifest files.", len(all_source_files))

    # 3. Translate each file
    for file_path in all_source_files:
        logger.info("Translating file: %s", file_path.name)
        manifests = load_yaml_manifests(file_path)
        translated_manifests = translate_workload_manifests(
            manifests,
            image_map,
            identity_map,
            storage_map,
            args.target_mode,
            target_namespaces,
        )

        if not args.validate_only:
            if translated_manifests:
                relative_path = file_path.relative_to(args.manifests_dir)
                target_path = args.output_dir / relative_path
                save_yaml_manifests(translated_manifests, target_path)
                logger.info("Saved translated manifests to: %s", target_path)
            else:
                logger.info(
                    "Skipping empty translated file: %s", file_path.name
                )

    logger.info("Workload translation complete.")


if __name__ == "__main__":
    main()
