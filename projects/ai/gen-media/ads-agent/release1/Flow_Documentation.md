# Personalized Marketing Agent

## Complete Agent Flow Documentation

**Version:** 5.20260410.1
**Platform:** Google ADK (Agent Development Kit)
**Runtime:** `uv run adk web marketing_agent`

---

## 1. Architecture Overview

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                            ROOT AGENT                                       │
│                  marketing_agent/agent.py                                    │
│                  [gemini-3.1-pro-preview]                                    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                    DATA & DISCOVERY LAYER                               │ │
│  │                                                                         │ │
│  │  ┌────────────────┐  ┌────────────────┐  ┌──────────────────────────┐   │ │
│  │  │  Inventory Tool │  │  Sales Tool     │  │  Trend Spotter           │   │ │
│  │  │  [BigQuery]     │  │  [BigQuery]     │  │  Sub-Agent               │   │ │
│  │  │  High stock +   │  │  Low velocity   │  │  [gemini-3.1-pro +       │   │ │
│  │  │  product data   │  │  sales analysis │  │   Google Search]         │   │ │
│  │  └────────────────┘  └────────────────┘  └──────────────────────────┘   │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                CAMPAIGN & PERSONALIZATION LAYER                          │ │
│  │                                                                         │ │
│  │  ┌────────────────┐  ┌────────────────┐  ┌──────────────────────────┐   │ │
│  │  │  Campaign XML   │  │  Personalization│  │  Asset Management        │   │ │
│  │  │  Engine          │  │  Engine         │  │                          │   │ │
│  │  │  [gemini-3.1-pro│  │  5 Personas:    │  │  check_existing_assets   │   │ │
│  │  │   + Google       │  │  1.Family       │  │  delete_asset_from_gcs   │   │ │
│  │  │   Search]        │  │  2.Travel       │  │  save_selected_*         │   │ │
│  │  │                  │  │  3.Professional │  │                          │   │ │
│  │  │  Campaigns →     │  │  4.Fitness      │  │  GCS: {product}_{persona}│   │ │
│  │  │  Segments →      │  │  5.Luxury       │  │                          │   │ │
│  │  │  Briefs →        │  │                 │  │                          │   │ │
│  │  │  Rationales      │  │  Tailors ALL    │  │                          │   │ │
│  │  │                  │  │  ads to persona │  │                          │   │ │
│  │  └────────────────┘  └────────────────┘  └──────────────────────────┘   │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                   MEDIA GENERATION LAYER                                │ │
│  │                                                                         │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │ │
│  │  │ Text Ads │ │ Asset    │ │ Image    │ │ Video    │ │ Post-        │  │ │
│  │  │ (RSA)    │ │ Sheets   │ │ Ads      │ │ Pipeline │ │ Production   │  │ │
│  │  │          │ │          │ │          │ │          │ │              │  │ │
│  │  │ gemini   │ │ gemini   │ │ gemini   │ │ Storyline│ │ ffmpeg:      │  │ │
│  │  │ 3.1-pro  │ │ 3.1-flash│ │ 3.1-flash│ │ [pro]   │ │ - stitch     │  │ │
│  │  │          │ │ -image   │ │ -image   │ │ Keyframe │ │ - audio mix  │  │ │
│  │  │ JSON     │ │          │ │          │ │ [flash]  │ │ - text overlay│  │ │
│  │  │ output   │ │ Parallel │ │ Parallel │ │ VEO 3.1  │ │ - end card   │  │ │
│  │  │          │ │ gen      │ │ gen      │ │ [3 clips]│ │ - logo       │  │ │
│  │  │          │ │          │ │          │ │ TTS      │ │              │  │ │
│  │  │          │ │          │ │          │ │ [Charon] │ │              │  │ │
│  │  │          │ │          │ │          │ │ Lyria    │ │              │  │ │
│  │  │          │ │          │ │          │ │ [music]  │ │              │  │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  ADK Skills (6) — Progressive Disclosure                                │ │
│  │  ad-copywriting | video-storytelling | visual-direction                  │ │
│  │  brand-strategy | trend-analysis | platform-specs                       │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  A2A — Google Ads Publisher                                             │ │
│  │  ads_agent/ (direct Python import)                                      │ │
│  │  → create_pmax_campaign() → Google Ads API + YouTube Upload             │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Model Usage Map

