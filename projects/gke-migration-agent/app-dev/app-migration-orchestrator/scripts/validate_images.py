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
"""Registry image validation and mapping verification script."""

import argparse
import logging
import os
import subprocess
from pathlib import Path

import yaml
from utils import load_json

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("validate_images")


def extract_images_from_yaml(
    file_path: Path, target_namespaces: set[str] = None
) -> list[str]:
    """Extracts all image references from a Kubernetes YAML file.

    Filters by namespace.
    """
    images = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            docs = yaml.safe_load_all(f)
            for doc in docs:
                if not doc or not isinstance(doc, dict):
                    continue

                # Flatten standard Kubernetes List resources
                flat_docs = []
                if doc.get("kind") == "List" or "items" in doc:
                    flat_docs.extend(doc.get("items", []))
                else:
                    flat_docs.append(doc)

                for item in flat_docs:
                    if not item or not isinstance(item, dict):
                        continue
                    kind = item.get("kind")
                    metadata = item.get("metadata", {})
                    namespace = metadata.get("namespace", "default")

                    if (
                        target_namespaces is not None
                        and namespace not in target_namespaces
                    ):
                        continue

                    if kind in [
                        "Deployment",
                        "StatefulSet",
                        "DaemonSet",
                        "Job",
                        "CronJob",
                    ]:
                        spec = item.get("spec", {})
                        template = (
                            spec.get("template", {})
                            if kind != "CronJob"
                            else spec.get("jobTemplate", {})
                            .get("spec", {})
                            .get("template", {})
                        )
                        pod_spec = template.get("spec", {})

                        # Extract from standard and init containers
                        containers = pod_spec.get("containers", [])
                        init_containers = pod_spec.get("initContainers", [])
                        for container in containers + init_containers:
                            img = container.get("image")
                            if img:
                                images.append(img)
    except (OSError, yaml.YAMLError) as e:
        logger.error(
            "Failed to parse YAML or extract images from %s: %s", file_path, e
        )
    return images


def verify_target_image_availability(target_image: str) -> None:
    """Verifies if the target image is available in GCP Artifact Registry."""
    logger.info("Checking target image availability: %s", target_image)
    try:
        subprocess.run(
            [
                "gcloud",
                "artifacts",
                "docker",
                "images",
                "describe",
                target_image,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as e:
        logger.error(
            "Target image '%s' is missing or inaccessible "
            "in Artifact Registry.",
            target_image,
        )
        raise SystemExit(1) from e


def main() -> None:
    parser = argparse.ArgumentParser(description="Image map validation script")
    parser.add_argument(
        "--workload-file",
        type=Path,
        required=True,
        help="Path to workload-handoff.json file",
    )
    parser.add_argument(
        "--image-map-file",
        type=Path,
        required=True,
        help="Path to image-map.json file",
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

    # 1. Load handoff & mapping data
    workload_data = load_json(args.workload_file)
    raw_image_map = load_json(args.image_map_file)
    if isinstance(raw_image_map, list):
        image_map = {
            item["source"]: item["target"]
            for item in raw_image_map
            if isinstance(item, dict) and "source" in item and "target" in item
        }
    else:
        image_map = raw_image_map

    # 2. Gather all unique source image references with their origins
    referenced_images = {}

    def add_image_ref(image_name: str, source: str) -> None:
        if image_name not in referenced_images:
            referenced_images[image_name] = set()
        referenced_images[image_name].add(source)

    workload_source = args.workload_file.name

    # Get from workload handoff
    if "clusters" in workload_data:
        for c in workload_data.get("clusters", []):
            for ns in c.get("namespaces", []):
                for wl in ns.get("workloads", []):
                    images = wl.get("dependencies", {}).get("images", [])
                    for img in images:
                        add_image_ref(img, workload_source)
    elif "workloads" in workload_data:
        for wl in workload_data.get("workloads", []):
            images = wl.get("dependencies", {}).get("images", [])
            for img in images:
                add_image_ref(img, workload_source)

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

    # Get from raw manifests if provided
    if args.raw_manifests_dir:
        logger.info("Scanning raw manifests for image references...")
        for root, dirs, files in os.walk(args.raw_manifests_dir):
            # Ignore hidden directories (e.g. .terraform, .git)
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for file in files:
                if file.endswith((".yaml", ".yml")):
                    file_path = Path(root) / file
                    try:
                        rel_path = file_path.relative_to(
                            args.raw_manifests_dir.parent
                        )
                    except ValueError:
                        rel_path = file_path
                    images = extract_images_from_yaml(
                        file_path, target_namespaces
                    )
                    for img in images:
                        add_image_ref(img, str(rel_path))

    logger.info(
        "Found %d unique source image references to validate.",
        len(referenced_images),
    )

    # 3. Verify mappings are present in image-map.json
    missing_mappings = []
    for img in referenced_images:
        if img not in image_map:
            missing_mappings.append(img)

    if missing_mappings:
        logger.error(
            "Verification failed! The following image references do not "
            "have a mapping in image-map.json:"
        )
        for img in missing_mappings:
            origins = ", ".join(sorted(referenced_images[img]))
            logger.error(" - %s (found in: %s)", img, origins)
        raise SystemExit(1)

    logger.info(
        "✓ All source image references have valid mappings in image-map.json."
    )

    # 4. Verify target image availability in Google Cloud Artifact Registry
    if not args.skip_cloud_checks:
        for img in referenced_images:
            target_image = image_map[img]
            verify_target_image_availability(target_image)
        logger.info("✓ All target images are available in Artifact Registry.")
    else:
        logger.info(
            "Skipped active Artifact Registry image availability checks."
        )


if __name__ == "__main__":
    main()
