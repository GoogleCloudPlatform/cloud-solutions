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

"""Session context cascade activation and baseline lookup tools."""

from typing import Any

from google.adk.tools.tool_context import ToolContext

from .. import config
from ..app_utils.profile_loader import (
    build_profile_drift_contract,
    list_available_profiles,
    load_active_profile,
    resolve_active_target_metadata,
)
from .mcp_registry import get_configured_catalog_mcp_specs


def _clear_session_targets(state: Any) -> None:
    state["active_workload_profile"] = ""
    state["zero_profile_project"] = ""
    state["zero_profile_tier"] = ""
    state["zero_profile_region"] = ""
    state["zero_profile_zone"] = ""
    state["live_catalog_app_id"] = ""
    state["live_catalog_context"] = {}


def list_workload_profiles(tool_context: ToolContext) -> dict[str, Any]:
    """Lists registered Workload Profiles and active session context."""
    meta = resolve_active_target_metadata(tool_context)
    mode = meta["mode"]
    if mode == "discovery":
        primary_proj = meta["primary_project_id"]
        active_id = f"discovery:{primary_proj}"
    elif mode == "catalog":
        app_id = meta["application_id"]
        active_id = f"catalog:{app_id}"
    elif mode == "profile":
        active_id = meta["profile_id"]
    else:
        active_id = (
            tool_context.state.get("active_workload_profile")
            or config.WORKLOAD_PROFILE_NAME
            or "UNSELECTED"
        )

    profiles = list_available_profiles()
    cat_specs = get_configured_catalog_mcp_specs()
    ext_mcp_enabled = bool(cat_specs)
    provider = (
        ", ".join(s["name"] for s in cat_specs)
        if ext_mcp_enabled
        else (config.CATALOG_MCP_PROVIDER_NAME or "google_cloud_apphub")
    )
    return {
        "active_context_source": meta["context_source"],
        "active_profile_id": active_id,
        "profiles_gcs_uri": config.PROFILES_GCS_URI or "local",
        "supports_live_project_discovery": True,
        "live_catalog_integration": {
            "apphub_supported": True,
            "external_catalog_mcp_enabled": ext_mcp_enabled,
            "catalog_provider": provider,
        },
        "available_profiles": profiles,
    }


def select_workload_profile(
    profile_id: str, tool_context: ToolContext
) -> dict[str, Any]:
    """Activates a declarative Workload Profile for the current session."""
    cleaned = (profile_id or "").strip().lower()
    if not cleaned:
        return {
            "switched": False,
            "error": "A non-empty profile_id is required.",
            "available_profile_ids": [
                p["profile_id"] for p in list_available_profiles()
            ],
        }

    catalog = list_available_profiles()
    available_map = {p["profile_id"].lower(): p["profile_id"] for p in catalog}

    if cleaned not in available_map:
        matches = [
            p["profile_id"]
            for p in catalog
            if cleaned in p["profile_id"].lower()
            or cleaned in str(p.get("display_name", "")).lower()
        ]
        if len(matches) == 1:
            cleaned = matches[0].lower()

    if cleaned not in available_map:
        return {
            "switched": False,
            "error": f"Profile '{profile_id}' not found.",
            "available_profile_ids": sorted(available_map.values()),
        }

    canonical_id = available_map[cleaned]
    spec = load_active_profile(canonical_id, force_refresh=True)
    _clear_session_targets(tool_context.state)
    tool_context.state["active_workload_profile"] = canonical_id
    return {
        "switched": True,
        "context_source": "workload_profile",
        "active_profile_id": canonical_id,
        "loaded_from": spec.get("_profile_source", "local"),
        "drift_baseline": build_profile_drift_contract(spec),
    }


def _normalize_gcp_project_id(raw_value: str) -> str:
    cleaned = (raw_value or "").strip().strip("/")
    if not cleaned:
        return ""
    if "/projects/" in cleaned:
        cleaned = cleaned.split("/projects/", 1)[1]
    elif cleaned.startswith("projects/"):
        cleaned = cleaned[len("projects/") :]
    return cleaned.split("/", 1)[0].strip()


def _normalize_apphub_app_id(raw_value: str) -> str:
    cleaned = (raw_value or "").strip().strip("/")
    if not cleaned:
        return ""
    if "/applications/" in cleaned:
        return cleaned.split("/applications/", 1)[1].split("/", 1)[0].strip()
    return cleaned.split("/")[-1].strip()


