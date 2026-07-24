# Personalized Marketing Ads Agent

End-to-end marketing campaign agent built on **Google ADK**. Generates personalized **text ads**, **image ads**, **asset sheets**, and **cinematic video ads** (24s with voiceover + background music) for any product — then publishes to **Google Ads** as a PMAX campaign.

## Quick Start

```bash
# 1. Install dependencies
pip install uv
uv sync --frozen

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

### Cloud Run

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

### Agent Engine (AgentSpace)

1. Go to Cloud Console > Agent Builder
2. Create new agent > Import from code
3. Point to the `marketing_agent/` directory
4. Configure environment variables from `.env`
5. Deploy

## Verification

1. Open agent UI
2. Say "show me inventory opportunities"
3. Select a product — verify product image displays inline
4. Proceed: trends → campaigns → personalize → asset sheets → text ad → image ads → video ad
5. Check: realistic images, 24s video, voiceover + music full duration, text overlays
6. Publish to Google Ads (optional)
