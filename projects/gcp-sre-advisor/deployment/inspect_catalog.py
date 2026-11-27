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

"""Readiness check across the context resolution cascade and MCP connectors."""

import json
import os
import subprocess
from collections.abc import Callable
from typing import Any

import requests
from app import config
from app.app_utils.profile_loader import list_available_profiles
from app.tools.mcp_registry import (
    _catalog_mcp_header_provider,
    _make_entry_header_provider,
    _normalize_catalog_mcp_endpoints,
    _observability_mcp_header_provider,
    get_configured_catalog_mcp_specs,
    get_configured_observability_mcp_specs,
)
from deployment.auth import gcloud_cmd, require_project_id


def _parse_mcp_rpc_response(
    resp: requests.Response, method: str
) -> dict[str, Any]:
    content_type = (resp.headers.get("Content-Type") or "").lower()
    raw_text = resp.text if isinstance(getattr(resp, "text", None), str) else ""
    payload: dict[str, Any] | None = None

    if "text/event-stream" in content_type or raw_text.lstrip().startswith(
        ("event:", "data:")
    ):
        for line in raw_text.splitlines():
            stripped = line.strip()
            if not stripped.startswith("data:"):
                continue
            chunk = stripped[5:].strip()
            if not chunk:
                continue
            candidate = json.loads(chunk)
            if isinstance(candidate, dict) and (
                "result" in candidate or "error" in candidate
            ):
                payload = candidate
        if payload is None:
            raise ValueError(
                f"No JSON-RPC message found in SSE stream for '{method}'."
            )
    else:
        parsed = resp.json()
        if not isinstance(parsed, dict):
            raise ValueError(f"Expected JSON-RPC object for '{method}'.")
        payload = parsed

    if "error" in payload and payload["error"]:
        err_obj = payload["error"]
        raise RuntimeError(f"MCP error on '{method}': {err_obj}")
    return payload


def _probe_streamable_mcp(
    raw_url: str,
    header_fn: Callable[[Any], dict[str, str]],
) -> dict[str, Any]:
    mcp_url, _ = _normalize_catalog_mcp_endpoints(raw_url)
    if not mcp_url:
        return {"configured": False, "tools": []}

    auth_headers = header_fn(None)
    headers = {
        **auth_headers,
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    init_resp = requests.post(
        mcp_url,
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "gcp-sre-advisor-cli",
                    "version": "1.0.0",
                },
            },
        },
        timeout=30,
    )
    init_resp.raise_for_status()
    init_payload = _parse_mcp_rpc_response(init_resp, "initialize")
    session_id = init_resp.headers.get("Mcp-Session-Id")
    if session_id:
        headers["Mcp-Session-Id"] = session_id

    notif_resp = requests.post(
        mcp_url,
        headers=headers,
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        timeout=15,
    )
    if notif_resp.status_code >= 400 and notif_resp.status_code not in (
        400,
        404,
        405,
    ):
        notif_resp.raise_for_status()

    list_resp = requests.post(
        mcp_url,
        headers=headers,
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        timeout=30,
    )
    list_resp.raise_for_status()
    payload = _parse_mcp_rpc_response(list_resp, "tools/list")
    tools = [
        str(item.get("name"))
        for item in (payload.get("result", {}).get("tools") or [])
        if isinstance(item, dict) and item.get("name")
    ]
    server_info = init_payload.get("result", {}).get("serverInfo") or {}
    return {
        "configured": True,
        "endpoint": mcp_url,
        "server_name": server_info.get("name", "unknown"),
        "tools": tools,
    }


def probe_catalog_mcp(raw_url: str) -> dict[str, Any]:
    """Probes an external application catalog MCP endpoint."""
    return _probe_streamable_mcp(raw_url, _catalog_mcp_header_provider)


def probe_observability_mcp(raw_url: str) -> dict[str, Any]:
    """Probes an external observability MCP endpoint."""
    return _probe_streamable_mcp(raw_url, _observability_mcp_header_provider)


def list_apphub_applications(
    project_id: str, region: str
) -> list[dict[str, str]]:
    """Lists registered Google Cloud App Hub applications in a region."""
    raw = subprocess.check_output(
        gcloud_cmd(
            "apphub",
            "applications",
            "list",
            f"--project={project_id}",
            f"--location={region}",
            "--format=json",
            "--quiet",
        ),
        text=True,
    )
    items = json.loads(raw or "[]")
    results: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        app_id = str(item.get("name") or "").rsplit("/", maxsplit=1)[-1]
        attrs = item.get("attributes") or {}
        crit = (attrs.get("criticality") or {}).get("type", "UNSPECIFIED")
        env_type = (attrs.get("environment") or {}).get("type", "UNSPECIFIED")
        results.append(
            {
                "application_id": app_id,
                "display_name": str(item.get("displayName") or app_id),
                "criticality": str(crit),
                "environment": str(env_type),
            }
        )
    return results


