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

"""Schema validator for declarative Workload Profile YAML bundles."""

import sys
from pathlib import Path
from typing import Any

from app.app_utils.profile_loader import (
    PROFILES_ROOT,
    get_enabled_mcp_keys_for_profile,
    load_active_profile,
)

REQUIRED_SECTIONS = (
    "workload_identity",
    "environment_and_projects",
    "architecture_archetype",
    "active_stack",
    "network_and_protocol_constraints",
    "finops_and_cost_controls",
    "slo_and_resilience_targets",
    "external_boundaries",
    "accepted_exceptions",
    "change_delivery_model",
)

STACK_CATEGORIES = (
    "compute",
    "databases",
    "caching_messaging",
    "edge_networking",
)


def validate_profile(
    profile_name: str, profiles_root: Path | None = None
) -> dict[str, Any]:
    """Validates a Workload Profile against the ten-section schema."""
    root_dir = profiles_root or PROFILES_ROOT
    profile_dir = root_dir / profile_name
    if not profile_dir.exists():
        available = (
            sorted(
                p.name
                for p in root_dir.iterdir()
                if p.is_dir() and not p.name.startswith("_")
            )
            if root_dir.exists()
            else []
        )
        raise FileNotFoundError(
            f"Profile '{profile_name}' not found in {root_dir}. "
            f"Available: {available}"
        )

    profile = load_active_profile(
        profile_name, force_refresh=True, profiles_root=root_dir
    )
    if not profile:
        raise ValueError(
            f"Profile '{profile_name}' has an empty or missing profile.yaml."
        )

    missing = [
        section for section in REQUIRED_SECTIONS if section not in profile
    ]
    if missing:
        raise ValueError(
            f"Profile '{profile_name}' is missing required sections: {missing}"
        )

    errors: list[str] = []

    if "gitops_governance" in profile:
        errors.append(
            "legacy section 'gitops_governance' is not supported; "
            "use 'change_delivery_model'"
        )

    ident = profile.get("workload_identity")
    if not isinstance(ident, dict):
        errors.append("workload_identity must be a mapping")
    else:
        for req_key in ("id", "display_name", "business_domain", "criticality"):
            if (
                not isinstance(ident.get(req_key), str)
                or not ident.get(req_key, "").strip()
            ):
                errors.append(
                    f"workload_identity.{req_key} must be a non-empty string"
                )

    env_proj = profile.get("environment_and_projects")
    if not isinstance(env_proj, dict):
        errors.append("environment_and_projects must be a mapping")
    else:
        for req_key in ("environment_tier", "primary_region", "primary_zone"):
            if (
                not isinstance(env_proj.get(req_key), str)
                or not env_proj.get(req_key, "").strip()
            ):
                errors.append(
                    f"environment_and_projects.{req_key} must be a "
                    "non-empty string"
                )
        projects_map = env_proj.get("projects_by_role")
        if not isinstance(projects_map, dict) or not projects_map:
            errors.append(
                "environment_and_projects.projects_by_role must be a "
                "non-empty mapping"
            )
        else:
            for role_key, proj_val in projects_map.items():
                if (
                    not str(role_key).strip()
                    or not isinstance(proj_val, str)
                    or not proj_val.strip()
                ):
                    errors.append(
                        f"environment_and_projects.projects_by_role"
                        f"['{role_key}'] must be a non-empty project ID string"
                    )

    archetype = profile.get("architecture_archetype")
    if not isinstance(archetype, str) or not archetype.strip():
        errors.append("architecture_archetype must be a non-empty string")

    stack = profile.get("active_stack")
    if not isinstance(stack, dict):
        errors.append("active_stack must be a mapping")
    else:
        for cat in STACK_CATEGORIES:
            items = stack.get(cat)
            if not isinstance(items, list) or any(
                not isinstance(tok, str) or not tok.strip() for tok in items
            ):
                errors.append(
                    f"active_stack.{cat} must be a list of non-empty strings"
                )

    net_proto = profile.get("network_and_protocol_constraints")
    if not isinstance(net_proto, dict):
        errors.append("network_and_protocol_constraints must be a mapping")
    else:
        for list_key in ("egress_static_ips", "special_protocols"):
            if list_key in net_proto:
                val = net_proto.get(list_key)
                if not isinstance(val, list) or any(
                    not isinstance(x, str) for x in val
                ):
                    errors.append(
                        f"network_and_protocol_constraints.{list_key} "
                        "must be a list of strings"
                    )

    finops = profile.get("finops_and_cost_controls")
    if not isinstance(finops, dict):
        errors.append("finops_and_cost_controls must be a mapping")
    elif "required_labels" in finops:
        labels = finops.get("required_labels")
        if not isinstance(labels, list) or any(
            not isinstance(lbl, str) or not lbl.strip() for lbl in labels
        ):
            errors.append(
                "finops_and_cost_controls.required_labels must be a list of "
                "non-empty strings"
            )

    slos = profile.get("slo_and_resilience_targets")
    if not isinstance(slos, dict):
        errors.append("slo_and_resilience_targets must be a mapping")
    else:
        for req_key in (
            "availability_slo_pct",
            "latency_p95_ms",
            "rpo_minutes",
            "rto_minutes",
        ):
            raw_num = slos.get(req_key)
            if isinstance(raw_num, bool) or not isinstance(
                raw_num, int | float
            ):
                errors.append(
                    f"slo_and_resilience_targets.{req_key} must be a number"
                )
            elif req_key == "availability_slo_pct" and not (
                0 < float(raw_num) <= 100
            ):
                errors.append(
                    "slo_and_resilience_targets.availability_slo_pct "
                    "must be between 0 and 100"
                )
            elif req_key == "latency_p95_ms" and float(raw_num) <= 0:
                errors.append(
                    "slo_and_resilience_targets.latency_p95_ms "
                    "must be greater than 0"
                )
            elif (
                req_key in ("rpo_minutes", "rto_minutes") and float(raw_num) < 0
            ):
                errors.append(
                    f"slo_and_resilience_targets.{req_key} "
                    "must be non-negative"
                )

    ext_bounds = profile.get("external_boundaries")
    if not isinstance(ext_bounds, dict):
        errors.append("external_boundaries must be a mapping")
    else:
        for list_key in (
            "identity_providers",
            "edge_and_dns",
            "external_apis_or_clouds",
        ):
            if list_key in ext_bounds:
                val = ext_bounds.get(list_key)
                if not isinstance(val, list) or any(
                    not isinstance(x, str) for x in val
                ):
                    errors.append(
                        f"external_boundaries.{list_key} "
                        "must be a list of strings"
                    )

    exceptions = profile.get("accepted_exceptions")
    if not isinstance(exceptions, list):
        errors.append("accepted_exceptions must be a list")
    else:
        for idx, exc_item in enumerate(exceptions):
            if not isinstance(exc_item, dict):
                errors.append(f"accepted_exceptions[{idx}] must be a mapping")
                continue
            for exc_key in ("id", "pillar", "summary", "rationale"):
                if (
                    not isinstance(exc_item.get(exc_key), str)
                    or not exc_item.get(exc_key, "").strip()
                ):
                    errors.append(
                        f"accepted_exceptions[{idx}].{exc_key} "
                        "must be a non-empty string"
                    )

    delivery = profile.get("change_delivery_model")
    if not isinstance(delivery, dict):
        errors.append("change_delivery_model must be a mapping")
    else:
        for req_key in ("delivery_mode", "tooling", "remediation_format"):
            if (
                not isinstance(delivery.get(req_key), str)
                or not delivery.get(req_key, "").strip()
            ):
                errors.append(
                    f"change_delivery_model.{req_key} "
                    "must be a non-empty string"
                )

    if errors:
        joined_errs = "; ".join(errors)
        raise ValueError(
            f"Profile '{profile_name}' failed schema validation: {joined_errs}"
        )

    mcps = sorted(get_enabled_mcp_keys_for_profile(profile))
    exceptions = profile.get("accepted_exceptions") or []

    w_name = ident.get("display_name")
    e_tier = env_proj.get("environment_tier")
    mapped_cnt = len(env_proj.get("projects_by_role") or {})
    mcps_str = ", ".join(mcps)
    print(f"Profile validated : {profile_name}")
    print(f"Workload name     : {w_name}")
    print(f"Environment tier  : {e_tier}")
    print(f"Projects mapped   : {mapped_cnt}")
    print(f"Accepted risks    : {len(exceptions)}")
    print(f"Enabled MCPs      : {mcps_str}")
    return profile


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "_sample"
    validate_profile(target)
