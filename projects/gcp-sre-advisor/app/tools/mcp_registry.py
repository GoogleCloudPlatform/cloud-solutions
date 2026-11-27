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

"""MCP endpoint catalog, authentication providers, and toolset builders."""

import base64
import json
import logging
import os
import subprocess
import threading
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

import google.auth
import requests
from google.adk.tools.mcp_tool.mcp_session_manager import (
    StreamableHTTPConnectionParams,
)
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2 import id_token

from .. import config
from ..app_utils.profile_loader import (
    get_enabled_mcp_keys_for_profile,
    load_active_profile,
)

logger = logging.getLogger(__name__)

MANAGED_GCP_MCP_CATALOG: dict[str, dict[str, Any]] = {
    "bigquery": {
        "url": "https://bigquery.googleapis.com/mcp",
        "read_only_tools": [
            "list_dataset_ids",
            "get_dataset_info",
            "list_table_ids",
            "get_table_info",
            "execute_sql_readonly",
            "get_query_results",
            "get_job",
        ],
    },
    "pubsub": {
        "url": "https://pubsub.googleapis.com/mcp",
        "read_only_tools": [
            "get_topic",
            "list_topics",
            "get_subscription",
            "list_subscriptions",
            "get_snapshot",
            "list_snapshots",
        ],
    },
    "logging": {
        "url": "https://logging.googleapis.com/mcp",
        "read_only_tools": [
            "list_log_entries",
            "list_log_names",
            "get_bucket",
            "list_buckets",
            "get_view",
            "list_views",
        ],
    },
    "monitoring": {
        "url": "https://monitoring.googleapis.com/mcp",
        "read_only_tools": [
            "list_timeseries",
            "query_range",
            "get_alert_policy",
            "list_alert_policies",
            "get_alert",
            "list_alerts",
            "get_dashboard",
            "list_dashboards",
            "list_metric_descriptors",
        ],
    },
    "sqladmin": {
        "url": "https://sqladmin.googleapis.com/mcp/readonly",
        "read_only_tools": [
            "list_instances",
            "get_instance",
            "execute_sql_readonly",
            "list_users",
            "get_operation",
            "postgres_upgrade_precheck",
        ],
    },
    "compute": {
        "url": "https://compute.googleapis.com/mcp",
        "read_only_tools": [
            "list_instances",
            "get_instance_basic_info",
            "list_instance_group_managers",
            "list_managed_instances",
            "list_disks",
            "get_disk_basic_info",
            "list_machine_types",
            "list_commitments",
        ],
    },
    "storage": {
        "url": "https://storage.googleapis.com/storage/mcp",
        "read_only_tools": [
            "list_buckets",
            "get_bucket_metadata",
            "list_objects",
            "get_object_metadata",
        ],
    },
    "resourcemanager": {
        "url": "https://cloudresourcemanager.googleapis.com/mcp",
        "read_only_tools": [
            "search_projects",
        ],
    },
    "iam": {
        "url": "https://iam.googleapis.com/mcp",
        "read_only_tools": [
            "get_deny_policy",
            "get_deny_policy_status",
            "list_deny_policies",
            "list_roles",
            "get_role",
        ],
    },
    "orgpolicy": {
        "url": "https://orgpolicy.googleapis.com/mcp",
        "read_only_tools": [
            "ListConstraints",
            "ListCustomConstraints",
            "GetCustomConstraint",
            "ListPolicies",
            "GetPolicy",
            "GetEffectivePolicy",
        ],
    },
    "cloudrun": {
        "url": "https://run.googleapis.com/mcp",
        "read_only_tools": [
            "list_services",
            "get_service",
        ],
    },
    "cloudtrace": {
        "url": "https://cloudtrace.googleapis.com/mcp",
        "read_only_tools": [
            "list_traces",
            "get_trace",
        ],
    },
    "gcloud_cli": {
        "url": "https://cloudcli.googleapis.com/mcp",
        "read_only_tools": [
            "run_gcloud_command",
        ],
    },
    "developerknowledge": {
        "url": "https://developerknowledge.googleapis.com/mcp",
        "read_only_tools": None,
    },
    "discoveryengine": {
        "url": "https://discoveryengine.googleapis.com/mcp",
        "read_only_tools": [
            "search",
            "conversational_search",
            "list_engines",
        ],
    },
    "cloudasset": {
        "url": "https://cloudasset.googleapis.com/mcp",
        "read_only_tools": [
            "list_assets",
            "analyze_iam_policy",
            "get_iam_policy_analysis_status",
        ],
    },
}

