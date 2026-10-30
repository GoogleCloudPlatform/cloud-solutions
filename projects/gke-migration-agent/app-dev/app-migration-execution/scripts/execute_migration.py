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
"""GKE Application Migration Execution Orchestrator with state persistence."""

import argparse
import datetime
import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

import jsonschema
import yaml

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("execute_migration")

STATE_FILE_NAME = "migration-execution-state.json"

PHASES = [
    "Phase 1: Namespace and Identity",
    "Phase 2: Storage and Data Sync",
    "Phase 3: Workloads Deployment",
    "Phase 4: Observability Integration",
    "Phase 5: Network Exposure",
]

PHASE_KINDS = {
    "Phase 1: Namespace and Identity": {
        "Namespace",
        "ServiceAccount",
        "CustomResourceDefinition",
        "SecretProviderClass",
        "ClusterRole",
        "ClusterRoleBinding",
        "Role",
        "RoleBinding",
    },
    "Phase 2: Storage and Data Sync": {
        "StorageClass",
        "PersistentVolumeClaim",
        "PersistentVolume",
        "VolumeSnapshot",
        "VolumeSnapshotClass",
        "VolumeSnapshotContent",
    },
    "Phase 3: Workloads Deployment": {
        "Deployment",
        "StatefulSet",
        "DaemonSet",
        "Job",
        "CronJob",
        "Pod",
        "ConfigMap",
        "Secret",
    },
    "Phase 4: Observability Integration": {
        "PodMonitoring",
        "ClusterPodMonitoring",
        "PrometheusRule",
        "ServiceMonitor",
        "PodMonitor",
    },
    "Phase 5: Network Exposure": {
        "Gateway",
        "HTTPRoute",
        "TLSRoute",
        "TCPRoute",
        "UDPRoute",
        "Service",
        "Ingress",
        "NetworkPolicy",
        "GCPBackendPolicy",
        "HealthCheckPolicy",
    },
}

SCHEMA_MAP = {
    "workload-handoff.json": "workload-handoff.schema.json",
    "workload-handoff-namespace.json": (
        "workload-handoff-namespace.schema.json"
    ),
    "platform-handoff.json": "platform-handoff.schema.json",
    "identity-map.json": "identity-map.schema.json",
    "image-map.json": "image-map.schema.json",
    "network-map.json": "network-map.schema.json",
    "observability-map.json": "observability-map.schema.json",
    "storage-map.json": "storage-map.schema.json",
}


def load_state(state_path: Path) -> dict:
    """Loads state file from disk."""
    if state_path.exists():
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error("Failed to load state file: %s", e)
    return {}


def save_state(state_data: dict, state_path: Path) -> None:
    """Saves state file to disk atomically."""
    temp_path = state_path.with_suffix(".tmp")
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2)
        temp_path.replace(state_path)
    except OSError as e:
        logger.error("Failed to save state file: %s", e)


def initialize_state(namespace: str) -> dict:
    """Initializes new state dict."""
    state = {
        "migration_id": (
            f"migration-{namespace}-"
            f"{int(datetime.datetime.now().timestamp())}"
        ),
        "target_namespace": namespace,
        "current_phase": PHASES[0],
        "overall_status": "IN_PROGRESS",
        "phases": {},
    }
    for phase in PHASES:
        state["phases"][phase] = {
            "status": "PENDING",
            "started_at": None,
            "completed_at": None,
            "resources_created": [],
        }
    return state


def archive_existing_state(state_path: Path) -> None:
    """Archives an existing state file with a timestamp suffix."""
    if state_path.exists():
        archive_path = state_path.with_name(
            f"{STATE_FILE_NAME}.old-"
            f"{int(datetime.datetime.now().timestamp())}"
        )
        state_path.rename(archive_path)


def ask_user_choice(prompt: str, choices: list[str]) -> str:
    """Asks user for terminal input from a list of choices."""
    choice_str = "/".join(choices)
    while True:
        sys.stdout.write(f"{prompt} [{choice_str}]: ")
        sys.stdout.flush()
        line = sys.stdin.readline().strip().upper()
        if line in choices:
            return line
        print(f"Invalid input. Please choose one of: {choices}")


def validate_schema(data: dict, schema_path: Path) -> None:
    """Validates data dictionary against a JSON schema file."""
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        jsonschema.validate(instance=data, schema=schema)
    except FileNotFoundError:
        logger.error("Schema file not found: %s", schema_path)
        raise
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JSON schema in %s: %s", schema_path, e)
        raise


