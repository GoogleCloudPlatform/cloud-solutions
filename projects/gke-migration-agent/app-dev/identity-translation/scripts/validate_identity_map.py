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
"""Identity Map validation script.

Validates that all Kubernetes ServiceAccounts requiring cloud access have valid
Google Service Account mappings in identity-map.json. The handoff directory
must point to a clean, specific directory for a single migration run.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import jsonschema

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("validate_identity_map")


VALID_GSA_SUFFIX = ".gserviceaccount.com"
COMPUTE_ENGINE_DEFAULT_SA_SUFFIX = "@developer.gserviceaccount.com"


def load_json(file_path: Path) -> dict | list:
    """Loads JSON file from disk.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_valid_gsa_email(email: str) -> bool:
    """Checks whether an email address ends with a valid GSA suffix."""
    return bool(email and email.endswith(VALID_GSA_SUFFIX))


def validate_schema(data: dict | list, schema_path: Path) -> None:
    """Validates data against a JSON schema file.

    Raises:
        FileNotFoundError: If the schema file does not exist.
        jsonschema.ValidationError: If data does not conform to the schema.
    """
    if not schema_path.is_file():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    schema = load_json(schema_path)
    jsonschema.validate(instance=data, schema=schema)


def validate_mappings(
    required_sas: dict[tuple[str, str], str],
    identity_map: dict[str, str],
) -> list[str]:
    """Validates that all required ServiceAccounts have valid GSA mappings.

    Returns a list of missing or invalid mapping descriptions.
    """
    missing_mappings = []
    for (namespace, sa), irsa_arn in required_sas.items():
        if irsa_arn not in identity_map:
            missing_mappings.append(f"{namespace}/{sa} (requires: {irsa_arn})")
        else:
            gsa_email = identity_map[irsa_arn]
            if not is_valid_gsa_email(gsa_email):
                logger.error(
                    "Invalid mapping for '%s/%s': GSA email '%s' must "
                    "end with '%s'.",
                    namespace,
                    sa,
                    gsa_email,
                    VALID_GSA_SUFFIX,
                )
                missing_mappings.append(
                    f"{namespace}/{sa} (requires: {irsa_arn})"
                )
            elif gsa_email.endswith(COMPUTE_ENGINE_DEFAULT_SA_SUFFIX):
                logger.warning(
                    "Mapping for '%s/%s' uses default Compute Engine service "
                    "account '%s'. Dedicated user-managed service accounts "
                    "are recommended.",
                    namespace,
                    sa,
                    gsa_email,
                )
    return missing_mappings


def _add_service_account(
    required_sas: dict[tuple[str, str], str],
    namespace: str,
    sa_name: str,
    irsa_arn: str,
) -> None:
    """Validates and adds a ServiceAccount IRSA mapping.

    Raises:
        ValueError: If conflicting IRSA Role ARNs are detected for the same
            ServiceAccount.
    """
    key = (namespace, sa_name)
    if key in required_sas and required_sas[key] != irsa_arn:
        raise ValueError(
            f"Conflicting IRSA Role ARNs detected for ServiceAccount "
            f"'{namespace}/{sa_name}': '{required_sas[key]}' vs '{irsa_arn}'. "
            f"GKE Workload Identity annotations are attached per "
            f"ServiceAccount and cannot differ."
        )
    required_sas[key] = irsa_arn


def _process_workload(
    workload: dict,
    namespace: str,
    required_sas: dict[tuple[str, str], str],
) -> None:
    """Extracts IRSA or Pod Identity requirement from a workload block."""
    deps = workload.get("dependencies", {})
    sa_name = deps.get("service_account")
    irsa_arn = deps.get("irsa_role_arn")
    if sa_name and irsa_arn:
        _add_service_account(required_sas, namespace, sa_name, irsa_arn)