_AUTH_LOCK = threading.Lock()
_ADC_CREDS: Any = None
_ADC_DEFAULT_PROJECT: str = ""
_OIDC_TOKEN_CACHE: dict[str, tuple[float, str]] = {}
_SECRET_VALUE_CACHE: dict[str, tuple[float, str]] = {}


def clear_auth_caches() -> None:
    global _ADC_CREDS, _ADC_DEFAULT_PROJECT
    with _AUTH_LOCK:
        _ADC_CREDS = None
        _ADC_DEFAULT_PROJECT = ""
        _OIDC_TOKEN_CACHE.clear()
        _SECRET_VALUE_CACHE.clear()


def _normalize_toolbox_endpoints(raw_url: str) -> tuple[str, str]:
    trimmed = (raw_url or "").strip().rstrip("/")
    if not trimmed:
        return "", ""
    base = trimmed.removesuffix("/mcp").rstrip("/")
    parsed = urlsplit(base)
    audience = (
        f"{parsed.scheme}://{parsed.netloc}"
        if parsed.scheme and parsed.netloc
        else base
    )
    return f"{base}/mcp", audience


def _normalize_catalog_mcp_endpoints(raw_url: str) -> tuple[str, str]:
    trimmed = (raw_url or "").strip().rstrip("/")
    if not trimmed:
        return "", ""
    parsed = urlsplit(trimmed)
    audience = (
        f"{parsed.scheme}://{parsed.netloc}"
        if parsed.scheme and parsed.netloc
        else trimmed
    )
    if parsed.path in ("", "/"):
        return f"{trimmed}/mcp", audience
    return trimmed, audience


def _creds_need_refresh(creds: Any) -> bool:
    if not getattr(creds, "token", None):
        return True
    if getattr(creds, "expired", False):
        return True
    expiry = getattr(creds, "expiry", None)
    if isinstance(expiry, datetime):
        now_utc = datetime.now(UTC)
        exp_utc = expiry if expiry.tzinfo else expiry.replace(tzinfo=UTC)
        if exp_utc <= now_utc + timedelta(seconds=60):
            return True
    return False


def _get_cached_adc_creds_and_project() -> tuple[Any, str]:
    global _ADC_CREDS, _ADC_DEFAULT_PROJECT
    with _AUTH_LOCK:
        if _ADC_CREDS is None:
            _ADC_CREDS, default_proj = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            _ADC_DEFAULT_PROJECT = (default_proj or "").strip()
        if _creds_need_refresh(_ADC_CREDS):
            _ADC_CREDS.refresh(Request())
        return _ADC_CREDS, _ADC_DEFAULT_PROJECT


def _get_cached_adc_token_and_project() -> tuple[str, str]:
    creds, default_proj = _get_cached_adc_creds_and_project()
    return str(creds.token), default_proj


def _jwt_monotonic_expiry(
    token: str, default_ttl_seconds: float = 3000.0
) -> float:
    now_mono = time.monotonic()
    parts = token.split(".")
    if len(parts) != 3:
        return now_mono + default_ttl_seconds
    try:
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded))
        exp = float(claims["exp"])
        ttl = max(0.0, exp - time.time())
        return now_mono + ttl
    except (KeyError, TypeError, ValueError):
        return now_mono + default_ttl_seconds


def resolve_delegated_user_oauth_token(
    readonly_context: Any = None,
) -> str | None:
    if readonly_context is None:
        return None

    auth_id = config.DELEGATED_OAUTH_AUTH_ID
    try:
        cred = readonly_context.get_credential(auth_id)
        if (
            cred
            and getattr(cred, "oauth2", None)
            and getattr(cred.oauth2, "access_token", None)
        ):
            return cred.oauth2.access_token
    except (
        AttributeError,
        KeyError,
        LookupError,
        TypeError,
        ValueError,
    ) as exc:
        logger.debug("Delegated OAuth credential lookup skipped: %s", exc)

    state = getattr(readonly_context, "state", None)
    if state:
        candidate_keys = (
            auth_id,
            f"temp:{auth_id}",
            "user_oauth_access_token",
            "temp:user_oauth_access_token",
        )
        for key in candidate_keys:
            val = state.get(key)
            if isinstance(val, str) and len(val) > 20:
                return val.strip()
            if isinstance(val, dict):
                tok = val.get("access_token") or val.get("token")
                if isinstance(tok, str) and len(tok) > 20:
                    return tok.strip()
    return None


