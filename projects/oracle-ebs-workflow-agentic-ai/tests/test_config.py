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

"""Unit tests for application configuration settings."""

import pytest
from src.config import get_settings


def test_default_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify default settings when environment variables are unset."""
    env_keys = [
        "ORACLE_HOST",
        "ORACLE_PORT",
        "ORACLE_SERVICE_NAME",
        "ORACLE_USER",
        "ORACLE_PASSWORD",
        "FND_USER_ID",
        "FND_RESP_ID",
        "FND_RESP_APPL_ID",
        "EBS_ISG_BASE_URL",
        "ISG_REST_BASE_URL",
        "EBS_WORKFLOW_DEFAULT_PATH",
        "WORKFLOW_EXECUTION_PATH",
        "ISG_USERNAME",
        "ISG_PASSWORD",
        "GEMINI_MODEL",
        "GEMINI_FLASH_LITE_MODEL",
        "GEMINI_FALLBACK_MODEL",
        "VERTEX_LOCATION",
        "GOOGLE_CLOUD_PROJECT",
        "PROJECT_ID",
        "A2A_SERVER_URL",
        "WORKFLOW_AGENT_URL",
        "EBS_API_KEY",
    ]
    for key in env_keys:
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()

    settings = get_settings()
    assert settings.oracle_host == "127.0.0.1"
    assert settings.oracle_port == 1521
    assert settings.oracle_service_name == "ebsdb"
    assert settings.oracle_user == "apps"
    assert settings.oracle_password == ""
    assert settings.db.dsn == "127.0.0.1:1521/ebsdb"
    assert settings.fnd_user_id == 0
    assert settings.fnd_resp_id == 20420
    assert settings.fnd_resp_appl_id == 1
    assert settings.isg_rest_base_url == "http://127.0.0.1:8000"
    assert settings.workflow.default_path == "REST"
    assert settings.gemini_model == "gemini-3.8-flash"
    assert settings.gemini_flash_lite_model == "gemini-3.5-flash-lite"
    assert settings.gemini_fallback_model == "gemini-3.7-flash"
    assert settings.a2a_server_url == "http://127.0.0.1:8080"
    assert settings.workflow_agent_url == "http://127.0.0.1:8001"


def test_environment_variable_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify environment variables override default configuration settings."""
    monkeypatch.setenv("ORACLE_HOST", "ebs.internal")
    monkeypatch.setenv("ORACLE_PORT", "1522")
    monkeypatch.setenv("ORACLE_SERVICE_NAME", "PROD")
    monkeypatch.setenv("ORACLE_USER", "ebs_admin")
    monkeypatch.setenv("ORACLE_PASSWORD", "secret_pw")
    monkeypatch.setenv("FND_USER_ID", "1318")
    monkeypatch.setenv("FND_RESP_ID", "50555")
    monkeypatch.setenv("FND_RESP_APPL_ID", "200")
    monkeypatch.setenv("EBS_ISG_BASE_URL", "https://ebs.internal:8443")
    monkeypatch.setenv("EBS_WORKFLOW_DEFAULT_PATH", "PLSQL")
    monkeypatch.setenv("ISG_USERNAME", "SYSADMIN")
    monkeypatch.setenv("ISG_PASSWORD", "isg_pw")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-custom-pro")
    monkeypatch.setenv("GEMINI_FLASH_LITE_MODEL", "gemini-custom-lite")
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "gemini-custom-fallback")
    monkeypatch.setenv("VERTEX_LOCATION", "us-central1")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "my-gcp-project")
    monkeypatch.setenv("A2A_SERVER_URL", "http://a2a:9000")
    monkeypatch.setenv("WORKFLOW_AGENT_URL", "http://wf:9001")
    monkeypatch.setenv("EBS_API_KEY", "api-key-123")
    get_settings.cache_clear()

    settings = get_settings()
    assert settings.oracle_host == "ebs.internal"
    assert settings.oracle_port == 1522
    assert settings.oracle_service_name == "PROD"
    assert settings.oracle_user == "ebs_admin"
    assert settings.oracle_password == "secret_pw"
    assert settings.db.dsn == "ebs.internal:1522/PROD"
    assert settings.fnd_user_id == 1318
    assert settings.fnd_resp_id == 50555
    assert settings.fnd_resp_appl_id == 200
    assert settings.isg_rest_base_url == "https://ebs.internal:8443"
    assert settings.workflow.default_path == "PLSQL"
    assert settings.workflow.isg_username == "SYSADMIN"
    assert settings.workflow.isg_password == "isg_pw"
    assert settings.gemini_model == "gemini-custom-pro"
    assert settings.gemini_flash_lite_model == "gemini-custom-lite"
    assert settings.gemini_fallback_model == "gemini-custom-fallback"
    assert settings.gemini.location == "us-central1"
    assert settings.gemini.project == "my-gcp-project"
    assert settings.a2a_server_url == "http://a2a:9000"
    assert settings.workflow_agent_url == "http://wf:9001"
    assert settings.network.api_key == "api-key-123"
    get_settings.cache_clear()
