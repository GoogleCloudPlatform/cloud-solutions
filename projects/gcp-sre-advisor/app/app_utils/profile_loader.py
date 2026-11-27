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

"""Context resolution across live catalogs, Cloud Storage profiles, and ADC."""

import logging
import os
import subprocess
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

import google.auth
import requests
import yaml
from google.auth.credentials import Credentials as BaseCredentials
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import AuthorizedSession
from google.oauth2.credentials import Credentials as OAuthCredentials

from .. import config

logger = logging.getLogger(__name__)

PROFILES_ROOT = Path(__file__).resolve().parent.parent / "profiles"
_PROFILE_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CATALOG_CACHE: tuple[float, list[dict[str, Any]]] | None = None
_GCS_SESSION_LOCK = threading.Lock()
_GCS_SESSIONS: dict[str, AuthorizedSession] = {}


class _GcloudCliCredentials(BaseCredentials):
    """Google Auth credentials backed by an explicit gcloud CLI account."""

    def __init__(self, account: str) -> None:
        super().__init__()
        self._account = account
        self.refresh(None)

    def refresh(self, _request: Any) -> None:
        out = subprocess.check_output(
            [
                "gcloud",
                "auth",
                "print-access-token",
                f"--account={self._account}",
                "--quiet",
            ],
            text=True,
        ).strip()
        self.token = out
        self.expiry = datetime.now(UTC).replace(tzinfo=None) + timedelta(
            minutes=45
        )


def clear_profile_caches() -> None:
    global _CATALOG_CACHE
    _PROFILE_CACHE.clear()
    _CATALOG_CACHE = None
    with _GCS_SESSION_LOCK:
        _GCS_SESSIONS.clear()


def parse_gcs_uri(uri: str) -> tuple[str, str] | None:
    cleaned = (uri or "").strip()
    if not cleaned.startswith("gs://"):
        return None
    without_scheme = cleaned[5:].strip("/")
    if not without_scheme:
        return None
    parts = without_scheme.split("/", 1)
    bucket = parts[0]
    prefix = parts[1].strip("/") if len(parts) > 1 else ""
    return bucket, prefix


def _gcs_session() -> AuthorizedSession:
    explicit_account = os.getenv("CLOUDSDK_CORE_ACCOUNT", "").strip()
    explicit_token = os.getenv("GOOGLE_OAUTH_ACCESS_TOKEN", "").strip()
    key = (
        f"acct:{explicit_account}"
        if explicit_account
        else (f"tok:{explicit_token[:16]}" if explicit_token else "adc")
    )
    with _GCS_SESSION_LOCK:
        existing = _GCS_SESSIONS.get(key)
        if existing is not None:
            return existing
        if explicit_account:
            creds: Any = _GcloudCliCredentials(explicit_account)
        elif explicit_token:
            creds = OAuthCredentials(token=explicit_token)
        else:
            creds, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
        session = AuthorizedSession(creds)
        _GCS_SESSIONS[key] = session
        return session


def _fetch_gcs_object_text(bucket: str, object_name: str) -> str | None:
    encoded = quote(object_name, safe="")
    url = f"https://storage.googleapis.com/storage/v1/b/{bucket}/o/{encoded}?alt=media"
    resp = _gcs_session().get(url, timeout=8)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.content.decode("utf-8")


def _load_profile_from_gcs(
    profile_name: str, gcs_uri: str
) -> dict[str, Any] | None:
    parsed = parse_gcs_uri(gcs_uri)
    if not parsed:
        return None
    bucket, prefix = parsed
    base = f"{prefix}/{profile_name}" if prefix else profile_name
    yaml_text = _fetch_gcs_object_text(bucket, f"{base}/profile.yaml")
    if yaml_text is None:
        return None
    spec = yaml.safe_load(yaml_text)
    if not isinstance(spec, dict) or not spec:
        return None
    md_text = _fetch_gcs_object_text(bucket, f"{base}/context.md") or ""
    spec["_narrative_context"] = md_text.strip()
    spec["_profile_name"] = profile_name
    spec["_profile_source"] = f"gs://{bucket}/{base}"
    return spec


