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

# pylint: disable=inconsistent-quotes,line-too-long

"""Pooled Tier 'What Breaks at 2 AM' Resilience Guards & Open Agentic Standards (`ADR-0008`).

Implements the operational resilience controls and open standards defined in the Multi-Tenant
Agentic AI Pooled Blueprint (Part 1 & Part 2):
1. **Control Plane 2 AM Guards (`ControlPlaneResilienceGuard`)**:
   - Immediate cache invalidation on tenant tier downgrade (preventing stale Enterprise access).
   - Fail-closed rejection when the Control Plane Agent Registry is unreachable.
2. **Compute Plane 2 AM Guards (`ComputePlane2AMGuard`)**:
   - Mid-turn A2A delegation token expiration enforcement & recursive sub-agent spawn depth cap.
   - Redis real-time token bucket vs. BigQuery billing truth drift reconciliation.
3. **Data Plane 3-Hop Substrate-Agnostic Adapter & MCP Conditional Policy
   (`SubstrateAgnostic3HopAdapter`, `MCPConditionalPerimeterGuard`)**:
   - Unified tenant claim propagation across AlloyDB/Cloud SQL (`SET LOCAL`), Cloud Spanner
     (`request.tag`),
     Cloud Firestore (`/tenants/{tenant_id}/documents/`), and BigQuery (`ROW ACCESS POLICY`).
   - Perimeter conditional rules on `mcp.toolName`, `mcp.method`, and `mcp.tool.isReadOnly` + MCP
     circuit breaker.
4. **Cross-Plane Observability & Open Standards (`ObservabilityCardinalityGuard`,
   `OKFKnowledgeVerifier`, `A2UITenantCardBuilder`)**:
   - High-cardinality `user_id` metric scrubbing to prevent trace cardinality explosion.
   - Open Knowledge Format (`OKF v0.2`) provenance, staleness TTL, and SHA-256 digest attestation.
   - Declarative `A2UI` (`a2ui/v1`) tenant-safe UI card generation with XSS sanitization.
"""

from __future__ import annotations

import dataclasses
import hashlib
import html
import json
import pathlib
import re
import time
from typing import Any

from agents.context import ContextEnvelope, SubscriptionTier
from agents.platform_config import get_platform_config

SAFE_TENANT_RE = re.compile(r"^tenant-[a-z0-9-]+$")
SAFE_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_-]{1,62}$")
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


class ControlPlaneResilienceGuard:
    """Protects the Control Plane against Registry cache staleness on tier downgrade & Registry
    outages.
    """

    def __init__(self) -> None:
        self._registry_healthy: bool = True
        self._tenant_tiers: dict[str, SubscriptionTier] = {
            "tenant-finvault-alpha": SubscriptionTier.ENTERPRISE,
            "tenant-retailstream-beta": SubscriptionTier.STANDARD,
        }
        self._tier_epochs: dict[str, int] = {
            "tenant-finvault-alpha": 1,
            "tenant-retailstream-beta": 1,
        }
        self._cached_entitlements: dict[str, tuple[int, list[str]]] = {}

    def set_registry_health(self, *, healthy: bool) -> None:
        self._registry_healthy = healthy

    def get_entitled_agents(self, *, tenant_id: str) -> list[str]:
        """Consults the Control Plane Registry PDP; fails closed if unreachable or if tier epoch
        changed.
        """
        if not self._registry_healthy:
            raise PermissionError(
                "503 E_CONTROL_PLANE_REGISTRY_UNAVAILABLE_FAIL_CLOSED: Control Plane Agent "
                "Registry is unreachable; Compute Plane fails closed (zero default-allow)."
            )
        current_epoch = self._tier_epochs.get(tenant_id, 1)
        cached = self._cached_entitlements.get(tenant_id)
        if cached and cached[0] == current_epoch:
            return list(cached[1])

        tier = self._tenant_tiers.get(tenant_id, SubscriptionTier.STANDARD)
        agents = ["cymbal_shared_diagnostic_agent"]
        if (
            tier == SubscriptionTier.ENTERPRISE
            and tenant_id == "tenant-finvault-alpha"
        ):
            agents.append("finvault_regulatory_escalation_agent")

        self._cached_entitlements[tenant_id] = (current_epoch, agents)
        return list(agents)

    def update_tenant_tier(
        self, *, tenant_id: str, new_tier: SubscriptionTier
    ) -> int:
        """Atomically updates a tenant's tier and increments its epoch to invalidate stale compute
        caches.
        """
        self._tenant_tiers[tenant_id] = new_tier
        new_epoch = self._tier_epochs.get(tenant_id, 1) + 1
        self._tier_epochs[tenant_id] = new_epoch
        self._cached_entitlements.pop(tenant_id, None)
        return new_epoch


