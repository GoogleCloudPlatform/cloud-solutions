# ADR-0013: Runtime Failure Mode Audit and Hardening Plan

- **Status**: Proposed (Updated per F1 Review)
- **Date**: 2026-10-30
- **Authors**: Google Cloud Solutions Architecture Team
- **Relates to**: `ADR-0009` (Hop 0 Federation & RFC 9449 Gateway Tokens),
  `ADR-0010` (Per-Tenant Service Account Blast Radius), `ADR-0011` (KMS v2
  Envelope Memory & RAG Quarantine), `ADR-0012` (Compute Scaling Gates & Model
  Router Preconditions), `docs/tenant_isolation_assurance.md`

## Context and Problem Statement

Pull Requests `#1` through `#21` (`freeze-f1` at `0bcfae5`) established the
5-Hop Cryptographic Context Chain: Hop 0 federated login and RFC 9449 DPoP
gateway tokens, per-tenant runtime service accounts, KMS v2 per-record envelope
encryption with `AAD = [v2, tenant, user, scope, key]`, leaf-level RAG
indirect-injection quarantine, MCP wire signature verification, and generic
caller-visible errors (`#18`, `#20`).

A code audit of `main` (`0bcfae5`; file:line citations refer to that commit
unless noted, and #25/#26 have since moved some code) identified **12 failure
modes (`FM-01` through `FM-12`)** across live GCP execution paths,
multi-instance state, token bulkheads, PostgreSQL extended-query SQL syntax, and
Terraform control-plane sync:

1.  **Scale-Out Gate (`FM-01`, P0 if `max_instance_count > 1`, P2 at
    single-instance `freeze-f1`)**:
    - `FM-01`: `_ReplayCache` and `_SubjectTokenBindings`
      (`app/gateway_tokens.py:119-202`) live in per-process memory, and
      `GatewayTokenService.verify_request()` (`app/gateway_tokens.py:266`, `kid`
      check at `:262`) checks a single `self.kid`. The sandbox is pinned to
      `max_instance_count = 1`, making shared Redis replay state and a `kid`
      ring the mandatory gate before horizontal scale-out.
1.  **Urgent Runtime, Bulkhead, SQL, and Guardrail Bugs (`FM-02`, `FM-03`,
    `FM-05`, `FM-06`, `FM-07`, `FM-10`, P1)**:
    - `FM-02`: `TokenBucketBulkhead.check_and_consume()`
      (`agents/auth/vault_and_bulkhead.py:296-306`) omits
      `"effective_thinking_tokens"`, causing `agents/turn_engine.py:393` to
      raise `KeyError` on every live turn (`CYMBAL_LIVE_GCP=1`) and skip
      BigQuery span export. The surrounding `except Exception:` block catches
      all errors (including `PermissionError`) and returns `HTTP 200 SUCCESS`.
    - `FM-03`: `enforce_tenant_isolation_interceptor`
      (`agents/interceptors.py:311-364`) reads `state["temp:authorized_scopes"]`
      without verifying `temp:obo_signature` first (defense-in-depth gap for
      in-process state mutation).
    - `FM-05`: `InvokeAgentRequest` accepted caller-supplied
      `estimated_total_tokens` and `prompt_cache_hit` (passing `0` bypassed the
      TPM bulkhead), `_execute_turn` omitted `session_id` at
      `app/api/v1/agents_and_sandboxes.py:266`, and `state.session_turns` grew
      without bound. _(Follow-up item: the per-session turn limit
      `max_turns_per_session` still does not fire for real callers because the
      gateway mints a new `session_id` per request; requires a stable
      `session_id` in the gateway token.)_
    - `FM-06`: `RLSDatabasePool.query_incidents` (`mcp_server/db.py:257`)
      executes `SET LOCAL app.current_tenant_id = $1;`, which PostgreSQL's
      extended query protocol rejects (`PostgresSyntaxError`; requires
      `SELECT set_config('app.current_tenant_id', $1, true);`), and
      `query_runbooks` (`mcp_server/db.py:294`) omits the
      `if self._pool is not None:` live branch.
    - `FM-07`: `LiveCloudDLPGuardrail.deidentify_tool_output`
      (`agents/adapters/guardrails.py:133`) hardcodes
      `tenant_id="tenant-finvault-alpha"`. _(Note: the 3LO owner leak and MCP
      `-32003` `str(exc)` leak were already closed in `#18`.)_
    - `FM-10`: `_try_live_vertex_model_armor` (`agents/interceptors.py:184-187`)
      permanently latches `_LIVE_MA_AVAILABLE = False` for the lifetime of the
      worker process after a single transient RPC error.
1.  **Step-3 Credential Broker, Offboarding, and Step-4 Terraform Items
    (`FM-04`, `FM-08`, `FM-09`, `FM-11`, `FM-12`, P1/P2)**:
    - `FM-04` (P1): `ContextEnvelope` uses a hardcoded symmetric HMAC key
      (`DEFAULT_PEP_SIGNING_SECRET`); moving to asymmetric `ES256` signing
      merges directly with the Step-3 Credential Broker (`#28`).
    - `FM-08` (P1): 60s DEK cache (`agents/memory_crypto.py:65`) and
      unsynchronized 240s SA token cache (`agents/tenant_credentials.py:264`)
      need an explicit `evict_tenant(tenant_id)` offboarding hook, and RAG
      `embedding` vectors sit in plaintext outside `SealedRecord`.
    - `FM-09` (P1): `LiveFirestoreMemoryBank` uses the shared runtime SA
      (`roles/datastore.user`) instead of per-tenant SA credentials + Firestore
      IAM conditions.
    - `FM-11` (P2): `_execute_turn` (`agents/turn_engine.py:269-289`) omitted
      `send_gmail_brief` and `read_sharepoint_runbook` tool dispatch and inline
      `verify_agent_output_deterministically()` checks.
    - `FM-12` (P2): `terraform/modules/tenant/main.tf:37-50` hardcodes two
      tenants instead of reading `config/tenants/*.yaml` via `fileset` +
      `yamldecode`.

## Decision Outcome

We align the remediation slices with the project roadmap (`PR-DA1` delivered
across **`#26`** core fixes and **`#25`** follow-up hardening, followed by the
scale-out gate, Step-3 Credential Broker in `#28`, offboarding, and Step-4
Terraform series):

| Slice                        | Roadmap Alignment                        | Failure Modes Closed                                                                   | Scope & Deliverables                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| :--------------------------- | :--------------------------------------- | :------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`PR-DA1` (`#26` + `#25`)** | **Merged (`freeze-f1` bugfix)**          | `FM-02`, `FM-03`, `FM-05`, `FM-06` (SQL), `FM-07`, `FM-10` (latch), `FM-11` (dispatch) | **`#26` (Core `DA1`)**: Return `effective_thinking_tokens` in `check_and_consume()`; verify `verify_signed_adk_state(state)` in `enforce_tenant_isolation_interceptor`; compute server-side `_metering(req)` in `app/main.py` (`len(prompt.encode()) // 4 + 1 + requested + 2000`), removing `estimated_total_tokens`/`prompt_cache_hit` from `InvokeAgentRequest` and forcing `cache_hit=False`; fix `SELECT set_config('app.current_tenant_id', $1, true)` in `query_incidents`; pass caller `tenant_id` in `LiveCloudDLPGuardrail`; replace sticky `_LIVE_MA_AVAILABLE = False` latch with `_LIVE_MA_RETRY_AT` / `LIVE_MA_RETRY_SECONDS` and fail-closed `4xx` (`E_MODEL_ARMOR_REQUEST_REJECTED`).; **`#25` (`DA1` Follow-Up)**: Fail closed on `live_cloud` step errors (`PermissionError` -> `403`, non-sandbox runtime errors -> `503 E_LIVE_GCP_STEP_FAILED`); add live `asyncpg` execution with `SELECT set_config(..., $1, true)` (`ORDER BY runbook_id`) to `query_runbooks`; dispatch `send_gmail_brief` and `read_sharepoint_runbook` in `_execute_turn`; pass `session_id` into `check_and_consume()` and cap `session_turns` at `MAX_TRACKED_SESSIONS = 4096`. |
| **`PR-DA2`**                 | **Pre-Scale-Out Gate**                   | `FM-01` + stable `session_id`                                                          | Shared Memorystore for Redis `_ReplayCache` and `_SubjectTokenBindings` (`SET key val NX EX ttl`), a 2-key `kid` verification ring in `GatewayTokenService.verify_request()`, and a stable `session_id` claim in the gateway token. _Status: partly landed in #29_ (replay and bulkhead store interfaces plus a gateway-token `session_id`). Still open: wiring Redis from config (fail startup without it when `max_instances > 1`), the `kid` ring, mapping Redis errors to 503, and keying the turn counter on the gateway token rather than the caller's `X-Session-ID` header so `max_turns_per_session` enforces across turns.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| **`PR-DA3` (`#28`)**         | **Merges with Step-3 Credential Broker** | `FM-04`                                                                                | Gateway signs `ContextEnvelope` (`typ: ctx+jwt`) with asymmetric `ES256`; Step-3 Broker, `verify_signed_adk_state`, and MCP server verify using only the public key.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| **`PR-DA4`**                 | **Merges with Tenant Offboarding**       | `FM-08`, `FM-06` (RLS posture)                                                         | Thread-safe `_TokenCache`, `evict_tenant(tenant_id)` across DEK and SA token caches, AEAD-sealed RAG embeddings, and startup `verify_live_rls_posture()`. (#30 is separate: per-event-loop pool and KMS verify-cache mechanisms, not yet wired in; it does not implement DA4.)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| **`PR-DA5` & `PR-DA6`**      | **Merges with Step-4 Terraform Series**  | `FM-09`, `FM-10` (Base64 screen), `FM-11` (verifier), `FM-12`                          | Per-tenant SA credentials on `LiveFirestoreMemoryBank`, the Model Armor fail-closed-on-outage decision, Base64 indirect-injection decoding, inline `verify_agent_output_deterministically()`, and YAML-driven `terraform/modules/tenant/main.tf`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |

## Consequences

- **Immediate bug closure (`#26` + `#25`)**: All confirmed runtime bugs on
  `main` (`FM-02`, `FM-03`, `FM-05`, `FM-06` SQL, `FM-07`, `FM-10` latch, and
  `FM-11` dispatch) land across `#26` (core `DA1`) and `#25` (follow-up slice)
  with hermetic unit and eval tests.
- **Zero duplicate work across roadmap steps**: `PR-DA3` merges into the Step-3
  Credential Broker, `PR-DA2` gates horizontal scale-out, `PR-DA4` lands with
  tenant offboarding, and `PR-DA5`/`PR-DA6` land with the Step-4 Terraform
  series.