def _list_gcs_profile_names(gcs_uri: str) -> list[str]:
    parsed = parse_gcs_uri(gcs_uri)
    if not parsed:
        return []
    bucket, prefix = parsed
    search_prefix = f"{prefix}/" if prefix else ""
    url = f"https://storage.googleapis.com/storage/v1/b/{bucket}/o"
    resp = _gcs_session().get(
        url, params={"prefix": search_prefix, "delimiter": "/"}, timeout=8
    )
    if resp.status_code != 200:
        return []
    prefixes = resp.json().get("prefixes") or []
    names = []
    for p in prefixes:
        rel = p[len(search_prefix) :].strip("/")
        if rel and not rel.startswith("_"):
            names.append(rel)
    return sorted(set(names))


def load_active_profile(
    profile_name: str | None = None,
    force_refresh: bool = False,
    profiles_root: Path | None = None,
) -> dict[str, Any]:
    selected_name = (
        profile_name
        if profile_name is not None
        else config.WORKLOAD_PROFILE_NAME
    ).strip()
    if not selected_name:
        return {}

    root_dir = profiles_root or PROFILES_ROOT
    cache_key = (
        f"{config.PROFILES_GCS_URI}|{config.WORKLOAD_PROFILE_DIR}|"
        f"{root_dir}|{selected_name}"
    )
    now = time.monotonic()

    if not force_refresh and cache_key in _PROFILE_CACHE:
        ts, cached = _PROFILE_CACHE[cache_key]
        if now - ts < config.PROFILE_CACHE_TTL_SECONDS:
            return cached

    if (
        profiles_root is None
        and config.PROFILES_GCS_URI
        and not config.WORKLOAD_PROFILE_DIR
    ):
        try:
            gcs_spec = _load_profile_from_gcs(
                selected_name, config.PROFILES_GCS_URI
            )
            if gcs_spec is not None:
                _PROFILE_CACHE[cache_key] = (now, gcs_spec)
                return gcs_spec
        except (
            GoogleAuthError,
            OSError,
            subprocess.SubprocessError,
            requests.RequestException,
            ValueError,
            yaml.YAMLError,
        ) as exc:
            logger.debug(
                "GCS profile fetch skipped for '%s': %s", selected_name, exc
            )

    profile_dir = (
        Path(config.WORKLOAD_PROFILE_DIR)
        if (
            profiles_root is None
            and config.WORKLOAD_PROFILE_DIR
            and not profile_name
        )
        else (root_dir / selected_name)
    )
    yaml_path = profile_dir / "profile.yaml"
    if not yaml_path.exists():
        return {}

    loaded = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict) or not loaded:
        return {}

    md_path = profile_dir / "context.md"
    narrative = (
        md_path.read_text(encoding="utf-8").strip() if md_path.exists() else ""
    )
    spec = dict(loaded)
    spec["_narrative_context"] = narrative
    spec["_profile_name"] = selected_name
    spec["_profile_dir"] = str(profile_dir)
    spec["_profile_source"] = f"local:{profile_dir}"
    _PROFILE_CACHE[cache_key] = (now, spec)
    return spec


