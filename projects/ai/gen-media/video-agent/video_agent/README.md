# Video Ads Studio (Streamlit + Cloud Run)

Multi-scene video ad generation with an interactive **Streamlit UI** deployed on
**Cloud Run**.

Upload scene images, generate or write voiceover scripts, create video clips
with Omni or Veo, and assemble a final professional video ad — all from a web
browser.

---

## Architecture

```text
Cloud Run (us-central1)
├── Streamlit UI (streamlit_video_ads.py)
├── Core engine (video_ads_agent/agent.py)
│   ├── Omni / Veo  → video clip generation
│   ├── Chirp3-HD   → TTS voiceover
│   ├── Lyria       → background music
│   ├── Gemini      → AI script generation (Google Search grounded)
│   └── FFmpeg      → trim, mix, title cards, dissolve, concat
└── GE CLI (ge_video_ads.py)  → spreadsheet-based batch pipeline
```

---

## Deployment (Step by Step)

### Prerequisites

- GCP project with billing enabled
- Cloud Shell or local machine with `gcloud` CLI
- `gcloud auth login` and `gcloud auth application-default login`

### Step 1: Set project and enable APIs

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

### Step 2: Upload files to Cloud Shell

Upload the `video_ads_agent/` folder to Cloud Shell via **Upload > Folder**.

Ensure the folder structure looks like:

```text
~/video_ads_agent/
├── video_ads_agent/
│   ├── __init__.py
│   ├── agent.py
│   └── prompt.md
├── streamlit_video_ads.py
├── ge_video_ads.py
├── google_logo.png
├── Dockerfile
├── deploy.sh
├── pyproject.toml
├── static/
│   └── style.css
└── .streamlit/
    └── config.toml
```

### Step 3: Create .env file

```bash
cd ~/video_ads_agent

cat > .env << EOF
GOOGLE_CLOUD_LOCATION=global
EOF
```

### Step 4: Deploy to Cloud Run

```bash
chmod +x deploy.sh
./deploy.sh
```

The script will:

1.  Auto-detect PROJECT_ID from `gcloud config` (or prompt you to enter it)
1.  Build container image via Cloud Build (~3 min)
1.  Deploy to Cloud Run with 8 vCPU / 8GB RAM, session affinity, 1-hour timeout
1.  Print the service URL

### Step 5: Grant permissions (if needed)

The default Compute Engine service account usually has Vertex AI access. If not:

```bash
SA=$(gcloud run services describe video-ads-studio \
  --region us-central1 --format='value(spec.template.spec.serviceAccountName)')

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA" --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA" --role="roles/cloudtexttospeech.client"
```

### Step 6: Open the app

The deploy script prints the Cloud Run URL. Open it in your browser.

---

## App Flow (Streamlit UI)

### 1. Setup (Sidebar)

On the left sidebar, configure:

- **Company name** — your brand (e.g. "Hyatt")
- **Number of scenes** — how many images/clips (1-15)
- **Video model** — Omni (fast, ~30s) or Veo (cinematic, ~5min)
- **Voice** — pick from Chirp3-HD male/female voices, with audio preview
- **Background music** — on/off toggle
- **Brand context** — optional brand description for smarter AI scripts

### 2. Upload Scene Images

Upload images for each scene (PNG, JPG, WebP). Each image becomes a video clip.

Images are displayed in the UI for review.

### 3. Voiceover Scripts

Two options:

- **AI Generate** — click the button to auto-generate scripts using Gemini with
  Google Search grounding. Scripts are based on the images + company name.
- **Manual** — type your own script for each scene in the text fields.

Edit any script before proceeding. Guidelines:

- Omni: 6-15 words per scene
- Veo: 6-12 words per scene
- Each script should use different vocabulary

### 4. Generate Video Clips

Click **Generate Clips** to create video clips for all scenes in parallel (max 4
concurrent).

Each clip is displayed inline with:

- Editable video generation prompt (expandable)
- Regenerate button per scene
- Progress tracking

Clips are visual-only (silent) — audio is added during assembly.

### 5. Review and Regenerate

