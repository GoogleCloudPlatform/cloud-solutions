# Compute Scaling & Agent Sandbox in Gemini Isolation ("The Brain vs. The Hands")

This guide documents how the Cymbal multi-tenant platform separates stateless
orchestration (**The Brain**) from untrusted code and shell execution (**The
Hands**), aligning
[ADR-0012](adr/0012-compute-sandbox-scale-and-workstream-alignment.md) with both
managed **Gemini Sandboxes** and self-managed **GKE Agent Sandbox (`gVisor`)**
warm pools.

---

## 1. Deployment Verification Matrix (3-Bucket Claim Discipline)

| Capability                                                | Live in Terraform (`cymbal-multitenancy-example`, `us-central1`)                                                                                                                                            | Built & Hermetically Verified in Repo                                                                                                                                                                                                                                               | Target Managed / Self-Managed Manifest                                                                                                                                                                                                                              |
| :-------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Stateless Agent Harness ("The Brain")**                 | `cymbal-pooled-gateway`, `cymbal-agent-shared`, `cymbal-agent-finvault-alpha`, and `cymbal-credential-broker` on Cloud Run (`us-central1`)                                                                  | `app/main.py`, `runtime_service/main.py`, `agents/turn_engine.py`                                                                                                                                                                                                                   | Horizontal multi-replica scaling gated on shared Memorystore replay store (`ADR-0012`)                                                                                                                                                                              |
| **Claim-and-Taint Session Sandbox Manager ("The Hands")** | Control-plane IAM and per-tenant `ct-*` service accounts isolated in `cymbal-credential-broker`; optional `agent_sandbox_reasoning_engine_name` variable wired in Terraform (unset `""` until live cutover) | `GeminiAgentSandboxManager`, `LiveGeminiAgentSandboxClient`, and `HermeticZeroCredentialSandboxBackend` (`agents/sandbox_execution.py`), wired into `app/main.py`, Phase B5 `runtime_service/main.py`, and ADK/MCP tool `execute_diagnostic_sandbox` (`2lo:cymbal.sandbox.execute`) | Provision parent `ReasoningEngine` via `scripts/provision_gemini_agent_sandbox.py --live` (`agentplatform` 2.7.0 `sandboxEnvironments`, `Chunk` `:execute`, Proto3 LRO polling) and propagate `AGENT_SANDBOX_*` flags on Cloud Run rollouts via `scripts/deploy.sh` |
| **Kubernetes Portability (`agents.x-k8s.io/v1beta1`)**    | Not provisioned in the Cloud Run sandbox project                                                                                                                                                            | Validated against `gVisor`, non-root UID `1000`, `automountServiceAccountToken: false`, and metadata-blocking `NetworkPolicy` invariants in `tests/security/test_gemini_agent_sandbox_isolation.py`                                                                                 | Reference manifest in [`terraform/examples/gke_sandbox_warm_pool.yaml`](../terraform/examples/gke_sandbox_warm_pool.yaml)                                                                                                                                           |

---

## 2. Why Separate "The Brain" from "The Hands"?

In a pooled multi-tenant architecture, the **Agent Harness ("The Brain")**
orchestrates prompts, enforces `Tenant ∩ User ∩ Agent` policy checks
(`AgentRegistryPDP`), verifies KMS-signed `ctx+jwt` context tokens, and calls
pre-registered stateless MCP tools. Because Python `asyncio` orchestration is
I/O-bound and runs only trusted platform code, multiple concurrent tenant
requests safely share a pooled Cloud Run container without accessing each
other's credentials (which live out-of-process in `cymbal-credential-broker`).

By contrast, **code execution, log-parsing scripts, dynamic skills, and shell
commands ("The Hands")** evaluate LLM-generated or untrusted logic. Running
untrusted code inside a shared multi-tenant Python worker would expose process
heap memory and sibling coroutines if an interpreter or native library
vulnerability were triggered.