def activate_zero_profile_discovery(
    project_id: str,
    environment_tier: str = "prod",
    region: str = "",
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Activates live discovery mode for an accessible Google Cloud project."""
    cleaned_proj = _normalize_gcp_project_id(project_id)
    if not cleaned_proj:
        return {
            "zero_profile_discovery_active": False,
            "error": (
                "A non-empty Google Cloud project_id is required for live "
                "discovery mode."
            ),
        }

    cleaned_tier = (environment_tier or "prod").strip().lower()
    explicit_region = (region or "").strip()
    cleaned_region = explicit_region or config.TARGET_REGION or "us-central1"
    cleaned_zone = (
        f"{cleaned_region}-a"
        if explicit_region
        and not config.TARGET_ZONE.startswith(f"{cleaned_region}-")
        else (config.TARGET_ZONE or f"{cleaned_region}-a")
    )

    if tool_context is not None:
        _clear_session_targets(tool_context.state)
        tool_context.state["zero_profile_project"] = cleaned_proj
        tool_context.state["zero_profile_tier"] = cleaned_tier
        tool_context.state["zero_profile_region"] = cleaned_region
        tool_context.state["zero_profile_zone"] = cleaned_zone

    return {
        "zero_profile_discovery_active": True,
        "context_source": "live_project_discovery",
        "target_project_id": cleaned_proj,
        "environment_tier": cleaned_tier,
        "primary_region": cleaned_region,
        "primary_zone": cleaned_zone,
    }


def activate_live_catalog_application(
    application_id: str,
    project_id: str = "",
    catalog_source: str = "",
    environment_tier: str = "prod",
    region: str = "",
    criticality: str = "",
    display_name: str = "",
    owner_team: str = "",
    apphub_application_id: str = "",
    slo_summary: str = "",
    finops_labels: str = "",
    delivery_model_summary: str = "",
    accepted_risks_summary: str = "",
    architecture_notes: str = "",
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Activates live catalog context from an MCP catalog or App Hub."""
    cleaned_app = _normalize_apphub_app_id(application_id)
    if not cleaned_app:
        return {
            "live_catalog_active": False,
            "error": (
                "A non-empty application_id is required for live catalog mode."
            ),
        }

    raw_tokens = (project_id or "").replace(";", ",").split(",")
    project_ids = list(
        dict.fromkeys(
            norm
            for tok in raw_tokens
            if (norm := _normalize_gcp_project_id(tok))
        )
    )
    if (
        not project_ids
        and not config.CATALOG_MCP_URL
        and not (project_id or "").strip()
    ):
        fallback_proj = _normalize_gcp_project_id(
            config.TARGET_PROJECT_ID or config.RUNTIME_PROJECT_ID
        )
        if fallback_proj:
            project_ids = [fallback_proj]

    if not project_ids:
        return {
            "live_catalog_active": False,
            "error": (
                "A non-empty Google Cloud project_id is required. Query the "
                "live catalog MCP tools first to resolve the mapped "
                "project_id, or ask the user for the App Hub host project."
            ),
        }

    cleaned_tier = (environment_tier or "prod").strip().lower()
    explicit_region = (region or "").strip()
    cleaned_region = explicit_region or config.TARGET_REGION or "us-central1"
    cleaned_zone = (
        f"{cleaned_region}-a"
        if explicit_region
        and not config.TARGET_ZONE.startswith(f"{cleaned_region}-")
        else (config.TARGET_ZONE or f"{cleaned_region}-a")
    )
    resolved_provider = (
        (catalog_source or "").strip()
        or config.CATALOG_MCP_PROVIDER_NAME
        or (
            "external_catalog_mcp"
            if config.CATALOG_MCP_URL
            else "google_cloud_apphub"
        )
    )
    resolved_apphub = (
        _normalize_apphub_app_id(apphub_application_id) or cleaned_app
    )

    catalog_ctx = {
        "application_id": cleaned_app,
        "display_name": (display_name or "").strip() or cleaned_app,
        "catalog_source": resolved_provider,
        "project_ids": project_ids,
        "primary_project_id": project_ids[0],
        "region": cleaned_region,
        "zone": cleaned_zone,
        "environment_tier": cleaned_tier,
        "criticality": (criticality or "mission-critical").strip(),
        "owner_team": (owner_team or "").strip(),
        "apphub_application_id": resolved_apphub,
        "slo_summary": (slo_summary or "").strip(),
        "finops_labels": (finops_labels or "").strip(),
        "delivery_model_summary": (delivery_model_summary or "").strip(),
        "accepted_risks_summary": (accepted_risks_summary or "").strip(),
        "architecture_notes": (architecture_notes or "").strip(),
    }

    if tool_context is not None:
        _clear_session_targets(tool_context.state)
        tool_context.state["live_catalog_app_id"] = cleaned_app
        tool_context.state["live_catalog_context"] = catalog_ctx

    return {
        "live_catalog_active": True,
        "context_source": "live_catalog",
        "application_id": cleaned_app,
        "catalog_source": resolved_provider,
        "apphub_application_id": resolved_apphub,
        "project_ids": project_ids,
        "primary_project_id": project_ids[0],
        "environment_tier": cleaned_tier,
        "primary_region": cleaned_region,
        "primary_zone": cleaned_zone,
    }


def get_active_profile_drift_baseline(
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Returns the declared baseline of the active Workload Profile."""
    current = (
        tool_context.state.get("active_workload_profile")
        or config.WORKLOAD_PROFILE_NAME
    )
    if not current:
        return {
            "error": (
                "No declarative Workload Profile is selected in this session."
            ),
            "available_profile_ids": [
                p["profile_id"] for p in list_available_profiles()
            ],
        }
    spec = load_active_profile(current)
    if not spec:
        return {
            "error": f"Profile '{current}' could not be loaded.",
            "available_profile_ids": [
                p["profile_id"] for p in list_available_profiles()
            ],
        }
    return build_profile_drift_contract(spec)
