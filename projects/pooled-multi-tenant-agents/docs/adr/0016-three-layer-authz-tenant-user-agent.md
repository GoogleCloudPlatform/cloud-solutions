# ADR-0016: Three-Layer Authorization — Tenant, User, Agent

**Status:** Accepted; A1–A3 (gateway, agent runtimes, credential broker)
deployed live (2026-11-09); separate MCP service enforcement built and
hermetically tested **Date:** 2026-11-06 **Related:**
[ADR-0014](0014-credential-broker-and-asymmetric-context-signing.md) (context
token, broker, B5 split),
[ADR-0003](0003-ard-catalog-filtering-and-adk-callback-tool-pruning.md) (agent
catalog and tool pruning), [ADR-0010](0010-tenant-blast-radius-containment.md)
(per-tenant service accounts)

Diagram: see `docs/assets/ws2_token_permission_flow.svg` (three-layer
authorization diagram).

## Implementation status

**A1–A3 deployed live in the sandbox (2026-11-09):**

- Both per-agent Cloud Run runtime services (`cymbal-agent-shared` for
  `cymbal_shared_diagnostic_agent`, and `cymbal-agent-finvault-alpha` for
  `finvault_regulatory_escalation_agent`) run live in
  `cymbal-multitenancy-example` (`us-central1`) with Cloud Run Agent Identity
  (`--identity-type=agent-identity --functional-type=agent --identity-certificate`,
  principals
  `principal://agents.global.org-100000000001.system.id.goog/resources/run/projects/123456789012/locations/us-central1/services/cymbal-agent-{shared,finvault-alpha}`).
- `config/environments/sandbox.yaml` binds each `agent_id` to its Cloud Run
  Agent Identity principal and allowed `broker:*` / `mcp:*` purposes.
- `CONTEXT_TOKEN_BIND_AGENT_ID=1` (gateway), `BROKER_REQUIRE_AGENT_BINDING=1`
  (credential broker), and `CONTEXT_TOKEN_REQUIRE_AGENT_ID=1` (gateway,
  credential broker, and both agent runtimes) are enabled live and codified in
  `terraform/sandbox.tfvars`.
- `cymbal-pooled-runtime-sa` is removed from `cymbal-credential-broker` invokers
  and `BROKER_ALLOWED_CALLERS` (`broker_keep_runtime_caller = false`); only the
  two agent runtime principals may invoke the credential broker.
- `MCP_REQUIRE_AGENT_BINDING` is implemented and hermetically tested in
  `mcp_server/server.py` (`tests/security/test_agent_identity_authz.py`) and
  will be enabled live when the MCP server is deployed as a separate Cloud Run
  service (currently runs in-process inside each agent runtime).

### Live verification summary (2026-11-09, B5 Stage 5 & Stage 6)

| Check                                     | Target                                                                                   | Caller & token                                                                               | Live result                                                                                                                              |
| :---------------------------------------- | :--------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------- |
| Positive live turns                       | `cymbal-agent-shared`, `cymbal-agent-finvault-alpha` (`POST /internal/v1/turn`)          | `cymbal-pooled-runtime-sa` + KMS-signed `runtime` context token bound to matching `agent_id` | `200 {"outcome": "ok"}` (verified with KMS public key over workload mTLS)                                                                |
| Cross-agent context token                 | `cymbal-agent-shared` with `finvault_regulatory_escalation_agent` token (and vice versa) | `cymbal-pooled-runtime-sa` + cross-agent KMS-signed context token                            | `403 {"detail": {"error": "E_RUNTIME_AGENT_MISMATCH"}}`                                                                                  |
| Unbound context / broker token            | `cymbal-agent-shared` (`aud=runtime`) & `cymbal-credential-broker` (`aud=broker`)        | KMS-signed token without `agent_id` under `CONTEXT_TOKEN_REQUIRE_AGENT_ID=1`                 | `401` (runtime) / `403` (broker) `{"detail": {"error": "E_CONTEXT_TOKEN_AGENT_ID_MISSING"}}`                                             |
| Gateway SA calling broker directly        | `cymbal-credential-broker` (`POST /internal/v1/tenant-credential`)                       | `cymbal-pooled-runtime-sa` + valid broker token bound to `cymbal_shared_diagnostic_agent`    | `403 E_AGENT_PRINCIPAL_MISMATCH` (Stage 5) and `403` at Cloud Run IAM edge after Stage 6 (`broker_keep_runtime_caller = false`)          |
| Non-gateway caller calling agent runtimes | `cymbal-agent-shared`, `cymbal-agent-finvault-alpha`                                     | `cymbal-broker-sa` ID token and unauthenticated requests                                     | `403` at Cloud Run IAM                                                                                                                   |
| KMS `ws2-context-signing` IAM audit       | `cymbal-platform-kr/ws2-context-signing`                                                 | IAM policy inspection                                                                        | `roles/cloudkms.signerVerifier` held **only** by `cymbal-pooled-runtime-sa`; agent principals hold only `roles/cloudkms.publicKeyViewer` |

## The rule

A call is allowed only if **tenant ∩ user ∩ agent** all pass. Any one layer
saying no is a refusal.

## Decision table

