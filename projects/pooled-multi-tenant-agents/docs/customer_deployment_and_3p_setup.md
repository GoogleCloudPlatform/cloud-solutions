# Customer & FDE Deployment Guide: Deploying to Your Own GCP, Atlassian, ServiceNow & Azure Environments

> [!NOTE] Older guide. It predates Hop 0 (company IdP login in front of the 5
> hops; onboarding a customer IdP is config, see
> `config/tenants/customer-example/tenant-acme-corp.yaml`). See
> [README.md](../README.md) and [architecture.md](architecture.md) for the
> current flow.

This repository is architected for **zero-edit portability (`REQ-PORT-01` –
`REQ-PORT-06`)**. Any engineer, partner, or customer can deploy the entire
**Pattern A (High-Density Pooled Multi-Tenancy)** stack into their own Google
Cloud project and connect their own 3rd-party SaaS instances in minutes using
**only 11 configuration values**.

---

## 0. The 11 Configuration Inputs Required

Everything else (KMS CMEK key URIs, Cloud DLP template IDs, Firestore database,
BigQuery OTel tables + Row Access Policies, GCS CMEK buckets, Secret Manager
secrets, and sample Jira/ServiceNow tickets) is automatically created and wired
by our two bootstrap scripts.

| Target Environment                                             | Config Variable / CLI Flag                                                                                                                          | What You Provide                                                                      | Where to Get It                                                                                                                                                                                                                                                  |
| :------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------ | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Google Cloud (GCP)**; _(`terraform/terraform.tfvars`)_    | `project_id`; `region` _(default `us-central1`)_                                                                                                    | Your target GCP Project ID & Region                                                   | Any GCP project where you have `roles/owner` or `roles/editor`                                                                                                                                                                                                   |
| **2. Atlassian Jira Cloud**; _(Tenant Alpha: FinVault)_        | `JIRA_BASE_URL` (`--jira-url`); `JIRA_EMAIL` (`--jira-email`); `JIRA_API_TOKEN` (`--jira-token`)                                                    | `https://<your-org>.atlassian.net`; Admin email address; Atlassian API Token          | Free site at [`atlassian.com/try/cloud/signup`](https://www.atlassian.com/try/cloud/signup?bundle=jira-software) $\rightarrow$ API token at [`id.atlassian.com/manage-profile/security/api-tokens`](https://id.atlassian.com/manage-profile/security/api-tokens) |
| **3. ServiceNow PDI / ITOM**; _(Tenant Beta: RetailStream)_    | `SERVICENOW_INSTANCE_URL` (`--servicenow-url`); `SERVICENOW_USERNAME` (`--servicenow-user`); `SERVICENOW_PASSWORD` (`--servicenow-password`)        | `https://devXXXXXX.service-now.com`; `admin`; Instance admin password                 | Free Personal Developer Instance at [`developer.servicenow.com`](https://developer.servicenow.com)                                                                                                                                                               |
| **4. Microsoft Azure Entra ID**; _(Tenant Beta: RetailStream)_ | `AZURE_ENTRA_TENANT_ID` (`--entra-tenant-id`); `AZURE_ENTRA_CLIENT_ID` (`--entra-client-id`); `AZURE_ENTRA_CLIENT_SECRET` (`--entra-client-secret`) | Directory (Tenant) ID (`UUID`); Application (Client) ID (`UUID`); Client Secret Value | [`portal.azure.com`](https://portal.azure.com) $\rightarrow$ **Microsoft Entra ID** $\rightarrow$ **App registrations** $\rightarrow$ **New registration** $\rightarrow$ **Certificates & secrets**                                                              |

---

## Mode 1: Instant Local Evaluation (Zero Cloud or 3P Accounts Required — 60 Seconds)

If you just cloned the repo and want to run the 5-Hop Context Chain, the
10-Vector Slide 11 Breach Simulation Matrix, the 70 offline pytest tests, and
the interactive Architecture & Packet Tracer UI locally before provisioning
cloud resources:

```bash
make setup
uv run python run_breach_simulations.py
make test
make serve
```

Open `http://localhost:8080` to interact with the Cymbal Multi-Tenant Control
Plane across all 4 tabs.

---

## Mode 2: 1-Command Google Cloud Bootstrap (`scripts/bootstrap_customer_env.sh`)

To deploy the full Google Cloud infrastructure (Cloud KMS per-tenant CMEKs,
Model Armor, Cloud DLP templates, Firestore 5-Level AEAD Memory Bank, BigQuery
OTel + Row Access Policies, Cloud Armor WAF, and Cloud Run service) into **your
own GCP project**:

```bash
./scripts/bootstrap_customer_env.sh <YOUR_GCP_PROJECT_ID> us-central1
```

What this script does automatically:

1.  Runs `terraform -chdir=terraform init && terraform -chdir=terraform apply`
    targeting `<YOUR_GCP_PROJECT_ID>`.
1.  Extracts the newly provisioned KMS CMEK keys (`finvault_cmek_key_id`,
    `retailstream_cmek_key_id`) and Cloud DLP template IDs from
    `terraform output` and writes your `.env` file.
1.  Runs the pytest verification suite.
1.  Deploys `cymbal-pooled-gateway` to Cloud Run
    (`--no-iap --no-allow-unauthenticated`).

_(Tip: For a fast 90-second control-plane-only deployment without waiting for
AlloyDB or Memorystore Redis VM creation, set `enable_alloydb_cluster = false`
and `enable_memorystore_redis = false` in `terraform/terraform.tfvars`.)_

---

## Mode 3: Wiring Your Own Atlassian Jira, ServiceNow & Microsoft Azure Entra ID (`scripts/configure_3p_connectors.py`)

You do **not** need to manually create test projects, tables, or tickets in Jira
or ServiceNow. Use our turnkey CLI (`scripts/configure_3p_connectors.py`) to
validate your credentials, auto-seed the sample `FINVAULT` (`FINVAULT-1`,
`FINVAULT-2`) and `ROA-2026-8812` (`INC0010001`) records via REST API, upload
CMEK-encrypted runbooks to GCS, and store the credentials in your GCP project's
Secret Manager:

```bash
uv run python scripts/configure_3p_connectors.py \
  --project-id <YOUR_GCP_PROJECT_ID> \
  --jira-url https://<your-site>.atlassian.net \
  --jira-email <your-email> \
  --jira-token <your-api-token> \
  --servicenow-url https://devXXXXXX.service-now.com \
  --servicenow-user admin \
  --servicenow-password '<your-admin-password>' \
  --entra-tenant-id <YOUR_ENTRA_TENANT_ID> \
  --entra-client-id <YOUR_ENTRA_CLIENT_ID> \
  --entra-client-secret '<YOUR_ENTRA_CLIENT_SECRET>' \
  --seed-sample-data \
  --seed-gcs-runbooks
```

### Verify Your Live 3P & GCP Connections

Once configured, run these two commands to verify live HTTP traces and
end-to-end 5-Hop isolation:

```bash
uv run python scripts/verify_live_3p_traces.py
uv run python run_breach_simulations.py --live
```

---

## Mode 4: Customizing or Adding New Tenants (`config/tenants.example.yaml`)

To onboard additional tenants or change a tenant's IdP / Workspace / ITSM stack
(e.g., swapping to `Okta + Slack/Notion + PagerDuty`), copy
[`config/tenants.example.yaml`](../config/tenants.example.yaml) to
`config/tenants.yaml` or call `WorkspacePluginRegistry.register_manifest()` in
[`agents/workspace_plugins.py`](../agents/workspace_plugins.py).
