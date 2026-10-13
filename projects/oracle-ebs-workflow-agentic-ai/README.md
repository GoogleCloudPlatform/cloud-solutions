# Oracle EBS workflow and approval triage agentic AI

An enterprise, policy-aware autonomous workflow management microservice
architecture for Oracle E-Business Suite (EBS) Release 12.x. Integrates with
Google Cloud Gemini Enterprise, Vertex AI (`gemini-3.8-flash`), Agent-to-Agent
(A2A) Protocol v0.3.0, Model Context Protocol (MCP), and certified Oracle EBS
Workflow REST and PL/SQL APIs.

> [!IMPORTANT]
>
> **Prerequisites and Required IAM Roles**:
>
> - **Tools**: Python 3.10+, Google Cloud CLI (`gcloud`), Terraform (v1.5.0+),
>   and Docker.
> - **Oracle EBS Vision Instance**: Active Oracle EBS instance on Google Cloud.
>   Clone and configure from [Oracle EBS Framework on Google
>   Cloud][ebs-sample-repo].
> - **Gemini Enterprise Entitlement**: Active Gemini Enterprise license on the
>   Google Cloud organization.
> - **Identity and Access Management (IAM) Roles**: Discovery Engine Admin
>   (`roles/discoveryengine.admin`), Cloud Run Invoker (`roles/run.invoker`),
>   and Secret Manager Secret Accessor (`roles/secretmanager.secretAccessor`).
> - **Enabled Google Cloud APIs**: Discovery Engine
>   (`discoveryengine.googleapis.com`), Vertex AI (`aiplatform.googleapis.com`),
>   Cloud Run (`run.googleapis.com`), Secret Manager
>   (`secretmanager.googleapis.com`), Artifact Registry
>   (`artifactregistry.googleapis.com`), and Cloud Build
>   (`cloudbuild.googleapis.com`).

## Key capabilities

- **Autonomous Multi-Workflow Triage**: Inspects, categorizes, and aggregates
  pending approvals across Expense Reports (`APEXP`), Purchase Orders
  (`POAPPR`), and Requisitions (`REQAPPR`).
