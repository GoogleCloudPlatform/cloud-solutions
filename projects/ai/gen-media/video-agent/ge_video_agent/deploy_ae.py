# Copyright 2026 Google LLC
# Author: Layolin Jesudhass
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Deploy Video Ads Agent to Vertex AI Agent Engine.

Usage:
    cd ge_video
    python deploy_ae.py
"""

import os
import subprocess
import sys

# from dotenv import load_dotenv

# load_dotenv()

# ── Config ──────────────────────────────────────────────────

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
if not PROJECT_ID:
    PROJECT_ID = subprocess.check_output(
        ["gcloud", "config", "get-value", "project"], text=True
    ).strip()

LOCATION = "us-central1"
BUCKET = os.environ.get(
    "GOOGLE_CLOUD_BUCKET_ARTIFACTS",
    f"{PROJECT_ID}-video-ads-artifacts",
)
AGENT_VERSION = os.environ.get("AGENT_VERSION", "1.0.0")

print("============================================")
print("Video Ads Agent — Agent Engine Deployment")
print(f"  Project:  {PROJECT_ID}")
print(f"  Location: {LOCATION}")
print(f"  Bucket:   {BUCKET}")
print(f"  Version:  {AGENT_VERSION}")
print("============================================")

# ── Write requirements.txt INSIDE the agent directory ───────
# The adk CLI looks for requirements.txt in the agent folder by default.

REQUIREMENTS = """\
google-adk>=1.20.0
google-genai>=1.0.0
google-cloud-aiplatform[adk,agent-engines]>=1.70.0
google-cloud-texttospeech>=2.0.0
google-cloud-storage>=2.0.0
pydantic>=2.0.0
Pillow>=10.0.0
python-dotenv>=1.0.0
requests
tenacity
imageio-ffmpeg
"""

req_path = os.path.join("ge_video", "requirements.txt")
with open(req_path, "w") as f:
    f.write(REQUIREMENTS)
print(f"Wrote {req_path}")

# ── Write .env INSIDE the agent directory ───────────────────
# The adk CLI reads .env from the agent folder for env vars.

env_path = os.path.join("ge_video", ".env")
with open(env_path, "w") as f:
    f.write(f"GOOGLE_CLOUD_PROJECT={PROJECT_ID}\n")
    f.write(f"GOOGLE_CLOUD_LOCATION=global\n")
    f.write(f"GOOGLE_CLOUD_BUCKET_ARTIFACTS={BUCKET}\n")
    f.write(f"AGENT_VERSION={AGENT_VERSION}\n")
    f.write(f"GOOGLE_GENAI_USE_VERTEXAI=TRUE\n")
    f.write(f"VIDEO_GENERATION_MODEL=veo-3.1-generate-001\n")
print(f"Wrote {env_path}")

# ── Upload voice preview assets to GCS ──────────────────────

PREVIEWS_DIR = "assets/voice_previews"
GCS_PREVIEWS = f"gs://{BUCKET}/video_ads/previews"

for gender in ("male", "female"):
    local_dir = os.path.join(PREVIEWS_DIR, gender)
    if os.path.isdir(local_dir):
        dest = f"{GCS_PREVIEWS}/{gender}/"
        print(f"Uploading {gender} voice previews to {dest}...")
        subprocess.run(
            ["gcloud", "storage", "cp", f"{local_dir}/*.mp4", dest],
            check=False, capture_output=True,
        )
        print(f"  {gender}: done")

# ── Deploy via ADK CLI ──────────────────────────────────────

print("\nDeploying to Agent Engine...")

cmd = [
    "adk",
    "deploy", "agent_engine",
    "--project", PROJECT_ID,
    "--region", LOCATION,
    "--display_name", "Video Ads Agent",
    "ge_video",
]

print(f"Running: {' '.join(cmd)}")
result = subprocess.run(cmd)

if result.returncode == 0:
    print("\n=== DEPLOYED ===")
    print("Updating Cloud Run HTTP timeout to 3600s (1 hour)...")
    subprocess.run(
        ["gcloud", "run", "services", "update", "video-ads-studio",
         "--timeout=3600", "--region", LOCATION, "--project", PROJECT_ID],
        check=False,
    )
    print("Done! Go to Vertex AI > Agent Engine in Cloud Console.")
else:
    print(f"\nDeployment failed with exit code {result.returncode}")
    sys.exit(result.returncode)
