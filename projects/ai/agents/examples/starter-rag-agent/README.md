<!-- markdownlint-disable-file -->

# Go/No-Go Decision Agent

![Agent Starter Pack](https://img.shields.io/badge/Generated_with-Agent_Starter_Pack-blue)
![ADK](https://img.shields.io/badge/Framework-ADK-orange)
![License](https://img.shields.io/badge/License-Apache_2.0-green)

A production-ready RAG agent built with Google's
[Agent Development Kit (ADK)](https://github.com/google/adk-python) that
demonstrates intelligent go/no-go decision-making by evaluating complex criteria
against retrieved documents. This example implementation analyzes commercial
real estate investment opportunities, but the pattern applies to any domain
requiring multi-factor decision analysis—vendor selection, project approvals,
compliance reviews, partnership evaluations, insurance qualification, and more.

Generated with
[`googleCloudPlatform/agent-starter-pack`](https://github.com/GoogleCloudPlatform/agent-starter-pack)
version `0.21.1`

## Creating This Project

This project was generated using the
[Agent Starter Pack](https://github.com/GoogleCloudPlatform/agent-starter-pack).
To create a similar project:

**Quick start:**

```bash
uvx agent-starter-pack create my-agent-name -a adk_base -d agent_engine
```

<details>
<summary>Alternative: Using pip</summary>

If you don't have `uv` installed:

```bash
python -m venv .venv && source .venv/bin/activate
pip install --upgrade agent-starter-pack
agent-starter-pack create my-agent-name -a agentic_rag -d agent_engine
```

</details>

Learn more:
[Agent Starter Pack Documentation](https://googlecloudplatform.github.io/agent-starter-pack/)

## Project Structure

This project is organized as follows:

```
starter-rag-agent/
├── app/                 # Core application code
│   ├── agent.py         # Main agent logic
│   ├── agent_engine_app.py # Agent Engine application logic
│   └── app_utils/       # App utilities and helpers
├── .cloudbuild/         # CI/CD pipeline configurations for Google Cloud Build
├── deployment/          # Infrastructure and deployment scripts
├── notebooks/           # Jupyter notebooks for prototyping and evaluation
├── tests/               # Unit, integration, and load tests
├── Makefile             # Makefile for common commands
├── GEMINI.md            # AI-assisted development guide
└── pyproject.toml       # Project dependencies and configuration
```

## Requirements

Before you begin, ensure you have:

- **uv**: Python package manager (used for all dependency management in this
  project) - [Install](https://docs.astral.sh/uv/getting-started/installation/)
  ([add packages](https://docs.astral.sh/uv/concepts/dependencies/) with
  `uv add <package>`)
- **Google Cloud SDK**: For GCP services -
  [Install](https://cloud.google.com/sdk/docs/install)
- **Terraform**: For infrastructure deployment -
  [Install](https://developer.hashicorp.com/terraform/downloads)
- **make**: Build automation tool -
  [Install](https://www.gnu.org/software/make/) (pre-installed on most
  Unix-based systems)

## RAG Corpus Setup

Before running the agent, you need to create a RAG corpus with your documents in
Vertex AI RAG Engine.

### 1. Upload Documents to Cloud Storage

This project includes sample commercial real estate documents in the `assets/`
directory for quick testing. To use them:

```bash
# Set your project ID
export PROJECT_ID="your-project-id"

# Create bucket (via gcloud CLI)
gsutil mb -l us-central1 gs://${PROJECT_ID}-rag-documents

# Upload the included sample documents
gsutil cp assets/* gs://${PROJECT_ID}-rag-documents/
```

Alternatively, create the bucket via the
[Google Cloud Console](https://console.cloud.google.com/storage).

<details>
<summary>Using your own documents</summary>

To use custom documents instead of the included samples:

```bash
# Create bucket
gsutil mb -l us-central1 gs://your-rag-documents-bucket

# Upload your documents
gsutil cp /path/to/your/documents/* gs://your-rag-documents-bucket/
```

**Important:** Ensure only the documents you want to ingest are in the
bucket/folder, as RAG Engine will process everything in the specified path.

</details>

### 2. Create RAG Corpus

1. Navigate to
   [RAG Engine](https://console.cloud.google.com/vertex-ai/generative/rag) in
   the Google Cloud Console
2. Click **Create Corpus**
3. Configure the corpus:
    - **Region:** Select your region (e.g., `us-central1`)
    - **Corpus name:** `cre-due-diligence` (or your preferred name)
4. **Import Data:**
    - Click **Select from Google Cloud Storage**
    - Select your bucket, folder, or specific files
    - Open **Advanced Options** and select:
        - **Parser:** LLM Parser
        - **Model:** Gemini 2.5 Flash
    - Click **Continue**
5. **Configure vector store:**
    - **Vector database:** RagManaged vector store
    - **Embedding model:** Text Multilingual Embedding 002
6. Click **Create Corpus**

### 3. Configure Environment Variable

Once created, navigate to the corpus details page and copy the **Resource Name**
(format:
`projects/your-project/locations/us-central1/ragCorpora/your-corpus-id`).

Add this to `app/agent.py` alongside the other environment variables:

```python
os.environ.setdefault("RAG_CORPUS", "projects/your-project/locations/us-central1/ragCorpora/your-corpus-id")
```

**Learn more:**
[RAG Engine Overview](https://cloud.google.com/vertex-ai/generative-ai/docs/rag-engine/rag-overview)

## Quick Start (Local Testing)

Install required packages and launch the local development environment:

```bash
make install && make playground
```

> **📊 Observability Note:** Agent telemetry (Cloud Trace) is always enabled.
> Prompt-response logging (GCS, BigQuery, Cloud Logging) is **disabled**
> locally, **enabled by default** in deployed environments (metadata only - no
> prompts/responses). See
> [Monitoring and Observability](#monitoring-and-observability) for details.

## Commands

| Command                           | Description                                                                                                                                         |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `make install`                    | Install all required dependencies using uv                                                                                                          |
| `make playground`                 | Launch local development environment for testing agent                                                                                              |
| `make deploy`                     | Deploy agent to Agent Engine                                                                                                                        |
| `make register-gemini-enterprise` | Register deployed agent to Gemini Enterprise ([docs](https://googlecloudplatform.github.io/agent-starter-pack/cli/register_gemini_enterprise.html)) |
| `make test`                       | Run unit and integration tests                                                                                                                      |
| `make lint`                       | Run code quality checks (codespell, ruff, mypy)                                                                                                     |
| `make setup-dev-env`              | Set up development environment resources using Terraform                                                                                            |

For full command options and usage, refer to the [Makefile](Makefile).

## Usage

This template follows a "bring your own agent" approach - you focus on your
business logic, and the template handles everything else (UI, infrastructure,
deployment, monitoring).

1. **Prototype:** Build your Generative AI Agent using the intro notebooks in
   `notebooks/` for guidance. Use Vertex AI Evaluation to assess performance.
2. **Integrate:** Import your agent into the app by editing `app/agent.py`.
3. **Test:** Explore your agent functionality using the local playground with
   `make playground`. The playground automatically reloads your agent on code
   changes.
4. **Deploy:** Set up and initiate the CI/CD pipelines, customizing tests as
   necessary. Refer to the [deployment section](#deployment) for comprehensive
   instructions. For streamlined infrastructure deployment, simply run
   `uvx agent-starter-pack setup-cicd`. Check out the
   [`agent-starter-pack setup-cicd` CLI command](https://googlecloudplatform.github.io/agent-starter-pack/cli/setup_cicd.html).
   Currently supports GitHub with both Google Cloud Build and GitHub Actions as
   CI/CD runners.
5. **Monitor:** Track performance and gather insights using BigQuery telemetry
   data, Cloud Logging, and Cloud Trace to iterate on your application.

The project includes a `GEMINI.md` file that provides context for AI tools like
Gemini CLI when asking questions about your template.

## Demo Scenarios

The following scenarios demonstrate how the agent analyzes commercial real
estate investments based on different investor profiles and constraints. Use
these to test the agent's decision-making capabilities across various risk
tolerance levels and investment strategies.

| Scenario                                | Investor Profile                                                             | Sample Prompt                                                                                                                                                                                        | Expected Outcome                    | Key Reasoning                                                                                                                                                                                       |
| --------------------------------------- | ---------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. The "Value-Add" Investor**         | Aggressive growth seeker, comfortable with construction and lease-up risk    | _"I am an opportunistic investor looking for properties with upside potential. I'm willing to handle major renovations and leasing risks if the Levered IRR is above 15%."_                          | **GO**                              | Agent identifies the 17.20% Levered IRR and "Lease-Up Upside" plan as a perfect fit for high risk/return profile                                                                                    |
| **2. The "Core" Conservative Investor** | Risk-averse, needs immediate stability and fully stabilized assets           | _"I represent a pension fund looking for 'Core' assets. We only buy stabilized buildings with at least 90% occupancy at closing. We cannot undertake any significant capital improvement projects."_ | **NO-GO**                           | Agent detects current 33% vacancy rate and required $2.73M CapEx budget, which strictly violate 90% occupancy and "no construction" constraints                                                     |
| **3. The "Tech Skeptic"**               | Sector-specific risk aversion, concerned about tech industry volatility      | _"I'm interested in this building, but I'm very worried about the tech sector right now. I don't want any exposure to large tech tenants who might downsize soon."_                                  | **NO-GO** (or High Risk Warning)    | Agent identifies "Tech Corp A" as largest tenant (33% of GLA) with lease expiring in 2026 (Year 2), creating specific "Leasing Risk" contradicting sector preference                                |
| **4. The "Turnkey" Buyer**              | Hands-off operator, wants pristine condition with no near-term capital needs | _"I am looking for a pristine, turnkey property. I do not want to deal with any deferred maintenance or system replacements in the first 3 years."_                                                  | **NO-GO**                           | Agent flags "HVAC system is aging and could fail" risk from RAMP document and $1M repair reserve, violating "pristine/turnkey" requirement                                                          |
| **5. The "Cash Flow" Buyer**            | Focused on immediate yield and positive leverage from day one                | _"I need positive leverage from Day 1. I can't invest if the cost of debt is higher than the Going-In Cap Rate."_                                                                                    | **NO-GO**                           | Agent compares Going-In Cap Rate (6.5%) against Senior Debt interest rate (7.0%), concluding negative leverage in Year 1 fails financial constraint                                                 |
| **6. The "Short-Term" Flipper**         | Needs quick liquidity, planning 2-year hold period                           | _"I need to park some capital for exactly 2 years and then sell. I need a stabilized asset that I can flip easily in 24 months."_                                                                    | **NO-GO**                           | Agent notes 18-month lease-up period and major tenant expiration (Tech Corp A) occurring in Year 2; selling at that moment maximizes risk, not value                                                |
| **7. The "Market Skeptic"**             | Concerned about competitive supply and market saturation                     | _"The financials look okay, but I'm worried about oversaturation. Are there other major office developments being built within a 1-mile radius of the Central Business District right now?"_         | Dependent on Search / Cautionary GO | Agent uses Google Search tool to validate external market conditions, cross-referencing internal document noting "Three new Class A office developments" nearby, potentially flagging "Supply Risk" |

### Using These Scenarios

These scenarios serve as starting points for exploring the agent's capabilities.
Use them to:

- **Understand decision patterns** across different risk profiles and investment
  strategies
- **Test the agent's reasoning** by adapting the prompts to your specific use
  cases
- **Explore edge cases** by combining constraints or introducing conflicting
  requirements
- **Validate RAG retrieval** by observing which documents the agent references

The agent demonstrates its ability to:

- Parse complex financial metrics (IRR, Cap Rate, leverage)
- Identify and flag specific risk factors from documents
- Match investor constraints to property characteristics
- Use external tools (Google Search) when internal data is insufficient
- Provide reasoned go/no-go recommendations with clear justification

## Deployment

> **Note:** For a streamlined one-command deployment of the entire CI/CD
> pipeline and infrastructure using Terraform, you can use the
> [`agent-starter-pack setup-cicd` CLI command](https://googlecloudplatform.github.io/agent-starter-pack/cli/setup_cicd.html).
> Currently supports GitHub with both Google Cloud Build and GitHub Actions as
> CI/CD runners.

### Dev Environment

You can test deployment towards a Dev Environment using the following command:

```bash
gcloud config set project <your-dev-project-id>
make deploy
```

The repository includes a Terraform configuration for the setup of the Dev
Google Cloud project. See [deployment/README.md](deployment/README.md) for
instructions.

### Production Deployment

The repository includes a Terraform configuration for the setup of a production
Google Cloud project. Refer to [deployment/README.md](deployment/README.md) for
detailed instructions on how to deploy the infrastructure and application.

## Monitoring and Observability

The application provides two levels of observability:

**1. Agent Telemetry Events (Always Enabled)**

- OpenTelemetry traces and spans exported to **Cloud Trace**
- Tracks agent execution, latency, and system metrics

**2. Prompt-Response Logging (Configurable)**

- GenAI instrumentation captures LLM interactions (tokens, model, timing)
- Exported to **Google Cloud Storage** (JSONL), **BigQuery** (external tables),
  and **Cloud Logging** (dedicated bucket)

| Environment                               | Prompt-Response Logging                                                             |
| ----------------------------------------- | ----------------------------------------------------------------------------------- |
| **Local Development** (`make playground`) | ❌ Disabled by default                                                              |
| **Deployed Environments** (via Terraform) | ✅ **Enabled by default** (privacy-preserving: metadata only, no prompts/responses) |

**To enable locally:** Set `LOGS_BUCKET_NAME` and
`OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=NO_CONTENT`.

**To disable in deployments:** Edit Terraform config to set
`OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=false`.

See the
[observability guide](https://googlecloudplatform.github.io/agent-starter-pack/guide/observability.html)
for detailed instructions, example queries, and visualization options.

## Contributing

Contributions are welcome! See the [Contributing Guide](CONTRIBUTING.md) or the
main
[Agent Starter Pack repository](https://github.com/GoogleCloudPlatform/agent-starter-pack).

## License

This project is licensed under the Apache License 2.0 - see the
[LICENSE](LICENSE) file for details.

## Disclaimer

This is not an officially supported Google product.
