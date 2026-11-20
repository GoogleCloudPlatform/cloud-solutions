# Changelog

All notable changes to this repository. Dates are UTC.

## Unreleased

## v0.2.4 — 2026-11-19

Fresh-project gateway signing-key v1 in-memory seeding and a concise landing-page `README.md`
backed by `docs/implementation_status.md` (incorporating fresh-customer deployment and
documentation review feedback).

### Fixed: fresh-project `cymbal-gateway-signing-key` v1 seeding (`scripts/deploy.sh`)

- **Early signing-secret shell target & in-memory v1 seed.** On a fresh customer or sandbox
  project whose environment config pins `identity.gateway_signing_secret` to version `1`
  (for example `cymbal-gateway-signing-key/versions/1`), `scripts/deploy.sh` now targets
  `module.platform_core.google_secret_manager_secret.platform_signing_shells` during the early
  bootstrap apply and—only when the secret shell exists and version `1` does not yet exist—generates
  an EC P-256 PKCS#8 PEM key strictly in memory via pipe
  (`openssl ecparam ... | openssl pkcs8 ... | gcloud secrets versions add ... --data-file=-`)
  without writing private key material to disk or stdout. Re-deploys where version `1` already
  exists, environments with `gateway_signing_secret: null`, and configs pinned to version `2+`
  skip seeding.
- Added unit tests in `tests/unit/test_deploy_and_smoke_scripts.py` covering missing v1 seeding
  (both `<secret>/versions/1` and bare `<secret>`), idempotent skip when v1 exists, and no-op when
  `gateway_signing_secret` is unset or pinned to v2.

### Changed: concise `README.md` + `docs/implementation_status.md`

- Trimmed `README.md` from 736 lines to a scannable ~170-line landing page covering the
  architecture diagram, Hop 0–5 (`Tenant ∩ User ∩ Agent`) security boundaries, 2-minute local
  hermetic quickstart, 5-minute turnkey GCP deploy, and repository/documentation map.
- Preserved the full 19-row `"At a glance"` implementation-status matrix, user journeys, token and
  compromise blast-radius tables, IAM model, verification evidence counts, 21-item known-gaps
  audit, roadmap, and customer-data gate in
  [`docs/implementation_status.md`](docs/implementation_status.md), linked prominently from
  `README.md`, `SECURITY.md`, and `CONTRIBUTING.md`.
- Updated `scripts/build_public_export.py` and its tests to rewrite sandbox-only passages cleanly
  across both `README.md` and `docs/implementation_status.md` while keeping the Google disclaimer
  near the top of the exported `README.md`.

## v0.2.3 — 2026-11-19

