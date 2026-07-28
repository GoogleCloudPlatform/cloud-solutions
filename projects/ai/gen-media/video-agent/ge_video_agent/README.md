# GE Video Ads Agent

Multi-scene video ad generation agent for **Agent Engine + Gemini Enterprise (GE)**.

Generates cinematic video ads from scene images with AI voiceover, background music, title cards, and dissolve transitions — all displayed inline in the GE chat.

---

## Architecture

```text
Agent Engine (us-central1)  ←  deploys here
    ↓
gemini-3.1-pro-preview (global)  ←  model calls go here
    ↓
Tools: Omni/Veo video gen, Chirp3-HD TTS, Lyria music, FFmpeg assembly
    ↓
GCS bucket  ←  stores images, clips, final video
    ↓
Gemini Enterprise  ←  inline media display
```text

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
  storage.googleapis.com
```text

### Step 2: Create GCS bucket (if not already created)

```bash
gcloud storage buckets create --location=us-central1 gs://${PROJECT_ID}-video-ads-artifacts
```text

### Step 3: Grant Agent Engine SA access to the bucket

Find your project number:

```bash
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
```text

Grant storage access:
```bash
gcloud storage buckets add-iam-policy-binding \
  gs://${PROJECT_ID}-video-ads-artifacts \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-aiplatform-re.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin" \
  --project=$PROJECT_ID
```text

### Step 4: Upload files to Cloud Shell

Upload the `ge_video/` folder to Cloud Shell via **Upload > Folder**.

Ensure the folder structure looks like:
```text
~/ge_video/
├── ge_video/
│   ├── __init__.py
│   ├── agent.py
│   ├── prompt.md
│   └── adk_common/        ← bundled by deploy script
├── assets/
│   └── voice_previews/    ← pre-generated MP4s (uploaded to GCS by deploy script)
│       ├── male/           (16 voices: 1_Achird.mp4 ... 16_Zubenelgenubi.mp4)
│       └── female/         (14 voices: 1_Achernar.mp4 ... 14_Zephyr.mp4)
├── adk_common/             ← must be here (copied from repo root)
├── generate_voice_previews.py  ← run once to create voice assets
├── pyproject.toml
├── requirements.txt
├── deploy_ae.sh
├── .env
└── README.md
```text

### Step 5: Create .env file

```bash
cd ~/ge_video

cat > .env << EOF
GOOGLE_CLOUD_LOCATION=global
AGENT_VERSION=1.0.0
EOF
```text

The deploy script auto-detects `GOOGLE_CLOUD_PROJECT` from `gcloud config` and derives `GOOGLE_CLOUD_BUCKET_ARTIFACTS` as `${PROJECT_ID}-video-ads-artifacts`.

**Why `GOOGLE_CLOUD_LOCATION=global`?** The model `gemini-3.1-pro-preview` is only available in the `global` region. Agent Engine deploys to `us-central1`, but model calls are routed to `global` at runtime.

### Step 6: Generate voice preview assets (one-time)

```bash
python generate_voice_previews.py
```text

This generates MP4 video previews for all 30 voices (16 male + 14 female) — each is a short video with a styled card and audio sample. Saves to `assets/voice_previews/male/` and `assets/voice_previews/female/`. Only needs to run once — the files are reused across deployments.

To download existing male previews from GCS first:
```bash
python generate_voice_previews.py --download-existing
```text

### Step 7: Deploy

```bash
chmod +x deploy_ae.sh
./deploy_ae.sh
```text

The script automatically:
1. Uploads voice preview assets from `assets/voice_previews/` to GCS bucket
2. Installs ADK v1.30.0 (required — v2.2.0 deploy is broken)
3. Bundles `adk_common/` into agent source
4. Deploys to Agent Engine with `--region=us-central1`
5. Passes `.env` vars for runtime
6. Cleans up bundled files after deploy

### Step 8: Connect to Gemini Enterprise

1. Go to **Vertex AI > Agent Engine** in Cloud Console
2. Find `ge_video` in the list
3. Test in the playground, or connect to **Gemini Enterprise**

---

## App Flow (GE Chat)

### 1. Greeting

User says **"hi"** and the agent responds:

```text
Welcome! I'm the Video Ads Agent. I create professional multi-scene video ads from your images.

To get started, tell me:
Company name, number of scenes, video model (omni/veo), voice gender (male/female)

Example: Hyatt, 4, veo, male
```text

### 2. Setup (one-line input)

User types: **`Hyatt, 4, veo, male`**

The agent parses: company=Hyatt, scenes=4, model=veo, gender=male.

### 3. Voice Selection

Agent calls `preview_all_voices("male")` which loads pre-deployed MP4 voice previews from GCS and displays each as an inline video with the voice name. No TTS generation at chat time.

Each voice appears as a short video card (voice name + audio) that the user can play inline:

```text
1. Achird     [▶ video preview]
2. Algenib    [▶ video preview]
3. Algieba    [▶ video preview]
4. Alnilam    [▶ video preview]
5. Charon     [▶ video preview]  ← recommended
...
```text

User plays each to listen, then types: **`5`** → Charon selected.

Agent calls `setup_video_ad` with all collected info.

### 4. Scene Images

Agent asks for images. User can provide them 3 ways:

**Option A — Bucket folder (easiest):**
```text
User: images are in gs://BUCKET_NAME
Agent: [calls load_images_from_bucket → finds scene images, skips logos → displays numbered inline]

  1. 1.webp    [image preview]
  2. 2.webp    [image preview]
  3. 3.webp    [image preview]
  4. 4.webp    [image preview]

