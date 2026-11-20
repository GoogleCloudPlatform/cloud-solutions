# Terraform: Pattern A pooled platform, plus modules for stamping silo and hybrid tenants

Terraform `>= 1.6.0`, `hashicorp/google` and `google-beta` `~> 6.50` (pinned in
`.terraform.lock.hcl`). The sandbox (`cymbal-multitenancy-example`) was adopted
and applied on 2026-11-06
([adoption record](../docs/terraform_adoption_2026-11-06.md)) and updated for
ADR-0014 B5 per-agent runtime services on 2026-11-09; Cloud Armor and VPC
Service Controls are still off.

## Module map

| Path                                                      | What it is                                                                                                                                                                                         | Contents                                                                                                                                                                                                                                                                                                                            |
| :-------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `main.tf`, `tenants.tf`, `moved.tf`                       | Sandbox composition (root)                                                                                                                                                                         | Providers, one `platform_core`, per-agent `agent_runtime` instances, one `tenant` per file in `config/tenants/<platform_environment>/*.yaml`; `moved` blocks from the pre-module addresses                                                                                                                                          |
| [`modules/platform_core`](modules/platform_core/)         | Shared by all tenants of one platform project                                                                                                                                                      | APIs; gateway, MCP, broker and build SAs (`cymbal-build-sa`) and their IAM; gateway and broker Cloud Run services; IAP; Cloud Armor (opt-in); context-signing and platform-global KMS keys; Model Armor and DLP templates; telemetry dataset, tables and COGS view; tenant key ring, runbook bucket, VPC, AlloyDB, Firestore, Redis |
| [`modules/agent_runtime`](modules/agent_runtime/)         | One per-agent Cloud Run runtime service ([ADR-0014 B5](../docs/adr/0014-credential-broker-and-asymmetric-context-signing.md), [ADR-0016](../docs/adr/0016-three-layer-authz-tenant-user-agent.md)) | `cymbal-agent-<key>` Cloud Run v2 service (`runtime_service.main:create_app`, `--identity-type=agent-identity --functional-type=agent`), gateway `roles/run.invoker` binding, and `lifecycle.ignore_changes` for beta Agent Identity annotations                                                                                    |
| [`modules/tenant`](modules/tenant/)                       | One tenant's blast radius ([ADR-0010](../docs/adr/0010-tenant-blast-radius-containment.md))                                                                                                        | `ct-<sha256(tenant_id)[:24]>` SA, CMEK key and its IAM, 3LO secrets and accessor, runbook managed folder, skills bucket, BigQuery row access policy and reader grants, broker (and optional runtime) TokenCreator, expiring operator access                                                                                         |
| [`modules/tenant_data_plane`](modules/tenant_data_plane/) | WS4 hybrid: data in the tenant's project                                                                                                                                                           | Tenant-held CMEK, AlloyDB with PSC, service attachment for the pooled consumer. Code only, not instantiated in the sandbox                                                                                                                                                                                                          |
| [`envs/silo-example`](envs/silo-example/)                 | WS3 silo shape                                                                                                                                                                                     | `platform_core` + one `tenant` in a dedicated project                                                                                                                                                                                                                                                                               |
| [`envs/hybrid-example`](envs/hybrid-example/)             | WS4 hybrid shape                                                                                                                                                                                   | `tenant_data_plane` in the tenant project + a PSC endpoint in the pooled project                                                                                                                                                                                                                                                    |

## WS2 / WS3 / WS4 Topology Passthrough & Module Handoff

A tenant's deployment pattern (`pool`, `silo`, or `hybrid`) is declared in
`config/tenants/<env>/<tenant>.yaml` (`topology.pattern`), validated fail-closed
at startup in [`agents/platform_config.py`](../agents/platform_config.py), and
resolved per turn by [`agents/topology_router.py`](../agents/topology_router.py)
(`TopologyRouter.route()`), which appears in every turn receipt under
`topology_route`:

| Workstream & Pattern                                           | Tenant YAML (`topology:`)                                                                                                            | Runtime Routing (`agents/topology_router.py`)                                                                                                                    | Token & Receiver Verification                                                                                                                                                                                                                           | Terraform Composition                                                                                                                                                             |
| :------------------------------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **WS2 — Pattern A: Pooled** (`pattern: pool`)                  | `pattern: pool` (no external topology URLs allowed)                                                                                  | `runtime_target = "in-process"`, `data_target = "in-process"`, `forwarded_token = None`                                                                          | Gateway signs `ctx+jwt` (`aud: ["runtime", "mcp"]`, `agent_id`) and dispatches to per-agent Cloud Run service (`cymbal-agent-*`); broker verifies caller SPIFFE principal ∩ `token.agent_id`                                                            | Root (`terraform/`): `module.platform_core` + `module.agent_runtime[*]` + `module.tenant["<tenant>"]`                                                                             |
| **WS3 — Pattern B: Dedicated Silo** (`pattern: silo`)          | `pattern: silo`, `runtime_url`, `project_id` (must differ from pooled project), `audience` (plain `https://` URL, unique per tenant) | `runtime_target = runtime_url`, `data_target = runtime_url`; derives a single-audience `ctx+jwt` (`aud = audience`, `exp <= 300s`) via `ContextTokenExchange`    | Silo runtime calls `verify_forwarded_context_token(token, audience=audience, tenant_id=tenant_id)` against the gateway's KMS public keys (JWKS); rejects internal audiences and cross-tenant tokens                                                     | [`envs/silo-example`](envs/silo-example/): dedicated tenant GCP project instantiating `module.platform_core` + one `module.tenant`                                                |
| **WS4 — Pattern C: Hybrid PSC Data Plane** (`pattern: hybrid`) | `pattern: hybrid`, `data_endpoint`, `data_project_id`, `mcp_audience` (plain `https://` URL, unique per tenant)                      | `runtime_target = "in-process"` (pooled compute), `data_target = data_endpoint` (PSC); derives a single-audience `ctx+jwt` (`aud = mcp_audience`, `exp <= 300s`) | Customer/PSC data-plane MCP receiver calls `verify_forwarded_context_token(token, audience=mcp_audience, tenant_id=tenant_id)` (or [`mcp_server/external_verifier.py`](../mcp_server/external_verifier.py)) over the Private Service Connect attachment | [`envs/hybrid-example`](envs/hybrid-example/): `module.tenant_data_plane` (tenant project CMEK + AlloyDB PSC service attachment) + consumer PSC forwarding rule in the pooled VPC |

## Stamping an environment

- **New pooled tenant (sandbox):** add `config/tenants/sandbox/<tenant>.yaml`
  (with `cmek_key`, optional `secret_ids` and `bigquery_row_policy_id`), then
  `terraform -chdir=terraform plan -var-file=sandbox.tfvars`: it adds one
  `module.tenant` instance.
- **Silo tenant:** copy `envs/silo-example`, set your values in an untracked
  `*.auto.tfvars` (`example.tfvars` shows the shape), create
  `<project>-tfstate`, then
  `terraform init -backend-config="bucket=<project>-tfstate" -backend-config="prefix=silo"`
  and plan.
- **Hybrid tenant:** same with `envs/hybrid-example`. It needs the pooled
  project's VPC and subnetwork for the PSC endpoint.
- CI runs `fmt -check`, and `init -backend=false` + `validate` for the root and
  every `envs/*`.

## Offboarding a tenant

Deleting the tenant's YAML file alone makes the next plan **fail**. This is
deliberate: the tenant's CMEK key has `prevent_destroy`, because destroying a
KMS key makes its data unrecoverable (and KMS never deletes key rings anyway).
Offboard in this order:

1.  Stop traffic first: offboard the tenant in the gateway and the broker (config
   change and redeploy; see README gap 15), so no new tokens are minted for its
   `ct-*` account.
1.  Retire the key outside Terraform: disable or schedule destruction of its key
   versions with `gcloud kms keys versions disable|destroy`, once the retention
   policy allows it.
1.  Release the key from state without destroying it: add a `removed` block
   (Terraform >= 1.7) and keep it until every state has been applied:

    ```hcl
    removed {
      from = module.tenant["tenant-x"].google_kms_crypto_key.tenant_cmek
      lifecycle {
        destroy = false
      }
    }
    ```

    (or
    `terraform state rm 'module.tenant["tenant-x"].google_kms_crypto_key.tenant_cmek'`).

1.  Remove `config/tenants/<env>/tenant-x.yaml` and plan. Expect destroys only
   under `module.tenant["tenant-x"]`: the service account and its IAM, the
   secrets and their accessors, the managed folder, the skills bucket and its
   IAM, and the row access policy. With `deletion_protection = true` the skills
   bucket is not force-destroyed, so empty it first (or export and delete its
   objects under your retention policy). Review the plan, then apply.