def _gcp_adc_header_provider(readonly_context: Any = None) -> dict[str, str]:
    delegated_token = resolve_delegated_user_oauth_token(readonly_context)
    if delegated_token:
        headers = {"Authorization": f"Bearer {delegated_token}"}
        if config.RUNTIME_PROJECT_ID:
            headers["X-Goog-User-Project"] = config.RUNTIME_PROJECT_ID
        return headers

    if config.REQUIRE_DELEGATED_USER_OAUTH:
        raise PermissionError(
            "Delegated OAuth token required under "
            f"'{config.DELEGATED_OAUTH_AUTH_ID}'."
        )

    token, adc_project = _get_cached_adc_token_and_project()
    quota_project = config.RUNTIME_PROJECT_ID or adc_project
    headers = {"Authorization": f"Bearer {token}"}
    if quota_project:
        headers["X-Goog-User-Project"] = quota_project
    return headers


def _oidc_header_for_audience(audience: str) -> dict[str, str]:
    explicit_acct = os.getenv("CLOUDSDK_CORE_ACCOUNT", "").strip()
    cache_key = (
        f"acct:{explicit_acct}|{audience}" if explicit_acct else audience
    )
    now = time.monotonic()
    with _AUTH_LOCK:
        cached = _OIDC_TOKEN_CACHE.get(cache_key)
        if cached and now < cached[0] - 60.0:
            return {"Authorization": f"Bearer {cached[1]}"}

    if explicit_acct:
        cmd = [
            "gcloud",
            f"--account={explicit_acct}",
            "auth",
            "print-identity-token",
            "--quiet",
        ]
        if audience and explicit_acct.endswith(".gserviceaccount.com"):
            cmd.append(f"--audiences={audience}")
        tok = subprocess.check_output(cmd, text=True).strip()
        exp_mono = _jwt_monotonic_expiry(tok)
        with _AUTH_LOCK:
            _OIDC_TOKEN_CACHE[cache_key] = (exp_mono, tok)
        return {"Authorization": f"Bearer {tok}"}

    req = Request()
    try:
        tok = id_token.fetch_id_token(req, audience)
    except (GoogleAuthError, OSError, ValueError):
        adc_creds, _ = _get_cached_adc_creds_and_project()
        user_id_token = getattr(adc_creds, "id_token", None)
        if isinstance(user_id_token, str) and user_id_token.strip():
            jwt_tok = user_id_token.strip()
            exp_mono = _jwt_monotonic_expiry(jwt_tok)
            with _AUTH_LOCK:
                _OIDC_TOKEN_CACHE[cache_key] = (exp_mono, jwt_tok)
            return {"Authorization": f"Bearer {jwt_tok}"}
        return {"Authorization": f"Bearer {adc_creds.token}"}

    exp_mono = _jwt_monotonic_expiry(tok)
    with _AUTH_LOCK:
        _OIDC_TOKEN_CACHE[cache_key] = (exp_mono, tok)
    return {"Authorization": f"Bearer {tok}"}


def _cloud_run_oidc_header_provider(
    _readonly_context: Any = None,
) -> dict[str, str]:
    _, audience = _normalize_toolbox_endpoints(config.DATABASE_MCP_TOOLBOX_URL)
    return _oidc_header_for_audience(audience)


def _fetch_secret_manager_text(
    secret_id: str, ttl_seconds: float = 600.0
) -> str:
    cleaned = (secret_id or "").strip()
    if not cleaned:
        return ""
    now = time.monotonic()
    with _AUTH_LOCK:
        cached = _SECRET_VALUE_CACHE.get(cleaned)
        if cached and now < cached[0]:
            return cached[1]

    token, adc_proj = _get_cached_adc_token_and_project()
    proj = config.RUNTIME_PROJECT_ID or adc_proj
    if cleaned.startswith("projects/"):
        resource_path = (
            cleaned if "/versions/" in cleaned else f"{cleaned}/versions/latest"
        )
    else:
        if not proj:
            raise ValueError(
                f"Cannot resolve Secret Manager secret '{cleaned}' "
                "without a runtime project."
            )
        resource_path = f"projects/{proj}/secrets/{cleaned}/versions/latest"

    url = f"https://secretmanager.googleapis.com/v1/{resource_path}:access"
    headers = {"Authorization": f"Bearer {token}"}
    if proj:
        headers["X-Goog-User-Project"] = proj
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    b64_data = (resp.json().get("payload") or {}).get("data") or ""
    decoded = base64.b64decode(b64_data).decode("utf-8").strip()
    with _AUTH_LOCK:
        _SECRET_VALUE_CACHE[cleaned] = (now + ttl_seconds, decoded)
    return decoded


