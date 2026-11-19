# Deploying the Pooled Platform (Sandbox or Customer)

There is **one deployment path**. Our sandbox and every customer project use the
same steps; only the configuration differs.

> **Status:** `scripts/bootstrap_customer_env.sh` and `scripts/deploy.sh`
> provide a single turnkey deployment path for clean-room projects as well as
> adopted environments (automatically creating `${PROJECT_ID}-tfstate`,
> pre-building the bootstrap image via Cloud Build with `cymbal-build-sa`,
> bootstrapping per-agent Cloud Run Agent Identity services, wiring Memorystore
> Redis AUTH+TLS, and applying AlloyDB PostgreSQL RLS schemas & per-tenant
> `ct-*` roles). Review every Terraform plan before approving in production.

## Prerequisites

- A Google Cloud project, plus an operator with rights to run Terraform in it.
- `gcloud` (authenticated), `terraform >= 1.6`, `uv` (Python `>= 3.12`).
- APIs are enabled by Terraform (`terraform/main.tf`).

## 1. Configure

```bash
cp config/environments/customer.example.yaml config/environments/acme.yaml   # set gcp.project_id
mkdir -p config/tenants/acme
cp config/tenants/customer-example/tenant-acme-corp.yaml config/tenants/acme/   # one file per tenant
sed -i 's#tenants/customer-example#tenants/acme#' config/environments/acme.yaml
cp terraform/terraform.tfvars.example terraform/acme.tfvars
make config-check ENV=acme
```

Notice `terraform/acme.tfvars` and `config/environments/acme.yaml` do not need
any hardcoded numeric GCP project number: `module.platform_core` derives
`CREDENTIAL_BROKER_URL`, `AGENT_RUNTIME_URLS`, and `BROKER_ALLOWED_CALLERS`
SPIFFE principals automatically, and `agent_identity.bindings` supports
`{org_id}`, `{project_number}`, and `{region}` placeholders resolved at startup.
See [configuration_reference.md](configuration_reference.md) for every field.

**AlloyDB public IP (`alloydb_enable_public_ip`).** The Terraform default is
`false`: the primary instance has a private VPC address only.
`scripts/deploy.sh` bootstraps the RLS schema through the AlloyDB Auth Proxy
from the machine it runs on, so choose one:

| Where `deploy.sh` runs                                                 | Setting                                                                                          | What it exposes                                                                                                                                                                                               |
| :--------------------------------------------------------------------- | :----------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Outside the VPC (laptop, default Cloud Shell)                          | `alloydb_enable_public_ip = true` (what `terraform.tfvars.example` ships, with this explanation) | An internet-facing AlloyDB endpoint. No authorized networks are configured, so it accepts only Auth Proxy / connector connections (mTLS, `roles/alloydb.client`, IAM database auth); raw TCP 5432 is refused. |
| Inside the VPC (bastion, Cloud Build private pool, Cloud Workstations) | leave it `false`                                                                                 | Nothing public. `deploy.sh` connects the proxy to the private address (`bootstrap_alloydb_rls.py --private-ip`).                                                                                              |

After the schema is bootstrapped you can set it back to `false` and
`terraform apply` to remove the public IP; later schema changes then need a
machine inside the VPC (or `--skip-db-bootstrap`).

## 2. Deploy

```bash
./scripts/bootstrap_customer_env.sh acme --provision-sandbox   # config-check -> zero-state infra + agent sandbox in Gemini + AlloyDB RLS -> smoke
# or:
make deploy ENV=acme                                        # config-check -> terraform apply -> image -> smoke
```

| Step                | What it does                                                                                                                                                                               | Run alone |
| :------------------ | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :-------- |
| `make config-check` | Validates config (fails fast)                                                                                                                                                              | ✅        |
| `make deploy-infra` | `terraform apply` (+ AlloyDB RLS bootstrap when primary enabled). Owns infra, IAM, **the gateway's single service account and env vars**, guardrail templates, and per-tenant row policies | ✅        |
| `make deploy-image` | Builds and rolls the image only, **without** changing identity or env                                                                                                                      | ✅        |
| `make smoke`        | Tier 3 post-deploy checks                                                                                                                                                                  | ✅        |

Enterprise CI/CD can call these targets individually instead of `make deploy`.

## 3. Load third-party secrets (optional)

Terraform creates the secret shells and grants each one **only** to its tenant's
service account. Scripts write **values only**:

```bash
uv run python scripts/configure_3p_connectors.py --project-id <project> ...   # values, no IAM
./scripts/rotate_jira_api_token.sh "<token>"                                   # verified rotation
```

## 4. Validate

| Tier | Command                         | Proves                                                                                                      |
| :--- | :------------------------------ | :---------------------------------------------------------------------------------------------------------- |
| 1    | `make test`                     | Logic, breach matrix, config, IAM, and env contracts (no cloud)                                             |
| 2    | `make serve`, `make breach-sim` | Local demo, offline                                                                                         |
| 3    | `make smoke ENV=acme`           | Gateway up; each tenant's catalog; 10/10 breach vectors blocked                                             |
| 4    | `make validate ENV=acme`        | Live: IAM denies cross-tenant key, secret, and runbook access; per-tenant BigQuery row policies; connectors |

## Design guarantees

- **One serving identity** (`cymbal-pooled-runtime-sa`), defined only in
  Terraform. It holds no project-wide KMS, Secret Manager, or Storage roles and
  no admin roles. It reaches tenant data only by impersonating that tenant's
  service account ([ADR-0010](adr/0010-tenant-blast-radius-containment.md)).
- **The runtime never provisions security resources.** Model Armor templates and
  BigQuery row policies are Terraform resources; the app only verifies them.
- **No hard-coded project.** A placeholder or missing project stops the gateway
  in live mode.
- **Secrets live only in Secret Manager**
  ([secrets_management.md](secrets_management.md)).