def validate_handoff_files(handoff_dir: Path, schemas_dir: Path) -> None:
    """Scans handoff_dir for handoff/map files and validates against schemas."""
    if not handoff_dir or not handoff_dir.exists():
        return

    validated_count = 0
    for filename, schema_name in SCHEMA_MAP.items():
        file_path = handoff_dir / filename
        if not file_path.exists():
            matches = list(handoff_dir.rglob(filename))
            if matches:
                file_path = matches[0]
            else:
                continue

        schema_path = schemas_dir / schema_name
        if not schema_path.exists():
            logger.warning(
                "Schema file %s not found in %s", schema_name, schemas_dir
            )
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            validate_schema(data, schema_path)
            logger.info(
                "✓ Validated %s against %s", file_path.name, schema_name
            )
            validated_count += 1
        except (jsonschema.ValidationError, json.JSONDecodeError, OSError) as e:
            logger.error("Validation error in %s: %s", file_path.name, e)
            raise RuntimeError(
                f"Handoff schema validation failed for {file_path.name}: {e}"
            ) from e

    if validated_count > 0:
        logger.info(
            "✓ Successfully validated %d handoff/map specification(s).",
            validated_count,
        )


def extract_matching_docs(docs: list, target_kinds: set[str]) -> list[dict]:
    """Recursively extracts matching document dicts, unpacking List objects."""
    matching = []
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        kind = doc.get("kind")
        if kind in ("List", "ConfigMapList", "PodList") and isinstance(
            doc.get("items"), list
        ):
            matching.extend(extract_matching_docs(doc["items"], target_kinds))
        elif kind in target_kinds:
            matching.append(doc)
    return matching


