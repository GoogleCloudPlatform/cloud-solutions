# GE Video Ads Agent & Closed-Loop Evaluation Suite

**Author:** Layolin Jesudhass

Multi-scene video ad generation and autonomous self-correction agent for **Agent
Engine + Gemini Enterprise (GE)** aligned with the
[Physion Labs ARC-1.0 Benchmark](https://physionlabs.ai/).

Generates cinematic 1080p video ads from storyboard scene images with AI
voiceover, Lyria background music, EBU R128 audio normalization, title cards,
and dissolve transitions — all self-corrected through a 3-attempt multimodal
evaluation loop and displayed inline in GE chat.

---

## 1. System Architecture

```text
Agent Engine (us-central1)  ←  deploys here
    ↓
gemini-3.1-pro-preview (global)  ←  reasoning & tool dispatch
    ↓
├── ge_video/
│   ├── eval_agent/
│   │   ├── evaluator.py          → Gemini Flash 100-pt Visual & Master Ad Critic
│   │   ├── clip_eval_loop.py     → 3-Attempt Adaptive Clip Self-Correction (>= 92%)
│   │   ├── final_ad_eval_loop.py → 3-Attempt Master Ad Broadcast Polish (>= 95%)
│   │   └── prompts.py            → Forensic Rubrics & Fatal Defect Gating
│   ├── chart_generator.py        → Pillow Visual Analytics Chart Engine
│   ├── agent.py                  → Omni / Veo 3.1 Video Diffusion & Lanczos Scaling
│   └── prompt.md                 → Full GE Conversational System Prompt
├── Gemini TTS (Charon/Aoede) → Broadcast Voiceover Narration (16 Male / 14 Female)
├── Lyria                     → Cinematic Ambient Music Generation
└── FFmpeg Master Mixer       → EBU R128 Audio Normalization (-14 / -24 LUFS)
    ↓
GCS Artifacts Bucket          ← stores video clips, audio, master ad MP4
    ↓
Gemini Enterprise (GE) Chat   ← inline media playback & scorecard display

```

---

## 2. Key Capabilities & Quality Standards

### 2.1. Dual-Tier Multimodal Quality Gating

- **Tier 1: Individual Scene Clips (`>= 92.0%` Pass Threshold):**
- _Subject Realism & Physical Plausibility (25 pts)_ — 100% rigid architecture,
  zero liquid wall/furniture warping.
- _Calm Swimming Pool Fluid Realism_ — Glassy, tranquil water with sunlight
  micro-sparkles (strictly penalizes unnatural violent sloshing / tidal waves).
- _Storyboard Consistency (25 pts)_ — Strict indoor room containment (zero
  flying out bedroom windows, zero diving down to the street).
- _Prompt Adherence & Action (20 pts)_ — Steady front-moving pan-in / dolly
  glide with 100% asset preservation (palm trees, sun loungers, cabanas).
- _Temporal Consistency & Motion (20 pts)_ — Single unbroken continuous take
  (zero mid-clip cuts, zero jump cuts).
- _Visual Polish & Sharpness (10 pts)_ — Edge-to-edge 1080p Lanczos scaling.

- **Tier 2: Master Commercial Ad (`>= 95.0%` Broadcast Pass Threshold):**
- _Voiceover Speech Clarity & Pacing (25 pts)_
- _Brand Identity & Outro Logo Aesthetics (20 pts)_
- _Typography & Tagline Legibility (15 pts)_
- _Multi-Scene Narrative Transitions (20 pts)_
- _Commercial Sound Balance (20 pts)_ — EBU R128 loudness normalization
  (`-14 LUFS` speech, `-24 LUFS` background music).

### 2.2. Autonomous 3-Attempt Self-Correction Loop

- **Per-Attempt Glitch Auto-Retry:** Automatically catches transient API
  timeouts or empty responses per attempt with exponential backoff (up to 3
  retries per candidate attempt).
- **Compound Negative Critique:** Automatically extracts failure critiques from
  Gemini Flash and injects targeted refinement directives for Attempt 2 and 3.
- **Unconditional 3-Attempt Continuation:** If Attempt 2 does not meet the 92.0%
  threshold, the engine unconditionally executes Attempt 3 and selects the
  highest-scoring candidate.

---

## 3. Step-by-Step Deployment (Agent Engine)

### Step 1: Set Project & Enable Required GCP APIs

```bash
export PROJECT_ID=$(gcloud config get-value project)
gcloud config set project $PROJECT_ID

gcloud services enable \
  aiplatform.googleapis.com \
  texttospeech.googleapis.com \
  storage.googleapis.com \
  cloudbuild.googleapis.com \
  run.googleapis.com

```

### Step 2: Create Artifacts Bucket

```bash
export BUCKET_NAME="${PROJECT_ID}-video-ads-artifacts"
gcloud storage buckets create --location=us-central1 gs://${BUCKET_NAME}

```

### Step 3: Configure IAM Permissions

Grant the Agent Engine runtime service account access to read/write artifacts:

```bash
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")

gcloud storage buckets add-iam-policy-binding \
  gs://${BUCKET_NAME} \
- -member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-aiplatform-re.iam.gserviceaccount.com" \
- -role="roles/storage.objectAdmin" \
- -project=$PROJECT_ID

```

- (Optional for Public/Demo Preview in Chat)\*: If you want inline video players
  in GE chat to render publicly without signed cookie hurdles:

```bash
gcloud storage buckets add-iam-policy-binding \
  gs://${BUCKET_NAME} \
- -member="allUsers" \
- -role="roles/storage.objectViewer"

```

### Step 4: Deploy Agent to Vertex AI Agent Engine

Run the automated deployment script (or execute `python deploy_ae.py`):

```bash
cd ge_video_agent_eval
chmod +x deploy_ae.sh
./deploy_ae.sh

```

The deployment script automatically:

1.  Generates `ge_video/requirements.txt` and `ge_video/.env`.
1.  Uploads pre-rendered voice preview MP4s to
    `gs://${BUCKET_NAME}/video_ads/previews/`.
1.  Runs `adk deploy agent_engine` targeting project `$PROJECT_ID` in
    `us-central1`.
1.  Extends the Cloud Run request timeout to 3600s for long-running video
    pipelines.

---

## 4. ADK Common & Custom UI Reusability

To ensure maximum versatility and decouple presentation layers from core logic,
the entire video generation and evaluation pipeline is housed inside the
independent and modular **`ge_video/adk_common/`** package on disk:

### 4.1. Core Engine Decoupling

- **Logical Isolation:** 100% of the multiscene voiceover generation, clip
  compilation, self-correction evaluation loop, master EBU R128 audio
  normalization, and transition assembly are fully encapsulated within
  `ge_video/adk_common/`.
- **Presentation Independence:** There is absolutely no UI or presentation
  framework dependencies inside `adk_common/`. All methods communicate via
  clean, structured Python data transfer objects (DTOs) and standardized schema
  models.

### 4.2. Build Your Own UI or CLI

Because of this complete separation of concerns, developers can easily build
custom frontends on top of the same underlying engine:

1.  **Custom Streamlit Apps:** Simply import `ge_video/adk_common/` and call its
    high-level pipeline orchestration methods to render interactive progress
    bars, tables, and multimedia objects.
1.  **Custom CLI Tools:** Wrap `adk_common/` methods inside an argument-parsed
    Python script (e.g., using `argparse` or `click`) to create a headless
    automation tool for terminal power-users.
1.  **Vertex Agent Builders:** Re-deploy the core engine package with standard
    Vertex AI ADK wrappers to power conversational chat integrations with zero
    structural modification.

---

## 5. Summary of Video Models

| Model                                  |   Resolution    |                   Best For                   |
| :------------------------------------- | :-------------: | :------------------------------------------: |
| **Omni** (`gemini-omni-flash-preview`) | 1080p (Lanczos) | Fast real-time multi-attempt self-correction |
| **Veo** (`veo-3.1-generate-001`)       |  1080p Native   |     High-end cinematic final production      |
