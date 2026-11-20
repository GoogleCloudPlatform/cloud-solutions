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

# pylint: disable=import-outside-toplevel,line-too-long,redefined-outer-name

"""Shared pytest fixtures and automatic suite markers for unit, security, and integration tests."""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from agents.context import (
    ContextEnvelope,
    EdgeAuthVerifier,
    MemoryBankPartitioner,
    TokenBucketBulkhead,
)
from agents.interceptors import OTelAuditSink
from agents.registry import AgentRegistryPDP
from mcp_server.db import RLSDatabasePool


def pytest_configure(config: pytest.Config) -> None:
    """Installs a per-run in-memory P-256 context-token signer strictly during pytest sessions,
    and opts the suite in to local sandbox mode (off a managed runtime it is otherwise off).
    """
    del config
    from agents.context_signing import install_local_test_signer_for_pytest
    from agents.platform_config import LOCAL_SANDBOX_ENV

    os.environ.setdefault(LOCAL_SANDBOX_ENV, "1")
    install_local_test_signer_for_pytest()


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Applies `unit`, `security`, or `integration` markers from each test file's directory."""
    for item in items:
        parts = Path(str(item.fspath)).parts
        if "unit" in parts:
            item.add_marker(pytest.mark.unit)
        elif "security" in parts:
            item.add_marker(pytest.mark.security)
        elif "integration" in parts:
            item.add_marker(pytest.mark.integration)


@pytest.fixture(autouse=True)
def _isolate_google_cloud_project_between_tests() -> Iterator[None]:
    """Restores `GOOGLE_CLOUD_PROJECT` between tests so `setdefault` calls never leak."""
    prior = os.environ.get("GOOGLE_CLOUD_PROJECT")
    yield
    if prior is None:
        os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
    else:
        os.environ["GOOGLE_CLOUD_PROJECT"] = prior


@pytest.fixture(autouse=True)
def _reset_control_plane_revocations_between_tests() -> Iterator[None]:
    """Clears dynamic agent suspensions and tenant revocations between pytest cases."""
    from agents.workload_identity import reset_control_plane_revocations

    reset_control_plane_revocations()
    yield
    reset_control_plane_revocations()


@pytest.fixture
def edge_verifier() -> EdgeAuthVerifier:
    """Returns a fresh `EdgeAuthVerifier` instance."""
    return EdgeAuthVerifier()


@pytest.fixture
def registry_pdp() -> AgentRegistryPDP:
    """Returns a fresh `AgentRegistryPDP` instance."""
    return AgentRegistryPDP()


@pytest.fixture
def otel_sink() -> OTelAuditSink:
    """Returns an in-memory `OTelAuditSink` instance."""
    return OTelAuditSink()


@pytest.fixture
def db_pool() -> RLSDatabasePool:
    """Returns an in-memory `RLSDatabasePool` instance."""
    return RLSDatabasePool()


@pytest.fixture
def memory_bank() -> MemoryBankPartitioner:
    """Returns a fresh `MemoryBankPartitioner` instance."""
    return MemoryBankPartitioner()


@pytest.fixture
def token_bulkhead() -> TokenBucketBulkhead:
    """Returns a fresh `TokenBucketBulkhead` instance."""
    return TokenBucketBulkhead()


@pytest.fixture
def finvault_envelope(edge_verifier: EdgeAuthVerifier) -> ContextEnvelope:
    """Mints a verified `ContextEnvelope` for Tenant Alpha (`tenant-finvault-alpha`)."""
    return edge_verifier.exchange_obo_token(
        verified_idp_claims={
            "iss": "https://accounts.google.com",
            "sub": "alice@finvault.com",
            "tenant_id": "tenant-finvault-alpha",
            "exp": int(time.time()) + 3600,
            "jti": "jwt-fv-001",
            "user_role": "sre_admin",
        },
        dpop_proof={"jkt": "thumbprint-finvault-alice", "jti": "dpop-fv-001"},
        session_id="sess-finvault-001",
    )


@pytest.fixture
def retailstream_envelope(edge_verifier: EdgeAuthVerifier) -> ContextEnvelope:
    """Mints a verified `ContextEnvelope` for Tenant Beta (`tenant-retailstream-beta`)."""
    return edge_verifier.exchange_obo_token(
        verified_idp_claims={
            "iss": "https://login.microsoftonline.com/retailstream-tenant-id/v2.0",
            "sub": "bob@retailstream.com",
            "tenant_id": "tenant-retailstream-beta",
            "exp": int(time.time()) + 3600,
            "jti": "jwt-rs-001",
            "user_role": "sre_admin",
        },
        dpop_proof={"jkt": "thumbprint-retailstream-bob", "jti": "dpop-rs-001"},
        session_id="sess-retailstream-001",
    )