def list_available_profiles(
    force_refresh: bool = False,
    profiles_root: Path | None = None,
) -> list[dict[str, Any]]:
    global _CATALOG_CACHE
    now = time.monotonic()
    use_global_cache = profiles_root is None
    if (
        use_global_cache
        and not force_refresh
        and _CATALOG_CACHE
        and (now - _CATALOG_CACHE[0] < config.PROFILE_CACHE_TTL_SECONDS)
    ):
        return _CATALOG_CACHE[1]

    root_dir = profiles_root or PROFILES_ROOT
    names: set[str] = set()
    if root_dir.exists():
        for item in root_dir.iterdir():
            if (
                item.is_dir()
                and not item.name.startswith("_")
                and (item / "profile.yaml").exists()
            ):
                names.add(item.name)

    if profiles_root is None and config.PROFILES_GCS_URI:
        try:
            names.update(_list_gcs_profile_names(config.PROFILES_GCS_URI))
        except (
            GoogleAuthError,
            OSError,
            subprocess.SubprocessError,
            requests.RequestException,
            ValueError,
        ) as exc:
            logger.debug("GCS catalog listing skipped: %s", exc)

    catalog: list[dict[str, Any]] = []
    for name in sorted(names):
        spec = load_active_profile(
            name, force_refresh=force_refresh, profiles_root=profiles_root
        )
        if not spec:
            continue
        ident = _as_dict(spec.get("workload_identity"))
        env_proj = _as_dict(spec.get("environment_and_projects"))
        stack = _as_dict(spec.get("active_stack"))
        catalog.append(
            {
                "profile_id": name,
                "display_name": ident.get("display_name")
                or ident.get("name")
                or name,
                "domain": ident.get("business_domain", "general"),
                "environment_tier": env_proj.get("environment_tier", "prod"),
                "source": spec.get("_profile_source", "local"),
                "active_stack": stack,
            }
        )
    if use_global_cache:
        _CATALOG_CACHE = (now, catalog)
    return catalog


def _as_dict(val: Any) -> dict[str, Any]:
    return val if isinstance(val, dict) else {}


def _as_str_list(val: Any) -> list[str]:
    if not isinstance(val, list):
        return []
    return [
        str(item).strip()
        for item in val
        if item is not None and str(item).strip()
    ]


def _resolve_projects_map(env_proj: dict[str, Any]) -> dict[str, str]:
    raw_projects = _as_dict(env_proj.get("projects_by_role"))
    mapped = {
        str(role): str(pid).strip()
        for role, pid in raw_projects.items()
        if pid is not None and str(pid).strip()
    }
    if mapped:
        return mapped
    if config.TARGET_PROJECT_ID:
        return {"primary": config.TARGET_PROJECT_ID}
    return {}


def build_profile_drift_contract(profile: dict[str, Any]) -> dict[str, Any]:
    ident = _as_dict(profile.get("workload_identity"))
    env_proj = _as_dict(profile.get("environment_and_projects"))
    finops = _as_dict(profile.get("finops_and_cost_controls"))
    raw_exceptions = profile.get("accepted_exceptions")
    exceptions = raw_exceptions if isinstance(raw_exceptions, list) else []
    return {
        "profile_id": profile.get("_profile_name") or ident.get("id") or "",
        "profile_source": profile.get("_profile_source", "local"),
        "workload_name": ident.get("display_name")
        or ident.get("name")
        or "Unspecified Workload",
        "architecture_archetype": str(
            profile.get("architecture_archetype") or "unspecified"
        ),
        "environment_tier": env_proj.get("environment_tier", "prod"),
        "primary_region": env_proj.get("primary_region")
        or config.TARGET_REGION,
        "primary_zone": env_proj.get("primary_zone") or config.TARGET_ZONE,
        "projects_by_role": _resolve_projects_map(env_proj),
        "declared_active_stack": _as_dict(profile.get("active_stack")),
        "slo_and_resilience_targets": _as_dict(
            profile.get("slo_and_resilience_targets")
        ),
        "required_finops_labels": _as_str_list(finops.get("required_labels")),
        "accepted_exception_ids": [
            str(ex.get("id")).strip()
            for ex in exceptions
            if isinstance(ex, dict) and str(ex.get("id") or "").strip()
        ],
    }