| Component | Model | Purpose |
| :--------- | :----- | :------- |
| Root Agent | `gemini-3.1-pro-preview` | Orchestration, user interaction, tool calling |
| Campaign XML | `gemini-3.1-pro-preview` + Google Search | Campaign structure with trend-aware creative direction |
| Trend Spotter | `gemini-3.1-pro-preview` + Google Search | Market trend research |
| Storyline | `gemini-3.1-pro-preview` | 3-act video storyline + lyria prompt (temp=1.0, top_p=0.95) |
| Text Ad (RSA) | `gemini-3.1-pro-preview` | Headlines + descriptions (response_mime_type=JSON) |
| Image Ads + Keyframes | `gemini-3.1-flash-image-preview` | All image generation with 120s timeout |
| Video Clips | `veo-3.1-generate-001` | 3 x 8s clips with keyframe interpolation |
| Voiceover | `gemini-2.5-pro-tts` (Chirp3-HD, Charon) | Deep authoritative male voice, speaking_rate=1.0, volume=1.5x |
| Background Music | `lyria-3-pro-preview` | Storyline-matched instrumental, volume=30% |
| Post-Production | `ffmpeg` | Stitch, audio mix, text overlays, end card overlay, logo |

---

## 3. File Structure

```text
marketing_agent/
├── __init__.py
├── agent.py                    # Main agent — all tools + video pipeline
├── prompt.md                   # Dynamic instruction template
├── config.py                   # BigQuery config, safety settings
├── schema.py                   # Pydantic models (Product, Brand, Trend, etc.)
├── campaign_utils.py           # XML parser → Campaign/Segment/Asset dataclasses
├── generate_campaigns.py       # Gemini → campaign XML with Google Search grounding
├── generate_display_ad.py      # On-request ad editing tool
├── data/
│   └── products.py             # Product database (BigQuery)
├── sub_agents/
│   └── trend_spotter.py        # Trend research sub-agent (Google Search)
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

- `adk_common/` — Shared utilities (GCS, logging, artifact rendering)
- `ads_agent/` — Google Ads PMAX publisher (optional)

---

## 4. Registered Tools

### Product & Campaign Pipeline

| Tool | Purpose |
| :---- | :------- |
| `identify_inventory_opportunities` | Queries BigQuery for high-stock + low-velocity products |
| `get_product_by_sku` | Retrieves product from BigQuery + displays image inline |
| `setup_campaign_from_sku` | Auto-fills brand/product/audience from SKU, generates campaigns |
| `setup_product_campaign` | Manual campaign setup (Path B) |
| `get_campaign_idea` | Returns N campaign concepts from generated XML |
| `save_selected_campaign` | Saves user's campaign choice |
| `get_selected_brief` | Returns creative brief for selected campaign |
| `set_customer_persona` | Sets persona (1-5) for personalized ad generation |
| `clear_customer_persona` | Resets to generic ad generation |
| `check_existing_assets` | Checks GCS for existing assets for product+persona |
| `delete_asset_from_gcs` | Deletes a specific asset before regeneration |

### Asset Generation

| Tool | Purpose |
| :---- | :------- |
| `get_asset_sheet` | Generates N asset sheet images in parallel |
| `generate_text_ad` | RSA text ad (3 headlines + 3 descriptions), JSON output |
| `get_image_ads_for_audience` | Generates N image ads in parallel |
| `get_video_ads_for_audience` | Generates N cinematic 24s video ads in parallel |
| `save_selected_asset_sheet` | Saves user's asset sheet choice |

### Publishing

| Tool | Purpose |
| :---- | :------- |
| `publish_to_google_ads` | Publishes PMAX campaign via A2A to Google Ads |
| `recommend_campaign_settings` | Budget/bidding/targeting recommendations |

### Sub-Agent

| Agent | Purpose |
| :----- | :------- |
| `trend_spotter` | Market trend research with Google Search grounding |

### ADK Skills (6)

| Skill | Purpose |
| :----- | :------- |
| `ad-copywriting` | Headline/description best practices |
| `video-storytelling` | 3-act narrative structure |
| `visual-direction` | Color palettes, photography direction |
| `brand-strategy` | Brand positioning |
| `trend-analysis` | Trend evaluation frameworks |
| `platform-specs` | Ad format specs |

---

## 5. End-to-End Flow

### Path A: Inventory-Based

```text
1. Greeting → 2 options (inventory or manual)

