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

# pylint: disable=line-too-long

"""Shared gateway singletons, FastAPI caller dependencies, and monkeypatch-safe resolvers."""

from __future__ import annotations

import logging
import re
import sys
from typing import Annotated, Any

from agents import sandbox_execution
from agents.context import (
    ContextEnvelope,
    EdgeAuthVerifier,
    MemoryBankPartitioner,
    build_bulkhead_from_env,
)
from agents.context_signing import get_context_token_issuer
from agents.context_token import (
    ContextKeyWarmer,
    agent_id_required,
    get_context_verifier,
)
from agents.gcp_live_bridge import LiveGeminiAgentSandboxClient
from agents.interceptors import OTelAuditSink
from agents.model_routing import SharedModelRoutingPDP
from agents.platform_config import get_platform_config
from agents.registry import AgentRegistryPDP
from agents.runtime_env import validate_runtime_environment
from agents.turn_engine import TurnServices
from agents.workload_identity import flag_enabled
from app.auth import sandbox_mode_active
from app.gateway_tokens import (
    get_token_service,
    make_optional_caller,
    make_require_caller,
)
from app.remote_runtime import RemoteRuntimeClient
from app.schemas.gateway import InvokeAgentRequest, ScenarioTurn
from fastapi import Depends, HTTPException
from mcp_server.db import build_rls_db_pool_from_env

logger = logging.getLogger("app.main")


def gateway_module() -> Any:
    """Returns `app.main` when imported so `monkeypatch.setattr(main, ...)` applies everywhere."""
    return sys.modules.get("app.main", sys.modules[__name__])


def active_platform_config() -> Any:
    """Resolves `get_platform_config()` via `app.main` when monkeypatched in tests."""
    mod = gateway_module()
    fn = getattr(mod, "get_platform_config", get_platform_config)
    return fn()


def active_sandbox_mode() -> bool:
    """Resolves `sandbox_mode_active(get_platform_config())` via `app.main` when monkeypatched."""
    mod = gateway_module()
    fn = getattr(mod, "sandbox_mode_active", sandbox_mode_active)
    return bool(fn(active_platform_config()))


def routed_agent_binding_enabled() -> bool:
    """Returns True when routed `agent_id` binding is enabled on context tokens (ADR-0016)."""
    return flag_enabled("CONTEXT_TOKEN_BIND_AGENT_ID") or agent_id_required()


RUNTIME_STATUS = validate_runtime_environment()
CONTEXT_TOKEN_ISSUER = get_context_token_issuer()
EDGE_VERIFIER = EdgeAuthVerifier(context_issuer=CONTEXT_TOKEN_ISSUER)
REGISTRY_PDP = AgentRegistryPDP()
OTEL_SINK = OTelAuditSink()
DB_POOL = build_rls_db_pool_from_env()
_CACHED_RLS_POSTURE: tuple[int, dict[str, Any]] | None = None
MEMORY_BANK = MemoryBankPartitioner()
TOKEN_BULKHEAD = build_bulkhead_from_env()
MODEL_ROUTING_PDP = SharedModelRoutingPDP()
SANDBOX_MANAGER = sandbox_execution.GeminiAgentSandboxManager(
    backend=LiveGeminiAgentSandboxClient(),
    registry_pdp=REGISTRY_PDP,
)
TURN_SERVICES = TurnServices(
    registry_pdp=REGISTRY_PDP,
    otel_sink=OTEL_SINK,
    memory_bank=MEMORY_BANK,
    model_routing_pdp=MODEL_ROUTING_PDP,
    db_pool=DB_POOL,
    sandbox_mode_active=active_sandbox_mode,
    sandbox_manager=SANDBOX_MANAGER,
)
REMOTE_RUNTIME = RemoteRuntimeClient.from_env()
require_caller = make_require_caller(EDGE_VERIFIER)
if get_platform_config().identity.gateway_signing_secret:
    get_token_service()
Caller = Annotated[ContextEnvelope, Depends(require_caller)]
OptionalCaller = Annotated[
    ContextEnvelope, Depends(make_optional_caller(EDGE_VERIFIER))
]
CONTEXT_KEY_WARMER = ContextKeyWarmer(get_context_verifier)

_TOOL_OUTPUT_TOKEN_ALLOWANCE = 2000
_ERROR_CODE_RE = re.compile(r"\b(E_[A-Z0-9_]+)\b")


def stripped_header_names(headers: Any) -> list[str]:
    """Returns sorted untrusted client header names stripped at Hop 1."""
    raw = {str(key): str(val) for key, val in dict(headers).items()}
    return sorted(set(raw) - set(EdgeAuthVerifier.strip_untrusted_headers(raw)))


def metering(req: InvokeAgentRequest) -> tuple[int, bool]:
    """Computes server-side token estimate and prefix-cache flag for rate limiting and billing."""
    if isinstance(req, ScenarioTurn):
        return req.estimated_total_tokens, req.prompt_cache_hit
    prompt_tokens = len(req.prompt.encode("utf-8")) // 4 + 1
    sandbox_tokens = (
        len(req.sandbox_code.encode("utf-8")) // 4 + 1
        if req.sandbox_code
        else 0
    )
    allowance = int(
        getattr(
            gateway_module(),
            "_TOOL_OUTPUT_TOKEN_ALLOWANCE",
            _TOOL_OUTPUT_TOKEN_ALLOWANCE,
        )
    )
    return (
        prompt_tokens
        + sandbox_tokens
        + req.requested_thinking_tokens
        + allowance,
        False,
    )


def sandbox_only() -> None:
    """FastAPI dependency returning 404 outside the synthetic sandbox environment."""
    if not active_sandbox_mode():
        raise HTTPException(status_code=404, detail="Not found")


def public_error_code(exc: BaseException) -> str:
    """Extracts the stable `E_*` error code from a PEP exception without leaking internals."""
    match = _ERROR_CODE_RE.search(str(exc))
    return match.group(1) if match else "E_REQUEST_BLOCKED"


SandboxOnly = [Depends(sandbox_only)]