def inspect_catalog(
    project_id: str | None = None, region: str = ""
) -> dict[str, Any]:
    """Inspects live catalogs, App Hub, Workload Profiles, and MCP servers."""
    proj = require_project_id(project_id)
    resolved_region = (
        region
        or os.getenv("TARGET_REGION")
        or config.TARGET_REGION
        or "us-central1"
    ).strip()
    profiles = list_available_profiles(force_refresh=True)
    apphub_apps = list_apphub_applications(proj, resolved_region)
    raw_mcp_url = (
        os.getenv("CATALOG_MCP_URL") or config.CATALOG_MCP_URL or ""
    ).strip()
    raw_cat_multi = (
        os.getenv("CATALOG_MCP_SERVERS_JSON")
        or config.CATALOG_MCP_SERVERS_JSON
        or ""
    ).strip()
    if raw_cat_multi:
        cat_specs = get_configured_catalog_mcp_specs()
        cat_probes = [
            {
                "name": s["name"],
                "priority": s["priority"],
                **_probe_streamable_mcp(
                    s["raw_url"], _make_entry_header_provider(s, "CATALOG_MCP")
                ),
            }
            for s in cat_specs
        ]
        mcp_status: dict[str, Any] = {
            "configured": bool(cat_probes),
            "servers": cat_probes,
            "endpoint": cat_probes[0]["endpoint"] if cat_probes else "",
            "tools": [t for item in cat_probes for t in item["tools"]],
        }
    else:
        mcp_status = (
            probe_catalog_mcp(raw_mcp_url)
            if raw_mcp_url
            else {"configured": False, "tools": []}
        )

    raw_obs_url = (
        os.getenv("OBSERVABILITY_MCP_URL") or config.OBSERVABILITY_MCP_URL or ""
    ).strip()
    raw_obs_multi = (
        os.getenv("OBSERVABILITY_MCP_SERVERS_JSON")
        or config.OBSERVABILITY_MCP_SERVERS_JSON
        or ""
    ).strip()
    if raw_obs_multi:
        obs_specs = get_configured_observability_mcp_specs()
        obs_probes = [
            {
                "name": s["name"],
                "priority": s["priority"],
                "pillars": list(s["pillars"]) if s["pillars"] else ["all"],
                **_probe_streamable_mcp(
                    s["raw_url"],
                    _make_entry_header_provider(s, "OBSERVABILITY_MCP"),
                ),
            }
            for s in obs_specs
        ]
        obs_status: dict[str, Any] = {
            "configured": bool(obs_probes),
            "servers": obs_probes,
            "endpoint": obs_probes[0]["endpoint"] if obs_probes else "",
            "tools": [t for item in obs_probes for t in item["tools"]],
        }
    else:
        obs_status = (
            probe_observability_mcp(raw_obs_url)
            if raw_obs_url
            else {"configured": False, "tools": []}
        )

    runtime_sa = (
        os.getenv("AGENT_RUNTIME_SA")
        or f"sa-sre-advisor-reader@{proj}.iam.gserviceaccount.com"
    ).strip()

    print("Automatic Context Resolution Cascade:")
    if mcp_status["configured"]:
        mcp_ep = mcp_status["endpoint"]
        mcp_tools = mcp_status["tools"]
        print(
            "  [Priority 1] External Catalog MCP"
            f"                                : CONNECTED ({mcp_ep}) "
            f"tools={mcp_tools}"
        )
    else:
        print(
            "  [Priority 1] External Catalog MCP"
            "                                : NOT CONFIGURED "
            "(set CATALOG_MCP_URL to enable)"
        )
    apphub_ids = [a["application_id"] for a in apphub_apps]
    print(
        "  [Priority 1] Google Cloud App Hub"
        f"                                : {len(apphub_ids)} registered in "
        f"{resolved_region} -> {apphub_ids}"
    )
    prof_ids = [p["profile_id"] for p in profiles]
    gcs_src = (
        os.getenv("PROFILES_GCS_URI") or config.PROFILES_GCS_URI or "local"
    )
    print(
        "  [Priority 2] Workload Profiles"
        f"                                   : {len(prof_ids)} available "
        f"({gcs_src}) -> {prof_ids}"
    )
    print(
        "  [Priority 3] Accessible GCP Projects via Service Account / OAuth : "
        f"READY (project={proj}, region={resolved_region}, "
        f"runtime_sa={runtime_sa})"
    )
    if obs_status["configured"]:
        obs_ep = obs_status["endpoint"]
        obs_tools = obs_status["tools"]
        print(
            "  [Telemetry]  External Observability MCP"
            f"                          : CONNECTED ({obs_ep}) "
            f"tools={obs_tools}"
        )
    else:
        print(
            "  [Telemetry]  External Observability MCP"
            "                          : NOT CONFIGURED "
            "(set OBSERVABILITY_MCP_URL to enable Datadog, Dynatrace, "
            "Grafana, or Zabbix)"
        )

    return {
        "project_id": proj,
        "region": resolved_region,
        "external_catalog_mcp": mcp_status,
        "external_observability_mcp": obs_status,
        "apphub_applications": apphub_apps,
        "workload_profiles": prof_ids,
        "live_project_discovery_ready": True,
        "runtime_service_account": runtime_sa,
    }
