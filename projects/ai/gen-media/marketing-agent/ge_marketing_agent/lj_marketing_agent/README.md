# Personalized Marketing Ads Agent

**Author:** Layolin Jesudhass

End-to-end marketing campaign agent built on **Google ADK**. Generates personalized **text ads**, **image ads**, **asset sheets**, and **cinematic video ads** (24s with voiceover + background music) for any product — then publishes to **Google Ads** as a PMAX campaign.

## Quick Start

```bash
# 1. Install dependencies
pip install uv
uv sync --frozen --frozen

# 2. Configure environment
cp ../.env.example ../.env
```

Open the `.env` file in a text editor and update the values:

**On Mac:**
```bash
open -e ../.env
```

**On Linux:**
```bash
nano ../.env
```

**On Windows:**
```bash
notepad ..\.env
```

Inside the file, find and replace these values with your own:

```
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_BUCKET_ARTIFACTS=your-gcs-bucket-name
DEVELOPER_TOKEN=your-google-ads-developer-token
PROJECT_ID=your-gcp-project-id
BQ_DATASET=your-bigquery-dataset
```

```bash
# 3. Authenticate with Google Cloud
gcloud auth application-default login
gcloud config set project <YOUR_PROJECT_ID>

# 4. Run the agent
uv run adk web marketing_agent
```

Open `http://localhost:8000` in your browser.

## Prerequisites

### GCP Project Setup

Enable these APIs on your GCP project:

| API | Purpose |
|:----|:--------|
| Vertex AI | Gemini, VEO, Lyria models |
| Cloud Storage | Asset storage (images, videos, music) |
| BigQuery | Product catalog, inventory, sales analytics |
| Cloud Text-to-Speech | Voiceover generation (Chirp3-HD) |
| Google Ads API | PMAX campaign publishing |

### BigQuery Tables Required

The agent reads product and inventory data from BigQuery:

| Table | Purpose |
|:------|:--------|
| `{BQ_DATASET}.products` | Product catalog (sku, name, brand, price, image_uri, etc.) |
| `{BQ_DATASET}.inventory_analysis` | Stock levels, sales velocity, forecast data |

### IAM Roles

Your service account or user credentials need:

| Role | Purpose |
|:-----|:--------|
| `roles/aiplatform.user` | Vertex AI model access |
| `roles/storage.objectAdmin` | GCS read/write |
| `roles/bigquery.dataViewer` | BigQuery queries |
| `roles/texttospeech.user` | Cloud TTS |

### System Dependencies

| Dependency | Purpose | Install |
|:-----------|:--------|:--------|
| Python 3.13+ | Runtime | Required |
| ffmpeg | Video stitching, audio mixing, text overlays | `brew install ffmpeg` (macOS) |
| ffprobe | Video duration detection | Included with ffmpeg |

### Model Access

| Model | Status |
|:------|:-------|
| `gemini-3.1-pro-preview` | Generally available |
| `gemini-3.1-flash-image-preview` | Generally available |
| `veo-3.1-generate-001` | Requires allowlisting |
| `lyria-3-pro-preview` | Requires allowlisting |
| `gemini-2.5-pro-tts` (Chirp3-HD) | Generally available |

If VEO or Lyria are not enabled, the agent handles failures gracefully.

## Project Structure

```
marketing_agent/
├── __init__.py
├── agent.py                    # Main agent — all tools + video pipeline
├── prompt.md                   # Agent instruction template
├── config.py                   # BigQuery config, safety settings
├── schema.py                   # Pydantic models (Product, Brand, etc.)
├── campaign_utils.py           # Campaign XML parser
├── generate_campaigns.py       # Gemini → campaign XML
├── generate_display_ad.py      # On-request ad editing
├── data/
│   └── products.py             # Product database (BigQuery)
├── sub_agents/
│   └── trend_spotter.py        # Market trend research (Google Search)
├── tools/
│   ├── inventory.py            # BigQuery inventory queries
│   └── sales.py                # BigQuery sales queries
├── skills/                     # 6 ADK Skills (progressive disclosure)
│   ├── ad-copywriting/
│   ├── video-storytelling/
│   ├── visual-direction/
│   ├── brand-strategy/
│   ├── trend-analysis/
│   └── platform-specs/
└── prompts/
    └── trend_spotter.md
```

### Dependencies

- `adk_common/` — Shared utilities (GCS, logging, artifact rendering). Must be in the parent directory.
- `ads_agent/` — Google Ads PMAX publisher. Must be in the parent directory. Optional — agent works without it.

## Agent Flow

