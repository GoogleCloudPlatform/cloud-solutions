# GenMedia Ad Studio — AI-Powered Marketing Campaign Agent

From product URL to published Google Ads in minutes. This agent creates complete
marketing campaigns — text ads, image ads, cinematic video ads, and asset sheets
— powered by Google's latest generative AI (Gemini, Imagen, VEO, Lyria).

**Demo product:** Google Nest Learning Thermostat (4th gen)

## Quick Start

```bash
# First time — enables APIs, creates bucket, uploads assets, deploys
./setup_and_deploy.sh YOUR_PROJECT_ID

# Redeploy after code changes
./redeploy.sh YOUR_PROJECT_ID
```

One command. Everything is automated.

## What's Included

```text
nest_demo/
├── assets/                         # 11 pre-generated marketing assets
│   ├── google.png                  # Google logo (transparent)
│   ├── *_asset_sheet_*.png         # 4 asset sheet variations
│   ├── *_img_*.png                 # 4 image ad variations
│   ├── *_text_ad_*.json            # Text ad (headlines + descriptions)
│   └── video.mp4                   # 10-second cinematic video ad
├── streamlit_demo/                 # Agent code
│   ├── lj_marketing_agent/         # ADK marketing agent
│   ├── adk_common/                 # Shared utilities
│   └── ads_agent/                  # Google Ads publisher
├── streamlit_app.py                # Streamlit chat UI
├── setup_and_deploy.sh             # First-time deploy
├── redeploy.sh                     # Quick redeploy
├── Dockerfile                      # Container config
├── .env                            # Environment variables (auto-updated on deploy)
├── .streamlit/config.toml          # Dark theme
└── logo.jpg                        # Background watermark
```

## Prerequisites

- Google Cloud project with billing enabled
- `gcloud` CLI installed and authenticated (`gcloud auth login`)

That's it. The deploy script enables all required APIs automatically.

## Deploy

### First time

```bash
./setup_and_deploy.sh YOUR_PROJECT_ID
```

**What happens automatically:**

1.  Enables required APIs (Vertex AI, Cloud Run, Cloud Build, Cloud Storage)
1.  Updates `.env` with your project ID
1.  Creates a unique GCS bucket (`nest-demo-YOUR_PROJECT-XXXXXXX`)
1.  Uploads all 11 assets from `assets/` folder
1.  Builds Docker container from source
1.  Deploys to Cloud Run (8Gi memory, 4 CPU)
1.  Prints the app URL

### Redeploy (code changes only)

```bash
./redeploy.sh YOUR_PROJECT_ID
```

Reuses existing GCS bucket. Only rebuilds and redeploys the container.

### Reuse existing bucket

```bash
DEMO_BUCKET=nest-demo-PROJECT_ID-1234567 ./setup_and_deploy.sh YOUR_PROJECT_ID
```

### Grant access (if IAP is enabled)

```bash
gcloud run services add-iam-policy-binding lj-nest-demo \
  --region=us-central1 \
  --member="user:you@company.com" \
  --role="roles/run.invoker" \
  --project YOUR_PROJECT_ID
```

## Demo Flow — 3 Entry Paths

### Option 1: Paste a Product URL (Real-time)

Works with any product URL. Uses real AI generation.

| Step                   | What Happens                                       | Time      |
| ---------------------- | -------------------------------------------------- | --------- |
| Product extraction     | Fetches URL, extracts data, Google Search research | ~15s      |
| Trend research         | Google Search grounding for market trends          | ~15s      |
| Campaign concepts      | Gemini generates campaign ideas                    | ~20s      |
| Product fidelity guide | Gemini + Google Search generates product guide     | ~15s      |
| Asset sheets           | Imagen generates creative boards                   | ~30s each |
| Text ads               | Gemini generates RSA copy                          | ~10s      |
| Image ads              | Imagen generates marketing images                  | ~30s each |
| Video ad               | Gemini Omni generates 10s cinematic video          | ~1-2 min  |

Estimated duration: ~5-10 minutes

### Option 2: Show Inventory Opportunities

Queries BigQuery product database for high-stock, low-velocity items. Then
follows the same campaign creation flow as option 1.

### Option 3: Manual Product Entry

User provides product details manually (brand, name, description, image, logo).
Then follows the same campaign creation flow as option 1.

## Architecture

```text
User → Streamlit Chat UI → ADK Agent (Gemini 3.1 Pro)
                              ├── URL Extraction (httpx + Gemini)
                              ├── Google Search (trend research + product research)
                              ├── Campaign Generation (Gemini)
                              ├── Product Fidelity Guide (Gemini + Google Search)
                              ├── Asset Sheets (Imagen)
                              ├── Text Ads (Gemini → Google Ads RSA format)
                              ├── Image Ads (Imagen)
                              ├── Video Ads (Gemini Omni single-shot 10s video)
                              └── Google Ads Publish (A2A → PMAX campaign)
```

## Google Ads Integration