To eliminate that blast radius without provisioning one permanent agent
container per user session, "The Hands" run **out-of-process** in per-session
sandboxes governed by five strict invariants (`agents/sandbox_execution.py`):

1.  **Synchronous Policy Gate Before Lookup**: `GeminiAgentSandboxManager`
    verifies active tenant onboarding (`TENANT_DIRECTORY`), `AgentRegistryPDP`
    (`Tenant ∩ User ∩ Agent`), capability scope `2lo:cymbal.sandbox.execute`
    across all sandbox languages, and intra-tenant role RBAC (`sre_admin`
    required for interactive `bash`) _before_ inspecting the session-sandbox
    table.
1.  **One-Way Claim-and-Taint State Machine**:

    ```text
    STATE_UNCLAIMED -> STATE_RUNNING(tenant_id, user_sub, agent_id, session_id)
                    -> STATE_PAUSED
                    -> STATE_DESTROYED
    ```

    Once claimed, a sandbox is permanently bound to a single
    `(tenant_id, user_sub, agent_id, session_id)` 4-tuple. Releasing a session
    (`DELETE /api/v1/sandboxes/session`), offboarding a tenant
    (`offboard_tenant`), or reaching `ttl` (`900s` default, `3600s` ceiling)
    destroys the sandbox permanently—tainted sandboxes are **never** returned to
    a shared warm pool.

1.  **Zero Credentials & Metadata Lockdown**:
    `assert_zero_credentials_and_egress_safe` blocks `ct-*` service-account
    tokens, OAuth bearer tokens, private keys, `GOOGLE_APPLICATION_CREDENTIALS`,
    metadata-server IPs (`169.254.169.254`, `169.254.170.2`,
    `metadata.google.internal`), and `/proc/self/mem` probes in $O(N)$ linear
    time before execution. The harness fetches scoped data via MCP first and
    passes only sanitized read-only JSON into `/workspace`.
1.  **Per-Tenant Concurrency Bulkheads**: Active and paused sandboxes are capped
    per tenant (`Enterprise: 20`, `Standard: 5`), returning `HTTP 429`
    (`E_SANDBOX_BULKHEAD_EXHAUSTED`) to a noisy tenant while leaving sibling
    tenants unaffected.
1.  **Fail-Closed Availability (`HTTP 503`)**: Backend transport errors or
    warm-pool exhaustion raise `SandboxUnavailableError`, mapped to `HTTP 503`
    with `Retry-After: 15` and `Cache-Control: no-store`—never `HTTP 401` and
    never an unisolated fallback.

---

## 3. Two Supported Sandbox Backends

### Option A: Managed Gemini Sandboxes (Recommended)

[Gemini Sandboxes](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/sandbox)
(`sandboxEnvironments` parented to an Agent Engine `ReasoningEngine` or
`SandboxEnvironmentTemplate` on `aiplatform.googleapis.com`) provide managed
per-session execution without cluster operations:

- **Default-Safe `gVisor` Environments**: Built-in `CodeExecutionEnvironment`
  (`LANGUAGE_PYTHON`, `LANGUAGE_JAVASCRIPT`) runs inside a managed
  `4.19.0-gvisor` user-space kernel (`/home/bard`) with zero cloud credentials
  (`GOOGLE_*`/`GCE_*` absent) and both `169.254.169.254` metadata and public
  internet (`8.8.8.8`) blocked by default; custom `ShellSandbox` /
  `ContainerSandbox` runs as unprivileged `appuser` inside `/workspace` (`sudo`
  disabled) with zero mounted cloud credentials and metadata/egress disabled by
  default.
