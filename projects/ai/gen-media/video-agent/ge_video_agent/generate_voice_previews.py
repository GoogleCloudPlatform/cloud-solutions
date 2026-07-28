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

#!/usr/bin/env python3
"""Generate voice preview MP4s for all Chirp3-HD voices and upload to GCS.

Downloads existing MP3s from GCS (male voices), generates TTS for any missing
voices (female), wraps each MP3 + styled card into a short MP4 video, saves
locally and uploads to GCS so the GE agent can serve them as inline artifacts.

Requires:
  pip install google-cloud-texttospeech google-cloud-storage Pillow
  ffmpeg installed and on PATH

Usage:
  cd ge_video
  python generate_voice_previews.py
"""
import asyncio
import io
import os
import platform
import subprocess
import tempfile

from google.cloud import storage as gcs_storage

CHIRP3_HD_VOICES = {
    "female": [
        "Achernar", "Aoede", "Autonoe", "Callirrhoe", "Despina",
        "Erinome", "Gacrux", "Kore", "Laomedeia", "Leda",
        "Pulcherrima", "Sulafat", "Vindemiatrix", "Zephyr",
    ],
    "male": [
        "Achird", "Algenib", "Algieba", "Alnilam", "Charon",
        "Enceladus", "Fenrir", "Iapetus", "Orus", "Puck",
        "Rasalgethi", "Sadachbia", "Sadaltager", "Schedar",
        "Umbriel", "Zubenelgenubi",
    ],
}

PREVIEW_TEXT = "Welcome to our brand story. Experience the difference today."
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "voice_previews")


def _find_font() -> str:
    if platform.system() == "Darwin":
        return "/System/Library/Fonts/Helvetica.ttc"
    for p in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ]:
        if os.path.exists(p):
            return p
    return ""


