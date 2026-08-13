# Cymbal Institutional Contact Center & Clearing Portal

A state-of-the-art WebRTC voice and real-time messaging customer engagement
platform developed on Google Cloud Platform, integrating **Contact Center AI
(CCAI)**, **Gemini Enterprise for CX (GECX)**, **Dialogflow CX**, **Agent
Assist**, and **Identity-Aware Proxy (IAP)**.

---

## 🏗 Architectural Ecosystem

- **Cloud Run BFF API (`cymbal-bff-web-\${GCP_PROJECT_ID}`)**: Secured behind
  direct IAP, serving the premium HTML5/JS customer and assist workstations,
  orchestrating instantaneous room migration and WebRTC signaling.
- **Cloud Run Webhook API (`cymbal-gecx-webhook-\${GCP_PROJECT_ID}`)**:
  Dedicated, IAM-authenticated endpoint for external GECX virtual agents to
  execute dynamic multi-factor PIN verification and clearing DB inquiries.
- **BigQuery Ticket Repository**: Highly optimized database storing escalated
  institutional intake tickets.
- **GCS Audio Logging Bucket**: Dedicated object storage
  (`<project_id>-ccai-audio-export`) ingesting raw WebRTC voice streaming
  packets for deep asynchronous NLP Insights processing.

---

## 🚀 Full New Environment Deployment Guide

> [!TIP] **AI Agent Automated Setup (Zero-to-Hero Wizard)**: Instead of
> executing the manual steps below, you can ask an AI Agent (e.g., Antigravity,
> Gemini CLI, Claude Code) to deploy the entire solution automatically:
>
> _"I want to deploy this solution following
> [`DEPLOYMENT_INSTRUCTION.md`](DEPLOYMENT_INSTRUCTION.md)."_
>
> The AI Agent will proactively interview you for your Target GCP Project ID and
> deployment settings, automatically configure your `.env` and
> `terraform/terraform.tfvars` files, and provision the entire infrastructure
> and primary agent (`cymbal_support_agent`) automatically!

To deploy the Cymbal solution from scratch manually into a new Google Cloud
environment, follow these comprehensive end-to-end deployment steps:

### Prerequisites & GCP Project Preparation

> [!IMPORTANT] **Mandatory Billing & Quota Setup**: To prevent quota exhaustion
> or permission errors (e.g., `403 Forbidden` on service usage APIs) during
> deployment, you MUST complete these steps **before** initializing Terraform:
>
> 1.  **Link a Billing Account**: Confirm that the target GCP project has a
>     valid billing account linked.
> 1.  **Configure ADC Quota Project**: Force your Application Default
>     Credentials (ADC) to bill quota to the target project:
>
> ```bash
> gcloud auth application-default set-quota-project "<YOUR_PROJECT_ID>"
> ```
>
> 1.  **Assign IAM Roles**: The deploying identity requires the **`Owner`** or
>     **`Editor`** role, PLUS **`roles/resourcemanager.projectIamAdmin`** to
>     configure resource-level IAM policies for service accounts.

1.  Ensure the following Google Cloud APIs are enabled in your target project:

- `cloudresourcemanager.googleapis.com` (Resource Manager)
- `serviceusage.googleapis.com` (Service Usage)
- `orgpolicy.googleapis.com` (Organization Policy API)
- `iam.googleapis.com` (Identity and Access Management)
- `aiplatform.googleapis.com` (Vertex AI)
- `run.googleapis.com` (Cloud Run)
- `bigquery.googleapis.com` (BigQuery)
- `dialogflow.googleapis.com` (Dialogflow CX / GECX)
- `discoveryengine.googleapis.com` (Discovery Engine)
- `artifactregistry.googleapis.com` (Artifact Registry)
- `cloudbuild.googleapis.com` (Cloud Build)
- `compute.googleapis.com` (Compute Engine / Serverless NEGs)
- `iap.googleapis.com` (Identity-Aware Proxy)

1.  Authenticate locally using the Google Cloud CLI and set your target quota
    project:

```bash
gcloud auth login
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_PROJECT_ID
```

1.  **Organization Policies & AI Coach Provisioning**:

- Our automated deployment script (`./scripts/setup.sh`) automatically checks
  and unblocks `constraints/run.managed.requireInvokerIam` and
  `constraints/iam.allowedPolicyMemberDomains` to permit anonymous public access
  (`allUsers`) on Cloud Run services.