```
Product Selection → Trend Research → Campaign Setup → Personalization
→ Asset Sheets → Text Ads (RSA) → Image Ads → Video Ads (24s cinematic)
→ Publish to Google Ads (PMAX)
```

Each asset type includes user approval — the user can request regeneration of specific assets before proceeding.

### Two Entry Paths

**Path A — Inventory-Based:** Query BigQuery for high-stock/low-velocity products, select one, auto-fill all details.

**Path B — Manual Setup:** User provides product name, brand, description, price, image, logo, and reference documents.

### Personalization

5 customer personas tailor all generated ads:
1. Family with Kids
2. Vacation/Travel Enthusiast
3. Young Professional
4. Fitness/Wellness Seeker
5. Luxury/Premium Lifestyle

### Video Pipeline (~4-5 min per video)

```
Storyline [gemini-3.1-pro] ──────── 5s
├── Voiceover [Chirp3-HD Charon] ── 10s  ┐
├── Lyria Music [lyria-3-pro] ───── 15s  ├── all parallel
└── 4 Keyframes [flash-image] ───── 30s  ┘
3 VEO Clips [veo-3.1] ──────────── 3min (parallel)
Post-production [ffmpeg] ────────── 10s
```

Post-production includes: audio mix (voiceover 150% + music 30%), text overlays (brand, product, tagline, price), end card overlay, logo overlay.

### Models Used

| Component | Model |
|:----------|:------|
| Root Agent | `gemini-3.1-pro-preview` |
| Campaign Generation | `gemini-3.1-pro-preview` + Google Search |
| Trend Research | `gemini-3.1-pro-preview` + Google Search |
| Storyline | `gemini-3.1-pro-preview` |
| Image Ads + Keyframes | `gemini-3.1-flash-image-preview` |
| Video Clips | `veo-3.1-generate-001` |
| Voiceover | `gemini-2.5-pro-tts` (Chirp3-HD, Charon) |
| Background Music | `lyria-3-pro-preview` |
| Text Ads | `gemini-3.1-pro-preview` (JSON output) |

## Authentication

### Development (local)
```bash
gcloud auth application-default login
```

### Production (deployed)
```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa-key.json
```

### Service Account Impersonation
```bash
gcloud auth application-default login \
  --impersonate-service-account=<sa-name>@<project>.iam.gserviceaccount.com
```

## Deployment

### Agent Engine (Vertex AI) — Recommended

Deploy the agent to Vertex AI Agent Engine for production use.

#### Prerequisites

