# ADR-0014: Credential Broker and Asymmetric Context Signing (Step 3 + DA3)

**Status:** Accepted; B2–B4 deployed (2026-11-04), B5 deployed (2026-11-09);
Amendment A1 (customer-driven session length) proposed 2026-11-05 **Date:**
2026-10-30 **Owner:** Platform Security Architecture Team **Closes:** the
hard-coded envelope key P1 (and ADR-0013 FM-04) at B2; the "runtime can act as
any tenant" P1 at B5 (phase 3b, deployed 2026-11-09).

## Implementation status

**B2 deployed** (context token): live on Cloud Run `cymbal-pooled-gateway`
revision 00024 since 2026-11-04, signing with KMS key
`cymbal-platform-kr/ws2-context-signing` version 1. The gateway signs an ES256
`ctx+jwt` per gateway token with Cloud KMS key
`cymbal-platform-kr/ws2-context-signing` (`identity.context_signing_kms_key`);
the interceptor, sub-agent hops and the in-process MCP handler verify with
public keys only. `DEFAULT_PEP_SIGNING_SECRET` is removed and the gateway
refuses to start without a signing key. See `agents/context_signing.py`,
`agents/context_token.py`, `docs/configuration_reference.md` (gcloud steps,
preflight) and `tests/security/test_adr_0014_context_token.py`.

**B3 deployed** (JWKS + exchange; Cloud Run revision 00026, 2026-11-04):
`/.well-known/cymbal-context-jwks.json` publishes the rotation window of key
versions (configured - 1 .. + 2) via `getPublicKey`, so no list permission is
needed; `agents/context_exchange.py` implements the D3 exchange contract
(in-process API; nothing under `/internal/` on public ingress; moves to the
internal-only service in B5); `mcp_server/external_verifier.py` is the
standalone JWKS-based reference verifier. Derived tokens have exactly one
audience (`broker` or a registered external URL), at most 300 s, and a minimal
claim set
(`iss, sub, aud, iat, exp, jti, tenant_id, src_jti, max_delegation_depth`). The
exchange refuses offboarded tenants for every audience (broker included), issues
at most 20 derived tokens per presented context token per minute (so total
issuance is also bounded by gateway-token issuance: one context token per
gateway token; the per-source table is an LRU of 10k entries, and a slot is
refunded when signing fails), and audits every issuance, refusal and signing
failure with a pseudonymous user reference. The JWKS returns 503 if the signing
version itself is missing or DISABLED. Known limits: an external verifier may
keep trusting a disabled key version for up to JWKS max-age (300 s) + its stale
window (600 s in the reference verifier); and probing the JWKS window uses the
internal verifier's unknown-kid fetch budget (bounded: per-kid interval + global
cap per minute). In the sandbox the JWKS endpoint sits behind Cloud Run IAP
(anonymous callers get a 302 to sign-in), so external MCP servers can't fetch it
yet. Roadmap: before onboarding the first external MCP server, publish the JWKS
at a public location (e.g. a public Cloud Storage object updated on rotation, or
an unauthenticated JWKS-only service).