Agent: "All 4 images look good? Type 'all' to use them, or type numbers to remove (e.g. remove 3, 5)."
User: all
Agent: [calls confirm_images → assigns images to scenes]
```text

**Option B — Individual GCS URIs:**
```text
User: gs://my-bucket/lobby.png, gs://my-bucket/pool.png, ...
Agent: [calls store_scene_image for each → displays inline]
```text

**Option C — Direct upload:**
User uploads images in chat → agent saves to GCS → displays inline.

### 4b. Logo Selection

```text
Agent: [calls show_default_logo → displays default Google logo inline]
Agent: "Here's the default logo. I can use this for your video,
        or you can provide your own logo by uploading or via GCS path.
        Which do you prefer — default or provide your own?"
User: default
Agent: [calls store_logo with use_default=true]
```text

### 5. Voiceover Scripts

Agent says:

```text
If you'd prefer to provide your own scripts, type them as:
1- Your script for scene 1, 2- Your script for scene 2, ...

Otherwise, just say "ai" and I'll generate them using AI with Google Search.
```text

**User types `ai`** → agent calls `generate_ai_scripts`:
```text
Scene 1: "Step into a sanctuary where every detail welcomes you."
Scene 2: "Discover vibrant spaces designed to awaken wonder."
Scene 3: "Savor unforgettable moments crafted with Hyatt care."
Scene 4: "Rest peacefully, knowing tomorrow holds endless possibilities."

Tagline: "Be more here."
```text

User can edit any script: `Scene 3: "Indulge in moments of pure Hyatt elegance."`

### 6. Generate Video Clips

User says **"yes"** or **"generate clips"** → agent calls `generate_all_clips`.

- **Omni**: ~30 sec per clip (fast). Runs synchronously and displays clips inline immediately.
- **Veo**: ~5 min per clip (high-quality cinematic). Runs asynchronously in the background. The agent will ask the user to wait and check back. When the user asks for the status, the agent calls `check_veo_status` to poll Vertex AI, load completed clips to GCS, and display them inline.

Each completed clip displays inline for review. User can say **"regenerate scene 3"** to redo any clip.

### 7. Assemble Final Video

User approves clips → agent calls `assemble_final_video`.

Pipeline:
1. TTS voiceovers (parallel, Chirp3-HD)
2. Trim clips to voiceover duration + padding
3. Mix voiceover onto each clip
4. Generate intro title card (company name + logo) + outro (company name + tagline)
5. Concatenate with dissolve transitions
6. Add Lyria background music at 35% volume
7. Logo overlay on final video (top-right corner)

Final video displays inline in GE chat.

---

## Agent Tools

| Tool | Description |
|------|-------------|
| `list_voices` | List available Chirp3-HD voices by gender |
| `preview_voice` | Preview a single voice as inline video (pre-deployed MP4) |
| `preview_all_voices` | Preview ALL voices for a gender as inline videos (no TTS at chat time) |
| `setup_video_ad` | Initialize project (company, scenes, voice, model) |
| `show_default_logo` | Display default Google logo inline |
| `store_logo` | Store logo (default or user-provided GCS path) |
| `load_images_from_bucket` | List and preview images from GCS bucket (numbered, skips logos) |
| `confirm_images` | Confirm which previewed images to use for scenes |
| `save_uploaded_image` | Save a directly uploaded image to GCS |
| `store_scene_image` | Store a scene image from GCS URI |
| `store_scene_script` | Store/edit a voiceover script for a scene |
| `generate_ai_scripts` | Auto-generate scripts with Gemini + Google Search |
| `generate_scene_clip` | Generate video clip for one scene |
| `generate_all_clips` | Generate all clips in parallel (max 4 concurrent) |
| `check_veo_status` | Check background Veo generation status and render finished clips |
| `regenerate_scene_clip` | Re-generate a specific scene clip |
| `assemble_final_video` | Full assembly: TTS + trim + mix + titles + dissolve + music + logo |

## Video Models

| Model | Speed | Quality | Best For |
|-------|-------|---------|----------|
| Omni (`gemini-omni-flash-preview`) | ~30 seconds | Good | Quick previews, drafts |
| Veo (`veo-3.1-generate-001`) | ~5 minutes | Cinematic | Final production |

## Environment Variables

| Variable | Value | Purpose |
|----------|-------|---------|
| `GOOGLE_CLOUD_PROJECT` | your-project-id | GCP project |
| `GOOGLE_CLOUD_LOCATION` | `global` | Model endpoint (gemini-3.1-pro-preview) |
| `GOOGLE_CLOUD_BUCKET_ARTIFACTS` | your-bucket-name | GCS bucket for images/clips/videos |
| `AGENT_VERSION` | `1.0.0` | Required by adk_common |

## Troubleshooting

| Error | Fix |
|-------|-----|
| 404 gemini-3.1-pro-preview | Ensure `GOOGLE_CLOUD_LOCATION=global` in .env |
| 403 storage.objects.create | Grant Agent Engine SA `storage.objectAdmin` on bucket (Step 3) |
| Missing PIL module | Pillow should auto-install; code has fallback if missing |
| `AGENT_VERSION is not set` | Add `AGENT_VERSION=1.0.0` to .env |
| `adk_common not found` | Ensure `adk_common/` folder is next to `ge_video/` |
| Agent Engine deploy to global fails | Deploy always goes to us-central1 (hardcoded in deploy_ae.sh) |
| ADK v2.2.0 deploy broken | Script auto-installs v1.30.0 |
| No response after bucket URL | Redeploy — `load_images_from_bucket` tool handles this now |
| `audio/mpeg: Unsupported attachment` | Voice previews are served as MP4 video artifacts (not audio). Redeploy with latest code |
| No voice previews found | Run `python generate_voice_previews.py` then redeploy — MP4 assets must exist in GCS |
| TTS not installed on Agent Engine | Ensure `--requirements_file=requirements.txt` in deploy command |