def get_matching_manifest_docs(
    manifests_dir: Path, target_kinds: set[str]
) -> list[dict]:
    """Finds matching YAML document dicts and sorts Namespace first."""
    matching_docs = []
    for file_path in manifests_dir.rglob("*.yaml"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                docs = list(yaml.safe_load_all(f))
                matching_docs.extend(extract_matching_docs(docs, target_kinds))
        except (OSError, yaml.YAMLError) as e:
            logger.warning("Failed to parse %s: %s", file_path, e)

    # Sort Namespace resources first so namespaces exist before child resources
    matching_docs.sort(key=lambda d: 0 if d.get("kind") == "Namespace" else 1)
    return matching_docs


def execute_phase_action(
    phase: str,
    manifests_dir: Path,
    namespace: str,
    mock: bool,
    request_timeout: str = "30s",
) -> tuple[bool, list[str]]:
    """Applies kubectl manifests matching the resource kinds for the phase."""
    logger.info("Executing actions for: %s", phase)
    target_kinds = PHASE_KINDS.get(phase, set())
    if not target_kinds:
        logger.warning("No target resource kinds defined for phase: %s", phase)
        return True, []

    matching_docs = get_matching_manifest_docs(manifests_dir, target_kinds)
    if not matching_docs:
        logger.info("  No %s resources found in %s.", phase, manifests_dir.name)
        return True, []

    created_resources = []
    for doc in matching_docs:
        kind = doc.get("kind", "Unknown")
        name = doc.get("metadata", {}).get("name", "unnamed")
        created_resources.append(f"{kind}/{name}")

    if mock:
        logger.info(
            "  [Mock] Applying %d %s manifest(s) from %s in namespace %s...",
            len(matching_docs),
            phase,
            manifests_dir.name,
            namespace,
        )
        return True, created_resources

    with tempfile.NamedTemporaryFile("w+", suffix=".yaml", delete=False) as tmp:
        yaml.safe_dump_all(matching_docs, tmp)
        tmp_path = Path(tmp.name)

    try:
        cmd = [
            "kubectl",
            "apply",
            "-n",
            namespace,
            f"--request-timeout={request_timeout}",
            "-f",
            str(tmp_path),
        ]
        logger.info(
            "  Applying %d resource(s) for %s...",
            len(matching_docs),
            phase,
        )
        subprocess.run(cmd, check=True)
        return True, created_resources
    except subprocess.CalledProcessError as e:
        logger.error("Kubectl apply failed for %s: %s", phase, e)
        return False, created_resources
    finally:
        tmp_path.unlink(missing_ok=True)


def load_or_prompt_state(
    state_path: Path,
    namespace: str,
    force_fresh: bool,
    auto_approve: bool = False,
) -> dict:
    """Loads state file or prompts user for action based on state status."""
    if state_path.exists() and not force_fresh:
        existing_state = load_state(state_path)
        status = existing_state.get("overall_status")

        if status == "COMPLETED":
            logger.info(
                "Found previous migration state marked as COMPLETED (ID: %s).",
                existing_state.get("migration_id"),
            )
            if auto_approve:
                logger.info("Auto-approving start fresh for completed state.")
                choice = "START_FRESH"
            else:
                choice = ask_user_choice(
                    "Previous migration finished successfully. Overwrite state"
                    " and start fresh?",
                    ["START_FRESH", "CANCEL"],
                )
            if choice == "CANCEL":
                logger.info("Operation cancelled by user.")
                sys.exit(0)
            archive_existing_state(state_path)
            return initialize_state(namespace)

        if status in ["FAILED", "IN_PROGRESS"]:
            logger.info(
                "Found existing incomplete migration run: %s",
                existing_state.get("migration_id"),
            )
            logger.info(
                "Last recorded phase: %s", existing_state.get("current_phase")
            )
            if auto_approve:
                logger.info("Auto-approving resume for incomplete state.")
                choice = "RESUME"
            else:
                choice = ask_user_choice(
                    "How would you like to proceed?", ["RESUME", "START_FRESH"]
                )

            if choice == "RESUME":
                existing_state["overall_status"] = "IN_PROGRESS"
                logger.info("Resuming migration from failure point...")
                return existing_state

            logger.info("Archiving old state and starting fresh...")
            archive_existing_state(state_path)
            return initialize_state(namespace)

    return initialize_state(namespace)


def run_migration_loop(
    state: dict,
    state_path: Path,
    manifests_dir: Path,
    namespace: str,
    mock: bool,
    auto_approve: bool = False,
    request_timeout: str = "30s",
) -> None:
    """Iterates through execution phases, checking gates and applying
    resources."""
    try:
        for phase in PHASES:
            phase_state = state["phases"][phase]

            if phase_state["status"] == "COMPLETED":
                logger.info("Skipping already completed phase: %s", phase)
                continue

            state["current_phase"] = phase
            save_state(state, state_path)

            # Verification Gate
            logger.info("\n--- Verification Gate ---")
            logger.info("Next Phase: %s", phase)

            if auto_approve:
                logger.info("Auto-approving deployment for phase: %s", phase)
                approval = "APPROVE"
            else:
                approval = ask_user_choice(
                    "Approve deployment of this phase?", ["APPROVE", "CANCEL"]
                )

            if approval == "CANCEL":
                logger.info("Migration cancelled by user.")
                state["overall_status"] = "FAILED"
                save_state(state, state_path)
                sys.exit(1)

            # Mark phase started
            phase_state["status"] = "IN_PROGRESS"
            phase_state["started_at"] = datetime.datetime.now().isoformat()
            save_state(state, state_path)

            # Execute action
            success, created_resources = execute_phase_action(
                phase, manifests_dir, namespace, mock, request_timeout
            )
            phase_state["resources_created"] = created_resources

            if not success:
                logger.error("Phase %s failed to complete.", phase)
                phase_state["status"] = "FAILED"
                state["overall_status"] = "FAILED"
                save_state(state, state_path)
                sys.exit(1)

            # Mark phase completed
            phase_state["status"] = "COMPLETED"
            phase_state["completed_at"] = datetime.datetime.now().isoformat()
            save_state(state, state_path)
            logger.info("✓ Phase completed successfully: %s", phase)

        # All phases complete
        state["overall_status"] = "COMPLETED"
        save_state(state, state_path)
        logger.info("\n✓ Migration completed successfully! State file saved.")

    except KeyboardInterrupt:
        logger.warning("\nExecution interrupted by user. Saving current state.")
        state["overall_status"] = "FAILED"
        save_state(state, state_path)
        sys.exit(130)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="GKE App Migration Execution Orchestrator"
    )
    parser.add_argument(
        "--manifests-dir",
        type=Path,
        required=True,
        help="Directory containing GKE manifests to apply",
    )
    parser.add_argument(
        "--handoff-dir",
        type=Path,
        default=None,
        help=(
            "Optional directory containing handoff/map JSON files to validate"
            " against schemas"
        ),
    )
    parser.add_argument(
        "--namespace",
        type=str,
        default="production-app",
        help="Target GKE namespace",
    )
    parser.add_argument(
        "--mock-deploy",
        action="store_true",
        help="Simulate execution without running actual kubectl commands",
    )
    parser.add_argument(
        "--force-fresh",
        action="store_true",
        help="Ignore existing state files and start fresh",
    )
    parser.add_argument(
        "--auto-approve",
        "-y",
        action="store_true",
        help=(
            "Automatically approve phase deployment gates and state actions"
            " non-interactively"
        ),
    )
    parser.add_argument(
        "--request-timeout",
        type=str,
        default="30s",
        help="Timeout flag for kubectl apply command (default: 30s)",
    )

    args = parser.parse_args()

    # Validate handoff files against schemas if handoff-dir is provided or
    # present near manifests
    schemas_dir = Path(__file__).resolve().parent.parent / "assets" / "schemas"
    handoff_target = (
        args.handoff_dir if args.handoff_dir else args.manifests_dir
    )
    validate_handoff_files(handoff_target, schemas_dir)

    state_path = Path.cwd() / STATE_FILE_NAME
    state = load_or_prompt_state(
        state_path, args.namespace, args.force_fresh, args.auto_approve
    )
    save_state(state, state_path)

    run_migration_loop(
        state,
        state_path,
        args.manifests_dir,
        args.namespace,
        args.mock_deploy,
        args.auto_approve,
        args.request_timeout,
    )


if __name__ == "__main__":
    main()
