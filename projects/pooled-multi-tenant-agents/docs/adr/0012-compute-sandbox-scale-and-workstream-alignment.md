# ADR-0012: Compute Scaling Gates, Ephemeral Sandbox Reference, Model Router Preconditions, and Scope Alignment

- **Status**: Accepted (`PR-S1` & `PR-S2` implemented; `PR-S3` & `PR-S4` gated
  on shared replay store)
- **Date**: 2026-10-30 (Updated: 2026-11-16)
- **Authors**: Google Cloud Solutions Architecture Team
- **Reviewers**: Multi-Tenant Agent Platform Architecture Reviewers
- **Applies To**: Hop 3 Compute & Sandbox Scaling, Step-3 Credential Broker &
  Model Router Seam, Narrative & Compliance Scope
  (`docs/executive_review_writeup.md`, `docs/blog_outline.md`,
  `docs/blog_deep_dive_part2.md`, `docs/tenant_isolation_assurance.md`)
- **Companion TDD**:
  `docs/tdd_compute_sandbox_scale_and_workstream_alignment.md`

## Context

At the `freeze-f1` baseline (`0bcfae5`), the pooled gateway enforces Hop 0
federated login, RFC 9449 DPoP sender-constrained tokens, per-tenant Cloud KMS
envelope encryption (`ADR-0011`), and per-tenant service accounts (`ADR-0010`).
Four cross-workstream requirements remain before scaling beyond the
single-instance sandbox or publishing the external reference guide:

1.  **Single-Instance Scale-Out Gate (`FM-01`, `freeze-f1` P2)**: The gateway
    currently stores its DPoP proof replay cache (`_ReplayCache`) and ID-token
    key binding table (`_SubjectTokenBindings`) in process memory
    (`app/gateway_tokens.py`). In the sandbox (`max_instance_count = 1`),
    single-use proof enforcement is exact. Scaling horizontally
    (`min_instance_count >= 2`) requires landing a shared replay store
    (Memorystore for Redis) or stateless `DPoP-Nonce` challenge first, and
    applying Cloud Run sizing in the Step-4 import-first Terraform series.
1.  **Ephemeral Agent Sandbox Isolation (Design Reference Only)**: Customers who
    extend agents with untrusted code execution pair the pooled runtime with
    ephemeral gVisor (`runsc`) sandboxes. Because `freeze-f1` uses a fixed,
    pre-registered MCP tool catalog without code execution, adding a simulated
    Python sandbox class in `agents/` would misrepresent a design pattern as an
    active runtime control. Furthermore, untrusted sandboxes must never receive
    injected tenant service account tokens (`ct-<sha256[:24]>`); sandboxed tool
    calls must traverse the out-of-process Step-3 Credential Broker.
1.  **Model Router Preconditions and Step-3 Broker Ordering**: The Workstream 1
    Model Routing layer (`modelrouter`) handles multi-publisher routing,
    Provisioned Throughput (`PT`) `429` fallback chains, and token cost ledgers.
    However, three preconditions must be met before connecting `modelrouter` to
    a zero-leakage multi-tenant runtime:
    - `modelrouter`'s semantic cache (`Firestore` vector search) is not
      partitioned by `tenant_id`;
    - `modelrouter`'s auto-provisioning maps an email domain or GCP project
      (`X-Goog-User-Project`) to a single tenant;
    - `modelrouter`'s Redis rate limiter fails open on connection errors. In
      addition, minting router tokens inside the runtime container recreates the
      `roles/iam.serviceAccountTokenCreator` blast-radius gap (`freeze-f1` P1).
      The router identity bridge (`PR-S4`) must therefore sequence after the
      Step-3 Credential Broker and request router-audience tokens from that
      separate broker.
1.  **Data Residency vs. Model Processing and Vertical Scope**: Managed storage
    services (`Firestore`, `AlloyDB`, `Cloud Storage`, `Cloud KMS`) enforce
    regional data residency at rest, whereas managed agent runtime and LLM
    inference follow Vertex AI regional endpoint availability and are not
    accredited for sovereign model processing. Draft documents also reference
    three verticals including regulated Finance (`OCC 12 CFR Part 30`,
    `SEC Rule 17a-4`), which adds domain-specific banking compliance scope
    outside the core multi-tenant platform blueprint.

## Decision