2. Product Selection
   └── identify_inventory_opportunities() → BigQuery top products
   └── User selects product → get_product_by_sku() → image displayed inline

3. Trend Research
   └── trend_spotter sub-agent → Google Search → trends table
   └── Agent analyzes product-trend alignment

4. Campaign Setup
   └── setup_campaign_from_sku() → generate_campaigns_xml() [with Google Search]
   └── get_campaign_idea() → user selects concept
   └── get_selected_brief() → user selects segment

5. Personalization
   └── set_customer_persona(1-5) → sets output folder
   └── check_existing_assets() → reuse or regenerate

6. Asset Sheets (parallel generation, 120s timeout per image)
   └── User reviews → approves or requests regeneration
   └── Regeneration: delete_asset_from_gcs() → regenerate specific one

7. Text Ad (auto-generated after asset sheet approval)
   └── RSA format: 3 headlines (30 chars) + 3 descriptions (90 chars)
   └── JSON output via response_mime_type
   └── User reviews → approves or requests changes

8. Image Ads (parallel generation)
   └── User reviews → approves or requests regeneration of specific ones

9. Video Ads (24s cinematic — see pipeline below)
   └── User reviews → approves or requests regeneration

10. Publish to Google Ads
    └── Auto-populates from session: headlines, images, videos, logo
    └── Creates PMAX campaign via ads_agent
```

### Path B: Manual Campaign Setup

Same as Path A from step 3 onward, but user provides:

- Brand name, product name, description, price, target audience
- Product image (displayed inline immediately)
- Logo (optional)
- Reference documents (optional)

---

## 6. Video Pipeline (per video, ~4-5 min)

```text
PHASE 1: Storyline [gemini-3.1-pro-preview, temp=1.0] (~5s)
├── 3 acts: scene, end_scene, motion_prompt, voiceover (15 words/act)
├── lyria_prompt: storyline-matched music description
└── Fallback: hardcoded 3-act storyline

PHASE 2: Parallel Audio + Keyframes
├── Voiceover [Chirp3-HD Charon, rate=1.0] ─── 10s
├── Lyria Music [lyria-3-pro-preview] ──────── 15s
└── 4 Keyframes [flash-image, 120s timeout] ── 30s (all parallel)
    ├── KF1: BRIGHT DAYLIGHT
    ├── KF2: GOLDEN HOUR
    ├── KF3: DRAMATIC DUSK
    └── KF4: NIGHT / NEON
    Rules: product fidelity, real-world scale, no hallucination,
           subject consistency across keyframes, no close-up child faces

PHASE 3: VEO Clips [veo-3.1, 3 clips parallel]
├── Act 1: KF1 → KF2 (8s interpolation)
├── Act 2: KF2 → KF3 (8s interpolation)
└── Act 3: KF3 → KF4 (8s interpolation)
    Rules: real-life physics, no object teleportation,
           no product transformation, subject integrity
    Retry: interpolation fail → i2v → final sequential retry
    Saved: individual clips to GCS

PHASE 4: Post-Production [ffmpeg]
├── Stitch: concat clips
├── Audio Mix:
│   ├── Voiceover: 150% volume, full duration, fade out last 1.5s
│   ├── Music: 30% volume, full duration to last millisecond
│   └── amix duration=longest
├── Logo Overlay: top-right, 12% width, 40% opacity
├── Text Overlays:
│   ├── Brand name (0.5-5s, bottom-left)
│   ├── Product name (1-5.5s, below brand)
│   ├── Tagline (mid-video, 5s, bottom-center)
│   └── Price (last 6s, bottom-right) — from BQ or user input
├── End Card Overlay: last 3s of video
│   ├── Semi-transparent dark bar at bottom
│   ├── Brand name + tagline + price
│   └── No separate appended frame
└── Keyframes retained in GCS as keyframe_{N}.png
```

---

## 7. Agent-to-Agent (A2A) Integration

### Current Implementation: Direct Python Import

We use **direct Python import** instead of the A2A HTTP
protocol to connect the Marketing Agent to the Google Ads
Agent.

**Why direct import instead of A2A?**

- The A2A protocol (`RemoteA2aAgent`) required both agents
  to run as separate HTTP servers. During development, ADK
  SDK version mismatches between the agents prevented
  `RemoteA2aAgent` from working, and the HTTP A2A endpoint
  returned 404 in the dev environment.
- Direct import is simpler, faster (no network overhead),
  and runs in the same process — ideal for agents that are
  always deployed together.
- The `agent.json` A2A card exists in `ads_agent/` and is
  ready for future A2A HTTP deployment when needed.

**How it works:**

1.  Marketing agent collects all generated assets from
    session state
1.  Imports `create_pmax_campaign()` directly from
    `ads_agent/agent.py`
1.  Builds payload: headlines, descriptions, image URIs,
    video URIs, logo, targeting
1.  Ads agent downloads assets, uploads video to YouTube,
    creates PMAX campaign
1.  Returns campaign ID + status
1.  Graceful fallback: if ads_agent unavailable, returns
    payload for manual creation

### How to Enable A2A HTTP Protocol (Future)

To run the Ads Agent as a standalone A2A service
that other agents can connect to over HTTP:

#### Step 1: Deploy the Ads Agent as a separate ADK server

```bash
uv run adk web ads_agent --port 8001
```

#### Step 2: Register the A2A card

The `ads_agent/agent.json` already contains the
A2A agent card:

```json
{
  "name": "google_ads_agent",
  "description": "Creates Performance Max campaigns on Google Ads",
  "url": "http://localhost:8001"
}
```

Update the `url` to the deployed endpoint.

#### Step 3: Connect from Marketing Agent

Replace the direct import in
`publish_to_google_ads()` with:

```python
from google.adk.agents import RemoteA2aAgent