def get_enabled_mcp_keys_for_profile(profile: dict[str, Any]) -> set[str]:
    stack = _as_dict(profile.get("active_stack"))
    compute = set(_as_str_list(stack.get("compute")))
    databases = set(_as_str_list(stack.get("databases")))
    caching_msg = set(_as_str_list(stack.get("caching_messaging")))

    enabled = {
        "logging",
        "monitoring",
        "resourcemanager",
        "iam",
        "orgpolicy",
        "gcloud_cli",
        "developerknowledge",
        "discoveryengine",
        "storage",
        "cloudasset",
    }

    if compute & {"gke", "compute_engine"}:
        enabled.add("compute")
        enabled.add("cloudtrace")
    if (
        compute & {"cloud_run", "cloud_run_jobs", "cloud_run_worker_pools"}
        or "eventarc" in caching_msg
    ):
        enabled.add("cloudrun")
        enabled.add("cloudtrace")
    if databases & {
        "cloudsql_mysql",
        "cloudsql_postgres",
        "cloudsql_sqlserver",
    }:
        enabled.add("sqladmin")
    if "bigquery" in databases:
        enabled.add("bigquery")
    if caching_msg & {"pubsub", "eventarc"}:
        enabled.add("pubsub")

    return enabled


def _render_environment_tier_guidance(env_tier: str) -> str:
    cleaned = (env_tier or "prod").strip().lower()
    if cleaned in ("dev", "development", "sandbox"):
        return (
            "Environment tier is development. Prioritize cost efficiency and "
            "operational simplicity without demanding multi-zone redundancy, "
            "while maintaining identity and security controls."
        )
    if cleaned in ("uat", "hml", "homolog", "staging"):
        return (
            "Environment tier is staging. Balance financial control with "
            "sufficient architectural parity to validate performance and "
            "changes before production release."
        )
    return (
        "Environment tier is production. Apply full rigor across regional "
        "high availability, disaster recovery readiness, security posture, "
        "peak performance, and cost governance."
    )


def resolve_active_target_metadata(
    readonly_context: Any = None,
) -> dict[str, Any]:
    profile_id = ""
    catalog_app_id = ""
    catalog_ctx: dict[str, Any] = {}
    zero_proj = ""
    zero_tier = "prod"
    zero_region = ""
    zero_zone = ""

    if readonly_context is not None:
        state = getattr(readonly_context, "state", None)
        if state:
            profile_id = str(state.get("active_workload_profile") or "").strip()
            catalog_app_id = str(state.get("live_catalog_app_id") or "").strip()
            catalog_ctx = _as_dict(state.get("live_catalog_context"))
            zero_proj = str(state.get("zero_profile_project") or "").strip()
            zero_tier = str(state.get("zero_profile_tier") or "prod").strip()
            zero_region = str(state.get("zero_profile_region") or "").strip()
            zero_zone = str(state.get("zero_profile_zone") or "").strip()

    if (
        not profile_id
        and not catalog_app_id
        and not zero_proj
        and config.WORKLOAD_PROFILE_NAME
    ):
        profile_id = config.WORKLOAD_PROFILE_NAME.strip()

    if catalog_app_id:
        raw_pids = _as_str_list(catalog_ctx.get("project_ids"))
        primary_proj = str(catalog_ctx.get("primary_project_id") or "").strip()
        if primary_proj and primary_proj not in raw_pids:
            raw_pids.insert(0, primary_proj)
        resolved_primary = raw_pids[0] if raw_pids else ""
        region = str(
            catalog_ctx.get("region") or config.TARGET_REGION or "us-central1"
        ).strip()
        zone = str(
            catalog_ctx.get("zone")
            or (
                config.TARGET_ZONE
                if config.TARGET_ZONE.startswith(f"{region}-")
                else f"{region}-a"
            )
        ).strip()
        tier = str(catalog_ctx.get("environment_tier") or "prod").strip()
        merged_ctx = {
            **catalog_ctx,
            "application_id": catalog_app_id,
            "project_ids": raw_pids,
            "primary_project_id": resolved_primary,
            "region": region,
            "zone": zone,
            "environment_tier": tier,
        }
        return {
            "mode": "catalog",
            "context_source": "live_catalog",
            "profile_id": "",
            "profile": {},
            "catalog_context": merged_ctx,
            "application_id": catalog_app_id,
            "project_ids": raw_pids,
            "primary_project_id": resolved_primary,
            "region": region,
            "zone": zone,
            "tier": tier,
        }

    if profile_id:
        profile = load_active_profile(profile_id)
        if profile:
            env_proj = _as_dict(profile.get("environment_and_projects"))
            projects_map = _resolve_projects_map(env_proj)
            project_ids = list(dict.fromkeys(projects_map.values()))
            region = str(
                env_proj.get("primary_region")
                or config.TARGET_REGION
                or "us-central1"
            ).strip()
            zone = str(
                env_proj.get("primary_zone")
                or config.TARGET_ZONE
                or f"{region}-a"
            ).strip()
            return {
                "mode": "profile",
                "context_source": "workload_profile",
                "profile_id": profile_id,
                "profile": profile,
                "catalog_context": {},
                "application_id": "",
                "project_ids": project_ids,
                "primary_project_id": project_ids[0] if project_ids else "",
                "region": region,
                "zone": zone,
                "tier": str(env_proj.get("environment_tier") or "prod").strip(),
            }

    if (
        not zero_proj
        and not config.MULTI_PROFILE_MODE
        and config.TARGET_PROJECT_ID
    ):
        zero_proj = config.TARGET_PROJECT_ID

    if zero_proj:
        region = zero_region or config.TARGET_REGION or "us-central1"
        zone = zero_zone or (
            config.TARGET_ZONE
            if config.TARGET_ZONE.startswith(f"{region}-")
            else f"{region}-a"
        )
        return {
            "mode": "discovery",
            "context_source": "live_project_discovery",
            "profile_id": "",
            "profile": {},
            "catalog_context": {},
            "application_id": "",
            "project_ids": [zero_proj],
            "primary_project_id": zero_proj,
            "region": region,
            "zone": zone,
            "tier": zero_tier,
        }

    return {
        "mode": "unselected",
        "context_source": "unselected",
        "profile_id": "",
        "profile": {},
        "catalog_context": {},
        "application_id": "",
        "project_ids": [],
        "primary_project_id": "",
        "region": config.TARGET_REGION or "us-central1",
        "zone": config.TARGET_ZONE or "us-central1-a",
        "tier": "prod",
    }


