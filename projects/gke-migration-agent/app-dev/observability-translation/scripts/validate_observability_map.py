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
"""Observability Map validation script.

Validates JSON mapping files (`observability-map.json`) against their
JSON schemas (`observability-map.schema.json`) and verifies that every
Kubernetes workload with Prometheus scrape annotations
(`prometheus.io/scrape: "true"`) in raw manifests has a corresponding
mapping entry.
"""

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
logger = logging.getLogger("validate_observability_map")


def load_json(file_path: Path) -> dict | list:
    """Loads JSON file from disk."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("File not found: %s", file_path)
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JSON in %s: %s", file_path, e)
        sys.exit(1)


def has_prometheus_scrape_annotation(item: dict) -> bool:
    """Checks if a Kubernetes resource item has prometheus.io/scrape: 'true'."""
    if not isinstance(item, dict):
        return False
    kind = item.get("kind")
    if kind not in {"Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob"}:
        return False

    spec = item.get("spec", {})
    if kind == "CronJob":
        template = (
            spec.get("jobTemplate", {}).get("spec", {}).get("template", {})
        )
    else:
        template = spec.get("template", {})

    annotations = template.get("metadata", {}).get("annotations", {})
    return (
        isinstance(annotations, dict)
        and annotations.get("prometheus.io/scrape") == "true"
    )


def extract_scraped_workloads_from_file(
    file_path: Path,
) -> set[tuple[str, str]]:
    """Extracts (namespace, workload_name) for annotated workloads in a file."""
    scraped = set()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            docs = yaml.safe_load_all(f)
            for doc in docs:
                if not doc or not isinstance(doc, dict):
                    continue
                items = (
                    doc.get("items", [])
                    if doc.get("kind") == "List" or "items" in doc
                    else [doc]
                )
                for item in items:
                    if has_prometheus_scrape_annotation(item):
                        metadata = item.get("metadata", {})
                        name = metadata.get("name")
                        namespace = metadata.get("namespace", "default")
                        if name:
                            scraped.add((namespace, name))
    except (OSError, yaml.YAMLError) as e:
        logger.warning("Failed to parse %s: %s", file_path, e)
    return scraped


def scan_manifests_for_scraped_workloads(
    raw_manifests_dir: Path,
) -> set[tuple[str, str]]:
    """Scans YAML manifest files for prometheus.io/scrape: "true" annotations.

    Returns a set of tuples (namespace, workload_name).
    """
    scraped_workloads = set()
    logger.info(
        "Scanning raw manifests in '%s' for scrape annotations...",
        raw_manifests_dir,
    )

    for root, dirs, files in os.walk(raw_manifests_dir):
        # Ignore hidden directories (e.g. .terraform, .git)
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for file in files:
            if file.endswith((".yaml", ".yml")):
                file_path = Path(root) / file
                scraped_workloads.update(
                    extract_scraped_workloads_from_file(file_path)
                )

    return scraped_workloads


def find_file_recursively(directory: Path, filename: str) -> Path | None:
    """Recursively searches for a file in the directory and subdirectories.

    Ensures exactly one matching file is found within the specified handoff
    directory.
    """
    matches = []
    for root, dirs, files in os.walk(directory):
        # Ignore hidden directories (e.g. .terraform, .git)
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        if filename in files:
            matches.append(Path(root) / filename)

    if len(matches) > 1:
        logger.error(
            "Multiple instances of '%s' found in '%s':\n%s\n"
            "Please specify a --handoff-dir specific to a single "
            "migration run.",
            filename,
            directory,
            "\n".join(f" - {m}" for m in matches),
        )
        sys.exit(1)

    return matches[0] if matches else None


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate JSON mapping files against their JSON schemas and verify "
            "that all workloads with Prometheus scrape annotations are mapped."
        )
    )
    parser.add_argument(
        "--handoff-dir",
        type=Path,
        required=True,
        help=(
            "Path to directory containing handoff files "
            "(observability-map.json)"
        ),
    )
    parser.add_argument(
        "--raw-manifests-dir",
        type=Path,
        default=None,
        help=(
            "Path to raw Kubernetes manifests/YAML files to check "
            "for scrape annotations"
        ),
    )

    args = parser.parse_args()

    # 1. Resolve and Load observability-map.json file
    observability_map_file = find_file_recursively(
        args.handoff_dir, "observability-map.json"
    )

    if not observability_map_file:
        logger.error(
            "observability-map.json not found recursively in %s",
            args.handoff_dir,
        )
        sys.exit(1)

    observability_map = load_json(observability_map_file)

    # Validate against schema if available
    schema_file = find_file_recursively(
        Path(__file__).parent.parent, "observability-map.schema.json"
    )
    if schema_file:
        schema = load_json(schema_file)
        try:
            jsonschema.validate(instance=observability_map, schema=schema)
        except jsonschema.ValidationError as e:
            logger.error(
                "observability-map.json failed schema validation: %s",
                e.message,
            )
            sys.exit(1)

    scraped_workloads = set()

    # 2. Extract scraped workloads from raw manifests (if available)
    # or assume none
    if args.raw_manifests_dir and args.raw_manifests_dir.exists():
        scraped_workloads = scan_manifests_for_scraped_workloads(
            args.raw_manifests_dir
        )
    else:
        logger.warning(
            "No raw manifests directory provided or found. Skipping scan for "
            "prometheus.io/scrape annotations. Cross-checking "
            "only entries in map."
        )

    # 3. Check that every discovered scraped workload has an entry
    # in observability-map.json
    logger.info(
        "Found %d scraped workload(s) requiring mappings.",
        len(scraped_workloads),
    )
    missing_mappings = []

    if not isinstance(observability_map, list):
        logger.error(
            "Invalid observability-map.json format. Expected array at root."
        )
        sys.exit(1)

    for namespace, name in scraped_workloads:
        key = f"{namespace}/{name}"
        # Search the list of mappings
        found_mapping = None
        for item in observability_map:
            if not isinstance(item, dict):
                continue
            source = item.get("source", {})
            if (
                source.get("signal_type") == "metric"
                and source.get("name") == name
                and (
                    source.get("namespace") == namespace
                    or (not source.get("namespace") and namespace == "default")
                )
            ):
                found_mapping = item
                break

        if not found_mapping:
            missing_mappings.append(key)
        else:
            target = found_mapping.get("target", {})
            if target.get("provider") != "gmp":
                logger.error(
                    "Mapping for '%s' exists but target provider is not 'gmp'.",
                    key,
                )
                missing_mappings.append(key)
            elif not target.get("name"):
                logger.error(
                    "Mapping for '%s' is missing target resource name.", key
                )
                missing_mappings.append(key)

    if missing_mappings:
        logger.error(
            "Verification failed! The following workloads require GMP "
            "mappings but are missing or incomplete in "
            "observability-map.json:\n%s",
            "\n".join(f" - {wl}" for wl in missing_mappings),
        )
        sys.exit(1)

    logger.info(
        "✓ All scraped workloads have valid GMP mappings "
        "in observability-map.json."
    )


if __name__ == "__main__":
    main()