ads_agent = RemoteA2aAgent(
    name="google_ads_agent",
    url="http://<ads-agent-host>:8001",
)
```

#### Step 4: Send the payload via A2A message

```python
result = await ads_agent.send(payload)
```

### How to Integrate This Agent into Another ADK Agent

If someone wants to call the Marketing Agent from
their own ADK agent:

#### Option A: Direct Python Import (same repo)

```python
from marketing_agent.agent import root_agent

# Use as a sub-agent tool
from google.adk.tools import AgentTool
marketing_tool = AgentTool(agent=root_agent)
```

#### Option B: A2A HTTP (separate deployment)

1.  Deploy the Marketing Agent:
    `uv run adk web marketing_agent --port 8002`
1.  From your agent:

    ```python
    from google.adk.agents import RemoteA2aAgent

    marketing_agent = RemoteA2aAgent(
        name="marketing_agent",
        url="http://<marketing-agent-host>:8002",
    )
    ```

1.  Send a message to trigger the flow:

    ```python
    result = await marketing_agent.send({
        "message": "Create a campaign for product SKU FOOD-001 with Luxury persona"
    })
    ```

#### Option C: Agent Engine (Google Cloud managed)

1.  Deploy to Agent Engine via Cloud Console
1.  Use the Agent Engine API to invoke:

    ```python
    from google.cloud import aiplatform
    agent = aiplatform.Agent(
        "projects/.../agents/marketing-agent"
    )
    response = agent.query(
        "Show me inventory opportunities"
    )
    ```

### A2A File Structure

```text
ads_agent/
├── agent.py                    # create_pmax_campaign() entry point
├── agent.json                  # A2A agent card (name, description, URL)
├── services/
│   ├── google_ads_api_service_pmax.py  # Google Ads API + YouTube upload
│   └── storage_service.py     # GCS asset download
├── models/agent_models.py     # Request/response models
└── targeting_config/          # Location/language lookups
```

---

## 8. Data & Asset Setup

### Sample Data (included in `assets/` folder)

```text
assets/
├── bigquery/
│   ├── products.csv             # Product catalog (84 products)
│   └── inventory_analysis.csv   # Stock levels, sales velocity, forecast
├── product_images/              # Product photos (matched to products.csv SKUs)
│   ├── FOOD-001.png
│   ├── ELEC-001.png
│   └── ... (84 images)
└── samples/                     # Sample brand assets for demo
    ├── <your-product>.png       # Sample product photo
    ├── <your-logo>.png          # Sample brand logo
    └── <your-marketing-guide>.md  # Sample reference doc
