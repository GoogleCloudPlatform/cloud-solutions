# Personalized Marketing Agent

End-to-end marketing campaign agent built on **Google ADK**.
Generates personalized **text ads**, **image ads**,
**asset sheets**, and **cinematic video ads** (24s with
voiceover + background music) for any product — then publishes
to **Google Ads** as a PMAX campaign.

## Quick Start

All commands should be run from the **root of the release1
folder** (the folder containing `marketing_agent/`,
`adk_common/`, `ads_agent/`, and `.env.example`).

```bash
cd /path/to/release1

# 1. Install dependencies
pip install uv
uv sync

# 2. Configure environment
cp .env.example .env
```

Open the `.env` file in a text editor and update the values:

### On Mac

```bash
open -e .env
```

### On Linux

```bash
nano .env
```

### On Windows

```bash
notepad .env
```

Inside the file, find and replace these values with your own:

```text
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

# 4. Run the agent (from the release1 root folder)
uv run adk web marketing_agent
```

Open `http://localhost:8000` in your browser.

## Prerequisites

### GCP Project Setup

Enable these APIs on your GCP project:

| API | Purpose |
| :---- | :------- |
| Vertex AI | Gemini, VEO, Lyria models |
| Cloud Storage | Asset storage (images, videos, music) |
| BigQuery | Product catalog, inventory, sales analytics |
| Cloud Text-to-Speech | Voiceover generation (Chirp3-HD) |
| Google Ads API | PMAX campaign publishing |

### BigQuery Tables Required

The agent reads product and inventory data from BigQuery:

| Table | Purpose |
| :----- | :------- |
| `{BQ_DATASET}.products` | Product catalog (sku, name, brand, price, image_uri, etc.) |
| `{BQ_DATASET}.inventory_analysis` | Stock levels, sales velocity, forecast data |

### Data Setup

Sample data is provided in the `assets/` folder. Follow
these steps to load it:

#### Step 1: Upload product images to GCS

```bash
gcloud storage cp assets/product_images/*.png gs://<your-artifacts-bucket>/products/
```

#### Step 2: Upload sample assets to GCS

```bash
gcloud storage cp assets/samples/* gs://<your-artifacts-bucket>/samples/
```

#### Step 3: Update image URIs in the products CSV

Open `assets/bigquery/products.csv` and replace
`<your-artifacts-bucket>` with your actual GCS bucket name
in the `image_uri` column.

#### Step 4: Load CSV data into BigQuery

```bash
# Create dataset (if it doesn't exist)
bq mk --dataset <your-project-id>:retail_analytics

# Load products table
bq load --source_format=CSV --autodetect \
  retail_analytics.products \
  assets/bigquery/products.csv

# Load inventory analysis table
bq load --source_format=CSV --autodetect \
  retail_analytics.inventory_analysis \
  assets/bigquery/inventory_analysis.csv
```

#### Step 5: Verify

```bash
bq query "SELECT COUNT(*) FROM retail_analytics.products"
bq query "SELECT COUNT(*) FROM retail_analytics.inventory_analysis"
```

### GCS Folder Structure

```text
gs://<your-artifacts-bucket>/
├── products/                    # Product catalog images (from Step 1)
│   ├── FOOD-001.png
│   ├── ELEC-001.png
│   └── ...
├── samples/                     # Sample brand assets (from Step 2)
│   ├── nestguard_pro.png
│   ├── securevision_logo.png
│   └── nestguard_pro_marketing_guide.md
├── logo.png                     # Default logo (upload your own)
└── {ProductName}_{Persona}/     # Generated assets (created by the agent)
    ├── asset_sheet_*.png
    ├── img_*.png
    ├── text_ad_*.json
    ├── keyframe_{1-4}.png
    ├── clip_act{1-3}.mp4
    ├── background_music_*.mp3
    └── video_ad_*.mp4
```

### IAM Roles

Your service account or user credentials need:

| Role | Purpose |
| :---- | :------- |
| `roles/aiplatform.user` | Vertex AI model access |
| `roles/storage.objectAdmin` | GCS read/write |
| `roles/bigquery.dataViewer` | BigQuery queries |
| `roles/texttospeech.user` | Cloud TTS |

### System Dependencies

| Dependency | Purpose | Install |
| :---------- | :------- | :------- |
| Python 3.13+ | Runtime | Required |
| ffmpeg | Video stitching, audio mixing, text overlays | `brew install ffmpeg` (macOS) |
| ffprobe | Video duration detection | Included with ffmpeg |

### Model Access

| Model | Status |
| :----- | :------ |
| `gemini-3.1-pro-preview` | Generally available |
| `gemini-3.1-flash-image-preview` | Generally available |
| `veo-3.1-generate-001` | Requires allowlisting |
| `lyria-3-pro-preview` | Requires allowlisting |
| `gemini-2.5-pro-tts` (Chirp3-HD) | Generally available |

If VEO or Lyria are not enabled, the agent handles
failures gracefully.

## Project Structure