1.  **Three-Tier Compute Scaling with Explicit Pre-Scale Gates**:
    - **Tier 1 (Cloud Run Gateway PEP)**: Keep the sandbox pinned to
      `max_instance_count = 1` until the DPoP replay cache and subject-token
      binding store move to shared Memorystore for Redis (`PR-DA2`) or
      `DPoP-Nonce`. Once that gate lands, configure customer horizontal scaling
      (`min_instance_count = 2`, `max_instance_count = 20`,
      `max_instance_request_concurrency = 80` on `2 vCPU / 2 GiB`,
      `cpu_idle = false`) in the Step-4 import-first Terraform series (`PR-S3`).
    - **Tier 2 (Agent Runtime)**: The runtime executes on Cloud Run today, with
      agent runtime in Gemini (`ReasoningEngine`) supported as an optional
      managed deployment target (`4..16` concurrent reasoning loops per worker,
      `/24` Direct VPC Egress subnet sizing).
    - **Tier 3 (Per-Session agent sandboxes in Gemini & GKE `gVisor` Warm Pools,
      `PR-S2` Implemented)**: Implement the one-way `Claim-and-Taint` session
      sandbox manager (`GeminiAgentSandboxManager` and
      `LiveGeminiAgentSandboxClient` in
      [`agents/sandbox_execution.py`](../../agents/sandbox_execution.py),
      re-exported in
      [`agents/gcp_live_bridge.py`](../../agents/gcp_live_bridge.py) and wired
      into both `app/main.py` and Phase B5 `runtime_service/main.py`) targeting
      managed
      [Gemini Sandboxes](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/sandbox)
      (`sandboxEnvironments` + `SandboxEnvironmentTemplate`), exposed as a
      first-class opt-in ADK/MCP tool (`execute_diagnostic_sandbox`, scope
      `2lo:cymbal.sandbox.execute`), provisioned via
      [`scripts/provision_gemini_agent_sandbox.py`](../../scripts/provision_gemini_agent_sandbox.py)
      and Terraform (`agent_sandbox_reasoning_engine_name`), and paired with a
      portable Kubernetes `agents.x-k8s.io/v1beta1`
      `SandboxTemplate`/`SandboxWarmPool`/`SandboxClaim` manifest
      ([`terraform/examples/gke_sandbox_warm_pool.yaml`](../../terraform/examples/gke_sandbox_warm_pool.yaml))
      and scaling guide
      ([`docs/compute_and_sandbox_scaling.md`](../compute_and_sandbox_scaling.md)).
      Enforce synchronous policy checks before lookup, per-tenant active-sandbox
      bulkheads (`Standard: 5`, `Enterprise: 20`), immediate `offboard_tenant`
      destruction, zero credential or metadata-server (`169.254.169.254`) access
      inside the sandbox, and fail-closed `HTTP 503` availability semantics when
      `AGENT_SANDBOX_REASONING_ENGINE_NAME` or the sandbox backend is
      unavailable.
1.  **Model Router Integration Sequenced After the Step-3 Credential Broker
    (`PR-S4`)**:
    - Document `modelrouter`'s three multi-tenant preconditions
      (tenant-partitioned semantic cache, explicit per-SA `identities`
      registration with auto-provisioning disabled, and fail-closed rate
      limiting) as hard integration gates.
    - Sequence `PR-S4` after the Step-3 Credential Broker so the runtime holds
      zero `TokenCreator` privileges and requests a router-audience OIDC token
      (`aud = MODEL_ROUTER_URL`) from the broker on behalf of a verified caller.
1.  **Data-at-Rest Residency Boundaries and Vertical Scope (`PR-S1`)**:
    - Remove "sovereign model processing" claims, rename Pattern B in
      documentation from _"Pattern B: Sovereign Silos"_ to **"Pattern B:
      Dedicated Single-Tenant Silos"**, and state the boundary between regional
      data residency at rest and regional Vertex AI inference.
    - Scope the narrative and blog files (`docs/executive_review_writeup.md`,
      `docs/blog_outline.md`, `docs/blog_deep_dive_part2.md`,
      `docs/tenant_isolation_assurance.md`) to 1-2 enterprise SaaS and
      e-commerce operations verticals using the existing platform RBAC roles
      (`sre_admin`, `compliance_officer`, `read_only_analyst`), leaving
      `README.md` untouched so `PR-S1` merges without conflicts.

## Consequences

- **Honest 3-bucket separation between built runtime controls and live cloud
  cutover**: `GeminiAgentSandboxManager` enforces the Claim-and-Taint state
  machine, zero-credential/metadata screening, role RBAC, and tenant offboarding
  eviction in-process (verified hermetically with
  `HermeticZeroCredentialSandboxBackend`), while `LiveGeminiAgentSandboxClient`
  calls managed Gemini `sandboxEnvironments` when
  `AGENT_SANDBOX_REASONING_ENGINE_NAME` is configured and fails closed
  (`HTTP 503`) otherwise.
- **Preserves Step-3/B4 blast-radius reduction**: Sequencing `PR-S4` after
  `cymbal-credential-broker` and prohibiting `ct-*` or bearer credential
  injection into sandboxes ensures neither the agent runtime nor the code
  sandbox ever holds `TokenCreator` over `ct-*` service accounts.
- **Portable managed and Kubernetes execution**: Teams can run "The Hands" on
  managed Gemini `sandboxEnvironments` without cluster operations or deploy
  self-managed `gVisor` warm pools on GKE
  (`terraform/examples/gke_sandbox_warm_pool.yaml`) behind the same
  `SandboxBackendClient` protocol.