def render_profile_for_prompt(profile: dict[str, Any]) -> str:
    ident = _as_dict(profile.get("workload_identity"))
    env_proj = _as_dict(profile.get("environment_and_projects"))
    archetype = str(profile.get("architecture_archetype") or "unspecified")
    stack = _as_dict(profile.get("active_stack"))
    net_proto = _as_dict(profile.get("network_and_protocol_constraints"))
    finops = _as_dict(profile.get("finops_and_cost_controls"))
    slos = _as_dict(profile.get("slo_and_resilience_targets"))
    ext = _as_dict(profile.get("external_boundaries"))
    raw_exceptions = profile.get("accepted_exceptions")
    exceptions = raw_exceptions if isinstance(raw_exceptions, list) else []
    delivery = _as_dict(profile.get("change_delivery_model"))

    tier_guidance = _render_environment_tier_guidance(
        str(env_proj.get("environment_tier", "prod"))
    )

    projects_map = _resolve_projects_map(env_proj)
    projects_lines = (
        "\n".join(
            f"- Role `{role}` mapped to project `{pid}`"
            for role, pid in projects_map.items()
        )
        if projects_map
        else "- No target GCP projects mapped"
    )
    primary_region = env_proj.get("primary_region") or config.TARGET_REGION
    primary_zone = env_proj.get("primary_zone") or config.TARGET_ZONE

    stack_summary = []
    for label, key in (
        ("Compute", "compute"),
        ("Databases", "databases"),
        ("Caching and messaging", "caching_messaging"),
        ("Edge and networking", "edge_networking"),
    ):
        items = _as_str_list(stack.get(key))
        if items:
            joined_items = ", ".join(items)
            stack_summary.append(f"- {label}: {joined_items}")
    stack_block = (
        "\n".join(stack_summary)
        if stack_summary
        else "- Stack discovered dynamically via MCP"
    )

    net_lines = []
    for item in _as_str_list(net_proto.get("egress_static_ips")):
        net_lines.append(f"- Static egress constraint: {item}")
    for item in _as_str_list(net_proto.get("special_protocols")):
        net_lines.append(f"- Protocol constraint: {item}")
    net_block = (
        "\n".join(net_lines)
        if net_lines
        else "- Standard HTTP and private VPC communication."
    )

    req_labels = _as_str_list(finops.get("required_labels"))
    cost_policy = str(finops.get("nonprod_cost_saving_policy") or "").strip()
    finops_lines = []
    if req_labels:
        joined_labels = ", ".join(req_labels)
        finops_lines.append(
            f"- Required FinOps labels on resources: {joined_labels}"
        )
    if cost_policy:
        finops_lines.append(f"- Cost control policy: {cost_policy}")
    finops_block = (
        "\n".join(finops_lines)
        if finops_lines
        else "- Standard cloud financial governance."
    )

    ext_lines = []
    for k in ("identity_providers", "edge_and_dns", "external_apis_or_clouds"):
        for item in _as_str_list(ext.get(k)):
            ext_lines.append(f"- {item}")
    ext_block = (
        "\n".join(ext_lines)
        if ext_lines
        else "- No external boundaries declared."
    )

    exc_lines = []
    for ex in exceptions:
        if not isinstance(ex, dict):
            continue
        ex_id = ex.get("id", "N/A")
        ex_pillar = ex.get("pillar", "general")
        ex_summary = ex.get("summary", "")
        ex_rationale = ex.get("rationale", "")
        ex_review = ex.get("review_date", "unspecified")
        exc_lines.append(
            f"- Exception `{ex_id}` in domain `{ex_pillar}`: "
            f"{ex_summary}. Rationale: {ex_rationale}. "
            f"Review date: {ex_review}."
        )
    exc_block = (
        "Documented accepted risks and exceptions:\n" + "\n".join(exc_lines)
        if exc_lines
        else "No pre-approved architectural exceptions registered."
    )

    avail_raw = slos.get("availability_slo_pct")
    if avail_raw is not None:
        avail_clean = str(avail_raw).rstrip("%")
        avail_str = f"{avail_clean}%"
    else:
        avail_str = str(slos.get("availability_slo", "99.9%"))
    latency_ms = slos.get("latency_p95_ms", 500)
    rpo_min = slos.get("rpo_minutes", "unspecified")
    rto_min = slos.get("rto_minutes", "unspecified")
    peak_win = (
        slos.get("critical_business_windows")
        or ident.get("peak_windows")
        or "Business hours"
    )

    delivery_mode = delivery.get(
        "delivery_mode", "standard_operational_runbook"
    )
    tooling = delivery.get("tooling", "not specified")
    rem_format = delivery.get(
        "remediation_format",
        "Step-by-step operational remediation matching workload governance",
    )

    profile_id = profile.get("_profile_name") or ident.get("id") or ""
    profile_src = profile.get("_profile_source", "local")
    wname = (
        ident.get("display_name") or ident.get("name") or "Unspecified Workload"
    )
    domain = ident.get("business_domain", "Enterprise Application")
    criticality = ident.get("criticality", "standard")
    crit_summary = ident.get(
        "criticality_summary", "Standard production service"
    )
    narrative = profile.get("_narrative_context", "")

    return (
        "Workload Profile Context:\n"
        "- Context source: Declarative Workload Profile from "
        f"`{profile_src}`\n"
        f"- Active profile ID: `{profile_id}` | Workload name: {wname}\n"
        f"- Architecture archetype: {archetype} | Business domain: {domain}\n"
        f"- Criticality: `{criticality}` — {crit_summary}\n"
        f"- Environment tier policy: {tier_guidance}\n"
        f"- SLO and resilience targets: Availability {avail_str} | "
        f"Latency P95 {latency_ms} ms | RPO {rpo_min} min | "
        f"RTO {rto_min} min | Peak window: {peak_win}\n"
        f"- Change delivery mode: `{delivery_mode}` | "
        f"Operational tooling: {tooling} | "
        f"Remediation output format: {rem_format}\n\n"
        "Target GCP projects and regions:\n"
        f"{projects_lines}\n"
        f"- Primary region `{primary_region}` and "
        f"primary zone `{primary_zone}`\n\n"
        "Declared active technology stack:\n"
        f"{stack_block}\n\n"
        "Network and protocol constraints:\n"
        f"{net_block}\n\n"
        "FinOps and financial governance rules:\n"
        f"{finops_block}\n\n"
        "External integration boundaries:\n"
        f"{ext_block}\n\n"
        f"{exc_block}\n\n"
        "Additional workload context:\n"
        f"{narrative}"
    )