macOS (Bash 3.2) deploy fixes, a concurrent two-tenant end-to-end isolation test, safer defaults
for anyone who copies the repository, and a clean public export (#97, #98, #99, #100).

### Fixed: deploying from macOS and into a customer project (#100)

- **Bash 3.2 and `set -u`.** macOS ships Bash 3.2, where expanding an empty array under
  `set -u` is an "unbound variable" error. `scripts/deploy.sh`, `bootstrap_customer_env.sh` and the
  other shell scripts now expand every array as `${ARR[@]+"${ARR[@]}"}`; a unit test rejects an
  unguarded expansion. This was checked statically and by running the scripts under Bash 5; Bash
  3.2 itself was not available to run them on.
- **Customer bootstrap without a tfvars file.** `scripts/deploy.sh` no longer needs
  `terraform/<env>.tfvars` to exist (it already passes project, region and environment as `-var`
  arguments) and says so when the file is absent. `scripts/bootstrap_customer_env.sh` runs the
  prerequisite check for the environment it just created, and
  `scripts/check_prerequisites.py` checks the selected environment's project instead of a
  placeholder.
- **Intermittent batch-audit and eval-showcase failures.** Both offline PII graders scanned
  platform-generated identifiers; a random all-digit sandbox ID matched the card-number pattern
  and failed the batch audit or the eval showcase (`test_grader_and_nlc_hygiene.py`,
  `test_online_smart_sampler_and_runner.py`) roughly once in forty to fifty runs. The graders
  now share one helper that drops those identifier shapes; card numbers in content are still
  caught. The runtime DLP filter is unchanged and uses the same pattern, so it would redact an
  all-digit identifier as a card number (see SECURITY.md, Known limits).
- **Terraform drift from #98.** The Memory Bank IAM condition description in
  `terraform/modules/tenant/main.tf` is back to the text deployed in the sandbox (IAM conditions
  are replaced when their description changes); the public export rewrites it instead.

### Added: two tenants, four users, concurrent multi-turn isolation test (#100)

- [`tests/security/test_concurrent_two_tenant_e2e_isolation.py`](tests/security/test_concurrent_two_tenant_e2e_isolation.py)
  drives FinVault and RetailStream, two users each, through the real gateway app for five turns
  per session: three interleaved on one event loop (`asyncio.gather`) and two from four threads
  (`ThreadPoolExecutor`), with all four requests held in flight together. It then checks eight
  layers for cross-tenant and cross-user leakage: the token chain and per-request context,
  session state and turn counters, Memory Bank records, RLS rows / runbooks / DLP masking, the
  per-session code sandbox, policy and per-tenant rate limits, agent discovery, and plugins and
  delegated credentials. It runs in `make test` and CI.
- [`tests/integration/test_live_concurrent_two_tenant_isolation.py`](tests/integration/test_live_concurrent_two_tenant_isolation.py)
  is the opt-in counterpart for a deployed sandbox gateway (`RUN_LIVE_GCP_TESTS=1`,
  `CLOUD_RUN_URL`, `CLOUD_RUN_ID_TOKEN`). It covers what is observable over HTTP (layers 1, 2, 4,
  6 and 7).

### Added: multi-turn sessions, dynamic tenants and a 3LO consent flow (#99)

- Session memory keeps prior turns; turn responses carry `session_state` and
  `workspace_governance`; tenants and tenant-private agents can be onboarded at runtime (no HTTP
  route); [`tests/security/test_e2e_multiturn_and_two_enterprise_concurrency.py`](tests/security/test_e2e_multiturn_and_two_enterprise_concurrency.py)
  covers multi-turn scenarios and two enterprises running concurrently.
- `POST /api/v1/oauth/3lo/authorize` and `/callback` demonstrate delegated (3LO) consent.
  **They are sandbox-only (404 elsewhere) (#100):** the callback records a synthetic grant and
  does not exchange the authorization code with a provider, so it must not be reachable in a
  customer deployment until a real code exchange exists. The consent `state` is deterministic
  (no nonce or expiry) and is a known limit of the demonstration flow.
- **Fixed in #100:** a dynamically onboarded tenant could re-register another dynamic tenant's
  private agent ID and become its owner. Registration now refuses any ID that belongs to another
  tenant or to a built-in agent.

### Changed: public export and container contents (#98, #100)

- **Export builder (#98).** `scripts/build_public_export.py` writes a copy of the repository for
  publication: internal documents and operator scripts omitted, identifiers replaced, product
  names unified, Apache-2.0 headers added, and the result checked with
  `scripts/verify_repo_sanitized.py --public-export`.
- **Public project files (#100).** The export ships its own `SECURITY.md` (report through
  <https://g.co/vulnz>; the "Known limits" section is kept), `CONTRIBUTING.md` (Google CLA), and a
  README with "This is not an officially supported Google product." and without the
  private-repository access notes.
- **No links to the private repository (#100).** The export unwraps Markdown links that point at
  the private source repository and drops bare URLs to it, and the publish gate has a
  `private_repository` denylist class so a leftover reference fails `--public-export`.
- **Walkthrough page (#100).** The `/demos` page and its assets no longer use a third-party
  channel's name or an internal meeting name (`/tuesday` remains as an alias for old bookmarks).
  The walkthrough video and the script that renders it are not exported; without the video the
  page opens on the interactive canvas and offers no video controls.
- **Image and upload context (#100).** `.dockerignore` and `.gcloudignore` exclude the
  four operator-only files under `scripts/` (collaborator grants, sandbox state import, the
  export denylist and the export builder); the scripts the gateway calls at runtime stay in.
- Several documentation tests now skip, rather than fail, when a document the export omits is
  absent, so the hermetic suite passes inside the exported tree.

### Security: unsafe defaults a copy of this repository would inherit (#97)

- **Local sandbox mode is opt-in (`CYMBAL_LOCAL_SANDBOX=1`).** Off Cloud Run / GKE,
  `sandbox_mode_active` ([`app/auth.py`](app/auth.py)) now also requires the explicit flag. Before,
  `CYMBAL_ENV` defaulting to `sandbox` plus the config's own project ID was enough, so a bare
  `uvicorn app.main:app` (or the image on a plain VM, which binds `0.0.0.0`) served
  `POST /api/v1/sandbox/token` and minted synthetic `sre_admin` tokens to any caller. Now that
  route and every sandbox-only route return 404 without the flag. `make serve`, the offline
  scripts and the test suite set it; behaviour on managed runtimes (metadata-server project check)
  is unchanged.
- **AlloyDB public IP is opt-in (`alloydb_enable_public_ip`, default `false`).** It was hardcoded
  on in [`terraform/modules/platform_core/alloydb.tf`](terraform/modules/platform_core/alloydb.tf).
  `terraform/sandbox.tfvars` sets it explicitly (no change to the live sandbox);
  `terraform.tfvars.example` sets it with the reason and what it exposes; `scripts/deploy.sh` and
  `scripts/bootstrap_alloydb_rls.py --private-ip` connect the Auth Proxy to the private address
  when it is off.
- **`docker-compose.yml`** publishes Postgres and Redis on `127.0.0.1` only, requires
  `POSTGRES_PASSWORD` / `REDIS_PASSWORD` from the environment (no committed superuser password,
  Redis now needs a password), and `scripts/init_postgres_rls.py` no longer has a built-in DSN.
- **`scripts/verify_repo_sanitized.py`** documents exactly what its default mode checks (it never
  checked internal shortlinks, as its docstring claimed) and gains `--public-export`, the publish
  gate: shortlinks, internal document links, sandbox domain, corporate email, and the project,
  organization, third-party tenant identifiers and names listed in
  `scripts/public_export_denylist.txt`. That mode fails on this repository today by design; CI
  keeps running the default mode.

## v0.2.2 — 2026-11-18

Turnkey clean-room Terraform deployment hardening, end-to-end clean-room GCP verification, and
pre-review HTTP/documentation security polish (#95, #96).

### Added & Hardened

- **Turnkey zero-state Terraform & `deploy.sh` bootstrapping (#95):** auto-creates versioned,
  public-access-prevented `gs://${TF_STATE_BUCKET}`, pre-builds images with `cymbal-build-sa`,
  cleans up unimported/`Ready=False` `cymbal-pooled-gateway` services before apply, and sequences
  two-phase AlloyDB RLS bootstrap ([`scripts/bootstrap_alloydb_rls.py`](scripts/bootstrap_alloydb_rls.py))
  plus dynamic `{org_id}` / `{project_number}` / `{region}` resolution across
  [`agents/platform_config.py`](agents/platform_config.py), [`agents/workload_identity.py`](agents/workload_identity.py),
  and `LiveVertexMemoryBankAdapter`.
- **Memorystore Redis AUTH + Server TLS & Direct IAP smoke check (#95):** added
  `enable_redis_auth_and_tls` (`SERVER_AUTHENTICATION` TLS + Secret Manager `REDIS_TLS_SECRET_VERSION`),
  Cloud Run Direct IAP (`302`) smoke validation, SHA-256 `--require-hashes` [`requirements.txt`](requirements.txt),
  anchored PEP HTTP `503`/`429` mapping in [`app/api/v1/agents_and_sandboxes.py`](app/api/v1/agents_and_sandboxes.py),
  and clean-room E2E verification (`1,028` hermetic tests at `90.76%` coverage).
- **Pre-review HTTP & repository security polish (`v0.2.2`):**
  - Enforced `Cache-Control: no-store` and `Pragma: no-cache` on `/api/v1/sandbox/token` and
    `/api/v1/auth/token`, baseline `X-Content-Type-Options: nosniff` and `X-Frame-Options: DENY`
    headers across gateway responses, and gated `/openapi.json`, `/docs`, and `/redoc` to return
    `404` outside synthetic sandboxes ([`app/main.py`](app/main.py)).
  - Updated [`SECURITY.md`](SECURITY.md) to reflect shipped ADR-0014 B5 + ADR-0016 trust boundaries,
    aligned `0.2.2` version metadata, switched A2A `allowlisted_tools` naming, removed leftover
    scaffolding files, scrubbed internal terminology from ADR-0014, and hardened
    [`scripts/verify_repo_sanitized.py`](scripts/verify_repo_sanitized.py).

## v0.2.1 — 2026-11-17

Part 2 Pooled Architecture parity across repository code, Terraform infrastructure, live Cloud Run
services (`cymbal-multitenancy-example`), and public readiness (#84–#94).

### Added & Changed

- **Agent Sandbox in Gemini (ADR-0012):** implemented `GeminiAgentSandboxManager` and
  `LiveGeminiAgentSandboxClient` targeting out-of-process `sandboxEnvironments` (`4.19.0-gvisor`,
  non-root, stateful `pause`/`resume`/destroy) and portable GKE `SandboxWarmPool` manifest.
- **Modular Package Split & Public PyPI `uv.lock`:** factored monoliths into `agents/adapters/*`,
  `agents/auth/*`, `agents/sandbox/*`, `app/api/v1/*`, `app/ui/*`, and `tests/{unit,security,integration}/`.
- **Live Cloud Run Agent Identity Cutover & Shared Stores (`enable_live_mode = true`):** enabled
  SPIFFE workload mTLS, live AlloyDB PostgreSQL 18.4 `FORCE RLS` with per-tenant `ct-*` IAM DB users,
  atomic Lua `RedisBulkheadStore` (`REDIS_URL`), multi-replica `FirestoreRevocationStore`, per-tenant
  WIF pools/OIDC providers, and Memory Bank in Gemini `memoryScope` IAM CEL.
- **Universal Gemini 4 Routing & Pricing Quote Scrub:** set `gemini-4-hydrogen` as default across
  workloads with bounded `AskPro` escalation to `gemini-4-carbon`, scrubbed dollar pricing quotes
  from docs and UI, and verified `27/27` live GCP integration tests.

## v0.2.0 — 2026-11-10

Live deployment of the **ADR-0014 B5 gateway/runtime split** and **ADR-0016 three-layer
authorization (`Tenant ∩ User ∩ Agent`)** using Cloud Run Agent Identity (SPIFFE workload X.509
mTLS + RS256 ID tokens), together with full **Terraform adoption, modularization, and CI** for the
sandbox project (`cymbal-multitenancy-example`).

### Added

- **ADR-0014 B5 — Per-agent Cloud Run runtime split (live 2026-11-09):**
  - Separate per-agent runtime service entrypoint [`runtime_service/main.py`](runtime_service/main.py),
    shared turn execution engine [`agents/turn_engine.py`](agents/turn_engine.py), and gateway remote
    turn dispatcher [`app/remote_runtime.py`](app/remote_runtime.py) (#75).
  - Terraform [`terraform/modules/agent_runtime/`](terraform/modules/agent_runtime/) module and
    rollout runbook [`docs/runbooks/b5_agent_runtime_rollout.md`](docs/runbooks/b5_agent_runtime_rollout.md)
    (#76), deployed to `cymbal-agent-shared` and `cymbal-agent-finvault-alpha` (#78).
  - `cymbal-pooled-gateway` is now the sole holder of `roles/cloudkms.signerVerifier` on
    `ws2-context-signing` and holds zero `roles/run.invoker` on `cymbal-credential-broker`
    (`broker_keep_runtime_caller = false`); Hop 3–5 turns execute on the per-agent Cloud Run
    services with `roles/cloudkms.publicKeyViewer` over workload mTLS and zero signing keys (#78).
- **ADR-0016 — Three-Layer Authorization (`Tenant ∩ User ∩ Agent`) with Cloud Run Agent Identity / SPIFFE (live 2026-11-09):**
  - [ADR-0016](docs/adr/0016-three-layer-authz-tenant-user-agent.md) (#68) and workload identity
    verifier [`agents/workload_identity.py`](agents/workload_identity.py) verifying Cloud Run Agent
    Identity RS256 tokens (`spiffe://agents.global.org-100000000001.system.id.goog/...`) and
    normalizing to `principal://agents.global.org-100000000001.system.id.goog/resources/run/projects/...` (#72).
  - KMS-signed `agent_id` claim in `ctx+jwt` (`CONTEXT_TOKEN_BIND_AGENT_ID=1`), runtime recipient
    check (`CONTEXT_TOKEN_REQUIRE_AGENT_ID=1`), and broker / MCP per-agent workload principal and
    purpose bindings (`BROKER_REQUIRE_AGENT_BINDING=1`, `MCP_REQUIRE_AGENT_BINDING`) (#72, #77, #78).
- **Terraform adoption, modularization, and CI (live 2026-11-06 / 2026-11-09):**
  - Remote state in GCS (`gs://cymbal-multitenancy-example-tfstate`), 87 live sandbox resources imported
    and applied with zero drift (#71, #73; [`docs/terraform_adoption_2026-11-06.md`](docs/terraform_adoption_2026-11-06.md)).
  - Refactored into [`terraform/modules/platform_core/`](terraform/modules/platform_core/),
    [`terraform/modules/agent_runtime/`](terraform/modules/agent_runtime/),
    [`terraform/modules/tenant/`](terraform/modules/tenant/) (YAML-driven per tenant), and
    [`terraform/modules/tenant_data_plane/`](terraform/modules/tenant_data_plane/) (WS4, code only)
    with `moved` blocks and stamping examples in [`terraform/envs/silo-example/`](terraform/envs/silo-example/)
    and [`terraform/envs/hybrid-example/`](terraform/envs/hybrid-example/) (#74, #76).
  - GitHub Actions workflow [`.github/workflows/terraform.yml`](.github/workflows/terraform.yml) (#67).
  - Dedicated least-privilege build service account `cymbal-build-sa` (`enable_build_sa = true`),
    closing Terraform drift finding S4 (#76, #78).
- **Config-driven topology routing (`pool | silo | hybrid`):** [`agents/topology_router.py`](agents/topology_router.py)
  (#69), removing hardcoded topology delta numbers and routing per-tenant endpoints from YAML.

### Changed

- **Architecture, blog, and diagram updates** (`5225ac5`, `efa4132`, #78): updated README, ADR-0014,
  ADR-0016, and architecture diagrams to reflect the live B5 per-agent runtime split, Cloud Run
  Agent Identity SPIFFE principals, and converged Stage 6 Terraform state.

## v0.1.1 — 2026-11-06

Follow-up to v0.1.0: documentation accuracy, reworked user journeys, configurable token policy.
Synthetic tenants only. The hosted gateway still runs the v0.1.0 deployment (not redeployed).

### Added

- **Configurable token and session policy** (#62): gateway token TTL, DPoP proof age, tenant
  service-account token TTL and refresh margin, IdP lifetime caps and per-token call ceilings,
  settable via Terraform, environment YAML and per-tenant overrides, validated fail-closed at
  startup. Hard caps per ADR-0014 Amendment A1: context token ≤ 600 s, broker tokens ≤ 300 s,
  gateway token ≤ 3,600 s.
- **ADR-0014 Amendment A1** (proposed): separates customer session length from credential
  lifetime; tenants may tighten freely, loosening needs an explicit exception (not built yet).
- **README known gaps 18–20 and roadmap items:** modular agents and tools (manifests, tenant MCP
  servers, per-tenant versions, tenant config store); model routing and thinking budget not wired
  into the live agent; per-tenant token policy exceptions.

### Changed

- **User journeys** (#64): one product (Cymbal's incident and compliance ops agent) and one persona
  type: Priya, SRE at FinVault (web app, runs today), and Sam, SRE at RetailStream (embedded ops
  console, mostly planned). The shopper journey was removed.
- **Blog draft** (#64): framing note that it describes the target architecture; planned components
  labelled; Hop 0 described as direct IdP verification (Workforce Identity Federation is not on the
  Hop 0 path); benchmark table relabelled modeled / simulated / tested; new "What runs today" section.
- **Diagrams** (48b05bf, #63): W1 + W2, W2 gateway, 5-hop and token-flow diagrams redrawn (Pattern
  B/C labels fixed) and captioned as target architecture wherever embedded.

### Known gaps

Unchanged from v0.1.0 apart from the additions above. See README "Missing components and known gaps".

## v0.1.0 — 2026-11-05

First tagged release of the Workstream 2 pooled multi-tenant agent gateway (Pattern A) in the
sandbox project. Synthetic tenants only.

### Added

- **Hop 0 IdP federation** (`HopZeroFederationGate`): per-tenant issuer onboarding, pinned
  asymmetric algorithms, audience/expiry/lifetime checks, Entra `tid`, role mapping; Google Identity
  Platform broker path (tested hermetically). Okta and Ping are format tests only.
- **DPoP-bound gateway token** (10 min, ES256, `cnf.jkt`) with per-request proofs and single-use
  replay protection (in-process).
- **ADR-0014 B2 — KMS-signed context token:** ES256 `ctx+jwt` signed by a non-exportable Cloud KMS
  key; verifiers hold public keys only. Deployed on Cloud Run revision 00024 (2026-11-04).
- **ADR-0014 B3 — per-audience token exchange + JWKS:** audience-bound context tokens for
  customer-hosted MCP servers, a JWKS endpoint and a reference external verifier; per-source rate
  limit and audited refusals. Deployed on revision 00026 (2026-11-04).
- **ADR-0014 B4 — credential broker:** separate Cloud Run service `cymbal-credential-broker` that
  mints 5-minute tokens only for the calling token's tenant service account; invoker is the runtime
  service account only; replay and second-mint refusal; audited. Gateway revisions 00028/00029,
  broker revision 00001 (2026-11-04); live broker and blast-radius tests 13/13.
- **Cloud Run built-in IAP** in front of the hosted gateway (named, time-boxed reviewer access).
- **Terraform drift review** ([`docs/terraform_drift_2026-11-04.md`](docs/terraform_drift_2026-11-04.md))
  and an import script ([`scripts/terraform_import_sandbox.sh`](scripts/terraform_import_sandbox.sh)).
  Terraform is still not applied.
- `CONTRIBUTING.md`, `SECURITY.md` and this changelog.

### Security

- Runtime `TokenCreator` on the per-tenant service accounts removed (B4 Stage 4); only the broker
  service account can mint tenant tokens.
- Legacy `cymbal-ingress-pep-sa`: its `TokenCreator` grants on the tenant service accounts and all 7
  of its project roles were removed, and the account was disabled (2026-11-04).
- Operator access to tenant/runtime/broker service accounts is time-boxed only (standing grants
  removed); the runtime is decrypt-only on the platform-global memory key; only the IAP service
  agent may invoke the gateway (2026-11-04).
- Sandbox hardening: public access prevention enforced on all buckets, Firestore delete protection
  on, Artifact Registry vulnerability scanning enabled (2026-11-05).
- `invoke-agent-live` fails closed (`503 E_LIVE_GCP_STEP_FAILED`) outside the sandbox, matching
  `/invoke-agent`.
- Context-key prewarm failures log a warning and verification fetches keys on demand (no startup
  stall on throttled CPU).

### Changed

- README rewritten for v0.1 with status labels (live / simulated / modeled / built-not-live / not
  built), hops, tokens, security model, evidence and known gaps.
- ADR-0014 status: Accepted; B2–B4 deployed, B5 pending. ADR-0011 (memory envelope encryption):
  Accepted; implemented.
- Diagrams corrected to match the code: the 5-hop architecture diagram (no Apigee, Redis replay,
  Cloud SQL, WIF/STS or unmeasured numbers) and the token flow (credential broker lane). The older
  "life of a request" image was retired.
- Demo UI "Assurance & Roadmap" tab updated for B2–B4; next is B5.

### Known gaps

See [Missing components and known gaps](docs/implementation_status.md#missing-components-and-known-gaps). The largest:
until B5 a fully compromised runtime can still obtain KMS signatures and therefore broker tokens;
replay and rate limits are in-process (single instance, Redis not wired); Postgres RLS is tested on
a simulated database; the hosted gateway runs data calls in simulation mode; the JWKS endpoint is
behind IAP.

## History

- `freeze-f1` (2026-10-30): earlier freeze tag, before ADR-0014 B2–B4 were implemented. Not a release.
