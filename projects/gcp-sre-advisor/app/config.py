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

"""Runtime, model, OAuth, and MCP endpoint configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.models import Gemini
from google.genai import types

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")
if (
    "GOOGLE_GENAI_USE_VERTEXAI" in os.environ
    and "GOOGLE_GENAI_USE_ENTERPRISE" not in os.environ
):
    os.environ["GOOGLE_GENAI_USE_ENTERPRISE"] = os.environ[
        "GOOGLE_GENAI_USE_VERTEXAI"
    ]

RUNTIME_PROJECT_ID = (
    os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("RUNTIME_PROJECT_ID") or ""
).strip()
RUNTIME_LOCATION = (
    os.getenv("GOOGLE_CLOUD_LOCATION")
    or os.getenv("RUNTIME_LOCATION")
    or "us-central1"
).strip()
MODEL_ENDPOINT_LOCATION = os.getenv("MODEL_ENDPOINT_LOCATION", "global").strip()

WORKLOAD_PROFILE_NAME = os.getenv("WORKLOAD_PROFILE_NAME", "").strip()
WORKLOAD_PROFILE_DIR = os.getenv("WORKLOAD_PROFILE_DIR", "").strip()
PROFILES_GCS_URI = os.getenv("PROFILES_GCS_URI", "").strip()
PROFILE_CACHE_TTL_SECONDS = int(os.getenv("PROFILE_CACHE_TTL_SECONDS", "300"))
MULTI_PROFILE_MODE = os.getenv("MULTI_PROFILE_MODE", "true").lower() in (
    "1",
    "true",
    "yes",
)

DELEGATED_OAUTH_AUTH_ID = os.getenv(
    "DELEGATED_OAUTH_AUTH_ID", "gcp-sre-user-oauth"
).strip()
REQUIRE_DELEGATED_USER_OAUTH = os.getenv(
    "REQUIRE_DELEGATED_USER_OAUTH", "false"
).lower() in (
    "1",
    "true",
    "yes",
)

_RAW_TARGET_PROJECT_ID = os.getenv("TARGET_PROJECT_ID", "").strip()
TARGET_PROJECT_ID = (
    _RAW_TARGET_PROJECT_ID
    if MULTI_PROFILE_MODE
    else (_RAW_TARGET_PROJECT_ID or RUNTIME_PROJECT_ID)
).strip()
TARGET_REGION = os.getenv("TARGET_REGION", "us-central1").strip()
TARGET_ZONE = os.getenv("TARGET_ZONE", "us-central1-a").strip()

DATABASE_MCP_TOOLBOX_URL = os.getenv("DATABASE_MCP_TOOLBOX_URL", "").strip()

_DEFAULT_DB_MCP_TOOLS = (
    "list_primary_tables",
    "execute_primary_readonly_sql",
    "execute_replica_readonly_sql",
)


def _parse_database_mcp_tools(raw_value: str) -> list[str] | None:
    cleaned = raw_value.strip()
    if not cleaned:
        return list(_DEFAULT_DB_MCP_TOOLS)
    if cleaned.lower() in ("*", "all"):
        return None
    return [item.strip() for item in cleaned.split(",") if item.strip()]


DATABASE_MCP_TOOLS: list[str] | None = _parse_database_mcp_tools(
    os.getenv("DATABASE_MCP_TOOLS", "")
)

CATALOG_MCP_URL = os.getenv("CATALOG_MCP_URL", "").strip()
CATALOG_MCP_AUTH_MODE = (
    os.getenv("CATALOG_MCP_AUTH_MODE", "oidc").strip().lower() or "oidc"
)
CATALOG_MCP_BEARER_TOKEN = os.getenv("CATALOG_MCP_BEARER_TOKEN", "").strip()
CATALOG_MCP_TOKEN_SECRET_ID = os.getenv(
    "CATALOG_MCP_TOKEN_SECRET_ID", ""
).strip()
CATALOG_MCP_HEADERS_JSON = os.getenv("CATALOG_MCP_HEADERS_JSON", "").strip()
CATALOG_MCP_PROVIDER_NAME = os.getenv("CATALOG_MCP_PROVIDER_NAME", "").strip()


def _parse_optional_mcp_tools(raw_value: str) -> list[str] | None:
    cleaned = raw_value.strip()
    if not cleaned or cleaned.lower() in ("*", "all"):
        return None
    return [item.strip() for item in cleaned.split(",") if item.strip()]


CATALOG_MCP_TOOLS: list[str] | None = _parse_optional_mcp_tools(
    os.getenv("CATALOG_MCP_TOOLS", "")
)
CATALOG_MCP_SERVERS_JSON = os.getenv("CATALOG_MCP_SERVERS_JSON", "").strip()

OBSERVABILITY_MCP_URL = os.getenv("OBSERVABILITY_MCP_URL", "").strip()
OBSERVABILITY_MCP_AUTH_MODE = (
    os.getenv("OBSERVABILITY_MCP_AUTH_MODE", "bearer").strip().lower()
    or "bearer"
)
OBSERVABILITY_MCP_BEARER_TOKEN = os.getenv(
    "OBSERVABILITY_MCP_BEARER_TOKEN", ""
).strip()
OBSERVABILITY_MCP_TOKEN_SECRET_ID = os.getenv(
    "OBSERVABILITY_MCP_TOKEN_SECRET_ID", ""
).strip()
OBSERVABILITY_MCP_HEADERS_JSON = os.getenv(
    "OBSERVABILITY_MCP_HEADERS_JSON", ""
).strip()
OBSERVABILITY_MCP_PROVIDER_NAME = os.getenv(
    "OBSERVABILITY_MCP_PROVIDER_NAME", ""
).strip()
OBSERVABILITY_MCP_TOOLS: list[str] | None = _parse_optional_mcp_tools(
    os.getenv("OBSERVABILITY_MCP_TOOLS", "")
)
OBSERVABILITY_MCP_SERVERS_JSON = os.getenv(
    "OBSERVABILITY_MCP_SERVERS_JSON", ""
).strip()

ORCHESTRATOR_MODEL_ID = os.getenv(
    "ORCHESTRATOR_MODEL", "gemini-4-carbon"
).strip()
SPECIALIST_MODEL_ID = os.getenv("SPECIALIST_MODEL", "gemini-4-neon").strip()
SWEEP_CONCURRENCY_LIMIT = max(1, int(os.getenv("SWEEP_CONCURRENCY_LIMIT", "3")))
MODEL_HTTP_TIMEOUT_MS = max(
    10_000, int(os.getenv("MODEL_HTTP_TIMEOUT_MS", "75000"))
)

MODEL_RETRY_OPTIONS = types.HttpRetryOptions(
    attempts=5,
    initial_delay=2.0,
    max_delay=20.0,
    exp_base=2.0,
    http_status_codes=[408, 429, 500, 502, 503, 504],
)

MODEL_HTTP_OPTIONS = types.HttpOptions(timeout=MODEL_HTTP_TIMEOUT_MS)

ORCHESTRATOR_MODEL = Gemini(
    model=ORCHESTRATOR_MODEL_ID,
    client_kwargs={
        "location": MODEL_ENDPOINT_LOCATION,
        "http_options": MODEL_HTTP_OPTIONS,
    },
    retry_options=MODEL_RETRY_OPTIONS,
)

SPECIALIST_MODEL = Gemini(
    model=SPECIALIST_MODEL_ID,
    client_kwargs={
        "location": MODEL_ENDPOINT_LOCATION,
        "http_options": MODEL_HTTP_OPTIONS,
    },
    retry_options=MODEL_RETRY_OPTIONS,
)

ORCHESTRATOR_GEN_CONFIG = types.GenerateContentConfig(
    temperature=0.1,
    thinking_config=types.ThinkingConfig(thinking_level="LOW"),
)

SPECIALIST_GEN_CONFIG = types.GenerateContentConfig(
    temperature=0.1,
    thinking_config=types.ThinkingConfig(thinking_level="LOW"),
)
