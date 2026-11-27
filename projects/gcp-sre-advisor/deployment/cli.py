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

"""Unified CLI entrypoint for GCP SRE Advisor management tasks."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from deployment.auth import gcloud_cmd, require_project_id
from deployment.bootstrap_profile import bootstrap_profile
from deployment.check_profile_drift import check_profile_drift
from deployment.deploy_agent_engine import deploy_agent
from deployment.inspect_catalog import inspect_catalog
from deployment.setup_gemini_enterprise import setup_gemini_enterprise
from deployment.sync_profiles_gcs import sync_profiles
from deployment.validate_profile import validate_profile

ROOT_DIR = Path(__file__).resolve().parent.parent

MCP_APIS = (
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "sqladmin.googleapis.com",
    "compute.googleapis.com",
    "storage.googleapis.com",
    "bigquery.googleapis.com",
    "pubsub.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "orgpolicy.googleapis.com",
    "run.googleapis.com",
    "cloudtrace.googleapis.com",
    "cloudasset.googleapis.com",
    "cloudcli.googleapis.com",
    "developerknowledge.googleapis.com",
    "agentregistry.googleapis.com",
    "apphub.googleapis.com",
    "aiplatform.googleapis.com",
    "discoveryengine.googleapis.com",
)


def enable_apis(project_id: str | None = None) -> None:
    """Enables required Google Cloud APIs on the target runtime project."""
    proj = require_project_id(project_id)
    subprocess.run(
        gcloud_cmd(
            "services", "enable", *MCP_APIS, f"--project={proj}", "--quiet"
        ),
        check=True,
    )
    print(f"APIs enabled on {proj}")


def run_playground(default_profile: str = "") -> None:
    """Launches the local ADK web playground."""
    env = os.environ.copy()
    env["WORKLOAD_PROFILE_NAME"] = default_profile
    adk_bin = Path(sys.executable).with_name("adk")
    subprocess.run(
        [str(adk_bin), "web", "."], cwd=str(ROOT_DIR), env=env, check=True
    )


def _resolve_saved_reasoning_engine_id() -> str:
    meta_path = ROOT_DIR / "deployment_metadata.json"
    if meta_path.exists():
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            re_id = str(data.get("reasoning_engine_id") or "").strip()
            if re_id:
                return re_id
        except (OSError, ValueError):
            pass
    return (os.getenv("REASONING_ENGINE_ID") or "").strip()


def build_parser() -> argparse.ArgumentParser:
    """Builds the command-line argument parser."""
    parser = argparse.ArgumentParser(prog="python3 cli.py")
    sub = parser.add_subparsers(dest="command", required=True)

    p_val = sub.add_parser("validate", aliases=["validate-profile"])
    p_val.add_argument("profile_pos", nargs="?", default="")
    p_val.add_argument("--profile", default="")

    p_boot = sub.add_parser("bootstrap", aliases=["bootstrap-profile"])
    p_boot.add_argument("project_pos", nargs="?", default="")
    p_boot.add_argument("profile_pos", nargs="?", default="")
    p_boot.add_argument("--project", default="")
    p_boot.add_argument("--profile", default="")
    p_boot.add_argument("--tier", default="prod")
    p_boot.add_argument("--region", default="us-central1")
    p_boot.add_argument("--zone", default="")
    p_boot.add_argument("--iac-dir", default="")

    p_sync = sub.add_parser("sync", aliases=["sync-profiles"])
    p_sync.add_argument("--gcs-uri", default="")
    p_sync.add_argument("--project", default="")
    p_sync.add_argument("--prune", action="store_true")

    p_drift = sub.add_parser("drift", aliases=["check-drift"])
    p_drift.add_argument("profile_pos", nargs="?", default="")
    p_drift.add_argument("--profile", default="")
    p_drift.add_argument("--project", default="")

    p_cat = sub.add_parser("catalog", aliases=["inspect-catalog"])
    p_cat.add_argument("project_pos", nargs="?", default="")
    p_cat.add_argument("--project", default="")
    p_cat.add_argument("--region", default="")

    p_apis = sub.add_parser("apis", aliases=["enable-apis"])
    p_apis.add_argument("project_pos", nargs="?", default="")
    p_apis.add_argument("--project", default="")

    p_dep = sub.add_parser("deploy", aliases=["deploy-agent"])
    p_dep.add_argument("--project", default="")
    p_dep.add_argument("--default-profile", default="")
    p_dep.add_argument("--skip-sync", action="store_true")

    p_ge = sub.add_parser("register", aliases=["setup-gemini-enterprise"])
    p_ge.add_argument("re_id_pos", nargs="?", default="")
    p_ge.add_argument("--reasoning-engine-id", default="")
    p_ge.add_argument("--project", default="")
    p_ge.add_argument("--engine-id", default="")
    p_ge.add_argument("--datastore-id", default="")

    p_play = sub.add_parser("playground")
    p_play.add_argument("--default-profile", default="")

    return parser


def _ensure_cli_gcloud_account_alignment() -> None:
    if any(
        os.getenv(k, "").strip()
        for k in (
            "CLOUDSDK_CORE_ACCOUNT",
            "GOOGLE_OAUTH_ACCESS_TOKEN",
            "GOOGLE_APPLICATION_CREDENTIALS",
            "K_SERVICE",
        )
    ):
        return
    try:
        active = subprocess.check_output(
            ["gcloud", "config", "get-value", "core/account", "--quiet"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return
    if (
        active
        and active != "(unset)"
        and not active.endswith(".gserviceaccount.com")
    ):
        os.environ["CLOUDSDK_CORE_ACCOUNT"] = active


def main(argv: list[str] | None = None) -> None:
    if argv is None:
        _ensure_cli_gcloud_account_alignment()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in ("validate", "validate-profile"):
        prof = (args.profile or args.profile_pos or "_sample").strip()
        validate_profile(prof)
    elif args.command in ("bootstrap", "bootstrap-profile"):
        proj = (args.project or args.project_pos).strip()
        prof = (args.profile or args.profile_pos).strip()
        if not proj or not prof:
            parser.error("bootstrap requires <project-id> and <profile-name>.")
        bootstrap_profile(
            project_id=proj,
            profile_slug=prof,
            tier=args.tier,
            iac_dir=args.iac_dir,
            region=args.region,
            zone=args.zone,
        )
    elif args.command in ("sync", "sync-profiles"):
        sync_profiles(
            gcs_uri=args.gcs_uri or None,
            runtime_project=args.project or None,
            prune=args.prune,
        )
    elif args.command in ("drift", "check-drift"):
        prof = (args.profile or args.profile_pos).strip()
        if not prof:
            parser.error("drift requires <profile-name>.")
        check_profile_drift(prof, args.project or None)
    elif args.command in ("catalog", "inspect-catalog"):
        proj = (args.project or args.project_pos or "").strip() or None
        inspect_catalog(proj, args.region)
    elif args.command in ("apis", "enable-apis"):
        proj = (args.project or args.project_pos or "").strip() or None
        enable_apis(proj)
    elif args.command in ("deploy", "deploy-agent"):
        if not args.skip_sync:
            sync_profiles(runtime_project=args.project or None, prune=False)
        deploy_agent(
            default_profile=args.default_profile,
            project_id=args.project or None,
        )
    elif args.command in ("register", "setup-gemini-enterprise"):
        re_id = (
            args.reasoning_engine_id
            or args.re_id_pos
            or _resolve_saved_reasoning_engine_id()
        ).strip()
        if not re_id:
            raise ValueError(
                "No Reasoning Engine ID provided and none found in "
                "deployment_metadata.json or REASONING_ENGINE_ID."
            )
        setup_gemini_enterprise(
            reasoning_engine_id=re_id,
            project_id=args.project or None,
            engine_id=args.engine_id or None,
            datastore_id=args.datastore_id or None,
        )
    elif args.command == "playground":
        run_playground(args.default_profile)


if __name__ == "__main__":
    main()
