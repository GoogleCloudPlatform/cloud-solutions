# Configuration Reference

All tenant and environment configuration lives in `config/` and is validated by
[`agents/platform_config.py`](../agents/platform_config.py). Unknown fields are
**rejected**, so a typo fails `make config-check` instead of silently falling
back to a default.

```text
config/
  base.yaml                        # product defaults (every environment)
  environments/
    sandbox.yaml                   # our shared test environment (synthetic data)
    customer.example.yaml          # template: copy to <name>.yaml for a customer
  tenants/
    sandbox/<tenant_id>.yaml       # one file per tenant; file name == tenant_id
    customer-example/<tenant_id>.yaml
```

**Merge order:** `base.yaml` → `environments/<env>.yaml` →
`<tenants_dir>/*.yaml`. **Selecting an environment:** `CYMBAL_ENV=<env>`
(default `sandbox`). Use `CYMBAL_CONFIG_DIR` to point at an enterprise-owned
config directory.

## `base.yaml` / `environments/<env>.yaml`

| Field                                                                 | Default                                            | Description                                                                                                                                                                                                                                                                                                                                                                                                     |
| :-------------------------------------------------------------------- | :------------------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `schema_version`                                                      | `1`                                                | Config schema version                                                                                                                                                                                                                                                                                                                                                                                           |
| `environment`                                                         | (required)                                         | Environment name, reported by `/api/v1/health`                                                                                                                                                                                                                                                                                                                                                                  |
| `data_classification`                                                 | (required)                                         | `synthetic` (sandbox/demo) or `customer`                                                                                                                                                                                                                                                                                                                                                                        |
| `tenants_dir`                                                         | (required)                                         | Directory of tenant files, relative to `config/`                                                                                                                                                                                                                                                                                                                                                                |
| `gcp.project_id`                                                      | (required in live mode)                            | Target project. `GOOGLE_CLOUD_PROJECT` overrides it. Placeholders fail closed in live mode.                                                                                                                                                                                                                                                                                                                     |
| `gcp.project_number`                                                  | none                                               | Lets numeric project numbers map to `project_id`                                                                                                                                                                                                                                                                                                                                                                |
| `gcp.region`                                                          | `us-central1`                                      | Region (`GOOGLE_CLOUD_REGION` overrides)                                                                                                                                                                                                                                                                                                                                                                        |
| `gcp.kms_keyring`                                                     | `cymbal-tenant-kr-prod`                            | Keyring holding per-tenant CMEK keys                                                                                                                                                                                                                                                                                                                                                                            |
| `gcp.runbook_bucket`                                                  | `{project_id}-runbooks`                            | Pooled runbook bucket (per-tenant managed folders)                                                                                                                                                                                                                                                                                                                                                              |
| `gcp.bigquery_dataset`                                                | `cymbal_agent_analytics`                           | Telemetry dataset                                                                                                                                                                                                                                                                                                                                                                                               |
| `gcp.firestore_database`                                              | `cymbal-memory-bank-prod`                          | Memory bank database                                                                                                                                                                                                                                                                                                                                                                                            |
| `gcp.model_armor_template_id`                                         | `cymbal-pooled-inbound-pep`                        | Template created by Terraform, verified at runtime                                                                                                                                                                                                                                                                                                                                                              |
| `gcp.dlp_inspect_template_id` / `gcp.dlp_deidentify_template_id`      | none                                               | DLP template IDs. On Cloud Run, Terraform sets the full names via `DLP_INSPECT_TEMPLATE` / `DLP_DEIDENTIFY_TEMPLATE`.                                                                                                                                                                                                                                                                                           |
| `tiers.<enterprise\|standard>`                                        | see `base.yaml`                                    | `thinking_budget`, `rpm_limit`, `tpm_limit`, `max_turns_per_session`                                                                                                                                                                                                                                                                                                                                            |
| `models.default_shared_model`                                         | `gemini-4-hydrogen`                                | Universal default model for the pooled shared diagnostic agent (`location=global`, 4,096-token durable implicit caching)                                                                                                                                                                                                                                                                                        |
| `models.default_executor_model`                                       | `gemini-4-hydrogen`                                | Default fast executor for Standard tier and `FastSearch` read-only lookup turns                                                                                                                                                                                                                                                                                                                                 |
| `models.default_frontier_model`                                       | `gemini-4-carbon`                                  | Frontier advisor model invoked on bounded mid-turn `AskPro` escalation (`location=global`)                                                                                                                                                                                                                                                                                                                      |
| `models.fallback_frontier_model` / `models.fallback_fast_model`       | `gemini-4-argon` / `gemini-3.8-flash`              | Configured fallback models permitted across tiers (`location=global`)                                                                                                                                                                                                                                                                                                                                           |
| `models.private_regulatory_model` / `models.eval_judge_model`         | `claude-3-7-sonnet@20250219` / `gemini-4-hydrogen` | Private regulatory escalation model (`Agent Alpha`) and structured `DecomposedJudgeVerdict` eval judge                                                                                                                                                                                                                                                                                                          |
| `models.standard_allowed_models` / `models.enterprise_allowed_models` | see `base.yaml`                                    | Per-tier allowlisted model catalogs enforced by `SharedModelRoutingPDP`                                                                                                                                                                                                                                                                                                                                         |
| `default_scopes`                                                      | telemetry/runbook read + shared agent              | Scopes for tenants that don't list `authorized_scopes`                                                                                                                                                                                                                                                                                                                                                          |
| `identity.gateway_audience`                                           | `https://agent-gateway.cymbal.internal`            | Expected `aud` for direct-federation tokens (unless a tenant sets `identity.audience`)                                                                                                                                                                                                                                                                                                                          |
| `identity.broker_project_id`                                          | none                                               | Google Identity Platform project. Set it to sign tenants in through the broker (tenants then set `gcip_tenant_id`)                                                                                                                                                                                                                                                                                              |
| `identity.dev_issuer`                                                 | `false`                                            | **Sandbox only.** In-process issuer that mints synthetic users' tokens (`POST /api/v1/sandbox/token`) for the demo UI, scripts and CI. Rejected unless `environment: sandbox` and `data_classification: synthetic`, **and** the gateway runs in that config's own `gcp.project_id` (a sandbox config in another project gets no dev issuer). Its key is per process: run the sandbox gateway with one instance. |
| `identity.public_origin`                                              |                                                    | Public HTTPS origin clients call (e.g. `https://agents.example.com`, no path). Fixes the DPoP `htu` origin so forwarding headers can't redirect proofs. **Required for `data_classification: customer`**; the sandbox uses the `Host` header.                                                                                                                                                                   |
| `identity.gateway_signing_secret`                                     |                                                    | Secret Manager `<secret-id>/versions/<n>` (pinned) holding the gateway token signing key (EC P-256 PKCS#8 PEM), shared by all instances and loaded at startup. **Required for customer data.**                                                                                                                                                                                                                  |
| `identity.context_signing_kms_key`                                    |                                                    | Cloud KMS key that signs context tokens (ADR-0014 B2): `projects/<p>/locations/<l>/keyRings/<r>/cryptoKeys/<k>`, an asymmetric `EC_SIGN_P256_SHA256` key. Env `CONTEXT_SIGNING_KMS_KEY` overrides it (a key or a full key version). **Required for customer data**; without any key the gateway refuses to start.                                                                                               |
| `identity.context_signing_kms_key_version`                            | `1`                                                | Key version the gateway signs with (env `CONTEXT_SIGNING_KMS_KEY_VERSION`). Verifiers trust versions up to this + 2 while they are ENABLED.                                                                                                                                                                                                                                                                     |
| `token_policy.gateway_token_ttl_seconds`                              | `600`                                              | Lifetime (`60` to `3600` s) of DPoP-bound gateway session tokens (`at+jwt`), overridden on Cloud Run by `GATEWAY_TOKEN_TTL_SECONDS`. Irrevocable Cloud KMS context tokens (`ctx+jwt`) remain capped at `min(gateway_token_ttl_seconds, 600)` s and re-sign transparently when needed.                                                                                                                           |
| `token_policy.dpop_proof_max_age_seconds`                             | `120`                                              | Freshness window (`30` to `300` s, `<= gateway_token_ttl_seconds`) for single-use RFC 9449 DPoP proofs (`DPOP_PROOF_MAX_AGE_SECONDS`).                                                                                                                                                                                                                                                                          |
| `token_policy.tenant_sa_token_ttl_seconds`                            | `300`                                              | Lifetime (`60` to `300` s; may only lower the broker's `300` s hard ceiling) of per-tenant `ct-<hash>` Google IAM access tokens (`TENANT_SA_TOKEN_TTL_SECONDS`).                                                                                                                                                                                                                                                |
| `token_policy.tenant_sa_refresh_margin_seconds`                       | `60`                                               | Lead window (`15` to `270` s, at least `30` s below `tenant_sa_token_ttl_seconds`) before expiry at which cached tenant SA tokens refresh proactively (`TENANT_SA_REFRESH_MARGIN_SECONDS`).                                                                                                                                                                                                                     |
| `token_policy.idp_broker_max_token_lifetime_seconds`                  | `3600`                                             | Maximum accepted Hop 0 ID token lifetime (`300` to `28800` s) in Google Identity Platform broker mode (`IDP_BROKER_MAX_TOKEN_LIFETIME_SECONDS`).                                                                                                                                                                                                                                                                |
| `token_policy.idp_direct_max_token_lifetime_seconds`                  | `5400`                                             | Maximum accepted Hop 0 ID token lifetime (`300` to `28800` s) in direct OIDC federation mode (`IDP_DIRECT_MAX_TOKEN_LIFETIME_SECONDS`).                                                                                                                                                                                                                                                                         |

## Tenant file: `tenants/<dir>/<tenant_id>.yaml`

| Field                                                                | Required    | Description                                                                                                                                                                                                                                                                                                                                                         |
| :------------------------------------------------------------------- | :---------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `tenant_id`                                                          | ✅          | Lowercase letters, digits, and hyphens; **must equal the file name**                                                                                                                                                                                                                                                                                                |
| `display_name`                                                       | ✅          | Human-readable name                                                                                                                                                                                                                                                                                                                                                 |
| `tier`                                                               | ✅          | `enterprise` or `standard` (limits come from `tiers`)                                                                                                                                                                                                                                                                                                               |
| `identity.issuer`                                                    | ✅          | The tenant's IdP issuer (`https://` only)                                                                                                                                                                                                                                                                                                                           |
| `identity.provider`                                                  |             | `google` (default), `entra`, `okta` or `ping`                                                                                                                                                                                                                                                                                                                       |
| `identity.audience`                                                  |             | Token `aud` (your IdP app's client ID); defaults to `identity.gateway_audience`                                                                                                                                                                                                                                                                                     |
| `identity.directory_id`                                              | for `entra` | Entra tenant ID; tokens must carry this `tid`                                                                                                                                                                                                                                                                                                                       |
| `identity.role_claim`                                                |             | Claim with the user's role or groups (defaults: Google `user_role`, Entra `roles`, Okta/Ping `groups`)                                                                                                                                                                                                                                                              |
| `identity.role_map`                                                  |             | IdP group / App Role name → platform role (`sre_admin`, `compliance_officer`, `read_only_analyst`). Defaults (synthetic data only): Entra `Cymbal.*` App Roles; Okta/Ping groups named after the roles. **Required for `data_classification: customer`**, along with `identity.audience`; direct `provider: google` is rejected for customer data (use the broker). |
| `identity.gcip_tenant_id` + `identity.sign_in_providers`             |             | Broker mode: the Identity Platform tenant and allowed sign-in providers (e.g. `saml.okta-acme`). `issuer` must then be `https://securetoken.google.com/<broker_project_id>`                                                                                                                                                                                         |
| `cmek_key`                                                           | ✅          | KMS key name in `gcp.kms_keyring`. **Must be unique per tenant** (no shared keys).                                                                                                                                                                                                                                                                                  |
| `org_unit`                                                           |             | Defaults to `pooled-saas-tenant`                                                                                                                                                                                                                                                                                                                                    |
| `authorized_scopes`                                                  |             | Overrides `default_scopes`                                                                                                                                                                                                                                                                                                                                          |
| `bigquery_row_policy_id`                                             |             | Defaults to `rap_<tenant_id with _>`. Set only to adopt an existing policy.                                                                                                                                                                                                                                                                                         |
| `secret_ids`                                                         |             | Secret Manager secret IDs this tenant owns (3LO connector credentials). Only the tenant's service account may read them; a secret listed for two tenants is rejected.                                                                                                                                                                                               |
| `external_mcp_audiences`                                             |             | Customer-hosted HTTPS MCP URLs that Hop 5 derived-token exchange may target for this tenant.                                                                                                                                                                                                                                                                        |
| `broker_id_token_audiences`                                          |             | HTTPS audiences the credential broker may mint Google ID tokens for on behalf of this tenant's `ct-<hash>` service account.                                                                                                                                                                                                                                         |
| `identity.max_token_lifetime_seconds`                                |             | Per-tenant maximum Hop 0 ID token lifetime (`300` to `28800` s, `>= gateway_token_ttl_seconds`), overriding `token_policy.idp_*_max_token_lifetime_seconds`.                                                                                                                                                                                                        |
| `thinking_budget`, `rpm_limit`, `tpm_limit`, `max_turns_per_session` |             | Optional per-tenant quota and autonomous call-ceiling overrides (`max_turns_per_session` in `1` to `500`) over `tiers.<tier>`.                                                                                                                                                                                                                                      |

The smallest valid tenant file is five lines (see
`config/tenants/customer-example/tenant-acme-corp.yaml`).

## Environment variables

[`agents/runtime_env.py`](../agents/runtime_env.py) holds the **only** list of
environment variables the platform reads. Terraform's Cloud Run definition and
the code are tested against it (`tests/unit/test_platform_config_contract.py`).
Secrets are never environment variables in live mode
([secrets_management.md](secrets_management.md)).

## Token expiry, call ceilings, and recommended profiles

Enterprises tune the balance between blast-radius containment and continuous
multi-step agent execution without modifying Python code. Configure defaults
across a deployment with Terraform's
[`var.token_and_session_policy`](../terraform/variables.tf) (wired to Cloud Run
in
[`terraform/modules/platform_core/iap_gateway.tf`](../terraform/modules/platform_core/iap_gateway.tf)
and
[`terraform/modules/platform_core/credential_broker.tf`](../terraform/modules/platform_core/credential_broker.tf)),
per environment in `config/environments/<env>.yaml` (`token_policy:` and
`tiers:`), or per tenant in `config/tenants/<dir>/<tenant_id>.yaml`.

**Precedence:** Cloud Run environment variable >
`config/environments/<env>.yaml` > [`config/base.yaml`](../config/base.yaml).
For `max_turns_per_session`, an explicit per-tenant YAML value overrides the
tier value. Startup check `validate_runtime_environment()` fails closed on
out-of-range values or invalid cross-token bounds (for example
`dpop_proof_max_age_seconds > gateway_token_ttl_seconds` or
`tenant_sa_token_ttl_seconds - tenant_sa_refresh_margin_seconds < 30`).

### Avoiding user re-authentication across token boundaries

Short gateway tokens (`600` s default) and bounded call ceilings (`5` Standard,
`12` Enterprise calls per gateway token) contain blast radius and runaway agent
loops without prompting the human user to sign in again:

1.  **Hop 0 → Hop 1 same-key DPoP re-exchange (programmatic SDK callers):**
    `max_turns_per_session` is scoped per gateway token (`sess-{jti}`) and
    resets whenever a new gateway token is issued. While the user's enterprise
    IdP token remains valid (up to `3,600` s via Identity Platform or `5,400` s
    via direct OIDC), a client SDK (`scripts/sandbox_auth.py` `SandboxCaller`)
    can call `POST /api/v1/auth/token` with that ID token signed by the **same**
    client ECDSA P-256 key (`cnf.jkt`) to obtain a fresh `at+jwt` (resetting the
    per-token call counter) without an IdP login prompt, while rejecting any
    stolen ID token replayed from another key (`401`). Automatic silent
    background renewal in the web UI and per-user rolling budgets that span
    re-exchanges are not built yet (see README Known Gap 8).
1.  **Decoupled session length vs. irrevocable downstream credentials (ADR-0014
    Amendment A1):** Raising `gateway_token_ttl_seconds` (up to `3,600` s)
    extends the DPoP-bound client session (checked on every request and
    immediately refused upon offboarding), while irrevocable KMS `ctx+jwt`
    tokens remain capped at `min(gateway_token_ttl_seconds, 600)` s (re-signed
    transparently when an earlier `600` s context token expires) and brokered
    `ct-<hash>` IAM access tokens stay hard-capped at `<= 300` s.
    `TenantCredentialBroker` refreshes each tenant's cached SA token
    `tenant_sa_refresh_margin_seconds` (`60` s default) prior to expiry, and
    `offboard_tenant()` immediately evicts cached credentials on the notified
    instance.

### Recommended profiles ([`terraform/terraform.tfvars.example`](../terraform/terraform.tfvars.example))

| Setting                                 | Balanced B2B SaaS _(default)_ | Regulated Banking | Long-Horizon Autonomous Triage |
| :-------------------------------------- | ----------------------------: | ----------------: | -----------------------------: |
| `gateway_token_ttl_seconds`             |                `600` (10 min) |     `300` (5 min) |                `1800` (30 min) |
| `dpop_proof_max_age_seconds`            |                 `120` (2 min) |      `60` (1 min) |                  `120` (2 min) |
| `tenant_sa_token_ttl_seconds`           |                 `300` (5 min) |     `180` (3 min) |              `300` (5 min cap) |
| `tenant_sa_refresh_margin_seconds`      |                  `60` (1 min) |            `45` s |                   `60` (1 min) |
| `idp_broker_max_token_lifetime_seconds` |                  `3600` (1 h) |      `3600` (1 h) |                   `3600` (1 h) |
| `idp_direct_max_token_lifetime_seconds` |               `5400` (90 min) |      `3600` (1 h) |                   `7200` (2 h) |
| `standard_max_turns_per_session`        |               `5` calls/token |   `4` calls/token |               `15` calls/token |
| `enterprise_max_turns_per_session`      |              `12` calls/token |   `8` calls/token |               `40` calls/token |

**Signing-key rotation drain coupling:** When raising
`gateway_token_ttl_seconds`, lengthen Stage 3 of gateway Secret Manager
signing-key rotation accordingly: wait at least `gateway_token_ttl_seconds + 30`
s clock skew before disabling `gateway_previous_signing_secret`. Because Cloud
KMS context tokens stay capped at `<= 600` s (`CONTEXT_TOKEN_MAX_TTL_SECONDS`),
KMS context-key rotation wait lengths stay unchanged (`10` min max token
lifetime + `15` min cache/stale window internally, or `300` s JWKS `max-age` +
`600` s + `30` s skew for external verifiers).

## Calling the gateway (Hop 0 → gateway token)

Identity never comes from request bodies, query strings, or tenancy headers.

1.  The user signs in with their IdP (or, in the sandbox only,
    `POST /api/v1/sandbox/token`).
1.  The client exchanges that ID token once: `POST /api/v1/auth/token` with
    `{"subject_token": "<ID token>"}` and a DPoP proof for that URL. The
    response is a short-lived gateway token bound to the client's ES256 key
    (`cnf.jkt`).
1.  Each request sends `Authorization: DPoP <gateway token>` and a fresh DPoP
    proof for that method and URL, carrying `ath` (the token hash). Proofs are
    single use.

`scripts/sandbox_auth.py` (`SandboxCaller`) and the demo UI implement this flow.
Behind Cloud Run IAM, send the Cloud Run identity token in
`X-Serverless-Authorization`.

The gateway signing key comes from the Secret Manager secret
`identity.gateway_signing_secret` (EC P-256 PKCS#8 PEM), read as the serving
identity. **Required for customer data.** Without it, only a synthetic sandbox
runs, with a per-process key (one instance). Demo and simulation endpoints
(`/api/v1/breach-*`, `/api/v1/topology-deltas/*`, `/api/v1/2am-chaos/*`,
`/api/v1/live-*`, `/api/v1/prerequisites-check/*`, `/api/v1/golden-e2e-suite`,
`/api/v1/finops-telemetry`) return 404 outside the sandbox.

## Context-token signing key (ADR-0014 B2)

The gateway signs one ES256 context token (`typ: ctx+jwt`) per gateway token
with a non-exportable Cloud KMS key; the interceptor, sub-agent hops and the MCP
handler verify it with the public key only. There is no key in code. Sandbox
names:

```bash
PROJECT=cymbal-multitenancy-example
LOCATION=us-central1
SA=cymbal-pooled-runtime-sa@${PROJECT}.iam.gserviceaccount.com

gcloud kms keyrings create cymbal-platform-kr --project=$PROJECT --location=$LOCATION
gcloud kms keys create ws2-context-signing --project=$PROJECT --location=$LOCATION \
  --keyring=cymbal-platform-kr --purpose=asymmetric-signing \
  --default-algorithm=ec-sign-p256-sha256 --protection-level=software
# signerVerifier on THIS KEY ONLY (it includes viewPublicKey, which the verifiers need).
gcloud kms keys add-iam-policy-binding ws2-context-signing --project=$PROJECT \
  --location=$LOCATION --keyring=cymbal-platform-kr \
  --member="serviceAccount:${SA}" --role=roles/cloudkms.signerVerifier

# Preflight as the serving identity: signs one digest, fetches the public key, verifies.
gcloud auth application-default login --impersonate-service-account=$SA
CYMBAL_ENV=sandbox uv run python scripts/preflight_context_signing.py
```

- **Deploy:** `CYMBAL_ENV=sandbox` is enough (`config/environments/sandbox.yaml`
  names the key). Never set `CYMBAL_LOCAL_CONTEXT_SIGNER` on Cloud Run: the
  gateway refuses to start there.
- **Startup prewarm:** the gateway loads the public key in the background at
  startup and, until that succeeds, retries once per 30 s on incoming requests
  (never blocking them). Cloud Run throttles CPU outside requests, so the
  startup attempt can time out; that is logged once at WARNING and verification
  simply fetches the key on demand (still fail-closed). Optional: Cloud Run
  startup CPU boost (`gcloud run services update ... --cpu-boost`) makes the
  startup prewarm usually succeed.
- **Outages:** a KMS signing error or timeout (5 s) returns **503**
  `E_CONTEXT_SIGNING_UNAVAILABLE`; a public-key outage returns 503
  `E_CONTEXT_KEY_UNAVAILABLE`. Nothing falls back to a local key. Cached public
  keys are served through KMS blips for up to TTL (5 min) + 10 min.
- **Rotation:** create version `n+1`, wait until every instance trusts it
  (verifiers accept up to configured + 2), set
  `context_signing_kms_key_version: n+1`, roll out, then disable version `n`
  after at least 10 minutes (max token lifetime) + 15 minutes (key cache + stale
  window).
- **Capacity:** one KMS sign per gateway token (cached per token `jti`), through
  a 4-thread pool per instance with a 5 s deadline. At ~50 ms per sign that is
  ~80 new gateway tokens/s per instance before queueing; check the KMS
  asymmetric-sign quota for the project.
- **Offline runs** (`make serve`, demo and simulation scripts, CI): a
  per-process local key, only with `CYMBAL_LOCAL_CONTEXT_SIGNER=1`, the
  synthetic `sandbox` config, and not on a managed runtime (`K_SERVICE`,
  `CLOUD_RUN_JOB`, `KUBERNETES_SERVICE_HOST`).
- **Local sandbox mode** (dev issuer, demo and simulation endpoints): off a
  managed runtime it needs the explicit `CYMBAL_LOCAL_SANDBOX=1` (set by
  `make serve`, the offline scripts and the test suite). `CYMBAL_ENV` defaults
  to `sandbox` and, locally, nothing proves which project the process runs in,
  so without the flag `/api/v1/sandbox/token` and every sandbox-only route
  return 404. On Cloud Run / GKE the flag is ignored: the metadata server's
  project must equal the config's project.

## Published keys and per-audience tokens (ADR-0014 B3)

- **JWKS:** `GET /.well-known/cymbal-context-jwks.json` (no auth) publishes the
  public keys that verify context tokens: every usable version in the window
  `configured - 1 .. configured + 2` (missing or DISABLED versions are omitted;
  public keys only). `Cache-Control: public, max-age=300`. If the configured
  version can't be read it returns 503 (`no-store`).
    - Listing ENABLED versions would need `cloudkms.cryptoKeyVersions.list`,
      which `roles/cloudkms.signerVerifier` doesn't have. The window needs only
      `viewPublicKey`, which it does, so **no extra IAM**. (Alternative if
      arbitrary old versions must be published: `roles/cloudkms.viewer` on this
      key only.)
    - **Rotation with external verifiers:** create version `n+1` (it appears in
      the JWKS at once, as `configured + 1`), wait at least 300 s (JWKS max-age)
      before switching `context_signing_kms_key_version` to `n+1`, and disable
      version `n` no sooner than 300 s + 600 s (max token lifetime) + 30 s skew
      after the switch.
- **Token exchange:**
  `agents.context_exchange.ContextTokenExchange.exchange(token, audience=...)`.
  Present a valid internal context token; get a single-audience token for
  `broker` or for an external MCP URL registered for that tenant
  (`external_mcp_audiences` in the tenant file, plain `https` URLs). `tenant_id`
  and `sub` come from the presented token; `exp <= min(300 s, remaining)`; fresh
  `jti`; one audit line per issuance (logger `cymbal.audit.context_exchange`, no
  token values). Internal audiences (`runtime`, `mcp`) are never issued.
    - **Not on public ingress:** in this phase the exchange is an in-process API
      (gateway and runtime share one process). The public app serves nothing
      under `/internal/` (404). When the gateway and runtime split (B5), it
      moves to the internal-only gateway service (ingress `internal`, Cloud Run
      IAM `run.invoker` for the runtime SA only). Until then, anyone with code
      execution in the process can call it, which is the same trust level as the
      KMS signer today.
- **Customer-hosted MCP servers:** `mcp_server/external_verifier.py` is a
  standalone reference verifier (PyJWT + `cryptography` + `httpx` only). Point
  `JwksCache` at the gateway JWKS URL and set `audience` to the server's
  registered URL; it checks `typ`, `alg`, `kid`, signature, `iss`, `aud`
  (exactly this server), `exp` and lifetime, then hand `tenant_id` to row-level
  isolation.

## Credential broker (ADR-0014 B4)

- **Runtime:** live mode must choose a credential backend explicitly. Set
  `CREDENTIAL_BROKER_URL` (the broker service URL; tenant credentials are then
  minted by the broker) or, pre-B4 only, `CYMBAL_DIRECT_IMPERSONATION=1` (the
  runtime impersonates `ct-*` itself). With neither, credential minting fails
  closed (`E_CREDENTIAL_BACKEND_UNCONFIGURED`).
- **Broker service** (same image):
  `uvicorn broker_service.main:create_app --factory`. It needs
  `BROKER_ALLOWED_CALLERS` (the runtime SA email) and `BROKER_EXPECTED_AUDIENCE`
  (its own URL, the same string as the runtime's `CREDENTIAL_BROKER_URL`); it
  refuses to start without either, or outside Cloud Run. Deploy it with
  `--no-allow-unauthenticated`, give `run.invoker` to the runtime SA only, and
  use `--max-instances=1`.
- **Tenant file:** `broker_id_token_audiences` lists the audiences the broker
  may mint Google ID tokens for (empty means none).
- **Rollout and rollback:**
  [docs/runbooks/credential_broker_b4.md](runbooks/credential_broker_b4.md).

## Agent-level authorization (ADR-0016, off by default)

All flags default off; with none set, tokens and the live deployment are
unchanged.

| Setting                                                                            | Where           | Effect                                                                                                                                                                                                                                                                                      |
| :--------------------------------------------------------------------------------- | :-------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `agent_identity.org_id`                                                            | platform config | Pins the issuer of Agent Identity caller tokens (the org's agent STS pool). Without it, agent-identity callers are refused. Set in `sandbox.yaml`.                                                                                                                                          |
| `agent_identity.bindings.<agent_id>`                                               | platform config | `workload_principal` (Agent Identity principal or SA email) and `allowed_purposes` (`broker:<kind>`, `mcp:<tool>`). Empty by default.                                                                                                                                                       |
| `CONTEXT_TOKEN_BIND_AGENT_ID=1`                                                    | gateway         | Signs the routed `agent_id` into the context token, after the registry entitles the caller to that agent.                                                                                                                                                                                   |
| `CONTEXT_TOKEN_REQUIRE_AGENT_ID=1`                                                 | any verifier    | Refuses context and derived tokens without `agent_id` (also turns on binding in the gateway process). Meant for the separate broker / MCP services after B5: set in today's gateway process, it also makes the in-process `/mcp/v1/jsonrpc` refuse, because no agent is bound on that path. |
| `BROKER_REQUIRE_AGENT_BINDING=1`                                                   | broker          | Caller principal must equal the bound principal of the token's `agent_id`, and the agent must be allowed `broker:<kind>`. Refuses to start with no bindings.                                                                                                                                |
| `BROKER_ALLOWED_CALLERS`                                                           | broker          | Now also accepts `principal://agents.global...` entries; malformed entries refuse start.                                                                                                                                                                                                    |
| `MCP_REQUIRE_AGENT_BINDING=1`                                                      | MCP server      | Gates `tools/call` only (`tools/list` is unchanged). Same check per tool (`mcp:<tool>`, and the tool must be in the agent's catalog entitlements). Needs a transport caller identity, so only once MCP is its own service (B5).                                                             |
| `WORKLOAD_IDENTITY_AGENT_PRINCIPAL_CLAIM` / `WORKLOAD_IDENTITY_SA_PRINCIPAL_CLAIM` | broker / MCP    | Which caller ID-token claim carries the principal (defaults `sub` (SPIFFE ID) / `email`, as seen in the spike).                                                                                                                                                                             |

## Checks

```bash
make config-check ENV=sandbox            # schema, unique tenants and CMEK keys, file name == tenant_id
uv run python scripts/config_check.py --env <env> --for-deploy   # also rejects placeholder projects
```

In live mode the gateway also validates at startup and **refuses to start** if
the project is unset or a placeholder, no tenants are configured, or DLP
templates are missing.
