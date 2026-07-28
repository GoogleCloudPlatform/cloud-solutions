#  Copyright 2026 Google LLC
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""Translation module to download, configure and run ingress2gateway tool."""

import hashlib
import json
import logging
import os
import platform
import tarfile
import tempfile
import urllib.error
import urllib.request
from typing import Any, Dict, List

from cluster_client import run_command
from config import BIN_DIR, MigrationError

EXPECTED_CHECKSUMS: Dict[str, str] = {
    "ingress2gateway_Darwin_arm64.tar.gz": (
        "5b0ac7b7cf5e3a4a0206364900daf154303818a2bd0dc1092b379d315798f98d"
    ),
    "ingress2gateway_Darwin_x86_64.tar.gz": (
        "907fa9b00d2c3fecb23d8c9d0544782a9506a8f3417c7fad81f14afd5d918596"
    ),
    "ingress2gateway_Linux_arm64.tar.gz": (
        "6d4b494eaecbe3fdb262f404cddfef6184f422386ef463d5142b679651c46841"
    ),
    "ingress2gateway_Linux_i386.tar.gz": (
        "7e98ebe2dfb146810d21187be69922e9a6606f72a7cd6b16c9b1d02f8b59d10d"
    ),
    "ingress2gateway_Linux_x86_64.tar.gz": (
        "3ec6d434a92be61560298eddb0f4fb53bfa76a0ab885b51e0b32f883cfacc20f"
    ),
}


def get_ingress_provider(ingress: Dict[str, Any]) -> str:
    """Helper to detect the ingress provider name from ingress metadata/spec.

    Args:
        ingress: The ingress resource to analyze.

    Returns:
        The name of the ingress provider (gce, nginx, etc.).
    """
    spec = ingress.get("spec", {})
    metadata = ingress.get("metadata", {})
    annotations = metadata.get("annotations", {})
    # Check for both ingress class name in spec and annotations respectively
    ingress_class = spec.get("ingressClassName")
    if not ingress_class:
        ingress_class = annotations.get("kubernetes.io/ingress.class")
    if not ingress_class:
        return "gce"
    ingress_class = ingress_class.lower()
    if "nginx" in ingress_class:
        return "nginx"
    if "gce" in ingress_class or "gke" in ingress_class:
        return "gce"
    return ingress_class


def ensure_ingress2gateway_binary() -> str:
    """Downloads and verifies the official ingress2gateway pre-compiled binary.

    Checks if the binary exists locally in the bin directory. If not, it
    identifies the OS and architecture, downloads the release archive from
    GitHub, extracts it, and sets executable permissions.

    Returns:
        The absolute path to the verified ingress2gateway executable.

    Raises:
        MigrationError: If downloading, extracting, or configuring the binary
            engine fails, or if running on an unsupported OS.
    """

    if platform.system() == "Windows":
        raise MigrationError(
            "Windows is not supported for ingress2gateway translation."
        )

    os.makedirs(BIN_DIR, exist_ok=True)
    binary_name = "ingress2gateway"
    binary_path = os.path.join(BIN_DIR, binary_name)

    if os.path.exists(binary_path):
        return binary_path

    logging.info(
        "▶ [RUNTIME] Downloading ingress2gateway build from GitHub releases..."
    )
    sys_os = platform.system()
    machine = platform.machine().lower()

    # Map architecture definitions
    if "arm64" in machine or "aarch64" in machine:
        arch = "arm64"
    elif "386" in machine or "i686" in machine:
        arch = "i386"
    else:
        arch = "x86_64"

    ext = "tar.gz"
    version = "v1.1.0"

    asset_name = f"ingress2gateway_{sys_os}_{arch}.{ext}"
    url = f"https://github.com/kubernetes-sigs/ingress2gateway/releases/download/{version}/{asset_name}"
    archive_path = os.path.join(BIN_DIR, asset_name)

    try:
        urllib.request.urlretrieve(url, archive_path)
        with open(archive_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()

        expected_hash = EXPECTED_CHECKSUMS.get(asset_name)
        if not expected_hash or file_hash != expected_hash:
            raise MigrationError(
                f"SHA-256 checksum verification failed for {asset_name}. "
                f"Expected {expected_hash}, got {file_hash}."
            )

        with tarfile.open(archive_path, "r:gz") as tar:
            # Extract only the binary from the archive. The archive may contain
            # other files and we only want the binary.
            member = tar.getmember(binary_name)
            tar.extract(member, path=BIN_DIR)

        os.chmod(binary_path, 0o755)

        logging.info("  ✓ Platform translation engine loaded successfully.")
        return binary_path
    except MigrationError:
        raise
    except (urllib.error.URLError, tarfile.TarError, OSError) as e:
        logging.error("Failed to fetch or configure translation binary: %s", e)
        raise MigrationError(
            f"Failed to fetch or configure translation binary engine: {e}"
        ) from e
    except Exception as e:
        logging.exception(
            "Unexpected error during engine initialization: %s", e
        )
        raise MigrationError(
            f"Unexpected error configuring translation binary engine: {e}"
        ) from e
    finally:
        if os.path.exists(archive_path):
            os.remove(archive_path)


def compile_translation(
    binary_path: str, target_ingresses: List[Dict[str, Any]]
) -> str:
    """Invokes the ingress2gateway tool to translate Ingress manifests.

    Writes the target Ingress resources to a temporary YAML manifest bundle,
    executes the translation tool for GCE Gateway API providers, and captures
    the generated Gateway and HTTPRoute specifications.

    Args:
        binary_path: The file path to the ingress2gateway executable.
        target_ingresses: A list of Kubernetes Ingress item dictionaries to
            translate.

    Returns:
        A string containing the compiled Gateway API YAML specifications.

    Raises:
        MigrationError: If the translation tool execution fails.
    """

    bundle = {"apiVersion": "v1", "kind": "List", "items": target_ingresses}
    with tempfile.NamedTemporaryFile(
        mode="w+", suffix=".yaml", delete=False
    ) as temp_f:
        temp_f.write(json.dumps(bundle))
        temp_file_path = temp_f.name

    # Dynamically resolve active providers
    supported_providers = {"gce", "nginx"}
    providers = set()
    for ing in target_ingresses:
        p = get_ingress_provider(ing)
        if p in supported_providers:
            providers.add(p)
        else:
            providers.add("gce")  # Fallback to gce
    if not providers:
        providers = {"gce"}
    providers_str = ",".join(sorted(providers))
    logging.info("Detected providers: %s", providers_str)

    try:
        # Execute the command for translation
        cmd = [
            binary_path,
            "print",
            f"--input-file={temp_file_path}",
            f"--providers={providers_str}",
            "--emitter=gce",
        ]
        gateway_yaml = run_command(cmd)
        return gateway_yaml
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


def execute_server_dry_run(gateway_yaml: str) -> None:
    """Validates translated Gateway specifications against the target cluster.

    Applies the generated YAML specifications using `kubectl apply` with the
    `--dry-run=server` flag to verify schema validity and server acceptance
    without persisting resources.

    Args:
        gateway_yaml: The translated Gateway API YAML specification string.

    Raises:
        MigrationError: If server-side dry-run validation fails or schema
            errors are rejected by the Kubernetes API server.
    """

    try:
        run_command(
            ["kubectl", "apply", "--dry-run=server", "-f", "-"],
            input_data=gateway_yaml,
        )
        logging.info(
            "  ✓ Server-side dry-run validation passed. "
            "Gateway API schema schemas validated."
        )

    except Exception as e:
        raise MigrationError(
            f"Gateway API server dry-run validation failed: {e}"
        ) from e