def _build_flexible_mcp_headers(
    *,
    raw_url: str,
    auth_mode: str,
    bearer_token: str,
    secret_id: str,
    headers_json: str,
    label: str,
    readonly_context: Any = None,
) -> dict[str, str]:
    mode = (auth_mode or "oidc").strip().lower()
    if mode == "none":
        return {}
    if mode in ("adc", "google_oauth"):
        return _gcp_adc_header_provider(readonly_context)
    if mode == "oidc":
        _, audience = _normalize_catalog_mcp_endpoints(raw_url)
        return _oidc_header_for_audience(audience)
    if mode == "bearer":
        token = (bearer_token or "").strip() or _fetch_secret_manager_text(
            secret_id
        )
        if not token:
            raise PermissionError(
                f"A bearer token or Secret Manager ID is required for "
                f"{label} MCP."
            )
        return {"Authorization": f"Bearer {token}"}
    if mode == "headers":
        raw_json = (headers_json or "").strip() or _fetch_secret_manager_text(
            secret_id
        )
        if not raw_json:
            raise PermissionError(
                f"A JSON header object or Secret Manager ID is required for "
                f"{label} MCP."
            )
        parsed = json.loads(raw_json)
        if not isinstance(parsed, dict) or not parsed:
            raise ValueError(
                f"Expected non-empty JSON object for {label} custom headers."
            )
        return {str(k): str(v) for k, v in parsed.items()}
    raise ValueError(
        f"Unsupported {label}_AUTH_MODE '{mode}'. "
        "Expected oidc, adc, bearer, headers, or none."
    )


def _catalog_mcp_header_provider(
    readonly_context: Any = None,
) -> dict[str, str]:
    return _build_flexible_mcp_headers(
        raw_url=config.CATALOG_MCP_URL,
        auth_mode=config.CATALOG_MCP_AUTH_MODE,
        bearer_token=config.CATALOG_MCP_BEARER_TOKEN,
        secret_id=config.CATALOG_MCP_TOKEN_SECRET_ID,
        headers_json=config.CATALOG_MCP_HEADERS_JSON,
        label="CATALOG_MCP",
        readonly_context=readonly_context,
    )


def _observability_mcp_header_provider(
    readonly_context: Any = None,
) -> dict[str, str]:
    return _build_flexible_mcp_headers(
        raw_url=config.OBSERVABILITY_MCP_URL,
        auth_mode=config.OBSERVABILITY_MCP_AUTH_MODE,
        bearer_token=config.OBSERVABILITY_MCP_BEARER_TOKEN,
        secret_id=config.OBSERVABILITY_MCP_TOKEN_SECRET_ID,
        headers_json=config.OBSERVABILITY_MCP_HEADERS_JSON,
        label="OBSERVABILITY_MCP",
        readonly_context=readonly_context,
    )


def build_managed_mcp_toolsets(*service_keys: str) -> list[McpToolset]:
    enabled_for_stack = None
    if not config.MULTI_PROFILE_MODE and config.WORKLOAD_PROFILE_NAME:
        active_profile = load_active_profile()
        if active_profile:
            enabled_for_stack = get_enabled_mcp_keys_for_profile(active_profile)

    toolsets: list[McpToolset] = []
    for key in service_keys:
        if enabled_for_stack is not None and key not in enabled_for_stack:
            continue
        entry = MANAGED_GCP_MCP_CATALOG.get(key)
        if not entry:
            continue
        kwargs: dict[str, Any] = {
            "connection_params": StreamableHTTPConnectionParams(
                url=entry["url"],
                timeout=30,
            ),
            "header_provider": _gcp_adc_header_provider,
            "tool_name_prefix": key,
            "tool_list_cache_ttl_seconds": 1800,
        }
        if entry.get("read_only_tools"):
            kwargs["tool_filter"] = entry["read_only_tools"]
        toolsets.append(McpToolset(**kwargs))
    return toolsets