def _create_voice_card(voice_name: str, number: int, gender: str) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    w, h = 480, 270
    img = Image.new("RGB", (w, h), color=(30, 30, 40))
    draw = ImageDraw.Draw(img)

    font_path = _find_font()
    try:
        title_font = ImageFont.truetype(font_path, 36) if font_path else ImageFont.load_default()
        sub_font = ImageFont.truetype(font_path, 20) if font_path else ImageFont.load_default()
    except (OSError, IOError):
        title_font = ImageFont.load_default()
        sub_font = ImageFont.load_default()

    accent = (100, 180, 255) if gender == "male" else (255, 130, 180)
    draw.rectangle([(0, 0), (w, 5)], fill=accent)
    draw.rectangle([(0, h - 5), (w, h)], fill=accent)

    title = f"{number}. {voice_name}"
    bbox = draw.textbbox((0, 0), title, font=title_font)
    tw = bbox[2] - bbox[0]
    draw.text(((w - tw) // 2, 80), title, fill="white", font=title_font)

    label = f"{gender.capitalize()} Voice"
    bbox2 = draw.textbbox((0, 0), label, font=sub_font)
    lw = bbox2[2] - bbox2[0]
    draw.text(((w - lw) // 2, 140), label, fill=(180, 180, 180), font=sub_font)

    play_hint = "Press play to listen"
    bbox3 = draw.textbbox((0, 0), play_hint, font=sub_font)
    pw = bbox3[2] - bbox3[0]
    draw.text(((w - pw) // 2, 190), play_hint, fill=accent, font=sub_font)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _wrap_mp3_as_mp4(mp3_bytes: bytes, card_png: bytes) -> bytes | None:
    with tempfile.TemporaryDirectory() as tmpdir:
        card_path = os.path.join(tmpdir, "card.png")
        mp3_path = os.path.join(tmpdir, "audio.mp3")
        out_path = os.path.join(tmpdir, "preview.mp4")

        with open(card_path, "wb") as f:
            f.write(card_png)
        with open(mp3_path, "wb") as f:
            f.write(mp3_bytes)

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", card_path,
            "-i", mp3_path,
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "44100", "-ac", "2",
            "-shortest",
            "-movflags", "+faststart",
            out_path,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode != 0:
            print(f"  FFmpeg error: {result.stderr.decode()[-200:]}")
            return None

        with open(out_path, "rb") as f:
            return f.read()


async def _generate_tts(voice_name: str) -> bytes | None:
    from google.cloud import texttospeech_v1 as tts

    client = tts.TextToSpeechAsyncClient()
    response = await client.synthesize_speech(
        input=tts.SynthesisInput(text=PREVIEW_TEXT),
        voice=tts.VoiceSelectionParams(
            language_code="en-US",
            name=f"en-US-Chirp3-HD-{voice_name}",
        ),
        audio_config=tts.AudioConfig(
            audio_encoding=tts.AudioEncoding.MP3,
            sample_rate_hertz=24000,
        ),
    )
    return response.audio_content


def _get_config():
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    if not project_id:
        import subprocess as sp
        project_id = sp.check_output(
            ["gcloud", "config", "get-value", "project"], text=True
        ).strip()
    bucket_name = os.environ.get(
        "GOOGLE_CLOUD_BUCKET_ARTIFACTS",
        f"{project_id}-video-ads-artifacts",
    )
    return project_id, bucket_name


def _download_existing_mp3s(bucket_name: str, project_id: str) -> dict[str, bytes]:
    """Download existing MP3 previews from GCS. Returns {voice_name: mp3_bytes}."""
    print(f"\nDownloading existing MP3s from gs://{bucket_name}/video_ads/previews/...")
    client = gcs_storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)
    mp3s = {}

    for blob in bucket.list_blobs(prefix="video_ads/previews/"):
        if not blob.name.endswith(".mp3"):
            continue
        filename = os.path.basename(blob.name)
        # Parse "5_Charon.mp3" → "Charon"
        parts = filename.rsplit(".", 1)[0].split("_", 1)
        if len(parts) == 2:
            voice_name = parts[1]
        else:
            voice_name = parts[0]
        data = blob.download_as_bytes()
        mp3s[voice_name] = data
        print(f"  {filename} ({len(data) // 1024} KB)")

    print(f"  Found {len(mp3s)} existing MP3s")
    return mp3s


def _upload_mp4_to_gcs(bucket_name: str, project_id: str, gender: str, filename: str, data: bytes):
    client = gcs_storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)
    blob_path = f"video_ads/previews/{gender}/{filename}"
    blob = bucket.blob(blob_path)
    blob.upload_from_string(data, content_type="video/mp4")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate voice preview MP4s")
    parser.add_argument("--upload", action="store_true",
                        help="Also upload MP4s to GCS after generating locally")
    parser.add_argument("--download-mp3s", action="store_true",
                        help="Download existing MP3s from GCS before generating (saves TTS calls)")
    args = parser.parse_args()

    project_id, bucket_name = _get_config()
    print(f"Project:  {project_id}")
    print(f"Bucket:   {bucket_name}")

    os.makedirs(os.path.join(ASSETS_DIR, "male"), exist_ok=True)
    os.makedirs(os.path.join(ASSETS_DIR, "female"), exist_ok=True)

    # Optionally download existing MP3s from GCS
    existing_mp3s = {}
    if args.download_mp3s:
        try:
            existing_mp3s = _download_existing_mp3s(bucket_name, project_id)
        except Exception as e:
            print(f"  GCS download failed ({e}), will generate all via TTS")

    total_created = 0

    for gender in ("male", "female"):
        voices = CHIRP3_HD_VOICES[gender]
        print(f"\n{'='*50}")
        print(f"Processing {gender} voices ({len(voices)} total)")
        print(f"{'='*50}")

        for number, voice_name in enumerate(voices, 1):
            mp4_filename = f"{number}_{voice_name}.mp4"
            mp4_local = os.path.join(ASSETS_DIR, gender, mp4_filename)

            # Skip if MP4 already exists locally
            if os.path.exists(mp4_local) and os.path.getsize(mp4_local) > 5000:
                print(f"  [{number}/{len(voices)}] {voice_name} — MP4 exists, skipping")
                total_created += 1
                continue

            # Get MP3: from GCS download or generate TTS
            mp3_bytes = existing_mp3s.get(voice_name)
            if mp3_bytes:
                print(f"  [{number}/{len(voices)}] {voice_name} — using existing MP3...", end="", flush=True)
            else:
                print(f"  [{number}/{len(voices)}] {voice_name} — generating TTS...", end="", flush=True)
                try:
                    mp3_bytes = await _generate_tts(voice_name)
                    if not mp3_bytes:
                        print(" FAILED (no audio)")
                        continue
                    print(f" MP3 OK ({len(mp3_bytes)//1024} KB)...", end="", flush=True)
                except Exception as e:
                    print(f" TTS ERROR: {e}")
                    continue

            # Create MP4
            card_png = _create_voice_card(voice_name, number, gender)
            mp4_bytes = _wrap_mp3_as_mp4(mp3_bytes, card_png)
            if not mp4_bytes:
                print(" MP4 wrap FAILED")
                continue

            # Save locally
            with open(mp4_local, "wb") as f:
                f.write(mp4_bytes)
            print(f" MP4 OK ({len(mp4_bytes)//1024} KB)", end="")

            # Optionally upload to GCS
            if args.upload:
                try:
                    _upload_mp4_to_gcs(bucket_name, project_id, gender, mp4_filename, mp4_bytes)
                    print(" — uploaded to GCS", end="")
                except Exception as e:
                    print(f" — GCS upload failed: {e}", end="")

            print()
            total_created += 1

    # Summary
    male_count = len([f for f in os.listdir(os.path.join(ASSETS_DIR, "male")) if f.endswith(".mp4")])
    female_count = len([f for f in os.listdir(os.path.join(ASSETS_DIR, "female")) if f.endswith(".mp4")])

    print(f"\n{'='*50}")
    print(f"Done! {male_count} male + {female_count} female = {male_count + female_count} MP4 previews")
    print(f"Local:  {ASSETS_DIR}")
    if args.upload:
        print(f"GCS:    gs://{bucket_name}/video_ads/previews/male/")
        print(f"        gs://{bucket_name}/video_ads/previews/female/")
    else:
        print("Run deploy_ae.sh to upload assets to your GCS bucket.")
    print(f"{'='*50}")


if __name__ == "__main__":
    asyncio.run(main())
