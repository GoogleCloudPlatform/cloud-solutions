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

"""Generates draft Workload Profiles from Cloud Asset Inventory and IaC."""

import json
import subprocess
from datetime import date
from pathlib import Path

import yaml
from app.app_utils.profile_loader import PROFILES_ROOT
from deployment.auth import gcloud_cmd
from deployment.check_profile_drift import classify_asset_item


def detect_delivery_tooling(repo_dir: str | None) -> dict[str, str]:
    """Detects declarative IaC tooling inside an optional repository path."""
    default_model = {
        "delivery_mode": "standard_operational_runbook",
        "tooling": "gcloud_cli, cloud_console",
        "remediation_format": (
            "Step-by-step operational remediation aligned with workload "
            "governance"
        ),
    }
    if not repo_dir:
        return default_model
    root = Path(repo_dir)
    if not root.exists():
        return default_model
    found: list[str] = []
    if any(root.rglob("terragrunt.hcl")):
        found.append("terragrunt")
    elif any(root.rglob("*.tf")):
        found.append("terraform")
    if any(root.rglob("Pulumi.yaml")):
        found.append("pulumi")
    if any(root.rglob("Chart.yaml")):
        found.append("helm")
    if any(root.rglob("kustomization.yaml")):
        found.append("kustomize")
    if not found:
        return default_model
    tools_joined = ", ".join(found)
    return {
        "delivery_mode": "declarative_iac",
        "tooling": tools_joined,
        "remediation_format": (
            f"Declarative configuration updates for {tools_joined} with "
            "read-only verification commands"
        ),
    }


def bootstrap_profile(
    project_id: str,
    profile_slug: str,
    tier: str = "prod",
    iac_dir: str = "",
    region: str = "us-central1",
    zone: str = "",
    output_root: Path | None = None,
) -> Path:
    """Bootstraps a draft profile.yaml and context.md from Cloud Assets."""
    cleaned_project = project_id.strip()
    cleaned_slug = profile_slug.strip()
    if not cleaned_project or not cleaned_slug:
        raise ValueError("Both project_id and profile_slug must be non-empty.")

    resolved_region = (region or "us-central1").strip()
    resolved_zone = (zone or f"{resolved_region}-a").strip()

    raw = subprocess.check_output(
        gcloud_cmd(
            "asset",
            "search-all-resources",
            f"--scope=projects/{cleaned_project}",
            f"--billing-project={cleaned_project}",
            "--format=json",
            "--quiet",
        ),
        text=True,
    )
    assets = json.loads(raw)

    stack: dict[str, set[str]] = {
        "compute": set(),
        "databases": set(),
        "caching_messaging": set(),
        "edge_networking": set(),
    }
    discovered_labels: set[str] = set()
    sample_names: list[str] = []

    for item in assets:
        atype = item.get("assetType", "")
        dname = item.get("displayName") or item.get("name", "").split("/")[-1]
        if dname and len(sample_names) < 12:
            short_type = atype.rsplit("/", maxsplit=1)[-1]
            sample_names.append(f"{short_type}:{dname}")
        for k in item.get("labels") or {}:
            if not k.startswith("goog-"):
                discovered_labels.add(k)
        classified = classify_asset_item(item)
        if classified is not None:
            cat, token = classified
            if token == "cloudsql":
                attrs = item.get("additionalAttributes") or {}
                db_ver = str(attrs.get("databaseVersion") or "").upper()
                if "MYSQL" in db_ver:
                    token = "cloudsql_mysql"
                elif "SQLSERVER" in db_ver:
                    token = "cloudsql_sqlserver"
                else:
                    token = "cloudsql_postgres"
            stack[cat].add(token)

    base_root = output_root or PROFILES_ROOT
    out_dir = base_root / cleaned_slug
    out_dir.mkdir(parents=True, exist_ok=True)

    is_prod = tier.strip().lower() == "prod"
    profile_doc = {
        "schema_version": "1.0",
        "curated_by": "Cloud Architecture Team",
        "last_reviewed": date.today().isoformat(),
        "workload_identity": {
            "id": cleaned_slug,
            "display_name": f"{cleaned_slug} (Draft)",
            "business_domain": "Pending domain confirmation",
            "criticality": "mission-critical" if is_prod else "standard",
            "criticality_summary": "Pending business impact confirmation",
            "peak_windows": "Business hours",
        },
        "environment_and_projects": {
            "environment_tier": tier,
            "primary_region": resolved_region,
            "primary_zone": resolved_zone,
            "projects_by_role": {"primary": cleaned_project},
        },
        "architecture_archetype": "auto-discovered",
        "active_stack": {k: sorted(v) for k, v in stack.items()},
        "network_and_protocol_constraints": {
            "egress_static_ips": [],
            "special_protocols": [],
        },
        "finops_and_cost_controls": {
            "required_labels": sorted(discovered_labels)[:6],
            "nonprod_cost_saving_policy": (
                "Standard resource utilization review"
            ),
        },
        "slo_and_resilience_targets": {
            "availability_slo_pct": 99.9 if is_prod else 99.0,
            "latency_p95_ms": 500,
            "rpo_minutes": 15 if is_prod else 60,
            "rto_minutes": 60 if is_prod else 240,
            "critical_business_windows": "Business hours",
        },
        "external_boundaries": {
            "identity_providers": [],
            "edge_and_dns": [],
            "external_apis_or_clouds": [],
        },
        "accepted_exceptions": [],
        "change_delivery_model": detect_delivery_tooling(iac_dir or None),
    }

    (out_dir / "profile.yaml").write_text(
        yaml.safe_dump(profile_doc, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    sample_list = ", ".join(sample_names) if sample_names else "none"
    context_md = (
        "# Workload architecture context\n\n"
        "1.  **Business role and user impact:**\n"
        "    Initial draft derived from Cloud Asset Inventory for project "
        f"`{cleaned_project}`. Replace with business criticality and user "
        "impact details.\n\n"
        "1.  **Discovered inventory summary:**\n"
        f"    Sample resources identified during discovery: {sample_list}.\n\n"
        "1.  **Architectural decisions and review notes:**\n"
        "    Document critical request flows, external integration "
        "boundaries, and any approved risk exceptions.\n"
    )
    (out_dir / "context.md").write_text(context_md, encoding="utf-8")
    print(f"Draft profile written to {out_dir}")
    return out_dir