class ComputePlane2AMGuard:
    """Protects the Compute Plane against mid-turn A2A expiration, recursive sub-agents & Redis/BQ
    drift.
    """

    MAX_SUBAGENT_DEPTH = 3

    @classmethod
    def verify_a2a_subagent_hop(
        cls,
        *,
        parent_envelope: ContextEnvelope,
        delegation_exp_epoch: int,
        current_depth: int,
        now_epoch: float | None = None,
    ) -> dict[str, Any]:
        """Enforces A2A mid-turn token expiration and prevents recursive sub-agent sandbox
        exhaustion.
        """
        now = now_epoch if now_epoch is not None else time.time()
        if now >= delegation_exp_epoch:
            raise PermissionError(
                "401 E_A2A_DELEGATION_EXPIRED_MID_TURN: A2A sub-agent delegation token expired "
                "mid-turn; halting child agent invocation."
            )
        if current_depth > cls.MAX_SUBAGENT_DEPTH:
            raise PermissionError(
                f"429 E_SUBAGENT_SPAWN_DEPTH_EXCEEDED: Sub-agent depth ({current_depth}) exceeds "
                f"sandbox limit ({cls.MAX_SUBAGENT_DEPTH})."
            )
        return {
            "temp:tenant_id": parent_envelope.tenant.tenant_id,
            "temp:subscription_tier": str(
                parent_envelope.tenant.subscription_tier
            ),
            "temp:trace_id": parent_envelope.request.trace_id,
            "a2a_depth": current_depth,
            "verified_at": now,
        }

    @staticmethod
    def reconcile_redis_with_bigquery_truth(
        *,
        tenant_id: str,
        redis_consumed_tokens: int,
        bigquery_billed_tokens: int,
        tier_tpm_limit: int,
    ) -> dict[str, int | bool | str]:
        """Reconciles Redis real-time token counters with BigQuery billing truth to fix export lag
        desync.
        """
        authoritative_used = max(redis_consumed_tokens, bigquery_billed_tokens)
        drift_tokens = abs(bigquery_billed_tokens - redis_consumed_tokens)
        remaining_budget = max(0, tier_tpm_limit - authoritative_used)
        return {
            "tenant_id": tenant_id,
            "authoritative_consumed_tokens": authoritative_used,
            "drift_corrected_tokens": drift_tokens,
            "remaining_tpm_budget": remaining_budget,
            "quota_exhausted": remaining_budget == 0,
        }