| Layer  | Question                                    | Proven by                                                                                                                                                                                               | Enforced where                                                                                                    | Built today?                                                                                           |
| :----- | :------------------------------------------ | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :---------------------------------------------------------------------------------------------------------------- | :----------------------------------------------------------------------------------------------------- |
| Tenant | Which customer is this for?                 | KMS-signed context token (`tenant_id`), from the gateway token                                                                                                                                          | Gateway, registry, broker, MCP, Postgres RLS, KMS/IAM per tenant                                                  | Yes                                                                                                    |
| User   | Which person, with which role and consent?  | Same context token (`sub`, role, scopes); 3LO consent per user                                                                                                                                          | Gateway, registry (role ∩ consent), MCP, memory encryption                                                        | Yes                                                                                                    |
| Agent  | Which agent is calling, and may it do this? | The **caller's workload identity** (Google-issued ID token: the org's agent STS pool, or accounts.google.com for service accounts), matched to the `agent_id` the gateway signed into the context token | Agent runtime (`RUNTIME_AGENT_ID`), broker (per purpose), MCP (per tool), registry (expected principal per agent) | **Yes (Live on gateway, agent runtimes & credential broker; built & hermetically tested on MCP wire)** |

## Design

1.  **The gateway signs `agent_id`** — the agent it routed the request to — into
    the context token. The agent can't choose or change it.
1.  **Downstream checks who is actually calling.** The broker and MCP server
    verify the caller's Google-issued ID token (the org's agent STS pool, or
    accounts.google.com) and get its principal (a service-account email today,
    an Agent Identity principal later). Request headers are never trusted for
    this.
1.  **Caller must match the registry.** The registry holds the expected
    principal for each `agent_id`. The call passes only if the caller's
    principal equals the registered principal for the signed `agent_id`.
1.  **Agent must be entitled.** The registry lists what each agent may do (for
    example `broker:access_token`, `mcp:query_telemetry_rls`). The broker checks
    the purpose; the MCP server checks the tool.
1.  **Off by default, fail closed when on.** Enforcement is switched on per
    service. When it is on, a missing `agent_id`, an unknown agent, a principal
    mismatch or a missing entitlement is refused. Outside sandbox/local, an
    agent with no registered principal is refused.

Result: a compromised agent A can't present a context token meant for agent B,
and can't use a purpose or tool it isn't entitled to, even inside the right
tenant and user.

## Relation to B5 and the live rollout

- **Agent Identity runs in its own Cloud Run service per agent (B5 split, live
  2026-11-09).** See
  [ADR-0014](0014-credential-broker-and-asymmetric-context-signing.md) and
  [`docs/runbooks/b5_agent_runtime_rollout.md`](../runbooks/b5_agent_runtime_rollout.md).
- Each agent service is deployed with `gcloud beta run deploy` with
  `--identity-type=agent-identity`, `--functional-type=agent`, and
  `--identity-certificate` (all three flags are required). Its IAM principal
  (used for `run.invoker`, the broker allow-list and registry bindings) is:
  `principal://agents.global.org-<ORG_ID>.system.id.goog/resources/run/projects/<PROJECT_NUMBER>/locations/<REGION>/services/<SERVICE>`.
- Its ID token (confirmed in the A0 and S0 live spikes, 2026-11-06) is RS256,
  issued by the org's agent STS pool
  (`https://sts.googleapis.com/v1/organizations/<ORG_ID>/locations/global/workloadIdentityPools/agents.global.org-<ORG_ID>.system.id.goog`,
  keys at `<issuer>/openid/jwks`), with `sub` =
  `spiffe://agents.global.org-<ORG_ID>.system.id.goog/resources/run/...` (same
  path as the IAM principal), a list `aud` and no `email`. Verifiers pin that
  issuer to the configured org (`agent_identity.org_id`) and map the SPIFFE ID
  to the `principal://` form.
- **Confirmed in S0 and live in S3 (2026-11-09):**
    1.  Cloud Run IAM verifies Agent Identity SPIFFE ID tokens at the edge in
        front of `cymbal-credential-broker` when the
        `principal://agents.global.org-...` URI holds `roles/run.invoker`,
        replacing the signature with `SIGNATURE_REMOVED_BY_GOOGLE`.
    1.  Google API access from an Agent Identity container requires
        `--identity-certificate` (which mounts
        `/var/run/secrets/workload-spiffe-credentials/credentials.json` and sets
        `GOOGLE_API_CERTIFICATE_CONFIG`) and calling the `*.mtls.googleapis.com`
        endpoint over a `google-auth` `AuthorizedSession` with
        `configure_mtls_channel()` (`agents/kms_rest.py`).
- **Fallback:** the service-account email path keeps working. Each agent can get
  its own service account instead, with the same checks.
- Rollout order (completed in S3, 2026-11-09): deploy the agent with its
  identity → grant it `run.invoker` on the broker → add its principal to the
  broker's allowed callers → route turns via `AGENT_RUNTIME_URLS` → turn on
  `CONTEXT_TOKEN_BIND_AGENT_ID=1`, `BROKER_REQUIRE_AGENT_BINDING=1`, and
  `CONTEXT_TOKEN_REQUIRE_AGENT_ID=1` → run the live verification suite → remove
  `cymbal-pooled-runtime-sa` from broker callers
  (`broker_keep_runtime_caller = false`).
- The managed Agent Registry / Agent Gateway are not used; the registry here is
  our own code. This ADR keeps the same three questions so a managed product can
  replace the registry later.

## What this does not cover

- Agent-to-agent calls (A2A) beyond the broker and MCP server.
- Per-agent rate limits or budgets.