def build_database_toolbox_mcp() -> list[McpToolset]:
    mcp_url, _ = _normalize_toolbox_endpoints(config.DATABASE_MCP_TOOLBOX_URL)
    if not mcp_url:
        return []
    kwargs: dict[str, Any] = {
        "connection_params": StreamableHTTPConnectionParams(
            url=mcp_url,
            timeout=25,
        ),
        "header_provider": _cloud_run_oidc_header_provider,
        "tool_name_prefix": "db_toolbox",
        "tool_list_cache_ttl_seconds": 1800,
    }
    if config.DATABASE_MCP_TOOLS:
        kwargs["tool_filter"] = list(config.DATABASE_MCP_TOOLS)
    return [McpToolset(**kwargs)]


def _sanitize_prefix(raw_name: str, fallback: str) -> str:
    cleaned = "".join(
        ch if ch.isalnum() else "_" for ch in (raw_name or "").strip().lower()
    ).strip("_")
    return cleaned or fallback


def _normalize_server_tools(raw_tools: Any) -> list[str] | None:
    if raw_tools is None:
        return None
    if isinstance(raw_tools, str):
        stripped = raw_tools.strip()
        if not stripped or stripped.lower() in ("*", "all"):
            return None
        return [item.strip() for item in stripped.split(",") if item.strip()]
    if isinstance(raw_tools, list):
        items = [str(item).strip() for item in raw_tools if str(item).strip()]
        if not items or items == ["*"]:
            return None
        return items
    return None


def _normalize_pillars(raw_pillars: Any) -> tuple[str, ...]:
    if raw_pillars is None:
        return ()
    if isinstance(raw_pillars, str):
        tokens = [
            item.strip().lower()
            for item in raw_pillars.split(",")
            if item.strip()
        ]
    elif isinstance(raw_pillars, list):
        tokens = [
            str(item).strip().lower()
            for item in raw_pillars
            if str(item).strip()
        ]
    else:
        return ()
    if not tokens or "*" in tokens or "all" in tokens:
        return ()
    return tuple(dict.fromkeys(tokens))


def _make_entry_header_provider(spec: dict[str, Any], label: str) -> Any:
    def _provider(readonly_context: Any = None) -> dict[str, str]:
        headers_val = spec.get("headers_json") or ""
        if isinstance(headers_val, dict):
            headers_val = json.dumps(headers_val)
        return _build_flexible_mcp_headers(
            raw_url=str(spec["raw_url"]),
            auth_mode=str(spec["auth_mode"]),
            bearer_token=str(spec.get("bearer_token") or ""),
            secret_id=str(spec.get("token_secret_id") or ""),
            headers_json=str(headers_val),
            label=label,
            readonly_context=readonly_context,
        )

    return _provider