- **Explicit Lifecycle & Measured Wire Protocol**:
  `LiveGeminiAgentSandboxClient` (`agents/sandbox_execution.py`, re-exported in
  `agents/gcp_live_bridge.py`) implements the `agentplatform` 2.7.0
  `sandboxEnvironments` protocol: Proto3 `done`-omitted LRO operation polling on
  `create` (`~2.0s` warm sandbox creation after initial `~175s` parent-engine
  pool warm-up), base64 `Chunk` `:execute` (`code` + read-only
  `readonly_input.json` inputs, `exit_status_int`/`msg_out`/`msg_err` outputs in
  `~1.0s–2.4s` across stateful multi-turn sessions), `spec.shellEnvironment` or
  `projects/{project}/locations/{location}/reasoningEngines/{id}/sandboxEnvironmentTemplates/{tpl}`
  for Bash with control-plane 3-chunk `:execute` proxy
  (`application/x.sandbox-request-uri`=`/exec`,
  `application/x.sandbox-request-port`=`8080`,
  `application/json`=`{"command": ...}`), `/:pause` (`STATE_PAUSED`) and
  `/:resume` (`STATE_RUNNING`) LROs, and `DELETE` (`STATE_DESTROYED`).
- **First-Class Opt-In ADK & MCP Tool (`execute_diagnostic_sandbox`)**:
  Registered in `TOOL_REGISTRY` and `AGENT_CATALOG` (`agents/registry.py`) under
  capability scope `2lo:cymbal.sandbox.execute`. Tenants without
  `2lo:cymbal.sandbox.execute` have the tool pruned automatically by
  `enforce_tenant_isolation_interceptor` before model invocation.
- **No Migration Off Cloud Run Required**: Creating an empty parent
  `ReasoningEngine` via `scripts/provision_gemini_agent_sandbox.py`
  (`--live --verify-manager --project-id <PROJECT_ID>`) takes ~`7.3s` and serves
  solely as the Vertex AI API parent resource for `sandboxEnvironments`.
  Stateless Cloud Run services (`cymbal-pooled-gateway`, `cymbal-agent-shared`,
  `cymbal-agent-finvault-alpha`) continue hosting **The Brain** while spawning
  per-session agent sandbox in Geminies out-of-process via Terraform variable
  `agent_sandbox_reasoning_engine_name` (`AGENT_SANDBOX_REASONING_ENGINE_NAME`).
  Because `module.agent_runtime` keeps `lifecycle.ignore_changes` on
  `template[0].containers[0].env` to protect Cloud Run `functional_type`,
  `scripts/deploy.sh` propagates configured `AGENT_SANDBOX_*` flags via
  `--update-env-vars` during Cloud Run rollouts. If
  `AGENT_SANDBOX_REASONING_ENGINE_NAME` is unset when `CYMBAL_LIVE_GCP=1`,
  `LiveGeminiAgentSandboxClient` fails closed with `HTTP 503`
  (`E_SANDBOX_UNAVAILABLE`).

### Option B: Self-Managed GKE Agent Sandbox (`gVisor` `SandboxWarmPool` + `SandboxClaim`)

For organizations standardizing on Kubernetes (`agents.x-k8s.io/v1beta1`),
[`terraform/examples/gke_sandbox_warm_pool.yaml`](../terraform/examples/gke_sandbox_warm_pool.yaml)
defines a portable Kubernetes YAML reference manifest (validated statically in
CI rather than via a live cluster or separate Python `SandboxBackendClient`
driver):

- **`SandboxTemplate`**: Pins `runtimeClassName: gvisor`,
  `automountServiceAccountToken: false`, `runAsNonRoot: true` (`UID 1000`),
  `readOnlyRootFilesystem: true`, `capabilities.drop: ["ALL"]`, and a `512Mi`
  memory-backed `emptyDir` at `/workspace`.
- **`SandboxWarmPool`**: Pre-warms `replicas: 10` un-tainted `gVisor` pods to
  eliminate cold-start latency when a session claims a sandbox.
- **`SandboxClaim` & `NetworkPolicy`**: Binds a claimed pod with
  `shutdownPolicy: Delete` and enforces default-deny ingress/egress blocking
  `169.254.169.254/32` and east-west RFC1918 ranges.
