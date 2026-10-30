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
"""GKE Manifest Validation and Schema Compliance Verification."""

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

import yaml

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("validate_manifests")


def verify_kubectl_client() -> bool:
    """Checks if kubectl CLI tool is installed."""
    try:
        subprocess.run(
            ["kubectl", "version", "--client"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def run_kubectl_dry_run(file_path: Path) -> bool:
    """Executes kubectl apply --dry-run=client on the manifest."""
    try:
        subprocess.run(
            ["kubectl", "apply", "-f", str(file_path), "--dry-run=client"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        return True
    except subprocess.CalledProcessError as e:
        logger.error(
            "Syntactic dry-run failed for %s:\n%s",
            file_path.name,
            e.stderr.decode("utf-8"),
        )
        return False


def check_autopilot_compatibility(manifest: dict) -> list[str]:
    """Runs structural checks for GKE Autopilot compatibility.

    Heuristics:
    - No privileged containers.
    - No hostNetwork, hostPID, hostIPC.
    - No hostPath volumes.
    - No added capabilities (e.g. CAP_SYS_ADMIN).
    """
    violations = []
    kind = manifest.get("kind")
    metadata = manifest.get("metadata", {})
    name = metadata.get("name", "unnamed")

    if kind in ["Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob"]:
        spec = manifest.get("spec", {})
        template = (
            spec.get("template", {})
            if kind != "CronJob"
            else spec.get("jobTemplate", {}).get("spec", {}).get("template", {})
        )
        pod_spec = template.get("spec", {})

        if not pod_spec:
            return violations

        # Check host network/namespace sharing
        if pod_spec.get("hostNetwork"):
            violations.append(
                f"{kind}/{name}: hostNetwork is enabled "
                "(forbidden in Autopilot)"
            )
        if pod_spec.get("hostPID"):
            violations.append(
                f"{kind}/{name}: hostPID is enabled (forbidden in Autopilot)"
            )
        if pod_spec.get("hostIPC"):
            violations.append(
                f"{kind}/{name}: hostIPC is enabled (forbidden in Autopilot)"
            )

        # Check volumes for hostPath
        volumes = pod_spec.get("volumes", [])
        for vol in volumes:
            if "hostPath" in vol:
                violations.append(
                    f'{kind}/{name}: volume "{vol.get("name")}" uses '
                    "hostPath (forbidden in Autopilot)"
                )

        # Check container securityContexts
        containers = pod_spec.get("containers", []) + pod_spec.get(
            "initContainers", []
        )
        for c in containers:
            c_name = c.get("name")
            sec_ctx = c.get("securityContext", {})
            if sec_ctx.get("privileged"):
                violations.append(
                    f'{kind}/{name}: container "{c_name}" is privileged '
                    "(forbidden in Autopilot)"
                )

            caps = sec_ctx.get("capabilities", {})
            added_caps = caps.get("add", [])
            if added_caps:
                violations.append(
                    f'{kind}/{name}: container "{c_name}" adds '
                    f"capabilities {added_caps} (restricted in Autopilot)"
                )

    return violations


def main() -> None:
    parser = argparse.ArgumentParser(
        description="GKE Manifest Validation Engine"
    )
    parser.add_argument(
        "--manifests-dir",
        type=Path,
        required=True,
        help="Directory containing translated GKE YAML manifests",
    )
    parser.add_argument(
        "--skip-kubectl",
        action="store_true",
        help="Skip syntactic dry-run validations with kubectl",
    )

    args = parser.parse_args()

    if not args.manifests_dir.exists():
        logger.error(
            "Manifests directory does not exist: %s", args.manifests_dir
        )
        sys.exit(1)

    all_files = []
    for root, dirs, files in os.walk(args.manifests_dir):
        # Ignore hidden directories (e.g. .terraform, .git)
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for file in files:
            if file.endswith((".yaml", ".yml")):
                all_files.append(Path(root) / file)

    logger.info("Found %d manifests to validate.", len(all_files))

    kubectl_available = verify_kubectl_client()
    if not kubectl_available and not args.skip_kubectl:
        logger.warning(
            "kubectl CLI not found. Skipping syntactic dry-run validations. "
            "Use --skip-kubectl to silence this warning."
        )

    failures = 0
    total_violations = []

    for file_path in all_files:
        logger.info("Validating manifest file: %s", file_path.name)

        # 1. Syntactic dry-run validation
        if kubectl_available and not args.skip_kubectl:
            if not run_kubectl_dry_run(file_path):
                failures += 1

        # 2. Structural Autopilot checks
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                manifests = list(yaml.safe_load_all(f))
            for manifest in manifests:
                if manifest:
                    violations = check_autopilot_compatibility(manifest)
                    total_violations.extend(violations)
        except (yaml.YAMLError, OSError) as e:
            logger.error(
                "Failed to parse YAML file for structural checks %s: %s",
                file_path.name,
                e,
            )
            failures += 1

    if total_violations:
        logger.error("GKE Autopilot Compatibility violations found:")
        for v in total_violations:
            logger.error("  - %s", v)
        failures += len(total_violations)

    if failures > 0:
        logger.error(
            "Validation failed! Total issues/failures found: %d", failures
        )
        sys.exit(1)

    logger.info(
        "✓ All GKE manifests passed schema compliance and Autopilot "
        "compatibility checks."
    )


if __name__ == "__main__":
    main()
