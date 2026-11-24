# ADR-0015: Model Routing Shared Map and First Move (Track 1 Harness Optimization + Track 2 Guarded Router)

- **Status**: Accepted
- **Date**: 2026-11-03
- **Governance Pillar / Hop**: Pillar 3: Compute, Model Routing & FinOps (Hop 3)
- **Implementation**:
  [`agents/model_routing.py`](../../agents/model_routing.py),
  [`app/main.py`](../../app/main.py)

---

## 1. Context and Problem Statement

Multi-tenant Agent-as-a-Service (AaaS) platforms face a compounding cost and
latency problem when every turn in a multi-step tool loop runs on a frontier
reasoning model (`gemini-2.5-pro` or `claude-3-7-sonnet@20250219`) with the full
enterprise tool catalog attached:

1.  **Tool-Schema Token Overhead**: Passing all mutating and read-only tool
    schemas (`2,200` tokens) and sub-agent instructions on simple read-only
    telemetry lookups inflates input tokens and increases time-to-first-token
    (TTFT).
1.  **Whole-Turn Model Over-Provisioning**: Most turns in an incident triage
    workflow are read-only telemetry queries or runbook lookups that
    `gemini-2.5-flash` executes accurately at roughly `8.3x` lower per-token
    input cost than `gemini-2.5-pro`, yet static agent bindings force every step
    onto the higher-cost model.
1.  **Cross-Family Session Bleed**: When an enterprise tenant (`FinVault Bank`)
    switches between `claude-3-7-sonnet@20250219` (on
    `finvault_regulatory_escalation_agent`) and `gemini-2.5-pro`/`flash` (on
    `cymbal_shared_diagnostic_agent`) within a session, raw `<thought>` or
    `<thinking>` blocks from one model family can cause schema errors or
    reasoning drift in the other, and underlying model switches risk overwriting
    the signed `agent_id`.
1.  **Opaque FinOps Value**: Platform operators and tenant administrators need a
    customer-visible ledger showing how many tokens and relative inference spend
    model routing and harness trimming saved per tenant, without leaking
    telemetry across tenants.

---

## 2. Decision: Two-Track Model Routing Architecture at Hop 3

We adopt the **Shared Map and First Move** architecture inside
[`agents/model_routing.py`](../../agents/model_routing.py)
(`SharedModelRoutingPDP`) and wire it into Hop 3 of `POST /api/v1/invoke-agent`
as well as three dedicated Hop 0/1 DPoP-authenticated endpoints
(`POST /api/v1/model-routing/decide`,
`POST /api/v1/model-routing/escalate-askpro`, and
`GET /api/v1/model-routing/telemetry`):

### 2.1 Track 1 (The Shared First Move): Task-Aware Routing and `FastSearch` Harness Trimming

- **`FastSearchHarnessTrimmer`**: Classifies incoming turns into
  `FAST_SEARCH_LOOKUP`, `STANDARD_DIAGNOSTIC`, or `REGULATORY_ESCALATION`.
- When a turn is classified as `FAST_SEARCH_LOOKUP`, Hop 3 routes execution to
  `gemini-2.5-flash`, trims `active_tools` to the read-only search allowlist
  (`query_telemetry_rls`, `read_runbook`, `read_sharepoint_runbook`), disables
  specialist sub-agent delegation (`allow_subagent_delegation=False`), clamps
  thinking budget to `2,048` tokens, and saves `1,400` tool-schema tokens per
  turn while preserving the shared `32,000`-token `READ_ONLY_IMMUTABLE_PREFIX`.

### 2.2 Mid-Task Escalation (`AskPro` Advisor Pattern)

- Instead of transferring an entire multi-turn conversation to `gemini-2.5-pro`,
  `gemini-2.5-flash` remains the primary session executor.
- When the executor encounters ambiguous evidence or a tool retry
  (`escalation_reason` in
  `{"tool_error_retry", "ambiguous_evidence", "complex_synthesis"}`), it invokes
  `SharedModelRoutingPDP.escalate_to_advisor()`, which sends a compact evidence
  digest to `gemini-2.5-pro`.
- Consultations are strictly bounded to `max_advisor_consultations_per_turn = 1`
  per `(tenant_id, trace_id)`; a second escalation attempt in the same turn
  fails closed with `HTTP 429 E_ASKPRO_CONSULTATION_CAP_EXCEEDED`.

### 2.3 Cross-Family Session Sanitizer (`CrossFamilySessionSanitizer`)

- Before dispatching a turn across distinct model families (`claude`
  $\leftrightarrow$ `gemini`), `sanitize_history_for_target_model()` strips raw
  `<thought>...</thought>` and `<thinking>...</thinking>` blocks from prior
  turns while preserving intra-family history unchanged.
- Verifies that `temp:tenant_id` and `temp:agent_id` in session state match the
  verified `ContextEnvelope` and target agent, raising `PermissionError`
  (`E_CROSS_TENANT_SESSION_STATE` or `E_AGENT_IDENTITY_DRIFT`) on any mismatch.

### 2.4 Track 2 Integration Boundary and Glass-Box Savings Ledger (`GlassBoxRoutingSavingsLedger`)

- Adaptive bandit routing (`ADAPTIVE_BANDIT_GUARDED`, integrating
  `Workstream 1 modelrouter`) is gated to Enterprise-tier tenants
  (`403 E_ROUTING_MODE_FORBIDDEN` for Standard tier) and enforces the three
  multi-tenant preconditions documented in
  [ADR-0012](0012-compute-sandbox-scale-and-workstream-alignment.md)
  (`SEMANTIC_CACHE_ENABLED=false` or `tenant_id`-partitioned cache keys,
  `verify_google_jwt` / Hop 0 allowlist, and `TokenBucketBulkhead` rate
  limiting).
- Every routing decision and `AskPro` escalation updates
  `GlassBoxRoutingSavingsLedger`, which is registered with
  `register_tenant_eviction_target()` so `offboard_tenant(tenant_id)`
  immediately purges cached routing policies, active turn counters, and ledger
  entries.
