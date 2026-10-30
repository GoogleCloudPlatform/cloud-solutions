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
"""GCP and GKE environment resource validation functions."""

import logging
import subprocess

logger = logging.getLogger("validate_platform_readiness")


def verify_kubectl_connection() -> bool:
    """Verifies connection to a Kubernetes cluster using kubectl.

    Returns:
        True if kubectl is installed and context is active, False otherwise.
    """
    try:
        subprocess.run(
            ["kubectl", "cluster-info"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("✓ kubectl connection verified successfully.")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning(
            "kubectl is not installed or cluster connection is unavailable. "
            "Skipping GKE active cluster connectivity checks."
        )
        return False


def verify_gke_context(cluster_name: str) -> None:
    """Checks if the active kubectl context is available for the target cluster.

    Args:
        cluster_name: Name of the target GKE cluster.
    """
    try:
        result = subprocess.run(
            ["kubectl", "config", "current-context"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        current_ctx = result.stdout.strip()
        logger.info("Current active kubectl context: '%s'", current_ctx)
        if cluster_name not in current_ctx:
            logger.warning(
                "Active context '%s' does not match target GKE cluster name "
                "'%s'. Ensure you switch context before running GKE "
                "validation steps.",
                current_ctx,
                cluster_name,
            )
    except subprocess.CalledProcessError:
        logger.warning("No active kubectl context configured.")


def verify_gcloud_connection() -> bool:
    """Verifies if gcloud is installed and authenticated.

    Returns:
        True if gcloud is installed and authenticated, False otherwise.
    """
    try:
        subprocess.run(
            ["gcloud", "version"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning(
            "gcloud is not installed or not in PATH. "
            "Skipping target GCP project and cluster verification."
        )
        return False


def verify_gcp_project(project_id: str) -> None:
    """Verifies if the specified GCP project exists and is accessible.

    Args:
        project_id: ID of the GCP project to verify.

    Raises:
        SystemExit(1): If the GCP project does not exist or is not accessible.
    """
    logger.info("Checking access to GCP project '%s'...", project_id)
    try:
        subprocess.run(
            ["gcloud", "projects", "describe", project_id],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info(
            "✓ Target GCP project '%s' exists and is accessible.", project_id
        )
    except subprocess.CalledProcessError as e:
        logger.error(
            "Failed to describe GCP project '%s'. "
            "Ensure you have active credentials and permission.",
            project_id,
        )
        raise SystemExit(1) from e


def verify_gke_cluster(
    cluster_name: str, location: str, project_id: str
) -> None:
    """Verifies if the target GKE cluster exists.

    Args:
        cluster_name: Name of the target GKE cluster.
        location: Location of the target GKE cluster.
        project_id: ID of the GCP project containing the cluster.

    Raises:
        SystemExit(1): If the GKE cluster does not exist or is not active.
    """
    logger.info(
        "Checking GKE cluster '%s' in location '%s'...", cluster_name, location
    )
    try:
        result = subprocess.run(
            [
                "gcloud",
                "container",
                "clusters",
                "describe",
                cluster_name,
                "--location",
                location,
                "--project",
                project_id,
                "--format",
                "value(status)",
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        status = result.stdout.strip()
        logger.info(
            "✓ Target GKE cluster '%s' exists. Status: %s", cluster_name, status
        )
        if status != "RUNNING":
            logger.warning(
                "Target GKE cluster '%s' status is '%s' (expected RUNNING).",
                cluster_name,
                status,
            )
    except subprocess.CalledProcessError as e:
        logger.error(
            "Failed to describe GKE cluster '%s' in '%s'. "
            "Ensure the cluster has been provisioned and is accessible "
            "with current credentials.",
            cluster_name,
            location,
        )
        raise SystemExit(1) from e


def is_active_gke_context(cluster_name: str) -> bool:
    """Checks if current active kubectl context matches target cluster."""
    try:
        result = subprocess.run(
            ["kubectl", "config", "current-context"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        current_ctx = result.stdout.strip()
        return cluster_name in current_ctx
    except subprocess.CalledProcessError:
        return False


def configure_gke_context(
    cluster_name: str, location: str, project_id: str
) -> None:
    """Configures the kubectl context for GKE using gcloud get-credentials."""
    logger.info(
        "Current active context does not match target GKE cluster. "
        "Configuring context..."
    )
    try:
        cmd = [
            "gcloud",
            "container",
            "clusters",
            "get-credentials",
            cluster_name,
            "--project",
            project_id,
        ]
        # Determine if location is a zone (e.g. us-west1-a)
        # or region (e.g. us-west1)
        if len(location.split("-")) == 3:
            cmd.extend(["--zone", location])
        else:
            cmd.extend(["--region", location])

        subprocess.run(
            cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        logger.info(
            "✓ Successfully configured GKE context for cluster '%s'.",
            cluster_name,
        )
    except subprocess.CalledProcessError as e:
        logger.error(
            "Failed to configure GKE context for cluster '%s'. Error: %s\n"
            "Please ensure you are authenticated by running "
            "'gcloud auth login' and try again.",
            cluster_name,
            e.stderr.decode().strip(),
        )
        raise SystemExit(1) from e