def get_configured_catalog_mcp_specs() -> list[dict[str, Any]]:
    raw_multi = (config.CATALOG_MCP_SERVERS_JSON or "").strip()
    specs: list[dict[str, Any]] = []
    if raw_multi:
        parsed = json.loads(raw_multi)
        if not isinstance(parsed, list):
            raise ValueError(
                "CATALOG_MCP_SERVERS_JSON must be a JSON array of server "
                "objects."
            )
        used_prefixes: set[str] = set()
        for idx, item in enumerate(parsed):
            if not isinstance(item, dict):
                raise ValueError(
                    "Each entry in CATALOG_MCP_SERVERS_JSON must be a JSON "
                    "object."
                )
            raw_url = str(item.get("url") or "").strip()
            mcp_url, _ = _normalize_catalog_mcp_endpoints(raw_url)
            if not mcp_url:
                continue
            auth_mode = (
                str(item.get("auth_mode") or "oidc").strip().lower() or "oidc"
            )
            if auth_mode not in (
                "oidc",
                "adc",
                "google_oauth",
                "bearer",
                "headers",
                "none",
            ):
                raise ValueError(
                    f"Unsupported CATALOG_MCP_AUTH_MODE '{auth_mode}'. "
                    "Expected oidc, adc, bearer, headers, or none."
                )
            provider_name = str(
                item.get("name") or item.get("provider") or f"source_{idx + 1}"
            ).strip()
            fallback_slug = f"s{idx + 1}"
            sanitized = _sanitize_prefix(provider_name, fallback_slug)
            base_prefix = f"app_catalog_{sanitized}"
            prefix = base_prefix
            suffix = 2
            while prefix in used_prefixes:
                prefix = f"{base_prefix}_{suffix}"
                suffix += 1
            used_prefixes.add(prefix)
            specs.append(
                {
                    "name": provider_name,
                    "priority": int(item.get("priority", idx + 1)),
                    "order": idx,
                    "raw_url": raw_url,
                    "mcp_url": mcp_url,
                    "auth_mode": auth_mode,
                    "bearer_token": str(item.get("bearer_token") or ""),
                    "token_secret_id": str(item.get("token_secret_id") or ""),
                    "headers_json": item.get("headers_json")
                    or item.get("headers")
                    or "",
                    "tools": _normalize_server_tools(item.get("tools")),
                    "tool_name_prefix": prefix,
                    "layer_role": str(
                        item.get("layer_role") or "Application catalog and CMDB"
                    ).strip(),
                }
            )
        specs.sort(key=lambda entry: (entry["priority"], entry["order"]))
        return specs

    mcp_url, _ = _normalize_catalog_mcp_endpoints(config.CATALOG_MCP_URL)
    if not mcp_url:
        return []
    mode = (config.CATALOG_MCP_AUTH_MODE or "oidc").strip().lower()
    if mode not in ("oidc", "adc", "google_oauth", "bearer", "headers", "none"):
        raise ValueError(
            f"Unsupported CATALOG_MCP_AUTH_MODE '{mode}'. "
            "Expected oidc, adc, bearer, headers, or none."
        )
    return [
        {
            "name": (
                config.CATALOG_MCP_PROVIDER_NAME or "external_catalog"
            ).strip(),
            "priority": 1,
            "order": 0,
            "raw_url": config.CATALOG_MCP_URL,
            "mcp_url": mcp_url,
            "auth_mode": mode,
            "bearer_token": config.CATALOG_MCP_BEARER_TOKEN,
            "token_secret_id": config.CATALOG_MCP_TOKEN_SECRET_ID,
            "headers_json": config.CATALOG_MCP_HEADERS_JSON,
            "tools": (
                list(config.CATALOG_MCP_TOOLS)
                if config.CATALOG_MCP_TOOLS
                else None
            ),
            "tool_name_prefix": "app_catalog",
            "layer_role": "Primary live application catalog and CMDB",
        }
    ]