- After Terraform completes, `./scripts/setup.sh` also automatically deploys and
  links the `Cymbal Demo` AI Coach Generator to your Conversation Profile!

### Step 1: Create AI Coach & Agent Assist Conversation Profile (UI Setup)

Before configuring your environment variables, you must create an AI Coach and
attach it to a Conversation Profile in Google Cloud so that human agents receive
real-time generative AI coaching during calls:

1.  **Create the AI Coach ("Bring your own Coach")**:

- Open the [Agent Assist Console](https://agentassist.cloud.google.com/) and
  select your GCP project.
- On the left panel, click **AI Coach** > **Create**.
- Configure **AI Coach Name** (`Cymbal Demo`), **Version** (`2.5`), **Language**
  (`English`), and set Generator-level trigger to `On every message`. Check
  `Enable suggestion deduping`.
- Click **Add instruction** (e.g., condition
  `When the agent is talking with the customer`, action
  `Agent must be professional and guide the user`
  `to give detailed information about their issues`) and click **Save**.

1.  **Create the Conversation Profile**:

- On the left panel, click **Conversation Profile** > **Create**.
- Check the **AI Coach** checkbox and select the `Cymbal Demo` AI Coach you just
  created.
- Under **Security Settings**, attach your security settings profile with
  **"Send data to Insights"** enabled.
- Click **Save** and copy your generated Conversation Profile Resource Name
  (`projects/<PROJECT_ID>/locations/global/conversationProfiles/<PROFILE_ID>`).

> [!TIP] **Automated AI Coach Provisioning (No UI Setup Needed)**: If you prefer
> automated provisioning over manual UI setup, simply leave
> `CONVERSATION_PROFILE_ID=""` empty in your `.env` file. Terraform will
> automatically create the Conversation Profile shell
> (`Cymbal Coach - Cymbal Demo`), and after deploying your agent in Step 5, you
> can execute Step 6 to automatically build and link the AI Coach Generator!

### Step 2: Configure Environment Variables (`.env`)

Create a `.env` file in the repository root containing your target environment
settings and credentials (including the `CONVERSATION_PROFILE_ID` created in
Step 1):

```ini
GCP_PROJECT_ID="YOUR PROJECT ID"
GCP_REGION="us-central1"
CONVERSATION_PROFILE_ID="<<PROFILE ID YOU CREATED ABOVE>>>"
SECRET_KEY="cymbal-secure-secret-999"
```

> [!NOTE]
>
> - **Auto-Detected Service Account**: Our deployment scripts
>   (`deploy_cloud_run.py` and `setup.sh`) automatically detect your project's
>   managed GECX/CES service account
>   (`service-<PROJECT_NUMBER>@gcp-sa-ces.iam.gserviceaccount.com`), so you do
>   not need to fill in `CCAAS_SERVICE_ACCOUNT` manually.
> - **Optional CCaaS Usage**: If you plan to deploy the optional CCaaS intake
>   queue channel, you may also define `CCAAS_COMPANY_ID` and `COMPANY_SECRET`.
>   Otherwise, they can be omitted safely.

### Step 3: Provision Cloud Run, BigQuery & GCS via IaC

Run our unified deployment automation script to synchronize `.env` variables
into `terraform/terraform.tfvars` and automatically apply the Terraform
configuration:

```bash
./scripts/setup.sh
```

This step provisions:

- **BigQuery**: The `cymbal_demo_${GCP_PROJECT_ID_UNDERLINE}` dataset and
  `support_tickets` table.
- **Artifact Registry & Cloud Build**: Compiles and pushes the container image.
- **Cloud Run Webhook (`cymbal-gecx-webhook-${GCP_PROJECT_ID}`)**: Dedicated
  OpenAPI webhook target for GECX tools.
- **Cloud Run Web BFF (`cymbal-bff-web-${GCP_PROJECT_ID}`)**: Customer and agent
  workstations behind Google IAP.
- **GCS Audio Logging Bucket**: `<project_id>-ccai-audio-export` for async CCAI
  Insights ingestion.

### Step 4: Set Up Python Virtual Environment & Install Dependencies

Before running the Python agent deployment scripts, create an isolated virtual
environment and install the required dependencies (including `cxas-scrapi`):

```bash
python3 -m venv venv
source venv/bin/activate
pip install --require-hashes -r scripts/requirements.txt
```

### Step 5: Deploy the Cymbal Support GECX Agent

Push the local conversational AI agent definition
(`src/gecx_agent/cymbal_support_agent`) to Gemini Enterprise for CX and bind its
OpenAPI tools (`create_ticket` and `verify_pin`) to the deployed Cloud Run
webhook:

```bash
python3 scripts/deploy_agent.py --widget-title "Cymbal Support"
```

<!-- markdownlint-disable MD033 -->

> [!IMPORTANT]
>
> - **Automatic Chat Widget Generation**: The script automatically reads
>   <a href="src/frontend/static/loopback/index.template.html#L855"><code>src/frontend/static/loopback/index.template.html</code></a>,
>   replaces `<<AGENT_DEPLOYMENT_NAME>>` with your newly created deployment
>   resource name
>   (`projects/<PROJECT_NUMBER>/locations/us/apps/cymbal-support-agent/deployments/<ID>`),
>   and outputs
>   <a href="src/frontend/static/loopback/index.html#L855"><code>index.html</code></a>.
> - **Rebuild Cloud Run Container**: After `deploy_agent.py` generates
>   `index.html`, re-run `./scripts/setup.sh` so your live Cloud Run service
>   (`cymbal-bff-web`) serves the updated frontend widget.

<!-- markdownlint-enable MD033 -->

### Step 6: Deploy & Link the Dialogflow AI Coach Generator

To provision the real-time generative AI Coach (`Cymbal Demo`, version `2.5`)
and attach it to your Dialogflow Conversation Profile:

```bash
# 1. Deploy the AI Coach Generator brain from JSON
python3 scripts/manage_agent_assist_coaches.py deploy \
    --project="${GCP_PROJECT_ID}" \
    --config="terraform/assets/coaches/ai-coach.json" \
    --id="generator-ai-coach"

# 2. Link the Generator to your Conversation Profile
python3 scripts/manage_agent_assist_coaches.py link \
    --project="${GCP_PROJECT_ID}" \
    --profile="Cymbal Coach - Cymbal Demo" \
    --generator="projects/${GCP_PROJECT_ID}/locations/global/generators/generator-ai-coach"
```

### Step 7: Verify Deployment Integration

Run the automated Pytest test suite against the deployed environment to verify
database DML writes, authentication, and WebSocket chat/signaling routes:

```bash
PYTHONPATH=. pytest -v
```

---

## 🔒 CCAI Console Security & AA Configuration Guide

To ensure that both web chat transcripts and live WebRTC voice interactions
export automatically to your **Contact Center AI Insights** dashboard upon call
completion, execute these exact visual setup steps in your Google Cloud Console:

### Step A: Configure CCAI Security Settings

1.  Navigate to **Contact Center AI > Security Settings** in the Google Cloud
    Console.
1.  Click **Create** (or edit your existing `cymbal` Security Settings profile).
1.  Under **Audio Export to Cloud Storage**, paste your newly provisioned bucket
    name into the **`GCS Bucket`** field:

- Example: `<your-gcs-bucket-name>`

1.  Under **Insights Export**, toggle **"Send data to Insights"** to the **ON**
    position.
1.  Click **Save**.

### Step B: Wire Up the AA Conversation Profile

1.  Navigate to **Agent Assist > Conversation Profiles**.
1.  Create a new global profile (or edit your manual global Profile ID matching
    your `.env` configuration).
1.  In the **`Security settings`** dropdown, select your newly configured
    `cymbal` security resource.
1.  Verify that **"Send data to Insights"** is actively enabled.
1.  Click **Save**.

---

## 🧪 Verification & Institutional Escalation Flow

1.  Open your live Cloud Run Web Portal:
    `https://cymbal-bff-web-<project-id>-<hash>-uc.a.run.app`.
1.  Notice your IAP authenticated circular user initial avatar rendered in the
    top-right corner.
1.  Click the bottom-right floating chat bubble to engage the automated GECX
    bot.
1.  Input your account and security PIN (`1234`) to escalate to a human agent.
1.  In your assist workstation, click **Accept Call** and permit the microphone.
1.  Verify that the turn-by-turn chat history backfills instantly onto the
    assist board and that live generative AI coaching suggestions stream as you
    speak.
1.  Click **Hang Up** — your complete interaction is immediately finalized and
    queued for async ingestion into **CCAI Insights**!
