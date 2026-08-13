#!/usr/bin/env python3

# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Cloud Run & Terraform deployment automation script.

Reads configurations from .env, injects them into Terraform variables,
and applies the Terraform configuration to deploy the Cloud Run infrastructure.
"""

import logging
import os
import re
import subprocess
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    """Main deployment orchestration execution."""
    workspace_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
    env_file = os.path.join(workspace_root, ".env")
    terraform_dir = os.path.join(workspace_root, "terraform")
    tfvars_file = os.path.join(terraform_dir, "terraform.tfvars")

    if not os.path.exists(env_file):
        logger.error("Error: .env file not found at %s", env_file)
        sys.exit(1)

    logger.info("Loading variables from %s...", env_file)
    env_vars = {}
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.match(r"([^=]+)=(.*)", line)
            if match:
                k = match.group(1).strip()
                v = match.group(2).strip().strip("'\"")
                env_vars[k] = v

    logger.info("Loaded %d environment variables.", len(env_vars))

    # Read existing terraform.tfvars or initialize new
    logger.info("Synchronizing variables into %s...", tfvars_file)

    # Map .env keys to terraform.tfvars names
    key_mapping = {
        "GCP_PROJECT_ID": "project_id",
        "CONVERSATION_PROFILE_ID": "conversation_profile_id",
        "CES_SERVICE_AGENT": "ces_service_agent",
    }

    # Prepare lines to write
    tfvars_content = {}
    if os.path.exists(tfvars_file):
        with open(tfvars_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                match = re.match(r"([^=]+)=(.*)", line)
                if match:
                    k = match.group(1).strip()
                    v = match.group(2).strip().strip("'\"")
                    tfvars_content[k] = v

    # Auto-detect CES_SERVICE_AGENT if not set in .env
    if "CES_SERVICE_AGENT" not in env_vars or not env_vars.get(
        "CES_SERVICE_AGENT"
    ):
        project_id = env_vars.get("GCP_PROJECT_ID") or env_vars.get(
            "GOOGLE_CLOUD_PROJECT"
        )
        if project_id:
            logger.info(
                "Auto-detecting CES_SERVICE_AGENT for project '%s'...",
                project_id,
            )
            try:
                res = subprocess.run(
                    [
                        "gcloud",
                        "projects",
                        "describe",
                        project_id,
                        "--format=value(projectNumber)",
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                project_number = res.stdout.strip()
                if project_number and project_number.isdigit():
                    auto_agent = (
                        f"service-{project_number}"
                        "@gcp-sa-ces.iam.gserviceaccount.com"
                    )
                    env_vars["CES_SERVICE_AGENT"] = auto_agent
                    logger.info(
                        "  [Auto-Detected] CES_SERVICE_AGENT = '%s'",
                        auto_agent,
                    )
            except (subprocess.CalledProcessError, OSError) as e:
                logger.warning(
                    "  [Warning] Could not auto-detect project number: %s", e
                )

    # Override with .env values
    for env_k, tf_k in key_mapping.items():
        if env_k in env_vars:
            tfvars_content[tf_k] = env_vars[env_k]
            logger.info("  -> %s = '%s'", tf_k, env_vars[env_k])

    # Write back to terraform.tfvars
    with open(tfvars_file, "w", encoding="utf-8") as f:
        for k, v in tfvars_content.items():
            f.write(f'{k} = "{v}"\n')

    logger.info("Successfully synchronized terraform.tfvars")

    logger.info(
        "\nEnabling required Google Cloud APIs & instantiating identities..."
    )
    project_id = env_vars.get("GCP_PROJECT_ID") or env_vars.get(
        "GOOGLE_CLOUD_PROJECT"
    )
    if project_id:
        subprocess.run(
            [
                "gcloud",
                "services",
                "enable",
                f"--project={project_id}",
                "iam.googleapis.com",
                "artifactregistry.googleapis.com",
                "cloudbuild.googleapis.com",
                "compute.googleapis.com",
                "run.googleapis.com",
                "dialogflow.googleapis.com",
                "ces.googleapis.com",
                "storage.googleapis.com",
                "iap.googleapis.com",
            ],
            check=False,
        )
        subprocess.run(
            [
                "gcloud",
                "beta",
                "services",
                "identity",
                "create",
                "--service=ces.googleapis.com",
                f"--project={project_id}",
            ],
            check=False,
        )
        subprocess.run(
            [
                "gcloud",
                "beta",
                "services",
                "identity",
                "create",
                "--service=dialogflow.googleapis.com",
                f"--project={project_id}",
            ],
            check=False,
        )

    # Run terraform init
    logger.info("\nRunning 'terraform init'...")
    res = subprocess.run(["terraform", "init"], cwd=terraform_dir, check=False)
    if res.returncode != 0:
        logger.error("Terraform init failed!")
        sys.exit(res.returncode)

    # Run terraform apply
    logger.info("\nRunning 'terraform apply -auto-approve'...")
    res = subprocess.run(
        ["terraform", "apply", "-auto-approve"], cwd=terraform_dir, check=False
    )
    if res.returncode != 0:
        logger.error("Terraform apply failed!")
        sys.exit(res.returncode)

    logger.info("\nCloud Run deployment completed successfully!")


if __name__ == "__main__":
    main()