```text
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

- `adk_common/` — Shared utilities (GCS, logging,
  artifact rendering). Must be in the parent directory.
- `ads_agent/` — Google Ads PMAX publisher. Must be in the
  parent directory. Optional — agent works without it.

## Agent Flow

```text
Product Selection → Trend Research → Campaign Setup
→ Personalization → Asset Sheets → Text Ads (RSA)
→ Image Ads → Video Ads (24s cinematic)
→ Publish to Google Ads (PMAX)
```

Each asset type includes user approval — the user can
request regeneration of specific assets before proceeding.

### Two Entry Paths

**Path A — Inventory-Based:** Query BigQuery for
high-stock/low-velocity products, select one, auto-fill
all details.

**Path B — Manual Setup:** User provides product name,
brand, description, price, image, logo, and reference
documents.

### Personalization

5 customer personas tailor all generated ads:

1.  Family with Kids
1.  Vacation/Travel Enthusiast
1.  Young Professional
1.  Fitness/Wellness Seeker
1.  Luxury/Premium Lifestyle

### Video Pipeline (~4-5 min per video)

```text
Storyline [gemini-3.1-pro] ──────── 5s
├── Voiceover [Chirp3-HD Charon] ── 10s  ┐
├── Lyria Music [lyria-3-pro] ───── 15s  ├── all parallel
└── 4 Keyframes [flash-image] ───── 30s  ┘
3 VEO Clips [veo-3.1] ──────────── 3min (parallel)
Post-production [ffmpeg] ────────── 10s
```

Post-production includes: audio mix (voiceover 150% +
music 30%), text overlays (brand, product, tagline,
price), end card overlay, logo overlay.

### Models Used

| Component | Model |
| :--------- | :----- |
| Root Agent | `gemini-3.1-pro-preview` |
| Campaign Generation | `gemini-3.1-pro-preview` + Google Search |
| Trend Research | `gemini-3.1-pro-preview` + Google Search |
| Storyline | `gemini-3.1-pro-preview` |
| Image Ads + Keyframes | `gemini-3.1-flash-image-preview` |
| Video Clips | `veo-3.1-generate-001` |
| Voiceover | `gemini-2.5-pro-tts` (Chirp3-HD, Charon) |
| Background Music | `lyria-3-pro-preview` |
| Text Ads | `gemini-3.1-pro-preview` (JSON output) |

## Authentication & Service Account Setup

### Step 1: Create a Service Account

```bash
PROJECT_ID=<your-project-id>
SA_NAME=marketing-agent

gcloud iam service-accounts create $SA_NAME \
  --display-name="Marketing Agent Service Account" \
  --project=$PROJECT_ID
```

### Step 2: Grant IAM Roles

```bash
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# Vertex AI (Gemini, VEO, Lyria)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/aiplatform.user"

# Cloud Storage (read/write assets)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.objectAdmin"

# BigQuery (product catalog, inventory)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/bigquery.dataViewer"

# Cloud TTS (voiceover)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/texttospeech.user"

# Allow your user to impersonate this SA
gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL \
  --member="user:<your-email>@<domain>.com" \
  --role="roles/iam.serviceAccountTokenCreator"
```

### Step 3: Google Ads Access (for publishing)

To publish PMAX campaigns, the service account needs
access to your Google Ads account:

1.  Go to [Google Ads](https://ads.google.com) →
    **Admin** → **Access and security**
1.  Click **+** to add a new user
1.  Enter the SA email:
    `marketing-agent@<your-project-id>.iam.gserviceaccount.com`
1.  Set access level to **Standard** or **Admin**
1.  Click **Send invitation** and accept it

Also ensure your Google Ads **Developer Token** is set
in `.env`:

```text
DEVELOPER_TOKEN=<your-google-ads-developer-token>
```

### Development (local — user credentials)

```bash
gcloud auth application-default login
```

### SA Impersonation

Runs the entire agent end-to-end — Vertex AI (Gemini,
VEO, Lyria), Cloud Storage, BigQuery, Cloud TTS, and
Google Ads — under the service account identity.

```bash
gcloud auth application-default login \
  --impersonate-service-account=${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com
```

### Production (deployed)

Use the `--service-account` flag when deploying to Cloud
Run or Agent Engine — no key files needed.

### Best Practices

- **Dedicated service account** per environment (dev,
  staging, prod) to avoid single point of compromise
- **Least privilege** — only grant the IAM roles listed
  above, avoid broad roles like Owner or Editor
- **No key files** — use Application Default Credentials
  (ADC) or `--service-account` flag at deploy time
- **Audit regularly** — review SA permissions and usage
  logs via Cloud Console > IAM
- **Agent Engine** — for production deployment, use
  Vertex AI Agent Engine which manages infrastructure,
  scaling, and auth automatically

## Deployment

### Required Packages for Deployment

The agent depends on all three packages — they must be
deployed together:

```text
release1/                        # Deploy from this root
├── marketing_agent/             # Main agent
├── adk_common/                  # Shared utilities (GCS, logging, artifacts)
├── ads_agent/                   # Google Ads PMAX publisher
└── .env                         # Environment configuration
```

### Agent Engine (recommended for production)

```bash
# Deploy using ADK CLI (from release1 root)
adk deploy agent_engine \
  --project=$PROJECT_ID \
  --region=us-central1 \
  --service_account=$SA_EMAIL \
  marketing_agent
```

Or via Cloud Console:

1.  Go to Cloud Console > Agent Builder
1.  Create new agent > Import from code
1.  Point to the **release1 root folder** (contains
    `marketing_agent/`, `adk_common/`, `ads_agent/`)
1.  Configure environment variables from `.env`
1.  Assign the service account
1.  Deploy

### Cloud Run (alternative)

```bash
# Build from release1 root (includes all packages)
gcloud builds submit --tag gcr.io/${PROJECT_ID}/marketing-agent

gcloud run deploy marketing-agent \
  --image gcr.io/${PROJECT_ID}/marketing-agent \
  --region us-central1 \
  --memory 4Gi \
  --cpu 2 \
  --timeout 900 \
  --concurrency 1 \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_GENAI_USE_VERTEXAI=TRUE" \
  --service-account $SA_EMAIL
```