class SubstrateAgnostic3HopAdapter:
    """Generates fail-closed 3-hop tenant RLS & user/agent RBAC predicates across AlloyDB,
    Spanner, Firestore & BigQuery.
    """

    @staticmethod
    def build_substrate_binding(
        *,
        envelope: ContextEnvelope,
        substrate: str,
        agent_id: str = "sre_diagnostic_agent",
    ) -> dict[str, str]:
        tenant_id = envelope.tenant.tenant_id
        user_role = getattr(envelope.security, "user_role", "sre_admin")
        if not SAFE_TENANT_RE.match(tenant_id):
            raise PermissionError(f"Invalid tenant_id format: {tenant_id}")
        if not SAFE_IDENTIFIER_RE.match(user_role):
            raise PermissionError(f"Invalid user_role format: {user_role}")
        if not SAFE_IDENTIFIER_RE.match(agent_id):
            raise PermissionError(f"Invalid agent_id format: {agent_id}")

        if substrate == "alloydb_postgresql":
            return {
                "substrate": "alloydb_postgresql",
                "hop3_statement": (
                    f"SET LOCAL app.current_tenant_id = '{tenant_id}'; "
                    f"SET LOCAL app.current_user_role = '{user_role}'; "
                    f"SET LOCAL app.current_agent_id = '{agent_id}';"
                ),
                "policy_ddl": (
                    "CREATE POLICY tenant_isolation ON tenant_incidents "
                    "USING (NULLIF(current_setting('app.current_tenant_id', true), '') IS NOT NULL "
                    "AND tenant_id = current_setting('app.current_tenant_id', true) "
                    "AND NULLIF(current_setting('app.current_user_role', true), '') IS NOT NULL "
                    "AND current_setting('app.current_user_role', true) IN "
                    "('sre_admin', 'compliance_officer', 'read_only_analyst', "
                    "'incident_responder') "
                    "AND NULLIF(current_setting('app.current_agent_id', true), '') IS NOT NULL "
                    "AND current_setting('app.current_agent_id', true) IN "
                    "('cymbal_shared_diagnostic_agent', "
                    "'finvault_regulatory_escalation_agent', 'sre_diagnostic_agent'));"
                ),
            }
        if substrate == "cloud_spanner":
            return {
                "substrate": "cloud_spanner",
                "hop3_statement": (
                    f"request.tag='tenant_id={tenant_id}', role='{user_role}', agent='{agent_id}'"
                ),
                "policy_ddl": (
                    "CREATE OR REPLACE VIEW v_tenant_incidents SQL SECURITY DEFINER AS "
                    "SELECT incident_id, tenant_id, service_name, severity, summary "
                    f"FROM tenant_incidents WHERE tenant_id = '{tenant_id}'; "
                    f"GRANT SELECT ON VIEW v_tenant_incidents TO ROLE pooled_agent_{user_role};"
                ),
            }
        if substrate == "cloud_firestore":
            return {
                "substrate": "cloud_firestore",
                "hop3_statement": f"/tenants/{tenant_id}/documents/incidents",
                "policy_ddl": (
                    f"match /tenants/{{tenantId}}/documents/{{doc=**}} {{ "
                    f"allow read: if request.auth.token.tenant_id == '{tenant_id}' "
                    f"&& request.auth.token.role == '{user_role}' "
                    f"&& request.auth.token.agent_id == '{agent_id}'; }}"
                ),
            }
        if substrate == "bigquery_rap":
            return {
                "substrate": "bigquery_rap",
                "hop3_statement": (
                    "SELECT * FROM `cymbal_agent_analytics.tenant_otel_spans` WHERE tenant_id = '"
                    f"{tenant_id}'"
                ),
                "policy_ddl": (
                    f"CREATE OR REPLACE ROW ACCESS POLICY rap_{tenant_id.replace('-', '_')} "
                    f"ON `cymbal_agent_analytics.tenant_otel_spans` "
                    "GRANT TO ('group:"
                    f"{user_role}"
                    "@cymbal.example', 'serviceAccount:"
                    f"{agent_id}"
                    "@cymbal.example') "
                    f"FILTER USING (tenant_id = '{tenant_id}');"
                ),
            }
        raise ValueError(f"Unsupported data substrate: {substrate}")