```

### Setup Steps

#### 1. Upload product images to GCS

```bash
gcloud storage cp assets/product_images/*.png \
  gs://<your-artifacts-bucket>/products/
gcloud storage cp assets/samples/* \
  gs://<your-artifacts-bucket>/samples/
```

#### 2. Update image URIs in products.csv

Replace `<your-artifacts-bucket>` with your actual
bucket name in the `image_uri` column.

#### 3. Load data into BigQuery

```bash
bq mk --dataset <your-project-id>:retail_analytics

bq load --source_format=CSV --autodetect \
  retail_analytics.products \
  assets/bigquery/products.csv

bq load --source_format=CSV --autodetect \
  retail_analytics.inventory_analysis \
  assets/bigquery/inventory_analysis.csv
```

### GCS Folder Structure

```text
gs://<your-artifacts-bucket>/
├── products/                    # Product catalog images (uploaded in setup)
│   ├── FOOD-001.png
│   ├── ELEC-001.png
│   └── ...
├── samples/                     # Sample brand assets
├── logo.png                     # Default logo
└── {ProductName}_{PersonaName}/ # Generated assets (created by the agent)
    ├── asset_sheet_*.png        # Asset sheets
    ├── img_*.png                # Image ads
    ├── text_ad_*.json           # Text ads (RSA format)
    ├── keyframe_{1-4}.png       # Video keyframes (retained)
    ├── clip_act{1-3}.mp4        # Individual VEO clips (retained)
    ├── background_music_*.mp3   # Lyria music (retained)
    └── video_ad_*.mp4           # Final video(s)
```

Persona folder names: `Family_with_Kids`,
`Travel_Enthusiast`, `Young_Professional`,
`Fitness_Wellness`, `Luxury_Premium`

Assets persist across sessions. Regenerated assets
replace old ones via `delete_asset_from_gcs`.

---

## 9. Asset Regeneration Flow

When user requests regeneration of a specific asset:

1.  Agent identifies the exact filename to replace
1.  Calls `delete_asset_from_gcs(filename)` — removes
    old file from GCS
1.  Calls the generation tool for just that one asset
1.  New asset uploads to GCS and displays inline
1.  Asks user again for approval

Works for: asset sheets, text ads, image ads, video ads.

---

## 10. Quality Controls

### Image Generation

- Product fidelity: exact match to reference image, no invented features
- Real-world scale: product proportional to people and environment
- Physics: gravity applies, no floating, no smoke from cold drinks
- Anatomy: no phantom hands, each person has exactly 2 hands
- Reference images: product photo + logo must be used as-is, not reimagined
- 120s timeout per image call to prevent hung API requests

### Video Generation

- Real-life physics: objects don't move by themselves, don't teleport
- Product integrity: no opening, closing, folding, transforming
- Subject consistency: same pose/direction across keyframes
- Anti-hallucination: every scene must be real-life plausible
- VEO safety: avoid close-up children's faces in keyframes
- Content sanitization: sensitive words stripped from VEO prompts

### Audio

- Voiceover runs full video duration, not truncated
- Music plays to the last millisecond
- Music mood matches storyline arc (not generic)
- Volume: voiceover 150%, music 30%

---

## 11. Retry & Error Handling

| API | Strategy |
| :--- | :-------- |
| Gemini LLM | 4 attempts, exponential backoff on 429 |
| Gemini Image | 5 attempts, 120s timeout per call, 429 backoff |
| VEO submit | 3 attempts, 429 backoff |
| VEO poll | 80 x 10s = 800s timeout |
| VEO clip fail | Retry as i2v, then final sequential retry |
| TTS | 3 attempts, 2s between |
| Campaign XML | 3 attempts, full re-generation on parse error |
| YouTube upload | 20 retries x 15s polling |

---

## 12. Deployment

### Prerequisites

- GCP project with: Vertex AI, Cloud Storage,
  BigQuery, Cloud TTS, Google Ads API
- Service account roles: `aiplatform.user`,
  `storage.objectAdmin`, `bigquery.dataViewer`,
  `texttospeech.user`
- `ffmpeg` installed
- Python 3.13+

### Quick Start

```bash
pip install uv && uv sync
cp .env.example .env  # Edit with your GCP project details
gcloud auth application-default login
uv run adk web marketing_agent
```

### Cloud Run

```bash
gcloud run deploy marketing-agent \
  --image gcr.io/${PROJECT_ID}/marketing-agent \
  --region us-central1 \
  --memory 4Gi --cpu 2 --timeout 900 --concurrency 1
```

### Verification

1.  Open agent → "show me inventory opportunities"
    → select product
1.  Verify: product image inline, trends, campaigns,
    personalization
1.  Generate: asset sheets → text ad → image ads
    → video ad
1.  Check: realistic images, 24s video, voiceover
    and music full duration
1.  Publish to Google Ads (optional)
