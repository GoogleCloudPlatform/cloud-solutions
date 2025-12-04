<!-- markdownlint-disable-file -->

# Deep Search Agent Development Kit (ADK) Quickstart

> **Note:** This agent was previously named `gemini-fullstack` and has been
> renamed to `deep-search`. If you're looking for the old `gemini-fullstack`
> agent, you're in the right place! All functionality remains the same.

The **Deep Search Agent Development Kit (ADK) Quickstart** is a production-ready
blueprint for building a sophisticated, fullstack research agent with Gemini.
It's built to demonstrate how the ADK helps structure complex agentic workflows,
build modular agents, and incorporate critical Human-in-the-Loop (HITL) steps.

<table>
  <thead>
    <tr>
      <th colspan="2">Key Features</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>🏗️</td>
      <td><strong>Fullstack & Production-Ready:</strong> A complete React frontend and ADK-powered FastAPI backend, with deployment options for <a href="https://cloud.google.com/run">Google Cloud Run</a> and <a href="https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/overview">Vertex AI Agent Engine</a>.</td>
    </tr>
    <tr>
      <td>🧠</td>
      <td><strong>Advanced Agentic Workflow:</strong> The agent uses Gemini to <strong>strategize</strong> a multi-step plan, <strong>reflect</strong> on findings to identify gaps, and <strong>synthesize</strong> a final, comprehensive report.</td>
    </tr>
    <tr>
      <td>🔄</td>
      <td><strong>Iterative & Human-in-the-Loop Research:</strong> Involves the user for plan approval, then autonomously loops through searching (via Gemini function calling) and refining its results until it has gathered sufficient information.</td>
    </tr>
  </tbody>
</table>

Here is the agent in action:

<img src="https://github.com/GoogleCloudPlatform/agent-starter-pack/blob/main/docs/images/adk_gemini_fullstack.gif?raw=true" width="80%" alt="Deep Search Agent Preview">

<img src="assets/deep-search.gif" width="80%" alt="Deep Search Agent Demo">