class MCPConditionalPerimeterGuard:
    """Enforces perimeter conditional rules (`mcp.toolName`, `mcp.method`, `mcp.tool.isReadOnly`)
    & circuit breaking.
    """

    def __init__(self) -> None:
        self._circuit_open_servers: set[str] = set()

    def set_mcp_server_circuit(self, *, server_id: str, is_open: bool) -> None:
        if is_open:
            self._circuit_open_servers.add(server_id)
        else:
            self._circuit_open_servers.discard(server_id)

    def evaluate_mcp_call(
        self,
        *,
        envelope: ContextEnvelope,
        server_id: str,
        mcp_tool_name: str,
        mcp_method: str,
        is_read_only: bool,
        allow_mutations_for_standard_tier: bool = False,
    ) -> dict[str, Any]:
        if server_id in self._circuit_open_servers:
            raise PermissionError(
                f"503 E_MCP_SERVER_CIRCUIT_OPEN: MCP server '{server_id}' circuit breaker is OPEN; "
                "returning graceful degradation fallback."
            )
        if mcp_method != "tools/call":
            raise PermissionError(
                f"403 E_MCP_METHOD_DENIED: Disallowed MCP method '{mcp_method}'."
            )
        if (
            envelope.tenant.subscription_tier == SubscriptionTier.STANDARD
            and not is_read_only
            and not allow_mutations_for_standard_tier
        ):
            raise PermissionError(
                f"403 E_MCP_CONDITIONAL_READONLY_POLICY: Standard tier tenant "
                f"'{envelope.tenant.tenant_id}' is restricted to mcp.tool.isReadOnly=true "
                f"(blocked mutating tool '{mcp_tool_name}')."
            )
        return {
            "status": "MCP_PERIMETER_ALLOWED",
            "tenant_id": envelope.tenant.tenant_id,
            "mcp.toolName": mcp_tool_name,
            "mcp.method": mcp_method,
            "mcp.tool.isReadOnly": is_read_only,
        }


@dataclasses.dataclass(frozen=True)
class OKFKnowledgeArtifact:
    """Open Knowledge Format (OKF v0.2) attested knowledge artifact."""

    okf_version: str
    document_id: str
    tenant_id: str
    trust_tier: str
    published_at_epoch: float
    freshness_ttl_seconds: int
    content: str
    sha256_digest: str


class OKFKnowledgeVerifier:
    """Verifies Open Knowledge Format (OKF v0.2) provenance, tenant ownership, staleness TTL &
    digest.
    """

    @staticmethod
    def create_attested_artifact(
        *,
        document_id: str,
        tenant_id: str,
        content: str,
        freshness_ttl_seconds: int = 3600,
        trust_tier: str = "VERIFIED_TENANT_RUNBOOK",
        published_at_epoch: float | None = None,
    ) -> OKFKnowledgeArtifact:
        pub = (
            published_at_epoch
            if published_at_epoch is not None
            else time.time()
        )
        digest = hashlib.sha256(
            f"{tenant_id}|{document_id}|{content}".encode()
        ).hexdigest()
        return OKFKnowledgeArtifact(
            okf_version="0.2",
            document_id=document_id,
            tenant_id=tenant_id,
            trust_tier=trust_tier,
            published_at_epoch=pub,
            freshness_ttl_seconds=freshness_ttl_seconds,
            content=content,
            sha256_digest=digest,
        )

    @staticmethod
    def verify_for_tenant(
        *,
        artifact: OKFKnowledgeArtifact,
        envelope: ContextEnvelope,
        now_epoch: float | None = None,
    ) -> dict[str, str]:
        now = now_epoch if now_epoch is not None else time.time()
        if artifact.okf_version != "0.2":
            raise PermissionError(
                f"E_OKF_UNSUPPORTED_VERSION: {artifact.okf_version}"
            )
        if artifact.tenant_id not in (envelope.tenant.tenant_id, "global"):
            raise PermissionError(
                "403 E_OKF_CROSS_TENANT_PROVENANCE: the artifact does not belong to the calling "
                "tenant."
            )
        expected_digest = hashlib.sha256(
            f"{artifact.tenant_id}|{artifact.document_id}|{artifact.content}".encode()
        ).hexdigest()
        if artifact.sha256_digest != expected_digest:
            raise PermissionError(
                "E_OKF_DIGEST_TAMPERED: Knowledge artifact SHA-256 mismatch."
            )
        if now - artifact.published_at_epoch > artifact.freshness_ttl_seconds:
            raise PermissionError(
                f"E_OKF_ARTIFACT_STALE: Knowledge artifact '{artifact.document_id}' exceeded "
                f"freshness TTL ({artifact.freshness_ttl_seconds}s)."
            )
        return {
            "okf_version": artifact.okf_version,
            "document_id": artifact.document_id,
            "tenant_id": artifact.tenant_id,
            "trust_tier": artifact.trust_tier,
            "verified_digest": artifact.sha256_digest,
        }