Review each clip in the UI. If you don't like one:

- Edit the generation prompt
- Click **Regenerate** for that scene
- The clip is replaced with the new version

### 6. Assemble Final Video

Click **Assemble Final Video**. The pipeline runs:

```text
1. TTS voiceovers generated (parallel, Chirp3-HD)
2. Each clip trimmed to voiceover duration + 0.5s padding
3. Voiceover mixed onto each clip
4. Intro title card (company name on blurred scene background)
5. Outro title card (company name + tagline)
6. Scene clips joined with dissolve transitions
7. Intro + scenes + outro hard-concatenated
8. Lyria background music layered at 35% volume
9. Logo overlay (if provided)
```

Final video displayed inline with download button.

Session logs are available in an expandable section showing all generation
details.

---

## GE CLI Pipeline

`ge_video_ads.py` generates video ads from CSV spreadsheets (batch/offline
mode).

```bash
# Generate a template CSV
python ge_video_ads.py --template --scenes 4 --output template.csv

# Fill in the CSV with image paths and scripts, then generate
python ge_video_ads.py \
  --spreadsheet scenes.csv \
  --company "Hyatt" \
  --voice Charon \
  --model omni \
  --music on \
  --output output/
```

| Flag              | Default  | Description                         |
| ----------------- | -------- | ----------------------------------- |
| `--spreadsheet`   | required | Path to completed CSV               |
| `--company`       | `""`     | Company/brand name                  |
| `--brand-context` | `""`     | Brand context for music/scripts     |
| `--voice`         | `Charon` | Chirp3-HD voice name                |
| `--model`         | `omni`   | Video model: `omni` or `veo`        |
| `--music`         | `on`     | Background music: `on` or `off`     |
| `--logo`          | `""`     | Path to brand logo PNG              |
| `--output`        | `output` | Output directory                    |
| `--prompt-file`   | `""`     | Custom video generation prompt file |

---

## Local Development

```bash
cd video_ads_agent
pip install .
streamlit run streamlit_video_ads.py
```

Opens at `http://localhost:8501`. Requires:

- Python 3.12+
- ffmpeg installed (`brew install ffmpeg` on Mac, `apt install ffmpeg` on Linux)
- `gcloud auth application-default login`

---

## Video Models

| Model                              | Speed       | Quality   | Duration       | Best For               |
| ---------------------------------- | ----------- | --------- | -------------- | ---------------------- |
| Omni (`gemini-omni-flash-preview`) | ~30 seconds | Good      | 8-10s per clip | Quick previews, drafts |
| Veo (`veo-3.1-generate-001`)       | ~5 minutes  | Cinematic | 8s per clip    | Final production       |

## Environment Variables

| Variable                | Value           | Purpose        |
| ----------------------- | --------------- | -------------- |
| `GOOGLE_CLOUD_PROJECT`  | your-project-id | GCP project    |
| `GOOGLE_CLOUD_LOCATION` | `global`        | Model endpoint |

## Required APIs

| API                      | Used For                                    |
| ------------------------ | ------------------------------------------- |
| Vertex AI API            | Omni/Veo video, Gemini scripts, Lyria music |
| Cloud Text-to-Speech API | Chirp3-HD voiceover                         |
| Cloud Storage API        | Static file serving                         |
| Cloud Build API          | Container image build                       |
| Cloud Run API            | Deployment                                  |

## Troubleshooting

| Error                          | Fix                                                                       |
| ------------------------------ | ------------------------------------------------------------------------- |
| 404 model not found            | Ensure `GOOGLE_CLOUD_LOCATION=global` in .env                             |
| Font errors in title cards     | Auto-detected: Helvetica (Mac), DejaVu Sans (Linux/Cloud Run)             |
| Cloud Build timeout            | Default 600s; increase with `--timeout=900` in deploy.sh                  |
| Permission denied on Vertex AI | Grant `roles/aiplatform.user` to Cloud Run SA (Step 5)                    |
| Static files 404               | Ensure `.streamlit/config.toml` has `[server] enableStaticServing = true` |
