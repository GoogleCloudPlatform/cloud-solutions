# Copyright 2026 Google LLC
# Author: Generic Author
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

"""Generate preview MP4 cards for all 31 Chirp3-HD voices using Cloud TTS."""

import argparse
import asyncio
import io
import os
import subprocess
import tempfile

from google.cloud import storage as gcs_storage
from google.cloud import texttospeech as tts
from PIL import Image, ImageDraw, ImageFont

PREVIEW_TEXT = (
    "Experience luxury redefined. Every detail crafted for your comfort."
)
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets", "voice_previews")
CHIRP3_HD_VOICES = {
    "male": [
        "Fenrir",
        "Puck",
        "Charon",
        "Kore",
        "Zephyr",
        "Orus",
        "Aoede",
        "Enceladus",
        "Iapetus",
        "Oberon",
        "Rhea",
        "Titan",
        "Proteus",
        "Triton",
        "Hyperion",
        "Dione",
    ],
    "female": [
        "Leda",
        "Callisto",
        "Europa",
        "Ganymede",
        "Io",
        "Metis",
        "Thebe",
        "Adrastea",
        "Amalthea",
        "Himalia",
        "Elara",
        "Pasiphae",
        "Sinope",
        "Lysithea",
        "Carme",
    ],
}


def _find_font() -> str | None:
    for p in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]:
        if os.path.exists(p):
            return p
    return None


def _create_voice_card(voice_name: str, gender: str, number: int) -> bytes:
    w, h = 480, 270
    img = Image.new("RGB", (w, h), color=(30, 30, 40))
    draw = ImageDraw.Draw(img)

    font_path = _find_font()
    try:
        if font_path:
            f_title = ImageFont.truetype(font_path, 28)
            f_sub = ImageFont.truetype(font_path, 16)
            f_num = ImageFont.truetype(font_path, 14)
            f_sample = ImageFont.truetype(font_path, 13)
        else:
            f_title = f_sub = f_num = f_sample = ImageFont.load_default()
    except (ValueError, TypeError, OSError):
        f_title = f_sub = f_num = f_sample = ImageFont.load_default()

    badge_color = (66, 133, 244) if gender.lower() == "male" else (234, 67, 53)
    draw.rounded_rectangle([(30, 24), (110, 48)], radius=6, fill=badge_color)
    draw.text((42, 28), gender.upper(), fill=(255, 255, 255), font=f_num)

    draw.text((120, 28), f"#{number} of 31", fill=(160, 160, 180), font=f_num)

    draw.text((30, 60), voice_name, fill=(255, 255, 255), font=f_title)
    draw.text(
        (30, 98),
        "Chirp3-HD • English (US)",
        fill=(140, 140, 160),
        font=f_sub,
    )

    draw.line([(30, 130), (450, 130)], fill=(60, 60, 80), width=1)

    draw.text(
        (30, 145),
        "SAMPLE AUDIO",
        fill=(100, 100, 120),
        font=f_num,
    )
    draw.text(
        (30, 168),
        f'"{PREVIEW_TEXT}"',
        fill=(200, 200, 220),
        font=f_sample,
    )

    draw.text(
        (30, 235),
        "Google Cloud Text-to-Speech",
        fill=(100, 100, 120),
        font=f_num,
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_video_card(card_png: bytes, audio_mp3: bytes) -> bytes | None:
    with tempfile.TemporaryDirectory() as td:
        img_path = os.path.join(td, "card.png")
        aud_path = os.path.join(td, "audio.mp3")
        out_path = os.path.join(td, "preview.mp4")

        with open(img_path, "wb") as f:
            f.write(card_png)
        with open(aud_path, "wb") as f:
            f.write(audio_mp3)

        cmd = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            img_path,
            "-i",
            aud_path,
            "-c:v",
            "libx264",
            "-tune",
            "stillimage",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-pix_fmt",
            "yuv420p",
            "-shortest",
            "-movflags",
            "+faststart",
            out_path,
        ]
        result = subprocess.run(
            cmd, capture_output=True, timeout=30, check=False
        )
        if result.returncode != 0:
            print(f"  FFmpeg error: {result.stderr.decode()[-200:]}")
            return None

        with open(out_path, "rb") as f:
            return f.read()