class ObservabilityCardinalityGuard:
    """Prevents 2 AM trace/metric cardinality explosion by scrubbing raw `user_id` from metric
    tags.
    """

    MANDATORY_LOW_CARDINALITY_KEYS = (
        "tenant_id",
        "agent_id",
        "tool_name",
        "model_id",
    )

    @classmethod
    def sanitize_otel_metric_attributes(
        cls, raw_attrs: dict[str, Any]
    ) -> dict[str, str]:
        for req_key in cls.MANDATORY_LOW_CARDINALITY_KEYS:
            if not raw_attrs.get(req_key):
                raise ValueError(f"Missing mandatory OTel attribute: {req_key}")

        sanitized: dict[str, str] = {
            k: str(raw_attrs[k]) for k in cls.MANDATORY_LOW_CARDINALITY_KEYS
        }
        # Hash high-cardinality user_id into a bounded 8-hex correlation bucket for trace linking
        # only
        if "user_id" in raw_attrs:
            uid_hash = hashlib.sha256(
                str(raw_attrs["user_id"]).encode()
            ).hexdigest()[:8]
            sanitized["user_hash_bucket"] = uid_hash
        return sanitized


class A2UITenantCardBuilder:
    """Builds declarative `a2ui/v1` UI components with strict tenant scoping and XSS escaping."""

    @staticmethod
    def build_diagnostic_card(
        *,
        envelope: ContextEnvelope,
        title: str,
        incident_id: str,
        summary: str,
    ) -> dict[str, Any]:
        return {
            "protocol": "a2ui/v1",
            "tenant_id": envelope.tenant.tenant_id,
            "subscription_tier": str(envelope.tenant.subscription_tier),
            "component": "DiagnosticIncidentCard",
            "props": {
                "title": html.escape(title, quote=True),
                "incident_id": html.escape(incident_id, quote=True),
                "summary": html.escape(summary, quote=True),
            },
        }


class DynamicModelTierRouter:
    """Blog Section 3: Intelligent Dynamic Model Tiering across Flash, Pro, Claude & Gemma 3."""

    ROUTINE_SUBTASKS = frozenset(
        {"intent_classification", "schema_formatting", "intent_parsing"}
    )

    @classmethod
    def route_model(
        cls,
        *,
        envelope: ContextEnvelope,
        task_type: str,
        sovereign_open_weight_required: bool = False,
    ) -> dict[str, Any]:
        """Routes routine tasks to lightweight Flash/Gemma 3 and complex synthesis to
        tier-entitled Pro/Claude.
        """
        model_cfg = get_platform_config().models
        if sovereign_open_weight_required:
            return {
                "selected_model": model_cfg.sovereign_open_weight_model,
                "hosting": "gke-vllm-sovereign",
                "routing_reason": "Sovereign open-weight mandate (Gemma 3 on GKE vLLM).",
                "relative_cost_multiplier": 0.15,
            }
        if task_type in cls.ROUTINE_SUBTASKS:
            return {
                "selected_model": model_cfg.default_executor_model,
                "hosting": "vertex-ai-pooled",
                "routing_reason": f"Routine sub-task '{task_type}' routed to fast Hydrogen tier.",
                "relative_cost_multiplier": 0.10,
            }
        if envelope.tenant.subscription_tier == SubscriptionTier.ENTERPRISE:
            return {
                "selected_model": model_cfg.default_shared_model,
                "hosting": "vertex-ai-pooled",
                "routing_reason": (
                    "Complex multi-step synthesis for Enterprise tier (8,000 thinking budget)."
                ),
                "relative_cost_multiplier": 0.75,
            }
        return {
            "selected_model": model_cfg.default_executor_model,
            "hosting": "vertex-ai-pooled",
            "routing_reason": "Standard tier synthesis capped to Hydrogen (4,000 thinking budget).",
            "relative_cost_multiplier": 0.10,
        }