- **Policy and risk verification engine**: Evaluates corporate policy rules
  (lodging limits, alcohol spend, delegation thresholds, budget overruns) and
  assigns risk tiers (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
- **Explicit Human Confirmation Gate**: Mutative actions (`APPROVE`, `REJECT`)
  strictly require explicit user confirmation (`confirmed=True`). Unconfirmed
  requests receive a detailed `ConfirmationProposal` with risk alerts and
  confirmation prompt.
- **Certified Oracle EBS Action Layer**: ZERO raw SQL updates or direct table
  mutations. Executes responses strictly using:
    - **Path A (Session PL/SQL)**: `apps.fnd_global.apps_initialize` +
      `apps.wf_notification.setattrtext` + `apps.wf_notification.respond`
    - **Path B (ISG REST)**: `POST /webservices/rest/wf/respond` through Oracle
      Integrated SOA Gateway (ISG).
- **A2A Protocol v0.3.0 and MCP compliance**: Exposes the agent catalog at
  `/a2a/card` and Model Context Protocol database tools at `/mcp/`.

## Architecture and microservices

1.  **Workflow A2A Gateway Server (`src/a2a/a2a_server.py`)**:

    - Cognitive natural language interface using Vertex AI Gemini
      (`gemini-3.8-flash` primary, `gemini-3.7-flash` fallback,
      `gemini-3.5-flash-lite` routing).
    - Dynamic intent extraction and Markdown table synthesis.
    - Google Cloud OIDC token validation and authenticated downstream routing.

1.  **Core Workflow Agent (`src/agents/workflow_agent.py`)**:

    - `/notifications`: Worklist retrieval through Oracle ISG REST and certified
      PL/SQL API (`apps.xx_ebs_wf_agent_pkg`).
    - `/notifications/{id}`: Detailed attribute inspection (amount, requester,
      justification).
    - `/verify-policy`: Risk tier calculation and violation identification.
    - `/triage`: Batch policy evaluation and rich Markdown table rendering.
    - `/execute`: Certified response execution with human confirmation gate
      enforcement.
    - `/respond`: Direct action execution for single notification items.

1.  **Workflow MCP Server (`src/mcp/mcp_server.py`)**:

    - Model Context Protocol tool endpoints for workflow triage, inspection,
      policy check, and response.

## Configuration and environment variables

| Variable                  | Description                             | Default                                |
| :------------------------ | :-------------------------------------- | :------------------------------------- |
| `ORACLE_HOST`             | Oracle Database Host / IP               | `127.0.0.1`                            |
| `ORACLE_PORT`             | Oracle Database Listener Port           | `1521`                                 |
| `ORACLE_SERVICE_NAME`     | Oracle Database Service Name            | `ebsdb`                                |
| `ORACLE_USER`             | Oracle EBS Schema / Apps User           | `apps`                                 |
| `ORACLE_PASSWORD`         | Oracle EBS User Password                | _(from Secret Manager / env)_          |
| `FND_USER_ID`             | Default FND User ID                     | `0` (SYSADMIN)                         |
| `FND_RESP_ID`             | Default FND Responsibility ID           | `20420` (System Administrator)         |
| `FND_RESP_APPL_ID`        | Default FND Responsibility App ID       | `1` (FND / Application Object Library) |
| `WORKFLOW_EXECUTION_PATH` | Execution Path: `REST` or `PLSQL`       | `REST`                                 |
| `ISG_REST_BASE_URL`       | Base URL for Integrated SOA Gateway     | `http://127.0.0.1:8000`                |
| `ISG_USERNAME`            | Oracle EBS ISG REST Basic Auth User     | `ISGADMIN`                             |
| `ISG_PASSWORD`            | Oracle EBS ISG REST Basic Auth Password | _(from Secret Manager / env)_          |
| `GOOGLE_CLOUD_PROJECT`    | Google Cloud Project ID                 | _(auto-detected)_                      |
| `GEMINI_MODEL`            | Primary Foundation Model                | `gemini-3.8-flash`                     |
| `GEMINI_FALLBACK_MODEL`   | Fallback Foundation Model               | `gemini-3.7-flash`                     |
| `GEMINI_FLASH_LITE_MODEL` | High-speed routing model                | `gemini-3.5-flash-lite`                |

> [!NOTE]
>
> **Tiered Hybrid Model Architecture**: The A2A gateway uses
> `gemini-3.5-flash-lite` for fast intent routing and Markdown rendering, and
> `gemini-3.8-flash` (`gemini-3.7-flash` fallback) for policy reasoning and tool
> orchestration.

## Deployment options

Before running either deployment method:

1.  **Create `terraform/terraform.tfvars`** (gitignored and auto-loaded by
    Terraform and `./scripts/deploy_stack.sh`) with your project, VPC/subnet,
    and Oracle settings mapped to the table above and `terraform/variables.tf`
    (such as `project_id`, `region`, `vpc_network_name`, `oracle_host`, and
    `isg_rest_base_url`).
1.  **Export database and ISG passwords in your shell** so credentials stay out
    of Terraform state and Secret Manager versions are not left empty:

    ```bash
    export ORACLE_PASSWORD="YOUR_APPS_DB_PASSWORD"   # EBS Vision default: apps
    export ISG_PASSWORD="YOUR_ISGADMIN_PASSWORD"     # EBS Vision default: Welcome1
    ```

### Method A: Local development and Identity-Aware Proxy (IAP) tunneling

Establish Identity-Aware Proxy (IAP) TCP tunnels to the private Oracle database
listener:

```bash
# Terminal 1: Oracle Database Listener Tunnel (Port 1521)
gcloud compute start-iap-tunnel oracle-vision 1521 \
  --project=YOUR_GOOGLE_CLOUD_PROJECT_ID \
  --zone=YOUR_ZONE \
  --local-host-port=localhost:1521

# Terminal 2: Start microservices locally
source .venv/bin/activate
uvicorn src.a2a.a2a_server:app --port 8080 --reload
uvicorn src.agents.workflow_agent:app --port 8001 --reload
uvicorn src.mcp.mcp_server:app --port 8000 --reload
```

### Method B: Google Cloud Run deployment using Terraform

#### Option 1: Automated script (recommended)

```bash
# Reads terraform/terraform.tfvars, populates Secret Manager from ORACLE_PASSWORD
# and ISG_PASSWORD, bootstraps EBS DB, builds image, and deploys Cloud Run services
./scripts/deploy_stack.sh

# Infrastructure teardown
./scripts/destroy_stack.sh
```

#### Option 2: Direct Terraform apply

```bash
cd terraform

# 1. Initialize Terraform and create APIs, secret containers, and Artifact Registry
terraform init
terraform apply \
  -target=google_project_service.enabled_apis \
  -target=google_secret_manager_secret.db_password \
  -target=google_secret_manager_secret.isg_password \
  -target=google_artifact_registry_repository.agent_repo \
  -target=google_artifact_registry_repository_iam_member.cloudbuild_ar_writer \
  -target=google_project_iam_member.cloudbuild_logging

# 2. Populate Secret Manager versions (required before Cloud Run can start)
printf "%s" "${ORACLE_PASSWORD}" | gcloud secrets versions add oracle-ebs-workflow-db-password-dev --project=YOUR_PROJECT_ID --data-file=-
printf "%s" "${ISG_PASSWORD}" | gcloud secrets versions add oracle-ebs-workflow-isg-password-dev --project=YOUR_PROJECT_ID --data-file=-

# 3. Build and push the container image, then deploy Cloud Run services
gcloud builds submit .. --project=YOUR_PROJECT_ID \
  --tag="us-central1-docker.pkg.dev/YOUR_PROJECT_ID/oracle-ebs-workflow-repo-dev/oracle-ebs-workflow-app:latest"
terraform apply \
  -var="container_image=us-central1-docker.pkg.dev/YOUR_PROJECT_ID/oracle-ebs-workflow-repo-dev/oracle-ebs-workflow-app:latest"
```

#### Configuring and accessing the agent in Gemini Enterprise

1.  In [Gemini Enterprise Apps][gemini-enterprise-apps], click **Create App**,
    enter application details, and select region.
1.  In **Overview** (or **Settings** > **Authentication** / **Resource access
    control**), configure **Google Identity** or **Workforce Identity
    Federation** and assign target Google Workspace groups or user emails.
1.  Click **Agents** > **+ Add agent**, paste the rendered Agent Card JSON from
    Cloud Storage
    (`gcloud storage cat "$(terraform -chdir=terraform output -raw a2a_agent_card_gcs_uri)"`)
    or `/.well-known/agent.json` (`/a2a/card`), click **Preview Agent Details**,
    and click **Next** (Display Name: `Oracle EBS Workflow AI Assistant`).
1.  In **Agent authorization** and **Tool authorizations**, keep the default
    **Basic HTTP authentication** (and optional **PKCE verification enabled**)
    checkboxes or leave external OAuth credentials unconfigured, and click
    **Next** > **Create** (Cloud Run OIDC authentication is handled
    by Google-managed Discovery Engine and Cloud AI Companion service agents).
1.  Click **Go to Gemini Enterprise** from **Overview** (or open [Gemini
    Enterprise][gemini-web-app]) and select **Oracle EBS Workflow AI Assistant**
    under **Agents from your organization**.

> [!NOTE]
>
> **Production security and least-privilege credentials**:
>
> - **Gemini Enterprise Identity**: End-user access is governed by **Google
>   Identity** (or **Workforce Identity Federation**) and per-app IAM resource
>   controls in **Overview** / **Settings** (the agent wizard's **Basic HTTP
>   authentication** and **PKCE** checkboxes apply only to optional external
>   OAuth 2.0 token exchanges).
> - **Cloud Run OIDC IAM**: Public access (`allUsers`) is disabled. Services
>   authenticate with Google Cloud OIDC tokens (`gemini-ebs-workflow-sa-dev`
>   and `ebs-workflow-agent-sa-dev`) and route database traffic over Direct
>   Virtual Private Cloud (VPC) Egress.
> - **Oracle EBS service account**: Defaults (`ISGADMIN`, `FND_USER_ID=0` /
>   `SYSADMIN`) target EBS 12.2 Vision demo instances. For production, use a
>   dedicated least-privilege `FND_USER` and workflow responsibility
>   (`ISG_USERNAME`, `ISG_PASSWORD`, `FND_USER_ID`, `FND_RESP_ID`).

### Enabling Oracle Integrated SOA Gateway (ISG) on EBS Vision

To execute workflow responses through **Path B (`REST`)** against a live Oracle
EBS 12.2 instance:

1.  Register the `ISGADMIN` password in `FND_USER` and `FND_VAULT` (`'ISG'`
    module) and grant the `UMX|FND_IREP_ADMIN` role.
1.  Verify that the `oafm_server1` WebLogic managed server is running on the EBS
    application tier (`sudo su - oracle` and source `EBSapps.env run`).
1.  In **Integrated SOA Gateway** > **Integration Repository**, deploy the
    `WF_NOTIFICATION` (**Workflow Notification System**) PL/SQL interface as a
    REST service with alias `wf` (`RESPOND`, `SETATTRTEXT`, `GETATTRTEXT`, and
    `GETINFO`) and create user grants.
1.  Set `WORKFLOW_EXECUTION_PATH=REST` and point `ISG_REST_BASE_URL` to your EBS
    web entry point (`http://<ebs-host>:8000`).

> [!IMPORTANT]
>
> **How `REST` (Path B) and `PLSQL` (Path A) route queries and actions**:
>
> - **`PLSQL` (Path A)**: Runs 100% of queries and `APPROVE`/`REJECT` actions
>   directly through `apps.wf_notification` (`apps_initialize`) over port
>   `1521` with zero ISG HTTP calls.
> - **`REST` (Path B, default)**:
>     - **Actions (`APPROVE` / `REJECT`)**: Calls ISG REST `POST`
>       `/webservices/rest/wf/setattrtext/` and `/respond/`, falling back to
>       PL/SQL if ISG is unreachable or if the workflow requires an initialized
>       FND session to transition to `CLOSED`.
>     - **Queries (`/notifications`, `/triage`)**: Seeded `WF_NOTIFICATION`
>       methods only accept a single `NID` over HTTP `POST` (no `GET`
>       `/notifications` collection exists in standard EBS 12.2 ISG), so
>       queries fall back to PL/SQL and cache that state. To
>       serve queries over REST, optionally expose `apps.xx_ebs_wf_agent_pkg`
>       (`src/workflow/sql/xx_ebs_wf_agent_pkg_spec.sql`) through Oracle REST Data
      Services (ORDS) or register
>       it in ISG with `irep_parser.pl` and `FNDLOAD`.

For complete SQL scripts, command-line steps, and resolution of common
deployment errors (`ISGADMIN` vault configuration, `node_info.txt` permissions,
`FND_DIAGNOSTICS`, and `FND_SOA_SERVICE_OPERATIONS_PK` constraint cleanup), see
the [Oracle EBS ISG setup and troubleshooting guide][isg-setup-guide].

## Recommended prompts for testing

- **Worklist and notifications triage**:
    - _"List pending approvals for user JSMITH"_
    - _"Show my pending notifications"_
    - _"Triage pending notifications for JSMITH"_
    - _"Summarize workflow items needing my approval"_
- **Item inspection**:
    - _"Inspect workflow notification 10294"_
    - _"What are the details of notification 99482?"_
    - _"Show line item breakdown for purchase order 99120"_
- **Policy compliance and risk evaluation**:
    - _"Verify policy compliance for notification 10294"_
    - _"Check expense policy violations for notification 8472"_
    - _"Evaluate approval risk for PO notification 99120"_
- **Human-in-the-loop action execution**:
    - _"Approve notification 10294"_ _(Triggers Human Confirmation Gate
      returning an advisory Proposal with risk status)_
    - _"Confirm approval for notification 10294 with comments 'Approved per
      project travel plan'"_ _(Executes certified
      `apps.wf_notification.respond`)_
    - _"Reject notification 99120 due to budget overrun and unapproved vendor"_
      _(Executes certified rejection)_

## Example API invocations

```bash
# 1. Multi-item workflow triage
curl -X GET "http://localhost:8080/triage?recipient=JSMITH&limit=10"

# 2. Request approval proposal (confirmed: false triggers Human Confirmation Gate)
curl -X POST "http://localhost:8080/execute" -H "Content-Type: application/json" \
  -d '{"notification_ids": [10294], "action": "APPROVE", "comments": "Standard travel expense", "confirmed": false}'

# 3. Execute confirmed approval (confirmed: true invokes apps.wf_notification.respond)
curl -X POST "http://localhost:8080/execute" -H "Content-Type: application/json" \
  -d '{"notification_ids": [10294], "action": "APPROVE", "comments": "Confirmed within budget", "confirmed": true}'
```

## Running automated tests

Run test suite verification against the integration suite:

```bash
./scripts/run_tests.sh
```

[ebs-sample-repo]:
    https://github.com/GoogleCloudPlatform/architecture-center-samples/tree/main/oracle-ebs-framework
[gemini-enterprise-apps]:
    https://console.cloud.google.com/gemini-enterprise/apps
[gemini-web-app]: https://gemini.google.com/
[isg-setup-guide]: docs/isg-setup-and-troubleshooting.md