**B4 deployed** (credential broker; 2026-11-04): broker service
`cymbal-credential-broker` (revision 00001, us-central1, SA `cymbal-broker-sa`,
invoker = runtime SA only); gateway revisions 00028 (Stage 0) and 00029 (Stage
3, `CREDENTIAL_BROKER_URL`); the runtime SA's TokenCreator on both `ct-*`
removed (Stage 4); live tests 13/13 (8 broker + 5 blast radius). The rollout
also found and removed TokenCreator on both `ct-*` held by the unused legacy
`cymbal-ingress-pep-sa` (see the runbook's rollout record). Honest limit:
containment completes with B5. Until the gateway and runtime are split, a fully
compromised runtime can still obtain KMS signatures and therefore broker tokens
for any onboarded tenant. Details (`docs/runbooks/credential_broker_b4.md`):
`broker_service/` is a separate entrypoint in the same image
(`uvicorn broker_service.main:create_app --factory`). It imports no ADK or agent
modules (tested; `agents/__init__.py` now loads the ADK agents lazily). It
accepts only callers whose Cloud Run-verified ID token is the runtime SA, and
only broker-audience context tokens (public-key verification). It takes the
tenant from the token and re-checks onboarding on every mint. Kinds are
allowlisted (`access_token` <= 300 s, `id_token` for per-tenant audiences in
`broker_id_token_audiences`). Replays are refused: one mint per (`jti`, kind,
audience), at most 3 per `jti`. It mints only `ct-<sha256(tenant)[:24]>` and
audits every mint and refusal. The runtime uses `RemoteBrokerBackend` when
`CREDENTIAL_BROKER_URL` is set (exchange -> broker). Terraform
(`terraform/modules/platform_core/credential_broker.tf` and
`terraform/modules/tenant`; applied in the sandbox since the 2026-11-06
Terraform adoption) adds the broker SA, its TokenCreator on `ct-*`, the broker
service with the runtime SA as its only invoker, and
`runtime_keeps_token_creator` for step 4. The broker refuses to start outside
Cloud Run, without `BROKER_ALLOWED_CALLERS`, or without
`BROKER_EXPECTED_AUDIENCE`. It takes the caller from
`X-Serverless-Authorization` when present (the header Cloud Run verifies) and
verifies the Google signature itself if Cloud Run did not mark it as removed.
Live mode requires an explicit backend: `CREDENTIAL_BROKER_URL` or
`CYMBAL_DIRECT_IMPERSONATION=1` (pre-B4). Limits: in-process replay store
(`max-instances=1`); broker onboarding comes from the image's platform config,
so offboarding needs a config change plus a broker redeploy; the caller check
relies on Cloud Run IAM (invoker = runtime SA only).

**B5 deployed** (gateway/runtime split + Cloud Run Agent Identity; 2026-11-09):
`cymbal-pooled-gateway` (revision `00034-bk7`) is now the sole holder of
`roles/cloudkms.signerVerifier` on `cymbal-platform-kr/ws2-context-signing`. It
executes Hop 0–2 admission, signs the `runtime`-audience context token with the
routed `agent_id` (`CONTEXT_TOKEN_BIND_AGENT_ID=1`), pre-mints a
`broker`-audience derived token when a turn needs tenant credentials, and
forwards Hop 3–5 execution over `POST /internal/v1/turn` (`AGENT_RUNTIME_URLS`)
to dedicated per-agent Cloud Run services: `cymbal-agent-shared`
(`cymbal_shared_diagnostic_agent`, revision `00005-z25`) and
`cymbal-agent-finvault-alpha` (`finvault_regulatory_escalation_agent`, revision
`00003-p7c`). Both agent runtime services run with Cloud Run Agent Identity
(`--identity-type=agent-identity --functional-type=agent --identity-certificate`,
principals
`principal://agents.global.org-100000000001.system.id.goog/resources/run/projects/123456789012/locations/us-central1/services/cymbal-agent-{shared,finvault-alpha}`),
verify context tokens using KMS public keys over workload mTLS
(`https://cloudkms.mtls.googleapis.com/v1` with
`roles/cloudkms.publicKeyViewer`), and hold zero signing keys (`signerVerifier`)
and zero `TokenCreator`. Their entrypoint (`runtime_service/main.py`) imports no
signing or token-exchange modules (enforced by
`tests/security/test_disaggregated_runtime_service.py`). On
`cymbal-credential-broker` (revision `00006`, Terraform-converged with
`broker_keep_runtime_caller = false`), `cymbal-pooled-runtime-sa` is removed
from both `roles/run.invoker` and `BROKER_ALLOWED_CALLERS`; only the two agent
runtime principals may invoke the broker, and `BROKER_REQUIRE_AGENT_BINDING=1` +
`CONTEXT_TOKEN_REQUIRE_AGENT_ID=1` enforce `Tenant ∩ User ∩ Agent`
([ADR-0016](0016-three-layer-authz-tenant-user-agent.md)). Image builds use the
dedicated least-privilege `cymbal-build-sa` (`enable_build_sa = true`, closing
drift finding S4). See `runtime_service/main.py`, `agents/runtime_protocol.py`,
`terraform/modules/agent_runtime/`, and
`docs/runbooks/b5_agent_runtime_rollout.md`.

Recorded deviations from D1 in B2:

- **3LO CSRF key:** a random key per process, not Secret Manager. There is no
  OAuth callback endpoint yet, so `state` is minted and checked in one process.
  TODO: pinned Secret Manager version when a real multi-instance callback lands.
- **Delegation depth:** the signed token carries `max_delegation_depth`; the
  current depth is bound to the token with an HMAC tag keyed by a random
  per-process key (never configured, never leaves the process). The in-process
  MCP handler checks it too; a separately deployed MCP (B3) won't.
- **Alerting:** a KMS signing failure is an `ALERT` error log line plus HTTP
  503; there is no log-based alert policy yet.
- **KMS client:** REST (`agents/kms_rest.py`, CRC32C-checked), not the
  `google-cloud-kms` library.
- **`kid` ring:** verifiers trust versions up to configured + 2, serve cached
  keys through KMS blips for TTL (5 min) + 10 min, evict only on NOT_FOUND /
  DISABLED, and give unknown kids a separate, capped refetch budget.
- **IAM revocation:** if the serving identity loses IAM on the key (KMS 403),
  signing stops at once (new requests get 503), but verifiers keep serving the
  cached public key for up to TTL + max_stale (~15 min). This is by design: a
  403 is treated like any transient error so a KMS or IAM blip can't take
  verification down. Only NOT_FOUND / DISABLED evicts a key immediately; disable
  the key version to revoke trust in tokens already issued.
- **Capacity:** signing runs in a 4-thread pool per instance with a 5 s
  deadline, once per gateway token (cached by `jti`). At ~50 ms per KMS sign
  that is roughly 80 new gateway tokens per second per instance before requests
  queue (and then time out as 503). Check the project's KMS asymmetric-sign
  quota before scale-out.

## Amendment A1 (proposed, 2026-11-05): customer-driven session length vs. credential lifetime

**Why.** Real customers ask for longer tokens. Usually the need is session
length ("don't make me sign in again during an hour-long investigation" or "let
a 30-minute autonomous job finish"), not longer-lived credentials. PR #62 makes
token lifetimes configurable; this amendment sets the limits that configuration
must respect. Customer requirements may still justify longer gateway tokens than
the 10-minute default; this amendment allows that within ceilings.

**Rule 1: tokens that can't be revoked stay short, whatever the configuration.**

- The KMS-signed context token keeps `exp` ≤ min(gateway token `exp`, issue
  time + 600 s). A longer gateway token gets a fresh context token re-signed
  when needed, instead of one long-lived context token. D1's "≤ 10 min" and the
  what-if table below stay true.
- Broker access tokens stay ≤ 300 s by a hard ceiling in the broker.
  Configuration may only lower it.

**Rule 2: the gateway token may be longer, up to a ceiling.** It is DPoP-bound,
checked on every request and cleared by offboarding, so a longer lifetime is
acceptable for customer needs. Default 600 s; configurable up to 3,600 s.
Per-token call ceilings and per-user budgets bound runaway loops.

**Rule 3: tenants may tighten freely; loosening needs an explicit exception.** A
per-tenant value above a platform cap (for example an IdP token lifetime above
`idp_*_max_token_lifetime_seconds`) is rejected unless the tenant file carries
an `exception:` entry with a reason and approver. Exceptions are logged at
startup and alerted on use.

**Rule 4: prefer the right mechanism over a longer token.**

| Customer need                                        | Mechanism                                                                                                          | Credential lifetimes             |
| :--------------------------------------------------- | :----------------------------------------------------------------------------------------------------------------- | :------------------------------- |
| Hour-long interactive investigation without re-login | Silent renewal with the same DPoP key while the IdP session is valid                                               | Short                            |
| Long-running autonomous job                          | Job-scoped token plus per-job budget and turn ceiling, renewed by the job runner (machine callers, roadmap)        | Short; the budget bounds the job |
| Customer IdP issues long-lived tokens (2–8 h)        | Accepted once at Hop 0 up to the platform cap (or an approved exception); everything after is our own short tokens | IdP token checked only at login  |
| Regulated tenant wants shorter lifetimes             | Per-tenant tightening                                                                                              | Shorter                          |

**Status.** Rules 1 and 2 implemented in PR #62 (context token capped at
`min(gateway_ttl, 600)`, broker hard ceiling 300 s, gateway token configurable
up to 3,600 s). Rule 3's exception path is not built yet (README gap 20). Rule
4's silent renewal and machine callers are roadmap items (README gaps 8 and 9).

## Context

Two P1s from `freeze-f1` share one root cause: the process that runs agents also
holds the power to speak for any tenant.

1.  **The envelope signature uses a hard-coded shared secret.**
    - `ContextEnvelope` and the ADK `temp:` state are signed with HMAC-SHA256
      using `DEFAULT_PEP_SIGNING_SECRET` (`agents/context.py:62`).
    - The same secret is used in several places:
        - the ADK interceptor (`agents/interceptors.py:362`);
        - the MCP wire handler (`mcp_server/server.py:279`);
        - sub-agent propagation (`agents/auth/edge_verifier.py:513`);
        - `EdgeAuthVerifier.verify_obo_envelope` / `verify_dpop_for_tool_call`;
        - the delegation tag (`agents/context.py:460, 632, 767, 803, 812`).
    - Consequences:
        - Anyone with the repository can forge an envelope.
        - Every verifier can also sign, so a compromised MCP server could mint
          envelopes for any tenant.
        - A customer-hosted MCP server (Hop 5 BYO, see "Managed Agent Identity
          alignment") cannot verify our envelopes without being given the
          secret.
    - The delegation-depth tag (`delegation_tag`) and the 3LO CSRF key
      (`agents/workspace_plugins.py:364`) have the same problem.
1.  **The runtime can mint any tenant's credentials.**
    - `TenantCredentialBroker` runs inside the serving process.
    - Its live backend (`ImpersonatedTenantCredentialBackend`,
      `agents/tenant_credentials.py:218`) impersonates tenant service accounts.
    - It can do that because `cymbal-pooled-runtime-sa` holds
      `roles/iam.serviceAccountTokenCreator` on every `ct-*` service account
      (`terraform/modules/tenant/main.tf`, `gateway_impersonates_tenant`).
    - A compromised runtime can therefore act as any tenant for as long as it is
      compromised.

What is already in good shape and should be reused:

- The gateway access token is ES256.
- Its key comes from a pinned Secret Manager version (`app/gateway_tokens.py`).
- Startup fails outside synthetic sandboxes if no key is configured.

## Decision

### D1. Replace the envelope HMAC with an ES256 "context token" signed only by the gateway

- **What is signed.** The gateway signs a compact JWS (`typ: ctx+jwt`) carrying
  the same access-deciding fields `compute_obo_hmac` covers today:
    - `iss`, `sub`, `jti`, `cnf.jkt`
    - `tenant_id`, `tier`, `thinking_budget`, `scopes`, `cmek_key_name`,
      `user_role`, `idp_provider`
    - `session_id` (`trace_id` and `correlation_id` move to unsigned per-turn
      fields; see below)
    - plus `aud`, `iat`, `exp`.
- **Lifetime.** `exp` is no later than the gateway token's `exp`, so at most 10
  minutes.
- **Audience.** The default context token carries `aud = [runtime, mcp]`. A
  **separate** broker-audience token (`aud = broker`) is issued only when the
  turn's tools need a cloud credential, so a token an MCP server sees can't be
  replayed to the broker. Broker-audience tokens come from the gateway through
  the D3 exchange contract:
    - present a valid internal context token;
    - tenant and `sub` are copied from it;
    - `exp` ≤ min(300 s, its remaining lifetime);
    - each one gets a fresh `jti`, one per turn that needs a credential;
    - each issuance is audited.

    The runtime never signs them, before or after 3b. External MCP servers get
    their own token with `aud = <their URL>` (D3).

- **Key and type separation.** The context-signing key is distinct from the
  gateway access-token key. Verifiers require `typ=ctx+jwt`, `alg=ES256` and
  `iss=<context issuer>`. Gateway access tokens (`at+jwt`, gateway-API audience)
  are rejected as context tokens. Context tokens are rejected as access tokens
  on every gateway data endpoint. The only gateway endpoint that accepts one is
  the internal token exchange (D3 per-server tokens and broker-audience tokens),
  which public ingress can't reach.
- **Bearer inside the trust boundary.** `cnf.jkt` is the _client's_ DPoP key.
  Downstream services never receive a client proof for their own URL, so
  `cnf.jkt` binds nothing downstream; it is carried for audit and correlation
  only. Inside our boundary, context tokens are sender-constrained by Cloud Run
  IAM (`run.invoker`) on the broker and internal MCP, and by short `exp` plus a
  narrow `aud` for external MCP. Workload-bound tokens (per-service DPoP keys or
  mTLS) are a later option.
- **No revocation.** Context tokens can't be revoked; they expire in ≤ 10 min.
  The broker re-checks onboarding on every mint, so user disablement lags by at
  most the gateway token TTL.
- **Verifiers hold only public keys.** The interceptor, MCP handler and
  sub-agent hops verify signatures; none of them can sign.
- **Per-turn values stay unsigned and clamped.** For example
  `temp:requested_thinking_budget`, exactly as #26 does today.
- **Signing key in Cloud KMS.** Use an asymmetric `EC_SIGN_P256_SHA256` key that
  cannot be exported. Only the gateway's service account gets
  `roles/cloudkms.signerVerifier`, and every signature appears in KMS audit
  logs.
    - **Alternative:** a PEM in Secret Manager, the same pattern as the gateway
      token key. Either way the key is not in code.
    - **Sign once per gateway token, not per request.** Cache the context token
      by gateway-token `jti` and refresh it when tenant config changes.
      Per-request values (`trace_id`, `correlation_id`) are therefore **not**
      signed: they travel unsigned per turn and are used only for tracing, never
      for access decisions. This keeps KMS latency and quota small; check
      capacity against the KMS asymmetric-sign quota anyway.
    - **KMS failure fails closed.** A KMS error or timeout (bounded) returns 503
      and raises an alert. There is no fallback to a local key.
    - **Implementation note:** KMS returns a DER-encoded ECDSA signature, which
      must be converted to JWS raw `r‖s`.
- **Key distribution and rotation.**
    - `kid` is the KMS key version.
    - Internal verifiers load public keys at startup with KMS `getPublicKey`
      (`roles/cloudkms.publicKeyViewer`), and re-fetch on an unknown `kid`
      (rate-limited).
    - The JWKS (D3) publishes every ENABLED version, with a `Cache-Control`
      max-age below the rotation overlap.
    - Rule: overlap ≥ JWKS cache TTL + max token lifetime. A version is disabled
      only after that.
    - This also fixes the "no `kid` overlap" known limit for this key.
- **Remove `DEFAULT_PEP_SIGNING_SECRET`.** Startup fails if no context-signing
  key is configured. Tests use per-run generated keys.
- **Delegation depth.**
    - The signed token carries `max_delegation_depth`.
    - The current depth is tracked in-process in the `contextvars` envelope, not
      in a hop-signed tag. Sub-agents run in the same trusted runtime, and depth
      limits loops; it doesn't grant access.
    - Cross-process hops (MCP) never decide access on depth.
    - Any cross-process delegation (A2A or a remote sub-agent) needs a fresh
      gateway-issued token with `max_delegation_depth` decremented. Until that
      exists, remote delegation is unsupported.
- **The 3LO CSRF key** moves to Secret Manager in the same PR.

### D2. Move credential minting into a separate broker service

- **Service and identity.** A new Cloud Run service, `cymbal-credential-broker`,
  with its own service account `cymbal-broker-sa`.
    - `TokenCreator` on `ct-*` service accounts **moves from the runtime SA to
      the broker SA**.
    - The runtime SA gets only `roles/run.invoker` on the broker.
- **API.** `POST /internal/v1/tenant-credential`, called with a broker-audience
  context token (`aud = broker`) and a requested credential kind. Allowed kinds:
    - `access_token` (cloud-platform scope, ≤ 300 s);
    - `id_token` (fixed audiences such as the model router, for ADR-0012 PR-S4).
- **What the broker checks, and when it refuses:**
    - It verifies the context token signature (public key only), `exp`, and
      `aud`.
    - It takes the tenant **from the token**. The caller cannot choose the
      tenant.
    - It refuses tenants that aren't onboarded (re-checked on every mint), kinds
      not on the allowlist, and audiences not configured for that tenant.
    - **Replay limits:** at most one mint per broker-token `jti` and (kind,
      audience), plus a per-`jti` rate limit. Broker tokens get a fresh `jti`
      per turn (D1), so legitimate turns are never blocked.
    - The caller identity on the Cloud Run IAM ID token must be the runtime SA.
      It is checked and logged.
    - It mints only for `ct-<sha256(tenant_id)[:24]>`.
- **Audit.** It writes one audit line per mint: tenant, kind, token `jti`,
  caller service. No token values are logged.
- **Minimal surface.** No other endpoints, no user-facing ingress, egress only
  to IAM Credentials.
- **Runtime-side change is small.** `TenantCredentialBroker` keeps its
  interface. Its live backend becomes `RemoteBrokerBackend`, which sends the
  context token to the broker. Per-tenant caching stays, keyed by tenant and
  token expiry.

### D3. Hop 5 verification for customer-hosted MCP servers

- **Published keys.** The gateway publishes the context-token public keys at
  `/.well-known/cymbal-context-jwks.json`.
- **Per-server tokens: an exchange, not a signing service.** For an external MCP
  server, the runtime asks the gateway for a token whose `aud` is that server's
  registered URL. The contract, fixed in B3 so B5 needs no redesign:
    - The request must carry a valid internal context token.
    - The gateway copies `tenant_id` and `sub` **from that token**; the caller
      cannot name them.
    - `aud` must be an MCP URL registered for **that** tenant.
    - `exp` is at most min(5 min, the context token's remaining lifetime).
    - `max_delegation_depth` is carried over.
    - Every issuance is audited.
- **Customer-side checks.** A customer server verifies signature, `aud`, `exp`
  and `tenant_id`, and then applies its own row-level isolation.
- **Reference implementation.** `mcp_server/` becomes the reference verifier:
  public key only, and the same checks a customer would run.
- No customer ever receives a shared secret.

### D4. Split the front door from the agent runtime (phase 3b)

Phase 3a (D1–D3) leaves the gateway and the agent runtime in one Cloud Run
service (`cymbal-pooled-gateway`). In that layout a compromised runtime can
still ask KMS for a signature, because it runs as the gateway identity. **Phase
3a alone does not reduce the blast radius of a full runtime compromise.** It
fixes:

- forgery from the repository;
- forgery by verifiers;
- Hop 5 verification;
- where `TokenCreator` lives.

Phase 3b splits the service:

- **`cymbal-pooled-gateway`** handles token exchange, context signing and
  request admission. It holds `signerVerifier`.
- **`cymbal-agent-runtime`** runs ADK agents. It holds only public keys and
  `run.invoker` on the broker.

After 3b, a compromised runtime can use only the context tokens it receives
while compromised. That is a rolling window over tenants with live traffic: each
token is usable for ≤ 10 min, plus ≤ 300 s for access tokens minted from it. It
can't reach tenants without live traffic.

## What-if analysis (component compromise)

| Compromised component                                                           | Today (`freeze-f1` + DA1)                              | After phase 3a                                                                                                                                 | After phase 3b                                                                                                                                                                                                                                                                                   |
| ------------------------------------------------------------------------------- | ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Source code / repo leak                                                         | Forge envelopes for any tenant (constant key)          | Nothing (no key in code)                                                                                                                       | Nothing                                                                                                                                                                                                                                                                                          |
| MCP server (separately deployed; today's in-process MCP shares the runtime row) | Holds the HMAC key: can forge envelopes for any tenant | Sees only requests sent to it. Cannot forge. Cannot replay to the broker (no broker audience)                                                  | Same                                                                                                                                                                                                                                                                                             |
| Agent runtime container                                                         | Mint any tenant's GCP token, indefinitely              | Same as today in practice: same identity can still get KMS signatures                                                                          | Tenants whose requests reach the runtime while it is compromised (a rolling window). Each stolen context token is usable for ≤ its remaining lifetime (≤ 10 min), plus ≤ 300 s for access tokens minted from it. No tenant without live traffic, and nothing after eviction beyond those windows |
| Gateway (front door)                                                            | Same as runtime (one service)                          | Same as runtime                                                                                                                                | Can sign context tokens for any tenant (it is the trust root). Mitigations: minimal code, KMS audit, alerting on sign volume                                                                                                                                                                     |
| Credential broker                                                               | n/a                                                    | Can mint for any onboarded tenant. Mitigations: tiny surface, no user ingress, audited mints, refuses tokens without a valid gateway signature | Same                                                                                                                                                                                                                                                                                             |
| One tenant's service account                                                    | One tenant (IAM, ADR-0010)                             | One tenant                                                                                                                                     | One tenant                                                                                                                                                                                                                                                                                       |
| Stolen client gateway token                                                     | Useless without the client's DPoP key (RFC 9449)       | Same                                                                                                                                           | Same                                                                                                                                                                                                                                                                                             |

This section defines the component-compromise blast-radius matrix. It will be
extended to every component in a separate doc.

## Mapping to the four security review points

1.  **Don't store secrets as-is:**
    - The signing key lives in KMS and cannot be exported.
    - The constant secret and the CSRF key are removed from code.
1.  **Don't pass JWTs along as-is:**
    - The IdP token already stops at the gateway (#15).
    - Downstream services receive short-lived context tokens restricted to their
      own audience (`aud`).
    - External servers get their own per-audience token, never the user's JWT.
1.  **Fine-grained access control:**
    - Credential kinds and audiences are allowlisted per tenant in the broker.
    - The runtime loses `TokenCreator`. The actual blast-radius reduction lands
      with phase 3b.
1.  **What-if analysis:** the table above.

## Managed Agent Identity alignment

If Google Cloud's managed Agent Identity / Agent Gateway issues per-agent
identity tokens that customers can verify through a JWKS, the D3 context token
becomes the bridge. We keep the claim names compatible (`iss`, `aud`, `sub`,
`tenant_id`, `exp`) so a Hop 5 server could accept either. The broker's role
maps onto Auth Manager auth providers. This can be revisited as managed Agent
Gateway JWKS federation capabilities expand for external MCP sinks.

## Rejected alternatives

- **Load the HMAC secret from Secret Manager (no asymmetric change).** Removes
  the constant but keeps "every verifier can sign" and doesn't solve Hop 5.
  Rejected.
- **Keep `TokenCreator` on the runtime and add IAM conditions.** IAM conditions
  can't bind impersonation to the tenant of the current request. Rejected.
- **Re-sign the token at every sub-agent hop via the broker.** Adds a network
  call per delegation for a loop limit that doesn't grant access. Rejected in
  favour of in-process depth (D1).

## Plan (small PRs, each with independent review and mutation checks)

| PR  | Scope                                                                                                                                        | Notes                                                                                                                                                                                                                                                                                                                                     |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| B1  | This ADR                                                                                                                                     | Docs only                                                                                                                                                                                                                                                                                                                                 |
| B2  | Context token (ES256) replaces HMAC. Verifiers become public-key-only. Remove `DEFAULT_PEP_SIGNING_SECRET` and the CSRF constant. `kid` ring | One switch, no dual mode: acceptable only because all verifiers are in one service and **no external MCP exists yet**. Signing key: KMS, or Secret Manager PEM in the sandbox until the KMS key exists                                                                                                                                    |
| B3  | JWKS endpoint plus the per-audience token exchange for external MCP (D3 contract). `mcp_server/` becomes the reference verifier              | Hop 5 reference. The exchange contract already assumes the B5 split                                                                                                                                                                                                                                                                       |
| B4  | Broker service (same image, separate entrypoint), `RemoteBrokerBackend`, Terraform for broker SA and IAM moves                               | Staged IAM move: (1) grant the broker SA TokenCreator, (2) deploy `RemoteBrokerBackend` and verify, (3) remove the runtime SA's TokenCreator, (4) run the live 403 test. Includes a test that the broker entrypoint imports no ADK/agent modules. Live IAM changes in the sandbox need approval; Terraform applies with the step-4 import |
| B5  | Split gateway and agent runtime (phase 3b)                                                                                                   | After B4                                                                                                                                                                                                                                                                                                                                  |

## Verification (what "done" means)

- **Forgery:** tokens signed with any other key, `alg: none`, HS256, an unknown
  `kid`, the wrong `aud`, or an expired `exp` are all rejected by every
  verifier.
- **Cross-use:**
    - A gateway access token is rejected as a context token.
    - A context token is rejected on every gateway data endpoint (accepted only
      by the internal exchange).
    - An MCP-audience token is rejected by the broker.
- **KMS outage:** a signing failure returns 503 and nothing falls back to a
  local key.
- **Verifiers can't sign:** the interceptor, MCP and broker modules never load
  private key material (test asserts this).
- **Broker:**
    - It mints only for the token's tenant.
    - It refuses a valid token that is being replayed after expiry.
    - It refuses a second mint for the same broker-token (`jti`, kind,
      audience), and a new turn with a fresh broker token still succeeds.
    - It refuses callers other than the runtime SA.
    - It refuses kinds and audiences that aren't allowlisted.
- **Live IAM:**
    - The runtime SA's `generateAccessToken` on a `ct-*` SA returns **403**.
    - The broker SA succeeds.
    - Cross-tenant tests still return 403 in both directions.
- **Rotation:** two `kid`s are valid during the overlap; a removed `kid` fails.
- **Regression:** breach 10/10, golden 55/55, batch 35/35, live suite, and the
  full unit suite.

## 3-Stage Rolling Signing-Key Rotation Runbook (`active_kid`, `previous_kid`, `next_kid`)

Multi-replica rolling deployments require a 3-key verification ring
(`active_kid`, `previous_kid`, `next_kid`) so that during a rolling update
neither old nor new replicas reject tokens signed by the other:

- **Prerequisite (before Stage 1):** Create the new EC P-256 secret version `B`
  in Secret Manager and verify that the serving Cloud Run service account holds
  `roles/secretmanager.secretAccessor` on secret version `B` before rolling out
  Stage 1 (otherwise Stage 1 startup fails closed).
- **Stage 1 (Pre-stage verify-only `next_kid`):** Configure
  `identity.gateway_signing_secret = A` and
  `identity.gateway_next_signing_secret = B`
  (`WS2_GATEWAY_NEXT_SIGNING_SECRET`). Roll out across all replicas so every
  instance accepts tokens signed by either `A` (`active_kid`) or `B`
  (`next_kid`) while still signing with `A`.
- **Stage 2 (Switch signing to `B`):** Configure
  `identity.gateway_signing_secret = B`,
  `identity.gateway_previous_signing_secret = A`
  (`WS2_GATEWAY_PREVIOUS_SIGNING_SECRET`), and clear
  `gateway_next_signing_secret`. New replicas sign with `B` (accepted by
  remaining Stage-1 replicas via `next_kid`) and verify tokens from Stage-1
  replicas via `previous_kid`.
    - **Safe Rollback (`Stage 2 -> Stage 1`):** Rolling back from Stage 2 to
      Stage 1 is zero-downtime safe because Stage-1 config retains `A` as
      `active_kid` and `B` as `next_kid`, so any tokens issued with `B` during
      Stage 2 continue to verify after rollback.
- **Stage 3 (Retire `A` after TTL drain):** Wait at least `630s`
  (`GATEWAY_TOKEN_TTL_SECONDS = 600` + `CLOCK_SKEW_SECONDS = 30`, plus any
  downstream JWKS cache TTL) after Stage 2 completes before clearing
  `gateway_previous_signing_secret` and disabling Secret Manager version `A`.
  Note that pseudonymous log references (`log_user_ref` / `log_key`) are derived
  from the active signing key and rotate at Stage 2.

## Open questions

1.  KMS signing (stronger; one KMS call per gateway token, so at most once every
    10 min per client) or a Secret Manager PEM (same as the gateway token) for
    the sandbox? Recommendation: KMS.
1.  Does phase 3b (split services) happen right after B4, or with the step-4
    Terraform work?
1.  Do we want the broker to also hold 3LO tokens (Auth Manager style), or keep
    them in the existing vault for now?