class AgentPluginLoader:
    """Blog Section 9: Loads portable Agent Plugins (`plugin.json`, `mcp.json`, `skills/`)."""

    @staticmethod
    def load_plugin_for_tenant(
        *,
        envelope: ContextEnvelope,
        plugin_dir: pathlib.Path | None = None,
    ) -> dict[str, Any]:
        target_dir = plugin_dir or (
            REPO_ROOT / "plugins" / "cymbal-sre-diagnostics"
        )
        plugin_meta = json.loads(
            (target_dir / "plugin.json").read_text(encoding="utf-8")
        )
        mcp_meta = json.loads(
            (target_dir / plugin_meta["mcp_config"]).read_text(encoding="utf-8")
        )
        skills_dir = target_dir / plugin_meta["skills_dir"]
        skill_files = sorted(
            str(p.relative_to(target_dir)) for p in skills_dir.rglob("SKILL.md")
        )

        tier_str = str(envelope.tenant.subscription_tier)
        entitled_mcp_tools: list[dict[str, Any]] = []
        for server_name, server_cfg in mcp_meta.get("mcpServers", {}).items():
            for tool in server_cfg.get("tools", []):
                if tier_str not in tool.get("allowed_tiers", []):
                    continue
                req_conn = tool.get("required_connector")
                if (
                    req_conn == "jira_3lo_finvault"
                    and envelope.tenant.tenant_id != "tenant-finvault-alpha"
                ):
                    continue
                if (
                    req_conn == "servicenow_3lo_retailstream"
                    and envelope.tenant.tenant_id != "tenant-retailstream-beta"
                ):
                    continue
                entitled_mcp_tools.append(
                    {
                        "server": server_name,
                        "name": tool["name"],
                        "method": tool["method"],
                        "isReadOnly": tool["isReadOnly"],
                    }
                )

        return {
            "plugin_name": plugin_meta["name"],
            "version": plugin_meta["version"],
            "tenant_id": envelope.tenant.tenant_id,
            "tier": tier_str,
            "skills": skill_files,
            "entitled_mcp_tools": entitled_mcp_tools,
        }


class A2AAgentCardRegistry:
    """Blog Section 1 & 9: Serves A2A-compatible Agent Cards (`/.well-known/agent.json`) with
    version pins.
    """

    @staticmethod
    def build_a2a_agent_cards(*, envelope: ContextEnvelope) -> dict[str, Any]:
        plugin_bundle = AgentPluginLoader.load_plugin_for_tenant(
            envelope=envelope
        )
        cards = [
            {
                "protocol": "a2a/v1",
                "agent_id": "cymbal_shared_diagnostic_agent",
                "version_pin": "2.1.0",
                "display_name": "Cymbal Shared Incident Diagnostic Agent",
                "tenant_scope": envelope.tenant.tenant_id,
                "subscription_tier": str(envelope.tenant.subscription_tier),
                "thinking_tokens_budget": envelope.tenant.thinking_token_budget,
                "requires_obo_dpop": True,
                "allowlisted_tools": [
                    t["name"] for t in plugin_bundle["entitled_mcp_tools"]
                ],
            }
        ]
        if (
            envelope.tenant.subscription_tier == SubscriptionTier.ENTERPRISE
            and envelope.tenant.tenant_id == "tenant-finvault-alpha"
        ):
            cards.append(
                {
                    "protocol": "a2a/v1",
                    "agent_id": "finvault_regulatory_escalation_agent",
                    "version_pin": "1.4.2",
                    "display_name": "FinVault Private Regulatory Escalation Agent (Agent Alpha)",
                    "tenant_scope": "tenant-finvault-alpha",
                    "subscription_tier": "enterprise",
                    "thinking_tokens_budget": 8000,
                    "requires_obo_dpop": True,
                    "allowlisted_tools": [
                        "query_telemetry_rls",
                        "read_runbook",
                        "create_jira_incident",
                        "escalate_regulatory_filing",
                    ],
                }
            )
        return {
            "a2a_DiscoveryVersion": "1.0",
            "tenant_id": envelope.tenant.tenant_id,
            "agent_cards": cards,
        }
