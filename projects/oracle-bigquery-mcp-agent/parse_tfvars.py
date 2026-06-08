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

"""Parses terraform.tfvars (HCL syntax) and outputs shell export statements.

This enables a single source of configuration (terraform.tfvars) for both raw
shell scripts (which need env vars) and Terraform sub-modules (which need
TF_VAR_).
"""

import os
import re
import sys


def main():
    if len(sys.argv) < 2:
        print("Usage: parse_tfvars.py <path_to_tfvars_file>", file=sys.stderr)
        sys.exit(1)

    filepath = sys.argv[1]
    if not os.path.exists(filepath):
        # Exit quietly if file does not exist, allowing scripts to fall back to
        # default settings
        sys.exit(0)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as e:
        print(f"Error reading {filepath}: {e}", file=sys.stderr)
        sys.exit(1)

    # Regex to match key = value assignments, ignoring comments (#, //)
    pattern = re.compile(
        r"^\s*([a-zA-Z0-9_]+)\s*=\s*(.+?)\s*(?:#|//|$)", re.MULTILINE
    )

    # Map HCL lowercase variables to script-internal uppercase environment
    # variables
    mapping = {
        "project_id": "ACTIVE_PROJECT",
        "db_password": "DB_PASSWORD",
        "region": "DEPLOY_REGION",
        "zone": "DEPLOY_ZONE",
        "gcs_bucket_name": "GCS_BUCKET_NAME",
        "ssh_user": "SSH_USER",
        "ssh_key_path": "SSH_KEY_PATH",
        "oauth_client_id": "OAUTH_CLIENT_ID",
        "oauth_client_secret": "OAUTH_CLIENT_SECRET",
        "create_vpc": "CREATE_VPC",
        "vpc_name": "VPC_NAME",
        "create_subnetwork": "CREATE_SUBNETWORK",
        "subnetwork_name": "SUBNETWORK_NAME",
        "create_gcs_bucket": "CREATE_GCS_BUCKET",
        "edition": "LOOKER_EDITION",
    }

    for match in pattern.finditer(content):
        key, val = match.groups()
        val_clean = val.strip()

        # Remove surrounding double/single quotes if present
        is_double = val_clean.startswith('"') and val_clean.endswith('"')
        is_single = val_clean.startswith("'") and val_clean.endswith("'")
        if is_double or is_single:
            val_clean = val_clean[1:-1]

        # Escape single quotes for safe inclusion in shell single-quoted strings
        val_escaped = val_clean.replace("'", "'\\''")

        # Export as Terraform-compatible TF_VAR_ variable
        print(f"export TF_VAR_{key}='{val_escaped}'")
        # Export as script-internal uppercase environment variable
        if key in mapping:
            print(f"export {mapping[key]}='{val_escaped}'")


if __name__ == "__main__":
    main()