- GCP project with Vertex AI API enabled
- `gcloud` CLI authenticated with sufficient permissions
- ADK CLI v1.30.0 (v2.x Dockerfile-based deploy is incompatible with Agent Engine's runtime)

#### Important: Import Requirements

All imports across the codebase **must use relative imports** — Agent Engine renames the package directory at deploy time, breaking absolute imports:

- Within `lj_marketing_agent/`: use `from ..adk_common.utils.xxx import yyy`
- Within `lj_marketing_agent/sub_agents/`: use `from ...adk_common.utils.xxx import yyy`
- Within `adk_common/utils/`: use `from .xxx import yyy`
- Within `lj_marketing_agent/` for sibling modules: use `from ..config import xxx`, `from ..schema import xxx`

#### Deploy Steps

```bash
# 1. Upload code to Cloud Shell
# Copy the lj_marketing_agent/ directory to ~/nest_demo/streamlit_demo/

# 2. Copy .env into the agent package
cp .env lj_marketing_agent/.env

# 3. Install ADK v1.30.0 in a temporary venv
python3 -m venv /tmp/adk130
/tmp/adk130/bin/pip install google-adk==1.30.0

# 4. Remove .agent_engine_config.json if present (v1.30.0 auto-detects entrypoint)
rm -f lj_marketing_agent/.agent_engine_config.json

# 5. Deploy to Agent Engine
cd ~/nest_demo/streamlit_demo
/tmp/adk130/bin/adk deploy agent_engine \
  --project=<YOUR_PROJECT_ID> \
  --region=us-central1 \
  --display_name="genmedia-ad-studio-ae" \
  lj_marketing_agent
```

On success you'll see the deployed agent in Cloud Console > Agent Engine.

#### Troubleshooting

If deploy fails with `failed to start and cannot serve traffic`, check the logs:

```bash
gcloud logging read \
  'resource.type="aiplatform.googleapis.com/ReasoningEngine" AND severity>=ERROR' \
  --project=<YOUR_PROJECT_ID> \
  --limit=5 \
  --format="value(textPayload)"
```

Common issues:
- **`ModuleNotFoundError: No module named 'xxx'`** — An absolute import exists. Change to relative import.
- **`Invalid requirement: '/app/agents/...'`** — A Docker-style path in `requirements.txt`. Remove it.
- **`requires-python` mismatch** — Set `requires-python = ">=3.11"` in `pyproject.toml`.

### Integrate with Gemini Enterprise (GE)

Once deployed to Agent Engine, register the agent in Gemini Enterprise.

#### Step 1: Enable APIs

```bash
gcloud services enable discoveryengine.googleapis.com --project=<PROJECT_ID>
gcloud services enable dialogflow.googleapis.com --project=<PROJECT_ID>
```

#### Step 2: IAM Roles

Grant these roles to the user registering the agent:

| Role | Purpose |
|:-----|:--------|
| `roles/dialogflow.admin` | Create/manage Conversational Agent apps |
| `roles/discoveryengine.admin` | Agent Builder app management |
| `roles/aiplatform.user` | Access reasoning engines |
| `roles/serviceusage.serviceUsageConsumer` | API quota/billing |

#### Step 3: Create or Use a Gemini Enterprise App

If you already have a GE app, skip to Step 4. Otherwise:

1. Go to **Cloud Console** > **Agent Builder**
2. Click **Create App** > **Conversational Agent**
3. Set app name and click **Create**

#### Step 4: Register the Agent (Recommended: agents-cli)

```bash
pip install google-agents-cli

agents-cli publish gemini-enterprise --interactive
```

Follow the prompts:
- **Registration type**: `2` (ADK)
- **Agent Runtime ID**: `projects/<PROJECT_ID>/locations/us-central1/reasoningEngines/<ENGINE_ID>`
- **GE App**: select from the list
- **Display Name**: `GenMedia Ad Studio`

**Alternative — Console UI:**
1. In your GE app, go to **Agents** > **Add agent** > **Custom agent via Agent Runtime**
2. Set the Reasoning Engine path: `projects/<PROJECT_ID>/locations/us-central1/reasoningEngines/<ENGINE_ID>`
3. Skip Authorization (can add later)
4. Click **Create**

#### Step 5: Add User Permissions

1. In the GE app > **Agents** > click on your agent
2. Go to **User permissions** > **Add user**
3. Add the user's email with **Agent User** role

#### Step 6: Set Up Identity Provider

1. In the GE app, go to **Integration**
2. Select **Use Google Identity**
3. Note the webapp URL provided

#### Step 7: Verify

```bash
gcloud ai reasoning-engines list --project=<PROJECT_ID> --region=us-central1
```

Access the agent via:
- **GE webapp URL** from Step 6
- **`@genmedia-ad-studio-ae`** mention in the GE chat box
- **Agents sidebar** (if pinned by admin)

### Package Structure

```
lj_marketing_agent/               # Project root (pyproject.toml here)
├── __init__.py                    # Re-exports root_agent + calls patch_agent()
├── agent.py                      # Re-exports root_agent
├── pyproject.toml                 # Package config (includes lj_marketing_agent + adk_common)
├── requirements.txt               # Runtime dependencies (no self-install paths)
├── lj_marketing_agent/            # Actual agent source code
│   ├── agent.py                   # root_agent definition
│   ├── demo_overrides.py          # Nest demo pre-generated assets (Option 1)
│   ├── prompt.md                  # Agent prompt (4 options)
│   ├── config.py
│   ├── schema.py
│   ├── campaign_utils.py
│   ├── generate_campaigns.py
│   ├── generate_display_ad.py
│   ├── data/products.py
│   ├── sub_agents/trend_spotter.py
│   └── tools/
├── adk_common/                    # Shared utilities (GCS, logging, Gemini)
└── ads_agent/                     # Google Ads PMAX publisher (optional)
```

### Cloud Run (Alternative)

```bash
gcloud builds submit --tag gcr.io/${PROJECT_ID}/marketing-agent

gcloud run deploy marketing-agent \
  --image gcr.io/${PROJECT_ID}/marketing-agent \
  --region us-central1 \
  --memory 4Gi \
  --cpu 2 \
  --timeout 900 \
  --concurrency 1 \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_GENAI_USE_VERTEXAI=TRUE" \
  --service-account <sa-name>@${PROJECT_ID}.iam.gserviceaccount.com
```

## Verification

1. Open agent UI
2. Say "show me inventory opportunities"
3. Select a product — verify product image displays inline
4. Proceed: trends → campaigns → personalize → asset sheets → text ad → image ads → video ad
5. Check: realistic images, 24s video, voiceover + music full duration, text overlays
6. Publish to Google Ads (optional)