This project adapts concepts from the
[Gemini FullStack LangGraph Quickstart](https://github.com/google-gemini/gemini-fullstack-langgraph-quickstart)
for the frontend app.

---

## 🚀 Getting Started: Two Deployment Paths

Choose the deployment path that best fits your needs:

### A. Cloud Run Deployment (Full Control & Customization)

**Best for:** Production deployments with full control over infrastructure,
custom UI, and complete code customization

**Prerequisites:** [Python 3.10+](https://www.python.org/downloads/),
[Node.js](https://nodejs.org/), [uv](https://github.com/astral-sh/uv),
[Google Cloud SDK](https://cloud.google.com/sdk/docs/install),
[Terraform](https://developer.hashicorp.com/terraform/downloads)

**Requirements:** Google Cloud Project with Vertex AI API enabled

Use the [Agent Starter Pack](https://goo.gle/agent-starter-pack) to create a
production-ready project with complete deployment infrastructure for **Cloud
Run**.

#### Step 1: Create Project from Template

This command uses the [Agent Starter Pack](https://goo.gle/agent-starter-pack)
to create a new directory (`my-fullstack-agent`) with all the necessary code and
infrastructure.

```bash
# Quick start with uvx (recommended)
uvx agent-starter-pack create my-fullstack-agent -a adk@deep-search -d cloud_run
```

<details>
<summary>Alternative: Using pip</summary>

If you don't have `uv` installed:

```bash
python -m venv .venv && source .venv/bin/activate # On Windows: .venv\Scripts\activate
pip install --upgrade agent-starter-pack
agent-starter-pack create my-fullstack-agent -a adk@deep-search -d cloud_run
```

</details>

You'll be prompted to verify your Google Cloud credentials and select
configuration options.

#### Step 2: Install & Run Locally

Navigate into your **newly created project folder**, then install dependencies
and start the servers.

```bash
cd my-fullstack-agent && make install && make dev
```

Your agent is now running at `http://localhost:5173`.

#### Step 3: Deploy to Cloud Run

See the [Cloud Deployment](#cloud-deployment-cloud-run) section below for
deployment instructions.

---

### B. Agent Engine via Agent Garden (Managed Deployment)

**Best for:** Quickest path to fully managed, enterprise-ready deployment
without infrastructure management

**Prerequisites:** Google Cloud Project with Vertex AI API enabled

For a fully managed deployment on Vertex AI Agent Engine with automatic scaling,
monitoring, and enterprise-grade security:

1. Navigate to the
   [Deep Search Agent in Agent Garden](https://console.cloud.google.com/vertex-ai/agents/agent-garden/samples/deep-search)
2. Click **Deploy** to create a managed instance in your Google Cloud project
3. Follow the guided setup to configure your agent

This option provides:

- ✅ Zero infrastructure management
- ✅ Automatic scaling and high availability
- ✅ Built-in monitoring and logging
- ✅ Enterprise security and compliance

**Learn more:**
[Agent Builder Overview](https://docs.cloud.google.com/agent-builder/overview)

---

## Project Structure (Cloud Run Deployments)

> **Note:** This structure applies to **Cloud Run deployments** created via
> Agent Starter Pack (Option A). Agent Garden deployments (Option B) are fully
> managed and don't require this project structure.

```
deep-search/
├── app/                 # Core application code
│   ├── agent.py         # Main agent logic
│   ├── fast_api_app.py  # FastAPI Backend server (for Cloud Run)
│   └── app_utils/       # App utilities and helpers
├── frontend/            # React frontend application
├── .cloudbuild/         # CI/CD pipeline configurations for Google Cloud Build
├── deployment/          # Infrastructure and deployment scripts (Terraform)
├── notebooks/           # Jupyter notebooks for prototyping and evaluation
├── tests/               # Unit, integration, and load tests
├── Makefile             # Makefile for common commands
├── GEMINI.md            # AI-assisted development guide
└── pyproject.toml       # Project dependencies and configuration
```

Generated with
[`googleCloudPlatform/agent-starter-pack`](https://github.com/GoogleCloudPlatform/agent-starter-pack)
version `0.21.0`

---

## Requirements

Before you begin with **Cloud Run deployment** (Option A), ensure you have:

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

---

## Quick Start (Local Testing)

For local development and testing with Cloud Run deployment:

```bash
make install && make dev
```

---

## Commands

These commands are available for **Cloud Run deployments** created via Agent
Starter Pack:

| Command              | Description                                                                                                      |
| -------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `make install`       | Install all required dependencies using uv                                                                       |
| `make dev`           | Launch local development server with custom React UI                                                             |
| `make playground`    | Launch local development environment with ADK web UI (alternative interface)                                     |
| `make deploy`        | Deploy agent to Cloud Run (use `IAP=true` to enable Identity-Aware Proxy, `PORT=8080` to specify container port) |
| `make local-backend` | Launch local development server with hot-reload                                                                  |
| `make test`          | Run unit and integration tests                                                                                   |
| `make lint`          | Run code quality checks (codespell, ruff, mypy)                                                                  |
| `make setup-dev-env` | Set up development environment resources using Terraform                                                         |

For full command options and usage, refer to the [Makefile](Makefile).

---

## Usage

This is a **complete, working demo agent** that showcases advanced agentic
patterns. Use it to:

1. **Explore the Demo:** Run the agent locally with `make dev` to see the full
   research workflow in action, including the custom React UI and
   human-in-the-loop planning phase.

2. **Understand the Architecture:** Review `app/agent.py` to see how multi-agent
   orchestration, iterative refinement loops, and structured output (via
   Pydantic schemas) work together. The `ResearchConfiguration` in
   `app/config.py` shows how to parameterize agent behavior.

3. **Adapt for Your Use Case:** This agent demonstrates patterns applicable to
   any multi-step research, analysis, or content generation task. Key
   customization points:
    - Agent prompts and instructions in `app/agent.py`
    - Research parameters (models, iteration limits) in `app/config.py`
    - Frontend behavior in `/frontend` (if using custom UI)

4. **Test & Iterate:** Use the notebooks in `notebooks/` for experimentation and
   Vertex AI Evaluation to assess performance.

5. **Deploy:** Follow the [deployment section](#deployment) for production
   deployment options. For streamlined CI/CD setup, run
   `uvx agent-starter-pack setup-cicd`. See the
   [`agent-starter-pack setup-cicd` CLI command](https://googlecloudplatform.github.io/agent-starter-pack/cli/setup_cicd.html)
   for details.

The project includes a `GEMINI.md` file that provides context for AI tools like
Gemini CLI when asking questions about the implementation.

---

## Agent Details

| Attribute            | Description                                                                  |
| :------------------- | :--------------------------------------------------------------------------- |
| **Interaction Type** | Workflow                                                                     |
| **Complexity**       | Advanced                                                                     |
| **Agent Type**       | Multi Agent                                                                  |
| **Components**       | Multi-agent, Function calling, Web search, React frontend, Human-in-the-Loop |
| **Vertical**         | Horizontal                                                                   |

---

## How the Agent Thinks: A Two-Phase Workflow

The backend agent, defined in `app/agent.py`, follows a sophisticated workflow
to move from a simple topic to a fully-researched report.

The following diagram illustrates the agent's architecture and workflow:

![ADK Deep Search Architecture](https://github.com/GoogleCloudPlatform/agent-starter-pack/blob/main/docs/images/adk_gemini_fullstack_architecture.png?raw=true)

This process is broken into two main phases:

### Phase 1: Plan & Refine (Human-in-the-Loop)

This is the collaborative brainstorming phase.

1.  **You provide a research topic.**
2.  The agent generates a high-level research plan with several key goals (e.g.,
    "Analyze the market impact," "Identify key competitors").
3.  The plan is presented to **you**. You can approve it, or chat with the agent
    to add, remove, or change goals until you're satisfied. Nothing happens
    without your explicit approval.

The plan will contains following tags as a signal to downstream agents,

- Research Plan Tags
    - [RESEARCH]: Guides info gathering via search.
    - [DELIVERABLE]: Guides creation of final outputs (e.g., tables, reports).

- Plan Refinement Tags
    - [MODIFIED]: Goal was updated.
    - [NEW]: New goal added per user.
    - [IMPLIED]: Deliverable proactively added by AI.

### Phase 2: Execute Autonomous Research

Once you approve the plan, the agent's `research_pipeline` takes over and works
autonomously.

1.  **Outlining:** It first converts the approved plan into a structured report
    outline (like a table of contents).
2.  **Iterative Research & Critique Loop:** For each section of the outline, it
    repeats a cycle:
    - **Search:** It performs web searches to gather information.
    - **Critique:** A "critic" model evaluates the findings for gaps or
      weaknesses.
    - **Refine:** If the critique finds weaknesses, the agent generates more
      specific follow-up questions and searches again. This loop continues until
      the research meets a high-quality bar.
3.  **Compose Final Report:** After the research loop is complete, a final agent
    takes all the verified findings and writes a polished report, automatically
    adding inline citations that link back to the original sources.

You can edit key parameters (Gemini models, research loop iterations) in the
`ResearchConfiguration` dataclass within `app/config.py`.

### Customization

You can modify and extend this agent's behavior by editing the backend code.

- **Modifying Agent Logic:** The core logic for all sub-agents (planner,
  researcher, critic, composer) is defined in `app/agent.py`. You can change the
  prompts, tools, or reasoning steps by modifying the agent definitions here.
- **Adjusting Research Parameters:** Key parameters, such as the Gemini models
  used or the number of research loop iterations, can be adjusted in the
  `ResearchConfiguration` dataclass within `app/config.py`.
- **Syncing with Frontend:** The frontend UI integrates with the backend through
  specific agent names that process outputs differently (e.g., research findings
  vs. final report), update the activity timeline with appropriate titles/icons,
  and track research metrics like website counts. Important agent names include:
    - `section_researcher` & `enhanced_search_executor` - track websites
      consulted
    - `report_composer_with_citations` - processes final report
    - `interactive_planner_agent` - updates AI messages during planning
    - `plan_generator` and `section_planner` - used for timeline labels

    If you rename agents in `app/agent.py`, you must update their names in the
    frontend code (`/frontend`) to maintain functionality.

### Example Interaction

> **User:** A report on the last Google I/O
>
> **Agent:** Here's a research plan for a report on the last Google I/O:
>
> - Analyze the key announcements and product updates made at Google I/O 2025.
> - Identify the central themes and strategic directions emphasized by Google
>   during the event, particularly concerning AI, Android, and other emerging
>   technologies like Android XR.
> - Investigate the reception and industry impact of the major product
>   unveilings and feature enhancements.
> - Examine any significant shifts or continuities in Google's developer
>   strategy as presented at the conference.
> - Assess the implications of the announced technologies and initiatives for
>   developers, consumers, and the broader tech landscape.
>
> Does this plan look good, or would you like to refine it further? Once
> approved, I can initiate the research.
>
> **User:** Looks good! _(The agent proceeds to autonomously execute the
> research, showing its progress on the timeline.)_
>
> **Agent:**
>
> Google I/O 2025: Key Announcements and Highlights ....

---

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

### Cloud Deployment (Cloud Run)

> **Note:** Cloud deployment applies only to projects created with
> **agent-starter-pack** (Getting Started Option A).

**Prerequisites:**

```bash
gcloud components update
gcloud config set project YOUR_PROJECT_ID
```

#### Option 1: Deploy with ADK Web UI (Default)

For a quick deployment using the built-in
[adk-web](https://github.com/google/adk-web) interface:

```bash
make deploy IAP=true
```

#### Option 2: Deploy with Custom UI (React Frontend)

This agent includes a custom React frontend. To deploy it:

1. **Configure the Dockerfile** - See the
   [Deploy UI Guide](https://googlecloudplatform.github.io/agent-starter-pack/guide/deploy-ui.html)
   for the required Dockerfile changes.

2. **Deploy with the frontend port:**

```bash
make deploy IAP=true PORT=5173
```

#### After Deployment

Once deployed, grant users access to your IAP-protected service by following the
[Manage User Access](https://cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run#manage_user_or_group_access)
documentation.

### Production Deployment

The repository includes a Terraform configuration for the setup of a production
Google Cloud project. Refer to [deployment/README.md](deployment/README.md) for
detailed instructions on how to deploy the infrastructure and application.

For production deployments with CI/CD, see the
[Agent Starter Pack Development Guide](https://googlecloudplatform.github.io/agent-starter-pack/guide/development-guide.html#b-production-ready-deployment-with-ci-cd).

---

## Monitoring and Observability

The application uses
[OpenTelemetry GenAI instrumentation](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
for comprehensive observability. Telemetry data is automatically captured and
exported to:

- **Google Cloud Storage**: GenAI telemetry in JSONL format for efficient
  querying
- **BigQuery**: External tables and linked datasets provide immediate access to
  telemetry data via SQL queries
- **Cloud Logging**: Dedicated logging bucket with 10-year retention for GenAI
  operation logs

**Query your telemetry data:**

```bash
# Example: Query recent completions
bq query --use_legacy_sql=false \
  "SELECT * FROM \`deep-search_telemetry.completions\` LIMIT 10"
```

For detailed setup instructions, example queries, testing in dev, and optional
dashboard visualization, see the
[starter pack observability guide](https://googlecloudplatform.github.io/agent-starter-pack/guide/observability.html).

---

## Troubleshooting

If you encounter issues while setting up or running this agent, here are some
resources to help you troubleshoot:

- [ADK Documentation](https://google.github.io/adk-docs/): Comprehensive
  documentation for the Agent Development Kit
- [Vertex AI Authentication Guide](https://cloud.google.com/vertex-ai/docs/authentication):
  Detailed instructions for setting up authentication
- [Agent Starter Pack Troubleshooting](https://googlecloudplatform.github.io/agent-starter-pack/guide/troubleshooting.html):
  Common issues and solutions

---

## 🛠️ Technologies Used

### Backend

- [**Agent Development Kit (ADK)**](https://github.com/google/adk-python): The
  core framework for building the stateful, multi-turn agent.
- [**FastAPI**](https://fastapi.tiangolo.com/): High-performance web framework
  for the backend API (Cloud Run deployments).
- [**Google Gemini**](https://cloud.google.com/vertex-ai/generative-ai/docs):
  Used for planning, reasoning, search query generation, and final synthesis.

### Frontend

- [**React**](https://reactjs.org/) (with [Vite](https://vitejs.dev/)): For
  building the interactive user interface.
- [**Tailwind CSS**](https://tailwindcss.com/): For utility-first styling.
- [**Shadcn UI**](https://ui.shadcn.com/): A set of beautifully designed,
  accessible components.

---

## Disclaimer

This agent sample is provided for illustrative purposes only. It serves as a
basic example of an agent and a foundational starting point for individuals or
teams to develop their own agents.

Users are solely responsible for any further development, testing, security
hardening, and deployment of agents based on this sample. We recommend thorough
review, testing, and the implementation of appropriate safeguards before using
any derived agent in a live or critical system.