The Google Ads publish code (`streamlit_demo/ads_agent/`) is fully implemented
and included. In demo mode, the agent shows a simulated success message. To
enable real publishing, follow the steps below.

### Google Ads Prerequisites

- A Google Ads account with API access
- An approved
  [Google Ads Developer Token](https://developers.google.com/google-ads/api/docs/get-started/dev-token)
- A Google Cloud OAuth client ID JSON file (for local auth)

### Step 1: Configure credentials in `.env` (root of this folder)

```env
DEVELOPER_TOKEN=your-developer-token
GOOGLE_ADS_ACCOUNT_ID=your-mcc-account-id
GOOGLE_ADS_CUSTOMER_ID=your-customer-id
GOOGLE_ADS_IS_MCC=true
RUN_LOCAL=True
```

### Step 2: Authenticate with required scopes

The Google Ads API needs `adwords` + `cloud-platform` scopes (the
`cloud-platform` scope is required for YouTube video uploads via the Google Ads
House Channel).

```bash
# Option A: Using the included auth script (requires OAuth client ID file)
cd streamlit_demo/ads_agent
bash auth.sh

# Option B: Using gcloud directly
gcloud auth application-default login \
  --scopes=https://www.googleapis.com/auth/adwords,https://www.googleapis.com/auth/cloud-platform

# Option C: Using Service Account impersonation (recommended for demos)
# See run_local.sh for an example that sets up SA impersonation automatically
```

### Step 3: Update the demo prompt

In prompt configuration, update rule 8 (GOOGLE ADS PUBLISH) to include your
account credentials:

```python
"8. GOOGLE ADS PUBLISH: When user wants to publish, call publish_to_google_ads with: "
"account_id='YOUR_ACCOUNT_ID', customer_id='YOUR_CUSTOMER_ID', is_mcc=true, budget=50.0, "
"final_urls=['https://your-product-page.com'], "
"location_id_targeting='1023191', language_id_targeting='1000'. "
```

### Step 4: Run locally

```bash
# With SA impersonation (recommended)
bash run_local.sh

# Or directly (after running auth.sh)
streamlit run streamlit_app.py
```

### What gets published (Performance Max campaign)

| Asset Type   | Details                                                    |
| ------------ | ---------------------------------------------------------- |
| Text Ads     | 3 headlines (max 30 chars) + 3 descriptions (max 90 chars) |
| Image Ads    | Marketing images from GCS                                  |
| Asset Sheets | Creative boards as marketing images                        |
| Video Ad     | Uploaded to YouTube via Google Ads House Channel           |
| Logo         | Auto-squared to min 300x300 with white padding             |
| Targeting    | Location ID, language ID, search themes                    |

### On Cloud Run

On Cloud Run, the service account running the app needs:

- `roles/aiplatform.user` (Vertex AI)
- `roles/storage.admin` (GCS)
- Google Ads API access configured for the service account

## Troubleshooting

| Issue                            | Fix                                                                         |
| -------------------------------- | --------------------------------------------------------------------------- |
| `PERMISSION_DENIED` on Vertex AI | Run `gcloud services enable aiplatform.googleapis.com --project=PROJECT_ID` |
| `Cloud Build bucket` error       | Deploy script uses `--source .` which handles this automatically            |
| Assets don't display             | Check `DEMO_BUCKET` env var in Cloud Run matches GCS bucket name            |
| `You don't have access`          | Grant IAP/Invoker access (see Grant Access section above)                   |
| App crashes on startup           | Check Cloud Run logs: `gcloud logs read --project=PROJECT_ID`               |

## Deployment

### Required Packages for Deployment

The agent depends on all three packages — they must be deployed together:

```text
release/                         # Deploy from this root
├── marketing_agent/             # Main agent
├── adk_common/                  # Shared utilities (GCS, logging, artifacts)
├── ads_agent/                   # Google Ads PMAX publisher
└── .env                         # Environment configuration
```

### Agent Engine (recommended for production)

```bash
# Deploy using ADK CLI (from release root)
adk deploy agent_engine \
  --project=$PROJECT_ID \
  --region=us-central1 \
  --service_account=$SA_EMAIL \
  marketing_agent
```

Or via Cloud Console:

1.  Go to Cloud Console > Agent Builder
1.  Create new agent > Import from code
1.  Point to the **release root folder** (contains `marketing_agent/`,
    `adk_common/`, `ads_agent/`)
1.  Configure environment variables from `.env`
1.  Assign the service account
1.  Deploy

### Cloud Run (alternative)

```bash
# Build from release root (includes all packages)
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

## Verification

1.  Open agent UI
1.  Say "show me inventory opportunities"
1.  Select a product — verify product image displays inline
1.  Proceed: trends → campaigns → personalize → asset sheets → text ad → image
    ads → video ad
1.  Check: realistic images, 10s video, voiceover + music full duration, text
    overlays
1.  Publish to Google Ads (optional)
