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

"""Audits declarative Workload Profile stacks against live Cloud Assets."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.app_utils.profile_loader import (
    build_profile_drift_contract,
    load_active_profile,
)
from deployment.auth import gcloud_cmd

ASSET_TYPE_TO_STACK_KEY: dict[str, tuple[str, str]] = {
    "container.googleapis.com/Cluster": ("compute", "gke"),
    "run.googleapis.com/Service": ("compute", "cloud_run"),
    "run.googleapis.com/Job": ("compute", "cloud_run_jobs"),
    "run.googleapis.com/WorkerPool": ("compute", "cloud_run_worker_pools"),
    "compute.googleapis.com/Instance": ("compute", "compute_engine"),
    "sqladmin.googleapis.com/Instance": ("databases", "cloudsql"),
    "alloydb.googleapis.com/Cluster": ("databases", "alloydb"),
    "spanner.googleapis.com/Instance": ("databases", "spanner"),
    "bigquery.googleapis.com/Dataset": ("databases", "bigquery"),
    "firestore.googleapis.com/Database": ("databases", "firestore"),
    "redis.googleapis.com/Instance": ("caching_messaging", "memorystore_redis"),
    "memorystore.googleapis.com/Instance": (
        "caching_messaging",
        "memorystore_redis",
    ),
    "pubsub.googleapis.com/Topic": ("caching_messaging", "pubsub"),
    "eventarc.googleapis.com/Trigger": ("caching_messaging", "eventarc"),
    "compute.googleapis.com/UrlMap": ("edge_networking", "global_external_alb"),
    "compute.googleapis.com/RegionUrlMap": ("edge_networking", "regional_alb"),
    "compute.googleapis.com/BackendBucket": ("edge_networking", "cloud_cdn"),
    "compute.googleapis.com/Router": ("edge_networking", "cloud_nat"),
    "compute.googleapis.com/RouterNat": ("edge_networking", "cloud_nat"),
    "compute.googleapis.com/SecurityPolicy": ("edge_networking", "cloud_armor"),
    "dns.googleapis.com/ManagedZone": ("edge_networking", "cloud_dns"),
}


def classify_asset_item(item: dict[str, Any]) -> tuple[str, str] | None:
    """Maps a Cloud Asset Inventory resource item to an active_stack token."""
    atype = str(item.get("assetType") or "")
    if atype == "compute.googleapis.com/UrlMap":
        loc = str(item.get("location") or "global").strip().lower()
        if loc and loc != "global":
            return ("edge_networking", "regional_alb")
        return ("edge_networking", "global_external_alb")
    return ASSET_TYPE_TO_STACK_KEY.get(atype)


def _normalize_stack_token(token: str) -> str:
    if token.startswith("cloudsql_"):
        return "cloudsql"
    if token == "global_alb":
        return "global_external_alb"
    if "cdn" in token:
        return "cloud_cdn"
    return token


def check_profile_drift(
    profile_name: str,
    project_id: str | None = None,
    profiles_root: Path | None = None,
) -> bool:
    """Compares declared active_stack tokens against live GCP resources."""
    spec = load_active_profile(
        profile_name, force_refresh=True, profiles_root=profiles_root
    )
    if not spec:
        raise ValueError(f"Profile '{profile_name}' not found.")
    contract = build_profile_drift_contract(spec)

    mapped_projects = list(
        dict.fromkeys(
            str(pid).strip()
            for pid in (contract.get("projects_by_role") or {}).values()
            if str(pid).strip()
        )
    )
    if project_id and project_id.strip():
        target_projects = [project_id.strip()]
    elif mapped_projects:
        target_projects = mapped_projects
    else:
        fallback = (
            os.getenv("TARGET_PROJECT_ID")
            or os.getenv("GOOGLE_CLOUD_PROJECT")
            or ""
        ).strip()
        target_projects = [fallback] if fallback else []

    if not target_projects:
        raise ValueError(
            "Target GCP project ID could not be resolved from profile or "
            "environment."
        )

    billing_project = (
        os.getenv("GOOGLE_CLOUD_PROJECT") or target_projects[0]
    ).strip()

    discovered: dict[str, set[str]] = {
        "compute": set(),
        "databases": set(),
        "caching_messaging": set(),
        "edge_networking": set(),
    }
    for proj in target_projects:
        raw = subprocess.check_output(
            gcloud_cmd(
                "asset",
                "search-all-resources",
                f"--scope=projects/{proj}",
                f"--billing-project={billing_project}",
                "--format=json",
                "--quiet",
            ),
            text=True,
        )
        assets = json.loads(raw)
        for item in assets:
            classified = classify_asset_item(item)
            if classified is not None:
                cat, token = classified
                discovered[cat].add(token)

    joined_targets = ", ".join(target_projects)
    prof_src = contract["profile_source"]
    print(
        f"Profile Drift Audit for '{profile_name}' ({prof_src}) "
        f"against '{joined_targets}':"
    )
    drift_found = False
    for cat in ("compute", "databases", "caching_messaging", "edge_networking"):
        declared_raw = set(contract["declared_active_stack"].get(cat) or [])
        declared_norm = {_normalize_stack_token(d) for d in declared_raw}
        live_set = discovered[cat]
        undeclared = sorted(live_set - declared_norm)
        missing_in_cloud = sorted(declared_norm - live_set)
        status = (
            "ALIGNED"
            if not (undeclared or missing_in_cloud)
            else "DRIFT_DETECTED"
        )
        if status != "ALIGNED":
            drift_found = True
        print(
            f"  [{cat}] status={status} | declared={sorted(declared_raw)} | "
            f"live={sorted(live_set)} | undeclared={undeclared} | "
            f"missing_live={missing_in_cloud}"
        )
    return not drift_found


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(
            "Usage: python -m deployment.check_profile_drift "
            "<profile-id> [project-id]"
        )
    proj_arg = sys.argv[2] if len(sys.argv) > 2 else None
    check_profile_drift(sys.argv[1], proj_arg)
