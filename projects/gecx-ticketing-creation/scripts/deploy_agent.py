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


"""Deploy GECX Agent script.

Pushes local app assets to GECX, creates a version, and creates/re-promotes
a WEB_UI channel deployment.
"""

import argparse
import os
import re
import subprocess
import sys
import time

from cxas_scrapi.core.deployments import Deployments
from dotenv import load_dotenv
from google.api_core.exceptions import GoogleAPICallError
from google.cloud.ces_v1beta import types
from google.protobuf import field_mask_pb2

load_dotenv()


def run_cmd(cmd):
    """Run a subprocess command and return stdout or exit on error."""
    cmd_str = " ".join(cmd)
    print(f"Running: {cmd_str}")
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        error_msg = (
            res.stderr.strip()
            or res.stdout.strip()
            or "Unknown command failure."
        )
        print(f"Error (exit code {res.returncode}):\n{error_msg}")
        sys.exit(res.returncode)
    return res.stdout


def update_openapi_schema_urls(app_dir, project_id, region="us-central1"):
    """Auto-detect and update OpenAPI webhook server URLs."""
    print("Resolving Cloud Run Webhook URL for 'cymbal-gecx-webhook'...")
    try:
        res = subprocess.run(
            [
                "gcloud",
                "run",
                "services",
                "describe",
                "cymbal-gecx-webhook",
                f"--project={project_id}",
                f"--region={region}",
                "--format=value(status.url)",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        webhook_url = res.stdout.strip()
        if not webhook_url or not webhook_url.startswith("https://"):
            print(
                "  [Warning] Could not auto-detect cymbal-gecx-webhook URL from"
                " gcloud."
            )
            return

        print(f"  [Auto-Detected] Webhook URL: {webhook_url}")
        tools_dir = os.path.join(app_dir, "tools")
        if not os.path.exists(tools_dir):
            return

        for root, _, files in os.walk(tools_dir):
            for file in files:
                if (
                    file.endswith((".yaml", ".yml"))
                    and "template" not in file
                ):
                    schema_path = os.path.join(root, file)
                    template_path = (
                        schema_path.replace(".yaml", ".template.yaml")
                        if schema_path.endswith(".yaml")
                        else schema_path.replace(".yml", ".template.yml")
                    )

                    source_path = (
                        template_path
                        if os.path.exists(template_path)
                        else schema_path
                    )
                    with open(source_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    updated_content, count = re.subn(
                        r"url:\s*(\$\{webhook_cloud_run_url\}|https://[^\s]+)",
                        f"url: {webhook_url}",
                        content,
                    )
                    with open(schema_path, "w", encoding="utf-8") as f:
                        f.write(updated_content)
                    rel_path = os.path.relpath(schema_path, app_dir)
                    print(
                        f"  [Auto-Update] Updated OpenAPI server url in"
                        f" {rel_path} ({count} replacement)"
                    )
    except (subprocess.SubprocessError, OSError, ValueError) as e:
        print(f"  [Warning] Error updating webhook URL in OpenAPI schemas: {e}")


def ensure_gecx_app_exists(project_id, app_id, location="us"):
    """Check if the GECX app exists; if not, create it first via cxas create."""
    print(
        f"Checking if GECX app '{app_id}' exists on project '{project_id}'..."
    )
    app_resource_name = (
        f"projects/{project_id}/locations/{location}/apps/{app_id}"
    )
    check_cmd = [
        sys.executable,
        "-m",
        "cxas_scrapi.cli.main",
        "apps",
        "get",
        app_resource_name,
        "--project-id",
        project_id,
        "--location",
        location,
    ]
    try:
        subprocess.run(
            check_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        print("  [Found] Existing GECX app found.")
    except subprocess.CalledProcessError:
        print(
            f"  [Not Found] App '{app_id}' does not exist yet. Creating via"
            " 'cxas create'..."
        )
        create_cmd = [
            sys.executable,
            "-m",
            "cxas_scrapi.cli.main",
            "create",
            "Cymbal Servicing Agent",
            "--app-id",
            app_id,
            "--project-id",
            project_id,
            "--location",
            location,
        ]
        for attempt in range(1, 4):
            res = subprocess.run(
                create_cmd, capture_output=True, text=True, check=False
            )
            if res.returncode == 0:
                print("  [Created] Successfully initialized GECX application.")
                break

            error_msg = res.stderr.strip() or res.stdout.strip()
            if "already exists" in error_msg.lower():
                print("  [Found] App already exists.")
                break
            if attempt == 3:
                print(f"Error (exit code {res.returncode}):\n{error_msg}")
                sys.exit(res.returncode)
            print(
                f"  [Warning] Attempt {attempt} to create app failed"
                f" ({error_msg}). Retrying in 15 seconds for GCP IAM"
                " propagation..."
            )
            time.sleep(15)


def main():
    """Main deployment flow for GECX agent and WEB_UI channel."""
    default_project = (
        os.getenv("GCP_PROJECT_ID")
        or os.getenv("GOOGLE_CLOUD_PROJECT")
    )
    parser = argparse.ArgumentParser(
        description="Deploy GECX Agent with WEB_UI channel type."
    )
    parser.add_argument(
        "--project-id",
        default=default_project,
        required=default_project is None,
        help="GCP Project ID (required if GCP_PROJECT_ID env var not set)",
    )
    parser.add_argument(
        "--region",
        default="us-central1",
        help="Google Cloud region for services (default: us-central1)",
    )
    parser.add_argument(
        "--location", default="us", help="GECX region (e.g. us)"
    )
    parser.add_argument(
        "--app-id", default="cymbal-support-agent", help="GECX App ID"
    )
    parser.add_argument(
        "--app-dir",
        default="src/gecx_agent/cymbal_support_agent",
        help="Local GECX app folder",
    )
    parser.add_argument(
        "--deployment-id",
        default="cymbal-support-agent-web",
        help="Target deployment ID",
    )
    parser.add_argument(
        "--widget-title",
        default="Cymbal Support",
        help="Title displayed on the web chat widget",
    )

    args = parser.parse_args()

    app_name = (
        f"projects/{args.project_id}/locations/{args.location}/apps/"
        f"{args.app_id}"
    )
    print(f"Deploying agent for app: {app_name}")

    ensure_gecx_app_exists(args.project_id, args.app_id, args.location)
    update_openapi_schema_urls(args.app_dir, args.project_id, args.region)

    # 1. Push local changes & create version
    push_cmd = [
        sys.executable,
        "-m",
        "cxas_scrapi.cli.main",
        "push",
        "--app-dir",
        args.app_dir,
        "--to",
        app_name,
        "--project-id",
        args.project_id,
        "--location",
        args.location,
        "--create-version",
        "--version-description",
        "Deployment via deploy_agent.py",
    ]
    stdout = run_cmd(push_cmd)

    # Typical output:
    # "Created app version: projects/.../versions/<version_uuid>"
    version_id = None
    for line in stdout.splitlines():
        if "Created app version:" in line:
            parts = line.split("Created app version:")
            if len(parts) > 1:
                version_id = parts[1].strip().split()[0]
                break

    if not version_id:
        print("Error: Could not parse version ID from push output.")
        sys.exit(1)

    print(f"Successfully created version: {version_id}")

    # 2. Re-create deployment with WEB_UI channel type
    deployments_client = Deployments(app_name=app_name)

    print(f"Deleting old deployment '{args.deployment_id}' if exists...")
    try:
        deployments_client.delete_deployment(deployment_id=args.deployment_id)
        print("Deleted old deployment.")
    except (GoogleAPICallError, KeyError, ValueError, RuntimeError) as e:
        print(f"Note: Delete skipped/not found ({e})")

    print(
        f"Creating new WEB_UI deployment '{args.deployment_id}' targeting"
        f" version '{version_id}'..."
    )
    new_dep = deployments_client.create_deployment(
        deployment_id=args.deployment_id,
        display_name="cymbal-support-agent",
        app_version=version_id,
        channel_type="WEB_UI",
        modality="CHAT_AND_VOICE",
        theme="LIGHT",
        web_widget_title=args.widget_title,
    )
    print(f"Deployment successfully active: {new_dep.name}")

    # Enable public access on the WEB_UI deployment channel
    print(f"Enabling public access on deployment '{new_dep.name}'...")
    try:
        sec_settings = types.ChannelProfile.WebWidgetConfig.SecuritySettings(
            enable_public_access=True
        )
        wwc = types.ChannelProfile.WebWidgetConfig(
            security_settings=sec_settings
        )
        channel_profile = types.ChannelProfile(
            channel_type=types.ChannelProfile.ChannelType.WEB_UI,
            web_widget_config=wwc,
        )
        deployment_update = types.Deployment(
            name=new_dep.name, channel_profile=channel_profile
        )
        update_mask = field_mask_pb2.FieldMask(
            paths=[
                "channel_profile.web_widget_config.security_settings"
                ".enable_public_access"
            ]
        )
        req = types.UpdateDeploymentRequest(
            deployment=deployment_update, update_mask=update_mask
        )
        deployments_client.client.update_deployment(request=req)
        print("  [🟢 Success] Public access enabled on deployment channel.")
    except (GoogleAPICallError, KeyError, AttributeError, RuntimeError) as e:
        print(f"  [Warning] Could not enable public access automatically: {e}")

    # 3. Automatically generate frontend index.html from index.template.html
    template_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "src",
            "frontend",
            "static",
            "loopback",
            "index.template.html",
        )
    )
    index_html_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "src",
            "frontend",
            "static",
            "loopback",
            "index.html",
        )
    )

    source_path = (
        template_path if os.path.exists(template_path) else index_html_path
    )
    if os.path.exists(source_path):
        source_name = os.path.basename(source_path)
        print(
            f"Generating {index_html_path} from {source_name} with new"
            f" deploymentName '{new_dep.name}'..."
        )
        try:
            with open(source_path, "r", encoding="utf-8") as f:
                content = f.read()

            pattern = (
                r'(deploymentName:\s*["\'])'
                r'(?:<<AGENT_DEPLOYMENT_NAME>>|projects/[^"\']+)(["\'])'
            )
            updated_content, count = re.subn(
                pattern,
                rf"\g<1>{new_dep.name}\g<2>",
                content,
            )
            with open(index_html_path, "w", encoding="utf-8") as f:
                f.write(updated_content)
            print(
                f"  [Auto-Update] Successfully generated index.html ({count}"
                " replacement)."
            )
        except (OSError, re.error) as e:
            print(f"  [Warning] Failed to generate index.html: {e}")


if __name__ == "__main__":
    main()
