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

"""Configuration module for Oracle EBS Workflow Agentic AI."""

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class OracleDBSettings:
    """Settings for Oracle EBS database connectivity."""

    host: str = "127.0.0.1"
    port: int = 1521
    service_name: str = "ebsdb"
    user: str = "apps"
    password: str = ""

    @property
    def dsn(self) -> str:
        """Construct Oracle DSN descriptor."""
        return f"{self.host}:{self.port}/{self.service_name}"


@dataclass(frozen=True)
class FndContextSettings:
    """Settings for Oracle EBS FND session initialization context."""

    user_id: int = 0
    resp_id: int = 20420
    resp_appl_id: int = 1


@dataclass(frozen=True)
class WorkflowSettings:
    """Settings for Oracle EBS Workflow integration paths."""

    isg_base_url: str = "http://127.0.0.1:8000"
    default_path: str = "REST"
    isg_username: str = "ISGADMIN"
    isg_password: str = ""


@dataclass(frozen=True)
class GeminiSettings:
    """Settings for Vertex AI and Gemini models."""

    primary_model: str = "gemini-3.8-flash"
    flash_lite_model: str = "gemini-3.5-flash-lite"
    fallback_model: str = "gemini-3.7-flash"
    location: str = "global"
    project: str = ""


@dataclass(frozen=True)
class NetworkSettings:
    """Settings for service discovery and networking."""

    a2a_server_url: str = "http://127.0.0.1:8080"
    workflow_agent_url: str = "http://127.0.0.1:8001"
    api_key: str = ""


@dataclass(frozen=True)
class Settings:
    """Root application configuration."""

    db: OracleDBSettings
    fnd: FndContextSettings
    workflow: WorkflowSettings
    gemini: GeminiSettings
    network: NetworkSettings

    @property
    def oracle_host(self) -> str:
        """Return Oracle host."""
        return self.db.host

    @property
    def oracle_port(self) -> int:
        """Return Oracle port."""
        return self.db.port

    @property
    def oracle_service_name(self) -> str:
        """Return Oracle service name."""
        return self.db.service_name

    @property
    def oracle_user(self) -> str:
        """Return Oracle user."""
        return self.db.user

    @property
    def oracle_password(self) -> str:
        """Return Oracle password."""
        return self.db.password

    @property
    def fnd_user_id(self) -> int:
        """Return FND user ID."""
        return self.fnd.user_id

    @property
    def fnd_resp_id(self) -> int:
        """Return FND responsibility ID."""
        return self.fnd.resp_id

    @property
    def fnd_resp_appl_id(self) -> int:
        """Return FND responsibility application ID."""
        return self.fnd.resp_appl_id

    @property
    def isg_rest_base_url(self) -> str:
        """Return ISG REST base URL."""
        return self.workflow.isg_base_url

    @property
    def gemini_model(self) -> str:
        """Return primary Gemini model."""
        return self.gemini.primary_model

    @property
    def gemini_fallback_model(self) -> str:
        """Return fallback Gemini model."""
        return self.gemini.fallback_model

    @property
    def gemini_flash_lite_model(self) -> str:
        """Return Gemini Flash Lite model."""
        return self.gemini.flash_lite_model

    @property
    def workflow_agent_url(self) -> str:
        """Return Workflow Agent URL."""
        return self.network.workflow_agent_url

    @property
    def a2a_server_url(self) -> str:
        """Return A2A Gateway Server URL."""
        return self.network.a2a_server_url


@lru_cache
def get_settings() -> Settings:
    """Retrieve application settings from environment variables."""
    oracle_host = os.environ.get("ORACLE_HOST") or "127.0.0.1"
    return Settings(
        db=OracleDBSettings(
            host=oracle_host,
            port=int(os.environ.get("ORACLE_PORT") or "1521"),
            service_name=os.environ.get("ORACLE_SERVICE_NAME") or "ebsdb",
            user=os.environ.get("ORACLE_USER") or "apps",
            password=os.environ.get("ORACLE_PASSWORD") or "",
        ),
        fnd=FndContextSettings(
            user_id=int(os.environ.get("FND_USER_ID") or "0"),
            resp_id=int(os.environ.get("FND_RESP_ID") or "20420"),
            resp_appl_id=int(os.environ.get("FND_RESP_APPL_ID") or "1"),
        ),
        workflow=WorkflowSettings(
            isg_base_url=(
                os.environ.get("EBS_ISG_BASE_URL")
                or os.environ.get("ISG_REST_BASE_URL")
                or f"http://{oracle_host}:8000"
            ),
            default_path=(
                os.environ.get("EBS_WORKFLOW_DEFAULT_PATH")
                or os.environ.get("WORKFLOW_EXECUTION_PATH")
                or "REST"
            ),
            isg_username=os.environ.get("ISG_USERNAME") or "ISGADMIN",
            isg_password=os.environ.get("ISG_PASSWORD") or "",
        ),
        gemini=GeminiSettings(
            primary_model=(
                os.environ.get("GEMINI_MODEL") or "gemini-3.8-flash"
            ),
            flash_lite_model=(
                os.environ.get("GEMINI_FLASH_LITE_MODEL")
                or "gemini-3.5-flash-lite"
            ),
            fallback_model=(
                os.environ.get("GEMINI_FALLBACK_MODEL") or "gemini-3.7-flash"
            ),
            location=os.environ.get("VERTEX_LOCATION") or "global",
            project=(
                os.environ.get("GOOGLE_CLOUD_PROJECT")
                or os.environ.get("PROJECT_ID")
                or ""
            ),
        ),
        network=NetworkSettings(
            a2a_server_url=os.environ.get(
                "A2A_SERVER_URL", "http://127.0.0.1:8080"
            ),
            workflow_agent_url=os.environ.get(
                "WORKFLOW_AGENT_URL", "http://127.0.0.1:8001"
            ),
            api_key=os.environ.get("EBS_API_KEY", ""),
        ),
    )