## Identity, memory and serving settings (Oct 2026)

- **`platform_environment` has no default.** Pass it explicitly
  (`scripts/deploy.sh` does); a defaulted `sandbox` in a real project would
  enable sandbox-only behaviour. The gateway also refuses sandbox mode unless
  Cloud Run's metadata server reports the sandbox's own project.
- **Platform key for GLOBAL memory (`cymbal-platform-global`):** the serving
  identity has `cryptoKeyDecrypter` only; writers are listed in
  **`global_memory_curators`** (`cryptoKeyEncrypter`, empty by default, so
  nobody can write GLOBAL until named; grant via PAM). The key exists in the
  sandbox already: `terraform import` it before the first apply.
- **Gateway signing key (customer environments):** create a Secret Manager
  secret holding an EC P-256 PKCS#8 key, grant the serving SA `secretAccessor`,
  and set `identity.gateway_signing_secret: <secret-id>/versions/<n>` in the
  environment config. Terraform for this secret is a follow-up.
- **Scale-out:** keep the gateway at one instance until the DPoP replay cache is
  shared (or `DPoP-Nonce` is added); see the follow-ups in
  [`../docs/tenant_isolation_assurance.md`](../docs/tenant_isolation_assurance.md).
- **Existing sandbox:** adopted and applied on 2026-11-06; see
  [`../docs/terraform_adoption_2026-11-06.md`](../docs/terraform_adoption_2026-11-06.md).
  Every apply needs a reviewed plan with **zero destroys and zero
  replacements**. The module refactor is moves only (`moved.tf`).
- **Deletion protection is on by default** (`deletion_protection = true`). It
  sets `deletion_protection` on the Cloud Run services and BigQuery tables and
  turns off `force_destroy` on the buckets. These are Terraform-side guards:
  `terraform destroy` fails instead of deleting data. Set
  `-var=deletion_protection=false`, then apply, only to tear down a throwaway
  environment.
- **Provider lock file** (`.terraform.lock.hcl`) is committed with hashes for
  linux and darwin (amd64 and arm64), so CI and applies use the same provider
  builds. Refresh it with `terraform providers lock -platform=...` when you
  change provider versions.

## Remote state

State is stored in GCS (`backend.tf`). No bucket is set by default, because
bucket names are global: `terraform init` fails until you pass your own bucket
and prefix at init time (`scripts/deploy.sh` does this, with `<project>-tfstate`
and the environment name):

```bash
terraform -chdir=terraform init -reconfigure \
  -backend-config="bucket=<project>-tfstate" -backend-config="prefix=<env>"
```

Create the state bucket once per project, before the first `init`:

```bash
gcloud storage buckets create gs://<project>-tfstate --project=<project> --location=<region> \
  --uniform-bucket-level-access --public-access-prevention
gcloud storage buckets update gs://<project>-tfstate --versioning --update-labels=purpose=terraform-state
```

State can contain sensitive values: never commit it, and limit bucket access to
the operators who run Terraform. Local validation without credentials still
works with `init -backend=false`.

Sandbox plan (reviewer / operator IAP lists stay in the untracked
`terraform/sandbox.auto.tfvars`):

```bash
terraform -chdir=terraform init
terraform -chdir=terraform plan -var-file=sandbox.tfvars
```

## Quickstart

Prefer the unified repository deployment workflow
(`make config-check ENV=sandbox` and `make deploy-infra ENV=sandbox`; see
[`../docs/customer_deployment.md`](../docs/customer_deployment.md)), or run
Terraform directly:

```bash
# 1. Initialize providers & validate HCL syntax locally (zero cloud credentials needed)
terraform -chdir=terraform init -backend=false
terraform -chdir=terraform validate

# 2. Fast Control-Plane Plan (skips long-running AlloyDB & Memorystore cluster creation)
terraform -chdir=terraform init -reconfigure \
  -backend-config="bucket=<project>-tfstate" -backend-config="prefix=<env>"
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
terraform -chdir=terraform plan \
  -var="enable_alloydb_cluster=false" \
  -var="enable_memorystore_redis=false"

# 3. Full Production Apply
terraform -chdir=terraform apply
```
