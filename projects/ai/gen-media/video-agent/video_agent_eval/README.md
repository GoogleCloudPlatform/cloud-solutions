# Video Ads Studio & Closed-Loop Multimodal Evaluation Agent

- \*Author:\*\* Layolin Jesudhass

Autonomous multi-scene video ad generation and closed-loop quality assurance
suite with an interactive **Streamlit Studio UI** and headless **Evaluation
Agent** aligned with the
[Physion Labs ARC-1.0 Benchmark](https://physionlabs.ai/).

Upload scene images, generate AI voiceover scripts, synthesize 1080p video clips
with Omni or Veo, autonomously evaluate and self-correct physical/cinematic
defects across a 3-attempt retry loop, and assemble broadcast-ready video ads
with EBU R128 mastered audio.

---

## 1. System Architecture

```text
Streamlit Studio & Evaluation Pipeline
├── Web UI & Analytics (streamlit_video_ads.py)
│   ├── All Scene Clips Multi-Attempt Evaluation Matrix
│   ├── 2 Visual Analytics Bar Charts (5D Quality & 16-Metric ARC Breakdown)
│   └── Dual Cloud & Local Persistence (GCS + Local JSON)
├── Multimodal Evaluation Suite (eval_agent/)
│   ├── evaluator.py          → Gemini Flash 100-pt Visual & Master Ad Critic
│   ├── clip_eval_loop.py     → 3-Attempt Adaptive Clip Self-Correction (>= 92%)
│   ├── final_ad_eval_loop.py → 3-Attempt Master Ad Broadcast Polish (>= 95%)
│   ├── chart_generator.py    → Pillow Visual Analytics Chart Engine
│   ├── prompts.py            → Forensic Rubrics & Fatal Defect Gating
│   └── run_complete_campaign_eval.py → Parallel Headless Campaign Runner
├── Core Generation Engine (video_ads_agent/agent.py)
│   ├── Omni / Veo 3.1        → 1080p Video Diffusion & Lanczos Super-Resolution
│   ├── Camera Dynamics       → Scenario-Adaptive (Pool Glide, Suite Containment)
│   ├── Gemini TTS            → High-Fidelity Voiceover Narration (Charon/Kore)
│   ├── Lyria                 → Cinematic Ambient Music Generation
│   └── FFmpeg Master Mixer   → EBU R128 Audio Normalization (-14 / -24 LUFS)
└── Batch CLI Pipeline (ge_video_ads.py) → Spreadsheet-based Batch Producer

```

---

## 2. Key Capabilities & Quality Standards

### 2.1. Dual-Tier Multimodal Evaluation Gating

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

### 2.3. Dual Cloud & Local Persistence

- **Dual GCS & Local Disk Storage:** All video clips, voiceovers, master ads,
  16-metric scorecards, and visual analytics are saved to both local disk and
  Google Cloud Storage (`gs://<project_id>-video-ads-projects/`).
- **Full State Restoration:** Loading any saved brand restores 100% of scene
  images, video players, evaluation scorecards, and visual charts.

---

## 3. Deployment & Setup

### Prerequisites

- GCP Project with Vertex AI & Cloud TTS enabled
- Authenticated `gcloud` session (`gcloud auth login` and
  `gcloud auth application-default login`)

### 3.1. Deploy to Google Cloud Run (Recommended for Cloud Shell)

When deploying to a new GCP project:

```bash
cd video_agent_eval

# Step 1: Set your active GCP project ID
export PROJECT_ID=$(gcloud config get-value project) # or replace with your-project-id
gcloud config set project $PROJECT_ID

# Step 2: Configure .env with your project ID (CRITICAL: update if deploying to a new project)
cat > .env << EOF
GOOGLE_CLOUD_PROJECT=$PROJECT_ID
GOOGLE_CLOUD_LOCATION=global
EOF

# Step 3: Enable required GCP services
gcloud services enable \
  aiplatform.googleapis.com \
  texttospeech.googleapis.com \
  storage.googleapis.com \
  cloudbuild.googleapis.com \
  run.googleapis.com

# Step 4: Deploy container to Cloud Run (8 vCPU, 16GB RAM, Session Affinity)
chmod +x deploy.sh
./deploy.sh

```

### 3.2. Local Development & Testing

```bash
cd video_agent_eval

# Install local virtual environment & dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install --require-hashes -r requirements.txt

# Run local studio app
streamlit run streamlit_video_ads.py --server.port 8501

```

### Step 2: Install Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --require-hashes -r requirements.txt

```

### Step 3: Run Interactive Studio App

```bash
streamlit run streamlit_video_ads.py --server.port 8501

```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## 4. Headless Campaign Evaluation & CLI Benchmarking

Run the complete 4-scene parallel evaluation benchmark:

```bash
python eval_agent/run_complete_campaign_eval.py

```

Run spreadsheet batch generation:

```bash
python ge_video_ads.py \
- -spreadsheet scenes.csv \
- -company "Hyatt Regency Maui" \
- -voice Charon \
- -model omni \
- -music on \
- -output output/

```

---

## 5. Summary of Video Models

| Model                                  |   Resolution    | Best For                                     |
| :------------------------------------- | :-------------: | :------------------------------------------- |
| **Omni** (`gemini-omni-flash-preview`) | 1080p (Lanczos) | Fast real-time multi-attempt self-correction |
| **Veo** (`veo-3.1-generate-001`)       |  1080p Native   | High-end cinematic final production          |