def render_live_catalog_for_prompt(catalog_ctx: dict[str, Any]) -> str:
    app_id = str(
        catalog_ctx.get("application_id") or "unspecified-application"
    ).strip()
    display_name = str(catalog_ctx.get("display_name") or app_id).strip()
    provider = str(
        catalog_ctx.get("catalog_source")
        or config.CATALOG_MCP_PROVIDER_NAME
        or (
            "external_catalog_mcp"
            if config.CATALOG_MCP_URL
            else "google_cloud_apphub"
        )
    ).strip()
    apphub_id = str(catalog_ctx.get("apphub_application_id") or app_id).strip()
    criticality = str(catalog_ctx.get("criticality") or "unspecified").strip()
    owner_team = str(
        catalog_ctx.get("owner_team") or "resolved dynamically via live catalog"
    ).strip()
    env_tier = str(catalog_ctx.get("environment_tier") or "prod").strip()
    tier_guidance = _render_environment_tier_guidance(env_tier)

    proj_ids = _as_str_list(catalog_ctx.get("project_ids"))
    primary_proj = str(catalog_ctx.get("primary_project_id") or "").strip()
    if primary_proj and primary_proj not in proj_ids:
        proj_ids.insert(0, primary_proj)
    projects_line = (
        ", ".join(f"`{p}`" for p in proj_ids) if proj_ids else "none mapped"
    )
    region = str(
        catalog_ctx.get("region") or config.TARGET_REGION or "us-central1"
    ).strip()
    zone = str(
        catalog_ctx.get("zone") or config.TARGET_ZONE or f"{region}-a"
    ).strip()

    slo_summary = str(
        catalog_ctx.get("slo_summary")
        or "Resolve SLO targets from live catalog MCP tools or apply "
        "Architecture Framework defaults"
    ).strip()
    finops_labels = str(
        catalog_ctx.get("finops_labels")
        or "Verify standard cost-allocation labels from live catalog or "
        "cloud resources"
    ).strip()
    delivery_summary = str(
        catalog_ctx.get("delivery_model_summary")
        or "Format remediation steps according to the live catalog delivery "
        "model or neutral operational steps"
    ).strip()
    accepted_risks = str(
        catalog_ctx.get("accepted_risks_summary")
        or "No pre-approved risk exceptions cached in session; check live "
        "catalog MCP tools if available"
    ).strip()
    notes = str(catalog_ctx.get("architecture_notes") or "").strip()
    notes_section = (
        f"\nLive catalog architecture notes:\n{notes}" if notes else ""
    )

    return (
        "Live Application Catalog Context:\n"
        "- Context source: Live Application Catalog and Google Cloud App Hub\n"
        f"- Active application ID: `{app_id}` | Display name: {display_name}\n"
        f"- Catalog provider: `{provider}` | Google Cloud App Hub "
        f"application ID: `{apphub_id}`\n"
        f"- Criticality: `{criticality}` | Ownership: {owner_team}\n"
        f"- Environment tier policy: {tier_guidance}\n"
        f"- Target GCP projects: {projects_line} | Primary region: "
        f"`{region}` | Primary zone: `{zone}`\n"
        f"- Live SLO and resilience targets: {slo_summary}\n"
        f"- Live FinOps label governance: {finops_labels}\n"
        f"- Live change delivery model: {delivery_summary}\n"
        f"- Live accepted risks and exceptions: {accepted_risks}{notes_section}"
    )