def get_configured_observability_mcp_specs(
    pillar_key: str | None = None,
) -> list[dict[str, Any]]:
    raw_multi = (config.OBSERVABILITY_MCP_SERVERS_JSON or "").strip()
    specs: list[dict[str, Any]] = []
    if raw_multi:
        parsed = json.loads(raw_multi)
        if not isinstance(parsed, list):
            raise ValueError(
                "OBSERVABILITY_MCP_SERVERS_JSON must be a JSON array of "
                "server objects."
            )
        used_prefixes: set[str] = set()
        for idx, item in enumerate(parsed):
            if not isinstance(item, dict):
                raise ValueError(
                    "Each entry in OBSERVABILITY_MCP_SERVERS_JSON must be a "
                    "JSON object."
                )
            raw_url = str(item.get("url") or "").strip()
            mcp_url, _ = _normalize_catalog_mcp_endpoints(raw_url)
            if not mcp_url:
                continue
            auth_mode = (
                str(item.get("auth_mode") or "bearer").strip().lower()
                or "bearer"
            )
            if auth_mode not in (
                "oidc",
                "adc",
                "google_oauth",
                "bearer",
                "headers",
                "none",
            ):
                raise ValueError(
                    f"Unsupported OBSERVABILITY_MCP_AUTH_MODE '{auth_mode}'. "
                    "Expected oidc, adc, bearer, headers, or none."
                )
            provider_name = str(
                item.get("name") or item.get("provider") or f"obs_{idx + 1}"
            ).strip()
            base_prefix = _sanitize_prefix(provider_name, f"ext_obs_{idx + 1}")
            prefix = base_prefix
            suffix = 2
            while prefix in used_prefixes:
                prefix = f"{base_prefix}_{suffix}"
                suffix += 1
            used_prefixes.add(prefix)
            specs.append(
                {
                    "name": provider_name,
                    "priority": int(item.get("priority", idx + 1)),
                    "order": idx,
                    "raw_url": raw_url,
                    "mcp_url": mcp_url,
                    "auth_mode": auth_mode,
                    "bearer_token": str(item.get("bearer_token") or ""),
                    "token_secret_id": str(item.get("token_secret_id") or ""),
                    "headers_json": item.get("headers_json")
                    or item.get("headers")
                    or "",
                    "tools": _normalize_server_tools(item.get("tools")),
                    "pillars": _normalize_pillars(item.get("pillars")),
                    "tool_name_prefix": prefix,
                    "layer_role": str(
                        item.get("layer_role")
                        or "External APM and observability telemetry"
                    ).strip(),
                }
            )
        specs.sort(key=lambda entry: (entry["priority"], entry["order"]))
    else:
        mcp_url, _ = _normalize_catalog_mcp_endpoints(
            config.OBSERVABILITY_MCP_URL
        )
        if mcp_url:
            mode = (
                (config.OBSERVABILITY_MCP_AUTH_MODE or "bearer").strip().lower()
            )
            if mode not in (
                "oidc",
                "adc",
                "google_oauth",
                "bearer",
                "headers",
                "none",
            ):
                raise ValueError(
                    f"Unsupported OBSERVABILITY_MCP_AUTH_MODE '{mode}'. "
                    "Expected oidc, adc, bearer, headers, or none."
                )
            raw_provider = (
                config.OBSERVABILITY_MCP_PROVIDER_NAME or "ext_obs"
            ).strip()
            specs.append(
                {
                    "name": raw_provider,
                    "priority": 1,
                    "order": 0,
                    "raw_url": config.OBSERVABILITY_MCP_URL,
                    "mcp_url": mcp_url,
                    "auth_mode": mode,
                    "bearer_token": config.OBSERVABILITY_MCP_BEARER_TOKEN,
                    "token_secret_id": config.OBSERVABILITY_MCP_TOKEN_SECRET_ID,
                    "headers_json": config.OBSERVABILITY_MCP_HEADERS_JSON,
                    "tools": (
                        list(config.OBSERVABILITY_MCP_TOOLS)
                        if config.OBSERVABILITY_MCP_TOOLS
                        else None
                    ),
                    "pillars": (),
                    "tool_name_prefix": _sanitize_prefix(
                        raw_provider, "ext_obs"
                    ),
                    "layer_role": "External APM and observability telemetry",
                }
            )

    if pillar_key:
        normalized_pillar = pillar_key.strip().lower()
        return [
            s
            for s in specs
            if not s["pillars"] or normalized_pillar in s["pillars"]
        ]
    return specs


def build_external_catalog_mcp() -> list[McpToolset]:
    specs = get_configured_catalog_mcp_specs()
    toolsets: list[McpToolset] = []
    use_legacy_single = not (config.CATALOG_MCP_SERVERS_JSON or "").strip()
    for spec in specs:
        kwargs: dict[str, Any] = {
            "connection_params": StreamableHTTPConnectionParams(
                url=spec["mcp_url"],
                timeout=25,
            ),
            "tool_name_prefix": spec["tool_name_prefix"],
            "tool_list_cache_ttl_seconds": 1800,
        }
        if spec["auth_mode"] != "none":
            kwargs["header_provider"] = (
                _catalog_mcp_header_provider
                if use_legacy_single
                else _make_entry_header_provider(spec, "CATALOG_MCP")
            )
        if spec["tools"]:
            kwargs["tool_filter"] = list(spec["tools"])
        toolsets.append(McpToolset(**kwargs))
    return toolsets


def build_external_observability_mcp(
    pillar_key: str | None = None,
) -> list[McpToolset]:
    specs = get_configured_observability_mcp_specs(pillar_key=pillar_key)
    toolsets: list[McpToolset] = []
    use_legacy_single = not (
        config.OBSERVABILITY_MCP_SERVERS_JSON or ""
    ).strip()
    for spec in specs:
        kwargs: dict[str, Any] = {
            "connection_params": StreamableHTTPConnectionParams(
                url=spec["mcp_url"],
                timeout=25,
            ),
            "tool_name_prefix": spec["tool_name_prefix"],
            "tool_list_cache_ttl_seconds": 1800,
        }
        if spec["auth_mode"] != "none":
            kwargs["header_provider"] = (
                _observability_mcp_header_provider
                if use_legacy_single
                else _make_entry_header_provider(spec, "OBSERVABILITY_MCP")
            )
        if spec["tools"]:
            kwargs["tool_filter"] = list(spec["tools"])
        toolsets.append(McpToolset(**kwargs))
    return toolsets