async def _generate_tts(voice_name: str) -> bytes | None:
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
        cmd_out = subprocess.check_output(
            ["gcloud", "config", "get-value", "project"], text=True
        )
        project_id = cmd_out.strip()
    bucket_name = os.environ.get(
        "GOOGLE_CLOUD_BUCKET_ARTIFACTS",
        f"{project_id}-video-ads-artifacts",
    )
    return project_id, bucket_name


def _download_existing_mp3s(
    bucket_name: str, project_id: str
) -> dict[str, bytes]:
    """Download existing MP3 previews from GCS. Returns "
    "{voice_name: mp3_bytes}."""
    print(
        f"\nDownloading existing MP3s from "
        f"gs://{bucket_name}/video_ads/previews/..."
    )
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


def _upload_mp4_to_gcs(
    bucket_name: str, project_id: str, gender: str, filename: str, data: bytes
):
    client = gcs_storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)
    blob_path = f"video_ads/previews/{gender}/{filename}"
    blob = bucket.blob(blob_path)
    blob.upload_from_string(data, content_type="video/mp4")


async def main():
    parser = argparse.ArgumentParser(description="Generate voice preview MP4s")
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Also upload MP4s to GCS after generating locally",
    )
    parser.add_argument(
        "--download-mp3s",
        action="store_true",
        help=(
            "Download existing MP3s from GCS before generating "
            "(saves TTS calls)"
        ),
    )
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
        except (ValueError, RuntimeError, OSError, IOError) as e:
            print(f"  GCS download failed ({e}), will generate all via TTS")

    total_created = 0

    for gender in ("male", "female"):
        voices = CHIRP3_HD_VOICES[gender]
        print("\n" + "=" * 50)
        print(f"Processing {gender} voices ({len(voices)} total)")
        print("=" * 50)

        for number, voice_name in enumerate(voices, 1):
            mp4_filename = f"{number}_{voice_name}.mp4"
            mp4_local = os.path.join(ASSETS_DIR, gender, mp4_filename)

            # Skip if MP4 already exists locally
            if os.path.exists(mp4_local) and os.path.getsize(mp4_local) > 5000:
                print(
                    f"  [{number}/{len(voices)}] {voice_name} — MP4 exists, "
                    f"skipping"
                )
                total_created += 1
                continue

            # Get MP3: from GCS download or generate TTS
            mp3_bytes = existing_mp3s.get(voice_name)
            if mp3_bytes:
                print(
                    (
                        f"  [{number}/{len(voices)}] {voice_name} — "
                        "using existing MP3..."
                    ),
                    end="",
                    flush=True,
                )
            else:
                print(
                    (
                        f"  [{number}/{len(voices)}] {voice_name} — "
                        "generating TTS..."
                    ),
                    end="",
                    flush=True,
                )
                try:
                    mp3_bytes = await _generate_tts(voice_name)
                    if not mp3_bytes:
                        print(" FAILED (no audio)")
                        continue
                    print(
                        f" MP3 OK ({len(mp3_bytes)//1024} KB)...",
                        end="",
                        flush=True,
                    )
                except (ValueError, RuntimeError, OSError, IOError) as e:
                    print(f" TTS ERROR: {e}")
                    continue

            # Create MP4
            card_png = _create_voice_card(
                voice_name=voice_name, gender=gender, number=number
            )
            mp4_bytes = _make_video_card(card_png, mp3_bytes)
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
                    _upload_mp4_to_gcs(
                        bucket_name, project_id, gender, mp4_filename, mp4_bytes
                    )
                    print(" — uploaded to GCS", end="")
                except (ValueError, RuntimeError, OSError, IOError) as e:
                    print(f" — GCS upload failed: {e}", end="")

            print()
            total_created += 1

    # Summary
    male_count = len(
        [
            f
            for f in os.listdir(os.path.join(ASSETS_DIR, "male"))
            if f.endswith(".mp4")
        ]
    )
    female_count = len(
        [
            f
            for f in os.listdir(os.path.join(ASSETS_DIR, "female"))
            if f.endswith(".mp4")
        ]
    )

    print("\n" + "=" * 50)
    print(
        f"Done! {male_count} male + {female_count} female = "
        f"{male_count + female_count} MP4 previews"
    )
    print(f"Local:  {ASSETS_DIR}")
    if args.upload:
        print(f"GCS:    gs://{bucket_name}/video_ads/previews/male/")
        print(f"        gs://{bucket_name}/video_ads/previews/female/")
    else:
        print("Run deploy_ae.sh to upload assets to your GCS bucket.")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
