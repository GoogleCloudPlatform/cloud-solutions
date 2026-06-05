<!-- markdownlint-disable -->
# Personalized Marketing Agent

**Authors:** Layolin Jesudhass, Ana Esqueda

End-to-end marketing campaign agent built on **Google ADK**. Generates personalized **text ads**, **image ads**, **asset sheets**, and **cinematic video ads** (24s with voiceover + background music) for any product — then publishes to **Google Ads** as a Performance Max (PMAX) campaign.

## Download

```bash
git clone --no-checkout https://github.com/GoogleCloudPlatform/cloud-solutions.git
cd cloud-solutions
git sparse-checkout set projects/ai/gen-media/ads-agent
git checkout main
cd projects/ai/gen-media/ads-agent/release1
```

## Setup & Run

See the detailed setup guide: [marketing_agent/README.md](marketing_agent/README.md)

**Quick version:**

```bash
# Install dependencies
pip install uv
uv sync

# Create .env file (see marketing_agent/README.md for full template)
# Update with your GCP project ID, bucket name, and developer token

# Authenticate
gcloud auth application-default login
gcloud config set project <YOUR_PROJECT_ID>

# Run
uv run adk web marketing_agent
```

Open `http://localhost:8000` in your browser.

## What's Included

```
release1/
├── README.md                    # This file
├── .env                         # Environment config (update with your values)
├── Flow_Documentation.md        # Full architecture and flow documentation
├── marketing_agent/             # Main agent code + detailed README
│   ├── README.md                # Detailed setup, deployment, and usage guide
│   └── marketing_agent/         # Agent source code
├── adk_common/                  # Shared utilities (GCS, logging, artifacts)
├── ads_agent/                   # Google Ads PMAX publisher (A2A)
└── assets/                      # Sample data
    ├── bigquery/                 # CSV files to load into BigQuery
    │   ├── products.csv          # Product catalog (84 products)
    │   └── inventory_analysis.csv # Stock levels and sales data
    ├── product_images/           # Product photos (matched to products.csv)
    └── samples/                  # Sample brand assets for demo
```

## Key Features

- **Two entry paths**: Inventory-based (BigQuery) or manual product setup
- **Trend research**: Google Search grounding for real-time market trends
- **5 customer personas**: Family, Travel, Professional, Fitness, Luxury
- **Asset generation**: Asset sheets, text ads (RSA), image ads — all in parallel
- **Video ads**: 24s cinematic video with 3-act storyline, voiceover, background music
- **Post-production**: Text overlays, end card, logo overlay, audio mixing via ffmpeg
- **Asset approval**: User reviews each asset type, can request selective regeneration
- **Google Ads publishing**: Auto-publishes as PMAX campaign via A2A integration

## Documentation

- **[marketing_agent/README.md](marketing_agent/README.md)** — Setup, prerequisites, deployment, authentication
- **[Flow_Documentation.md](Flow_Documentation.md)** — Full architecture, model map, video pipeline, A2A integration
