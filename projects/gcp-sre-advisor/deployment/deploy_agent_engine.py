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

"""Deploys or updates the GCP SRE Advisor runtime on Vertex AI Agent Engine."""

import importlib
import json
import os
import sys
import tomllib
from pathlib import Path

import vertexai
from deployment.auth import require_project_id, resolve_credentials
from google.cloud import storage
from vertexai import agent_engines

ROOT_DIR = Path(__file__).resolve().parent.parent


def _load_project_dependencies() -> list[str]:
    pyproject_path = ROOT_DIR / "pyproject.toml"
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    return list(data["project"]["dependencies"])


def _load_fresh_adk_app():
    ordered_modules = (
        "app.config",
        "app.app_utils.profile_loader",
        "app.tools.mcp_registry",
        "app.prompts",
        "app.sub_agents",
        "app.tools.catalog_tools",
        "app.tools.sweep_tool",
        "app.agent",
        "app",
    )
    for mod_name in ordered_modules:
        if mod_name in sys.modules:
            importlib.reload(sys.modules[mod_name])
    return importlib.import_module("app.agent").app


def deploy_agent(
    default_profile: str | None = None,
    project_id: str | None = None,
) -> str:
    """Packages and deploys the ADK App to Vertex AI Agent Engine."""
    runtime_project = require_project_id(project_id)
    runtime_location = (
        os.getenv("GOOGLE_CLOUD_LOCATION") or "us-central1"
    ).strip()
    profile_name = (
        default_profile
        if default_profile is not None
        else os.getenv("WORKLOAD_PROFILE_NAME", "")
    ).strip()
    display_suffix = profile_name if profile_name else "multi-workload"
    multi_profile_raw = os.getenv("MULTI_PROFILE_MODE", "true").strip()
    is_multi_profile = multi_profile_raw.lower() in ("1", "true", "yes")
    raw_target_project = os.getenv("TARGET_PROJECT_ID", "").strip()
    target_project = (
        raw_target_project
        if is_multi_profile
        else (raw_target_project or runtime_project)
    ).strip()
    staging_bucket = os.getenv(
        "AGENT_ENGINE_STAGING_BUCKET",
        f"gs://{runtime_project}-gcp-sre-advisor-staging",
    ).strip()
    profiles_gcs_uri = os.getenv(
        "PROFILES_GCS_URI", f"{staging_bucket}/profiles"
    ).strip()
    service_account = os.getenv(
        "AGENT_RUNTIME_SA",
        f"sa-sre-advisor-reader@{runtime_project}.iam.gserviceaccount.com",
    ).strip()
    toolbox_url = os.getenv("DATABASE_MCP_TOOLBOX_URL", "").strip()
    toolbox_tools = os.getenv("DATABASE_MCP_TOOLS", "").strip()
    catalog_mcp_url = os.getenv("CATALOG_MCP_URL", "").strip()
    catalog_mcp_auth = os.getenv("CATALOG_MCP_AUTH_MODE", "oidc").strip()
    catalog_mcp_token = os.getenv("CATALOG_MCP_BEARER_TOKEN", "").strip()
    catalog_mcp_secret = os.getenv("CATALOG_MCP_TOKEN_SECRET_ID", "").strip()
    catalog_mcp_headers = os.getenv("CATALOG_MCP_HEADERS_JSON", "").strip()
    catalog_mcp_provider = os.getenv("CATALOG_MCP_PROVIDER_NAME", "").strip()
    catalog_mcp_tools = os.getenv("CATALOG_MCP_TOOLS", "").strip()
    catalog_mcp_servers = os.getenv("CATALOG_MCP_SERVERS_JSON", "").strip()

    obs_mcp_url = os.getenv("OBSERVABILITY_MCP_URL", "").strip()
    obs_mcp_auth = os.getenv("OBSERVABILITY_MCP_AUTH_MODE", "bearer").strip()
    obs_mcp_token = os.getenv("OBSERVABILITY_MCP_BEARER_TOKEN", "").strip()
    obs_mcp_secret = os.getenv("OBSERVABILITY_MCP_TOKEN_SECRET_ID", "").strip()
    obs_mcp_headers = os.getenv("OBSERVABILITY_MCP_HEADERS_JSON", "").strip()
    obs_mcp_provider = os.getenv("OBSERVABILITY_MCP_PROVIDER_NAME", "").strip()
    obs_mcp_tools = os.getenv("OBSERVABILITY_MCP_TOOLS", "").strip()
    obs_mcp_servers = os.getenv("OBSERVABILITY_MCP_SERVERS_JSON", "").strip()

    raw_env_vars = {
        "RUNTIME_PROJECT_ID": runtime_project,
        "RUNTIME_LOCATION": runtime_location,
        "MODEL_ENDPOINT_LOCATION": os.getenv(
            "MODEL_ENDPOINT_LOCATION", "global"
        ),
        "ORCHESTRATOR_MODEL": os.getenv(
            "ORCHESTRATOR_MODEL", "gemini-4-carbon"
        ),
        "SPECIALIST_MODEL": os.getenv("SPECIALIST_MODEL", "gemini-4-neon"),
        "SWEEP_CONCURRENCY_LIMIT": os.getenv("SWEEP_CONCURRENCY_LIMIT", "3"),
        "MODEL_HTTP_TIMEOUT_MS": os.getenv("MODEL_HTTP_TIMEOUT_MS", "75000"),
        "WORKLOAD_PROFILE_NAME": profile_name,
        "PROFILES_GCS_URI": profiles_gcs_uri,
        "MULTI_PROFILE_MODE": multi_profile_raw,
        "DELEGATED_OAUTH_AUTH_ID": os.getenv(
            "DELEGATED_OAUTH_AUTH_ID", "gcp-sre-user-oauth"
        ),
        "REQUIRE_DELEGATED_USER_OAUTH": os.getenv(
            "REQUIRE_DELEGATED_USER_OAUTH", "false"
        ),
        "TARGET_PROJECT_ID": target_project,
        "TARGET_REGION": os.getenv("TARGET_REGION", "us-central1"),
        "TARGET_ZONE": os.getenv("TARGET_ZONE", "us-central1-a"),
        "DATABASE_MCP_TOOLBOX_URL": toolbox_url,
        "DATABASE_MCP_TOOLS": toolbox_tools,
        "CATALOG_MCP_URL": catalog_mcp_url,
        "CATALOG_MCP_AUTH_MODE": catalog_mcp_auth if catalog_mcp_url else "",
        "CATALOG_MCP_BEARER_TOKEN": catalog_mcp_token,
        "CATALOG_MCP_TOKEN_SECRET_ID": catalog_mcp_secret,
        "CATALOG_MCP_HEADERS_JSON": catalog_mcp_headers,
        "CATALOG_MCP_PROVIDER_NAME": catalog_mcp_provider,
        "CATALOG_MCP_TOOLS": catalog_mcp_tools,
        "CATALOG_MCP_SERVERS_JSON": catalog_mcp_servers,
        "OBSERVABILITY_MCP_URL": obs_mcp_url,
        "OBSERVABILITY_MCP_AUTH_MODE": obs_mcp_auth if obs_mcp_url else "",
        "OBSERVABILITY_MCP_BEARER_TOKEN": obs_mcp_token,
        "OBSERVABILITY_MCP_TOKEN_SECRET_ID": obs_mcp_secret,
        "OBSERVABILITY_MCP_HEADERS_JSON": obs_mcp_headers,
        "OBSERVABILITY_MCP_PROVIDER_NAME": obs_mcp_provider,
        "OBSERVABILITY_MCP_TOOLS": obs_mcp_tools,
        "OBSERVABILITY_MCP_SERVERS_JSON": obs_mcp_servers,
    }
    for env_key, env_val in raw_env_vars.items():
        os.environ[env_key] = str(env_val)
    os.environ["GOOGLE_CLOUD_PROJECT"] = runtime_project
    os.environ["GOOGLE_CLOUD_LOCATION"] = runtime_location

    credentials = resolve_credentials(runtime_project)
    if os.getenv("CLOUDSDK_CORE_ACCOUNT") or os.getenv(
        "GOOGLE_OAUTH_ACCESS_TOKEN"
    ):
        _orig_storage_client = storage.Client

        def _authenticated_storage_client(*args, **kwargs):
            kwargs.setdefault("credentials", credentials)
            return _orig_storage_client(*args, **kwargs)

        storage.Client = _authenticated_storage_client

    vertexai.init(
        project=runtime_project,
        location=runtime_location,
        staging_bucket=staging_bucket,
        credentials=credentials,
    )

    adk_app = agent_engines.AdkApp(
        app=_load_fresh_adk_app(),
        enable_tracing=True,
    )

    env_vars = {
        k: str(v)
        for k, v in raw_env_vars.items()
        if v is not None and str(v) != ""
    }

    os.chdir(ROOT_DIR)
    existing_re_id = os.getenv("REASONING_ENGINE_ID", "").strip()
    reqs = _load_project_dependencies()
    min_instances = int(os.getenv("AGENT_MIN_INSTANCES", "1"))
    description = (
        "Multi-agent Site Reliability Engineering and Cloud Architecture "
        "advisor"
    )

    if existing_re_id:
        resource_path = (
            existing_re_id
            if existing_re_id.startswith("projects/")
            else (
                f"projects/{runtime_project}/locations/{runtime_location}"
                f"/reasoningEngines/{existing_re_id}"
            )
        )
        remote_agent = agent_engines.update(
            resource_name=resource_path,
            agent_engine=adk_app,
            display_name=f"GCP-SRE-Advisor-{display_suffix}",
            description=description,
            requirements=reqs,
            extra_packages=["./app"],
            env_vars=env_vars,
            service_account=service_account,
            min_instances=min_instances,
        )
    else:
        remote_agent = agent_engines.create(
            agent_engine=adk_app,
            display_name=f"GCP-SRE-Advisor-{display_suffix}",
            description=description,
            requirements=reqs,
            extra_packages=["./app"],
            env_vars=env_vars,
            service_account=service_account,
            min_instances=min_instances,
        )

    re_id = remote_agent.resource_name.rsplit("/", maxsplit=1)[-1]
    meta_path = ROOT_DIR / "deployment_metadata.json"
    meta_path.write_text(
        json.dumps(
            {
                "reasoning_engine_id": re_id,
                "resource_name": remote_agent.resource_name,
                "project_id": runtime_project,
                "location": runtime_location,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Resource Name : {remote_agent.resource_name}")
    print(f"Reasoning ID  : {re_id}")
    return re_id


if __name__ == "__main__":
    deploy_agent()
