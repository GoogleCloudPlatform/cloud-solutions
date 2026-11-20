# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# pylint: disable=import-outside-toplevel,line-too-long,protected-access

"""Tests for Secret Manager Redis AUTH+TLS client loading and templated agent principals."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from agents import platform_config as pc
from agents import workload_identity as wi
from agents.auth import vault_and_bulkhead as vb
from pydantic import ValidationError


@pytest.fixture(autouse=True)
def _clear_redis_tls_cache() -> None:
    vb._REDIS_TLS_CACHE.clear()
    yield
    vb._REDIS_TLS_CACHE.clear()


def test_redis_tls_secret_rejects_unpinned_or_malformed_versions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "REDIS_TLS_SECRET_VERSION", "cymbal-redis-tls-auth-prod/versions/latest"
    )
    with pytest.raises(ValueError, match="E_REDIS_TLS_SECRET_UNPINNED"):
        vb.build_redis_client_from_env()

    monkeypatch.setenv("REDIS_TLS_SECRET_VERSION", "not-a-secret-version")
    with pytest.raises(ValueError, match="E_REDIS_TLS_SECRET_UNPINNED"):
        vb.build_redis_client_from_env()

    monkeypatch.setenv(
        "REDIS_TLS_SECRET_VERSION",
        "projects/123456/secrets/cymbal-redis-tls-auth-prod/versions/1",
    )
    monkeypatch.setattr(
        vb, "_fetch_secret_version_bytes", lambda _res: b"not-json"
    )
    with pytest.raises(RuntimeError, match="E_REDIS_TLS_SECRET_INVALID"):
        vb.build_redis_client_from_env()

    vb._REDIS_TLS_CACHE.clear()
    monkeypatch.setattr(
        vb,
        "_fetch_secret_version_bytes",
        lambda _res: json.dumps({"url": "http://bad", "ca_pem": ""}).encode(
            "utf-8"
        ),
    )
    with pytest.raises(RuntimeError, match="E_REDIS_TLS_SECRET_INVALID"):
        vb.build_redis_client_from_env()


def test_redis_tls_secret_builds_client_with_ca_and_caches_secret_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    from_url_calls: list[tuple[str, dict[str, Any]]] = []
    secret_res = "projects/123456/secrets/cymbal-redis-tls-auth-prod/versions/3"
    bundle = {
        "url": "rediss://:s3cr3t-auth@10.20.0.5:6378/0",
        "ca_pem": "-----BEGIN CERTIFICATE-----\nFAKECERTDATA\n-----END CERTIFICATE-----\n",
    }

    def fake_fetch(res: str) -> bytes:
        calls.append(res)
        return json.dumps(bundle).encode("utf-8")

    def fake_from_url(url: str, **kwargs: Any) -> str:
        from_url_calls.append((url, kwargs))
        return "FAKE_REDIS_CLIENT"

    monkeypatch.setenv("REDIS_TLS_SECRET_VERSION", secret_res)
    monkeypatch.setattr(vb, "_fetch_secret_version_bytes", fake_fetch)
    monkeypatch.setattr(vb.redis.Redis, "from_url", staticmethod(fake_from_url))

    client1 = vb.build_redis_client_from_env()
    client2 = vb.build_redis_client_from_env()
    assert client1 == "FAKE_REDIS_CLIENT"
    assert client2 == "FAKE_REDIS_CLIENT"
    assert calls == [secret_res]
    assert len(from_url_calls) == 2

    url, kwargs = from_url_calls[0]
    assert url == bundle["url"]
    assert kwargs["ssl_cert_reqs"] == "required"
    assert kwargs["ssl_check_hostname"] is False
    ca_path = kwargs["ssl_ca_certs"]
    assert os.path.exists(ca_path)
    assert stat.S_IMODE(os.stat(ca_path).st_mode) == 0o600
    assert "FAKECERTDATA" in Path(ca_path).read_text(encoding="utf-8")


def test_agent_identity_template_validation_and_dynamic_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # customer.example loads cleanly with {org_id}, {project_number}, {region} placeholders.
    customer_cfg = pc.load_platform_config("customer.example")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT_NUMBER", "777888999")
    resolved = wi.bindings_from_config(customer_cfg)
    assert (
        resolved["cymbal_shared_diagnostic_agent"].workload_principal
        == "principal://agents.global.org-000000000000.system.id.goog/resources/run/"
        "projects/777888999/locations/us-central1/services/cymbal-agent-shared"
    )

    # Unknown placeholder or missing org_id fails validation.
    with pytest.raises(ValidationError):
        pc.AgentIdentitySettings.model_validate(
            {
                "org_id": "123",
                "bindings": {
                    "cymbal_shared_diagnostic_agent": {
                        "workload_principal": (
                            "principal://agents.global.org-{org_id}.system.id.goog/resources/"
                            "run/projects/{bad_var}/locations/{region}/services/cymbal-agent-shared"
                        )
                    }
                },
            }
        )
    with pytest.raises(ValidationError):
        pc.AgentIdentitySettings.model_validate(
            {
                "bindings": {
                    "cymbal_shared_diagnostic_agent": {
                        "workload_principal": (
                            "principal://agents.global.org-{org_id}.system.id.goog/resources/"
                            "run/projects/{project_number}/locations/{region}/services/s"
                        )
                    }
                }
            }
        )

    # Metadata server fallback works when running on Cloud Run (K_SERVICE=1) without env num.
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT_NUMBER", raising=False)
    monkeypatch.setenv("K_SERVICE", "cymbal-credential-broker")
    pc._fetch_metadata_project_number.cache_clear()
    import httpx

    monkeypatch.setattr(
        httpx,
        "get",
        lambda url, **_kw: SimpleNamespace(status_code=200, text="555444333\n"),
    )
    resolved_meta = wi.bindings_from_config(customer_cfg)
    meta_principal = resolved_meta[
        "cymbal_shared_diagnostic_agent"
    ].workload_principal
    assert "/projects/555444333/" in meta_principal
    pc._fetch_metadata_project_number.cache_clear()

    # Fail closed if project number cannot be resolved.
    monkeypatch.delenv("K_SERVICE", raising=False)
    with pytest.raises(ValueError, match="resolve \\{project_number\\}"):
        wi.bindings_from_config(customer_cfg)


def test_memory_bank_adapter_allows_dynamically_resolved_project_number(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`LiveVertexMemoryBankAdapter` accepts numeric `reasoningEngines/` paths resolved via
    `resolve_project_number()` (when config omits `gcp.project_number`), and still rejects
    cross-project numbers.
    """
    from agents.adapters.storage_and_telemetry import (
        LiveVertexMemoryBankAdapter,
    )

    monkeypatch.setenv("CYMBAL_ENV", "customer.example")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "acme-prod-123")
    monkeypatch.setenv("K_SERVICE", "cymbal-agent-shared")
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT_NUMBER", raising=False)
    pc._cached_platform_config.cache_clear()
    pc._fetch_metadata_project_number.cache_clear()

    import httpx

    monkeypatch.setattr(
        httpx,
        "get",
        lambda url, **_kw: SimpleNamespace(
            status_code=200, text="234567890123\n"
        ),
    )
    engine = "projects/234567890123/locations/us-central1/reasoningEngines/1000000000000000005"
    adapter = LiveVertexMemoryBankAdapter(
        project_id="acme-prod-123",
        location="us-central1",
        reasoning_engine_name=engine,
    )
    assert adapter.reasoning_engine_name == engine

    with pytest.raises(PermissionError, match="E_MEMORY_IAM_CEL_REGIONAL_LOCK"):
        LiveVertexMemoryBankAdapter(
            project_id="acme-prod-123",
            location="us-central1",
            reasoning_engine_name=(
                "projects/999999999999/locations/us-central1/reasoningEngines/1000000000000000005"
            ),
        )
    pc._fetch_metadata_project_number.cache_clear()
    pc._cached_platform_config.cache_clear()
