<!-- markdownlint-disable -->

# Personalized Marketing Agent — Release 2

**Authors:** Layolin Jesudhass, Ana Esqueda

End-to-end marketing campaign agent built on **Google ADK**. Generates
personalized **text ads**, **image ads**, **asset sheets**, and **cinematic
video ads** (24s with voiceover + background music) for any product — then
publishes to **Google Ads** as a Performance Max (PMAX) campaign.

## What's New in Release 2

### New Entry Path: Product URL Extraction

- Paste any product page URL — the agent auto-extracts brand, name, price,
  description, features, specs, and product image
- Uses APP_STATE JSON-LD, Open Graph tags, structured data, and HTML parsing
- Product image is automatically uploaded to GCS for use in ad generation

### Product Fidelity Guide

- Google Search grounding researches the real product to ensure visual accuracy
- Generates a **KEYFRAME_INSTRUCTION** that appears in every image and video
  prompt
- Prevents hallucinations (wrong product appearance, incorrect usage context)
- User reviews and approves the guide before asset generation begins

### Google Ads Publishing (PMAX)

- Real Google Ads API integration via `ads_agent`
- Logo auto-squaring to min 300x300 with white padding (Google Ads compliance)
- YouTube video upload via Google Ads House Channel
- Clean search theme (special characters stripped for policy compliance)
- Supports MCC (Manager) and direct account authentication
- `RUN_LOCAL` mode for local testing with ADC

### Video Pipeline Enhancements

- **Hallucination word filter** — automatically removes problematic words from
  video storylines
- **Keyframe injection** — product fidelity guide drives visual consistency
  across all frames
- **Environment storytelling** — camera moves through the scene, product stays
  fixed
- **Director-grade scene descriptions** — each shot specifies camera angle,
  lighting, and mood

### Additional Improvements

- `get_product_by_sku` now displays product image inline after selection
- `delete_asset_from_gcs` cleans up stale assets from session state
- Enhanced error handling across all generation functions
- 84 product images (up from 13) in the sample catalog

## Download

```bash
git clone --no-checkout https://github.com/GoogleCloudPlatform/cloud-solutions.git
cd cloud-solutions
git sparse-checkout set projects/ai/gen-media/marketing-agent
git checkout main
cd projects/ai/gen-media/marketing-agent/release
```

## Setup & Run

See the detailed setup guide:
[marketing_agent/README.md](marketing_agent/README.md)

**Quick version:**

```bash
# 1. Install dependencies
pip install uv
uv sync

# 2. Authenticate
gcloud auth application-default login
gcloud config set project <YOUR_PROJECT_ID>

# 3. Create .env (copy from .env-template and fill in your values)
cp .env-template .env
# Edit .env with your GCP project ID

# 4. Run
./run.sh
```

Open `http://localhost:8000` in your browser.

### Running with Google Ads Integration

Google Ads publishing (including YouTube video upload) requires a Service
Account with `cloud-platform` scope:

```bash
# Option A: SA impersonation (recommended)
SA_EMAIL=your-sa@project.iam.gserviceaccount.com ./run.sh

# Option B: SA key file
GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa-key.json ./run.sh

# Option C: Plain ADC (everything works except video upload to Google Ads)
./run.sh
```

The SA needs these roles:

- `roles/aiplatform.user` (Vertex AI)
- `roles/storage.admin` (GCS)
- Google Ads API access configured

## What's Included

```
release/
├── README.md                    # This file
├── Flow_Documentation.md        # Full architecture and flow documentation
├── marketing_agent/             # Main agent code + detailed README
│   ├── README.md                # Detailed setup, deployment, and usage guide
│   └── marketing_agent/         # Agent source code
├── adk_common/                  # Shared utilities (GCS, logging, artifacts)
├── ads_agent/                   # Google Ads PMAX publisher
└── assets/                      # Sample data
    ├── bigquery/                 # CSV files to load into BigQuery
    │   ├── products.csv          # Product catalog (84 products)
    │   └── inventory_analysis.csv # Stock levels and sales data
    ├── product_images/           # Product photos (matched to products.csv)
    └── samples/                  # Sample brand assets for demo
```

## Entry Paths

### Path 1: Paste a Product URL (New in Release 2)

Paste any e-commerce product page URL. The agent extracts all product details
automatically, generates a fidelity guide via Google Search, then creates the
full campaign.

### Path 2: Inventory Opportunities (BigQuery)

Query the product database for high-stock, low-velocity items that need a
marketing boost. Select a product and the agent builds a targeted campaign.

### Path 3: Manual Product Entry

Provide product details manually (brand, name, description, image URL, logo).
The agent builds the campaign from your input.

## Key Features

- **Three entry paths**: URL extraction, inventory-based (BigQuery), or manual
  setup
- **Product fidelity guide**: Google Search grounding for visual accuracy
- **Trend research**: Google Search grounding for real-time market trends
- **5 customer personas**: Family, Travel, Professional, Fitness, Luxury
- **Asset generation**: Asset sheets, text ads (RSA), image ads — all in
  parallel
- **Video ads**: 24s cinematic video with 3-act storyline, voiceover, background
  music
- **Post-production**: Text overlays, end card, logo overlay, audio mixing via
  ffmpeg
- **Asset approval**: User reviews each asset type before proceeding
- **Google Ads publishing**: Auto-publishes as PMAX campaign with YouTube video
  upload

## Google Ads Integration

### Prerequisites

- Google Ads account with API access
- Approved
  [Developer Token](https://developers.google.com/google-ads/api/docs/get-started/dev-token)

### Authentication

```bash
# Option A: ADC with required scopes
gcloud auth application-default login \
  --scopes=https://www.googleapis.com/auth/adwords,https://www.googleapis.com/auth/cloud-platform

# Option B: Service Account impersonation
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa-credentials.json
```

### Configuration in `.env`

```env
DEVELOPER_TOKEN=your-developer-token
RUN_LOCAL=True
```

## Documentation

- **[marketing_agent/README.md](marketing_agent/README.md)** — Setup,
  prerequisites, deployment, authentication
- **[Flow_Documentation.md](Flow_Documentation.md)** — Full architecture, model
  map, video pipeline

## Changes from Release 1

| Feature               | Release 1          | Release 2                                |
| --------------------- | ------------------ | ---------------------------------------- |
| Entry paths           | Inventory + Manual | + URL Extraction                         |
| Product fidelity      | None               | Google Search grounded guide             |
| Google Ads publish    | Basic              | Logo squaring, YouTube upload, RUN_LOCAL |
| Video quality         | Standard           | Hallucination filter, keyframe injection |
| Product image display | Not shown          | Inline after selection                   |
| Asset cleanup         | Manual             | `delete_asset_from_gcs`                  |