def extract_required_service_accounts(
    workload_data: dict,
) -> dict[tuple[str, str], str]:
    """Extracts service accounts with AWS roles (requiring cloud access).

    Returns a dict mapping (namespace, service_account_name) -> irsa_role_arn.
    """
    required_sas = {}

    # Determine if it's cluster-level or namespace-level handoff
    if "clusters" in workload_data:
        # Cluster-level handoff
        for cluster in workload_data.get("clusters", []):
            for ns_block in cluster.get("namespaces", []):
                namespace = ns_block.get("name")
                for wl in ns_block.get("workloads", []):
                    _process_workload(wl, namespace, required_sas)
    elif "namespace" in workload_data:
        # Namespace-level handoff
        namespace = workload_data.get("namespace")
        for wl in workload_data.get("workloads", []):
            _process_workload(wl, namespace, required_sas)

    return required_sas


def find_file_recursively(directory: Path, filename: str) -> Path | None:
    """Recursively searches for a file in the directory and subdirectories.

    Ensures exactly one matching file is found within the specified handoff
    directory.

    Raises:
        ValueError: If multiple matching files are found in the directory tree.
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
            f"Please specify a --handoff-dir specific to a single migration "
            f"run."
        )

    return matches[0] if matches else None


def parse_identity_map(raw_identity_map: list[dict]) -> dict[str, str]:
    """Parses and normalizes identity-map list format (source -> target).

    Raises:
        ValueError: If conflicting duplicate source ARNs are detected.
    """
    identity_map = {}
    for item in raw_identity_map:
        source_arn = item.get("source", "")
        target_gsa = item.get("target", "")

        if (
            source_arn in identity_map
            and identity_map[source_arn] != target_gsa
        ):
            raise ValueError(
                f"Conflicting duplicate 'source' ARN '{source_arn}' found in "
                f"identity-map.json: '{identity_map[source_arn]}' vs "
                f"'{target_gsa}'."
            )

        identity_map[source_arn] = target_gsa
    return identity_map


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate Identity Mapping completeness"
    )
    parser.add_argument(
        "--handoff-dir",
        type=Path,
        required=True,
        help=(
            "Path to a clean, specific directory for a single migration run "
            "containing handoff files (workload-handoff.json and "
            "identity-map.json)"
        ),
    )

    args = parser.parse_args()

    try:
        # 1. Resolve and Load files
        workload_file = find_file_recursively(
            args.handoff_dir, "workload-handoff.json"
        )
        if not workload_file:
            workload_file = find_file_recursively(
                args.handoff_dir, "workload-handoff-namespace.json"
            )

        identity_map_file = find_file_recursively(
            args.handoff_dir, "identity-map.json"
        )

        if not workload_file:
            raise FileNotFoundError(
                f"Workload handoff file not found recursively in "
                f"{args.handoff_dir}"
            )
        if not identity_map_file:
            raise FileNotFoundError(
                f"identity-map.json not found recursively in {args.handoff_dir}"
            )

        workload_data = load_json(workload_file)
        raw_identity_map = load_json(identity_map_file)

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

        # 3. Validate identity-map.json against JSON schema
        identity_schema_file = find_file_recursively(
            skill_root, "identity-map.schema.json"
        )
        if not identity_schema_file:
            raise FileNotFoundError(
                "Schema file 'identity-map.schema.json' not found"
            )
        validate_schema(raw_identity_map, identity_schema_file)

        # Normalize identity_map list format (source -> target)
        identity_map = parse_identity_map(raw_identity_map)

        # 4. Extract SAs requiring cloud access
        required_sas = extract_required_service_accounts(workload_data)
        logger.info(
            "Found %d ServiceAccount(s) with cloud access configuration "
            "(IRSA / Pod Identity).",
            len(required_sas),
        )

        # 5. Verify mappings exist in identity-map.json
        missing_mappings = validate_mappings(required_sas, identity_map)

        if missing_mappings:
            formatted_missing = "\n".join(f" - {sa}" for sa in missing_mappings)
            raise ValueError(
                "Verification failed! The following ServiceAccounts require "
                "cloud access but are missing valid target GSA mappings in "
                f"identity-map.json:\n{formatted_missing}"
            )

        logger.info(
            "✓ All active ServiceAccounts have valid target GSA mappings "
            "in identity-map.json."
        )
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        logger.error("%s", e)
        sys.exit(1)
    except jsonschema.ValidationError as e:
        logger.error("Failed schema validation: %s", e.message)
        sys.exit(1)


if __name__ == "__main__":
    main()
