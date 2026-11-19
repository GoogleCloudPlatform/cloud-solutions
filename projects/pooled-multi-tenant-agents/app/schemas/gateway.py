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

"""Pydantic v2 request schemas (`extra='forbid'`) for the Cymbal multi-tenant gateway."""

from __future__ import annotations

from typing import Literal

from agents import sandbox_execution
from agents.model_routing import ModelRoutingMode
from pydantic import BaseModel, Field


class InvokeAgentRequest(BaseModel):
    """What the caller wants done. Who the caller is comes only from the verified gateway token
    (`Authorization: DPoP ...`); identity fields in the body are rejected (422).
    """

    model_config = {"extra": "forbid"}

    agent_id: str = Field(default="cymbal_shared_diagnostic_agent")
    prompt: str = Field(
        default="Correlate P1 production incidents and redact any customer PII.",
        max_length=16000,  # also keeps prompts within the Model Armor request size
    )
    tool_name: str = Field(default="query_telemetry_rls")
    requested_thinking_tokens: int = Field(default=4000, ge=0)
    raw_sql_override: str | None = Field(default=None)
    live_cloud: bool = Field(
        default=False,
        description=(
            "When True, executes real live GCP (Model Armor, KMS, DLP, Firestore, BigQuery) "
            "& 3P (Jira, ServiceNow, Entra ID) calls across all 5 Hops."
        ),
    )
    sandbox_code: str | None = Field(
        default=None,
        max_length=sandbox_execution.MAX_SANDBOX_CODE_CHARS,
        description=(
            "Optional diagnostic snippet or command executed out-of-process in a session-tainted "
            "Agent Sandbox in Gemini (`sandboxEnvironments`) with zero mounted credentials."
        ),
    )
    sandbox_language: Literal["python", "javascript", "bash"] = Field(
        default="python"
    )


class ScenarioTurn(InvokeAgentRequest):
    """SANDBOX-ONLY scripted turn: the server plays a synthetic persona (demo scenarios)."""

    authenticated_tenant_id: str = "tenant-finvault-alpha"
    # Scripted demos may stage token counts (e.g. the noisy-neighbour burst); real callers can't.
    estimated_total_tokens: int = Field(default=10000)
    prompt_cache_hit: bool = Field(default=True)
    idp_issuer: str | None = None
    user_sub: str = "alice@finvault.com"
    user_role: str = "sre_admin"
    spoofed_headers: dict[str, str] = Field(default_factory=dict)


class SandboxTokenRequest(BaseModel):
    """Synthetic user to mint a sandbox ID token for (sandbox environment only)."""

    model_config = {"extra": "forbid"}

    tenant_id: str = Field(min_length=3, max_length=63, pattern=r"^[a-z0-9-]+$")
    sub: str = Field(min_length=1, max_length=128)
    role: Literal["sre_admin", "compliance_officer", "read_only_analyst"] = (
        "read_only_analyst"
    )


class TokenExchangeRequest(BaseModel):
    """RFC 8693-style exchange: a verified IdP ID token for a DPoP-bound gateway token."""

    model_config = {"extra": "forbid"}

    subject_token: str = Field(min_length=1, max_length=16384)
    subject_token_type: Literal["urn:ietf:params:oauth:token-type:id_token"] = (
        "urn:ietf:params:oauth:token-type:id_token"
    )


class SandboxSessionActionRequest(BaseModel):
    """Lifecycle control request for the caller session's tainted Gemini `SandboxEnvironment`."""

    model_config = {"extra": "forbid"}

    agent_id: str = Field(
        default="cymbal_shared_diagnostic_agent",
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9_]+$",
    )
    language: Literal["python", "javascript", "bash"] | None = None


class ModelRoutingDecideRequest(BaseModel):
    """Request payload for Hop 3 Model Routing and FastSearch harness-trimming evaluation."""

    model_config = {"extra": "forbid"}

    agent_id: str = Field(default="cymbal_shared_diagnostic_agent")
    tool_name: str = Field(default="query_telemetry_rls")
    prompt: str = Field(
        default="Lookup P1 latency telemetry and summarize incident runbook status.",
        max_length=16000,
    )
    requested_thinking_tokens: int = Field(default=4000, ge=0)
    routing_mode: ModelRoutingMode | None = Field(default=None)
    previous_model_id: str | None = Field(default=None)
    session_history: list[str] = Field(default_factory=list)


class AskProEscalationRequest(BaseModel):
    """Request payload for bounded mid-task escalation from Flash executor to Pro advisor."""

    model_config = {"extra": "forbid"}

    trace_id: str = Field(min_length=1, max_length=128)
    escalation_reason: Literal[
        "tool_error_retry", "ambiguous_evidence", "complex_synthesis"
    ] = Field(default="ambiguous_evidence")
    compact_evidence_digest: str = Field(min_length=1, max_length=8000)


class AgentSuspensionActionRequest(BaseModel):
    """Control-plane request to suspend or resume a catalog agent (`C17`)."""

    model_config = {"extra": "forbid"}

    agent_id: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z][a-z0-9_]{0,63}$",
    )
    reason: str = Field(default="operator_emergency_suspension", max_length=256)
