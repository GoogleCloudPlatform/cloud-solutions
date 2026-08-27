# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Script 2: Agent Engine + GE Integration — Spreadsheet-driven video ad
pipeline.

Usage:
    # Generate a blank template CSV:
    python ge_video_ads.py --template --scenes 4 --output template.csv

    # Generate video ad from completed spreadsheet:
    python ge_video_ads.py --spreadsheet scenes.csv --company "Acme"
        " Corp" --output output/

    # With options:
    python ge_video_ads.py --spreadsheet scenes.csv --company "Acme Corp" \\
        --voice female --music off --brand-context "Premium lifestyle brand" \\
        --output output/

CSV format:
    Scene Number, Voiceover Script, Image Path
    Scene 1, Our fully renovated hotel lets you make the most of your stay,
    /path/to/image1.png
    Scene 2, Experience luxury in every detail, /path/to/image2.png
    ...

Image paths can be local files or GCS URIs (gs://bucket/path/image.png).
"""

import argparse
import asyncio
import csv
import os
import sys
import time

from dotenv import load_dotenv

try:
    from google.cloud import storage
except ImportError:
    storage = None

from video_ads_agent.agent import (
    GEMINI_TTS_VOICES,
    MAX_WORDS_OMNI,
    VOICE_EMOTIONS,
    add_background_music_to_final,
    build_omni_prompt,
    build_veo_prompt,
    concatenate_scenes_with_dissolve,
    create_outro_clip,
    generate_all_voiceovers,
    generate_background_music,
    generate_scene_video,
    generate_scene_video_veo,
    lookup_company_tagline,
    mix_scene_audio,
    overlay_logo_and_tagline_on_video,
    remove_logo_background,
    trim_clip_to_voiceover,
)

load_dotenv()


def generate_template_csv(num_scenes: int, output_path: str):
    """Generate a blank CSV template with pre-filled scene numbers."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Scene Number", "Voiceover Script", "Image Path"])
        for i in range(1, num_scenes + 1):
            writer.writerow([f"Scene {i}", "", ""])
    print(f"Template saved: {output_path} ({num_scenes} scenes)")


def load_image_bytes(path: str) -> bytes:
    """Load image from local file or GCS URI."""
    if path.startswith("gs://"):
        parts = path.replace("gs://", "").split("/", 1)
        bucket_name, blob_name = parts[0], parts[1]
        client = storage.Client()
        blob = client.bucket(bucket_name).blob(blob_name)
        return blob.download_as_bytes()
    else:
        with open(path, "rb") as f:
            return f.read()


def parse_spreadsheet(csv_path: str) -> list[dict]:
    """Parse the scene spreadsheet and load image bytes."""
    scenes = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            scene_num_raw = row.get("Scene Number", "").strip()
            voiceover = row.get("Voiceover Script", "").strip()
            image_path = row.get("Image Path", "").strip()

            if not scene_num_raw or not voiceover or not image_path:
                continue

            scene_number = int(
                "".join(filter(str.isdigit, scene_num_raw)) or "0"
            )
            if scene_number == 0:
                continue

            word_count = len(voiceover.split())
            max_w = MAX_WORDS_OMNI
            if word_count > max_w:
                print(
                    f"  WARNING: Scene {scene_number} voiceover"
                    f" has {word_count} words "
                    f"(max {max_w}). It may be too long for the clip duration."
                )

            try:
                image_bytes = load_image_bytes(image_path)
            except (
                ValueError,
                TypeError,
                KeyError,
                AttributeError,
                OSError,
                RuntimeError,
            ) as e:
                print(
                    f"  ERROR: Failed to load image"
                    f" for Scene {scene_number}: {e}"
                )
                continue

            scenes.append(
                {
                    "scene_number": scene_number,
                    "voiceover_text": voiceover,
                    "image_bytes": image_bytes,
                    "image_path": image_path,
                }
            )

    scenes.sort(key=lambda s: s["scene_number"])
    return scenes


async def run_pipeline(
    scenes: list[dict],
    company_name: str,
    brand_context: str,
    voice_name: str,
    voice_emotion: str = "Energetic",
    enable_music: bool = True,
    output_dir: str = "output",
    logo_path: str = "",
    video_model: str = "omni",
    prompt_template: str = "",
):
    """Run the full video ad generation pipeline."""
    os.makedirs(output_dir, exist_ok=True)
    start_time = time.time()

    gen_fn = (
        generate_scene_video
        if video_model == "omni"
        else generate_scene_video_veo
    )
    model_label = "Omni" if video_model == "omni" else "Veo"

    print(f'\n{"="*60}')
    print("VIDEO ADS PIPELINE")
    print(f"  Model: {model_label}")
    print(f"  Scenes: {len(scenes)}")
    print(f"  Company: {company_name}")
    print(f"  Voice: {voice_name} (Gemini TTS, {voice_emotion})")
    print(f'  Music: {"ON" if enable_music else "OFF"}')
    print(f'{"="*60}\n')

    # ── Step 1: Generate all scene clips (batched, max 4 concurrent) ──
    MAX_CONCURRENT = 4
    print(
        f"Step 1/5: Generating video clips with {model_label}"
        f" ({MAX_CONCURRENT} concurrent, visual only)..."
    )
    sem = asyncio.Semaphore(MAX_CONCURRENT)

    async def _gen_clip(s):
        scene_prompt = ""
        if prompt_template:
            scene_prompt = (
                prompt_template.replace(
                    "{scene_number}", str(s["scene_number"])
                )
                .replace("{voiceover_text}", s["voiceover_text"])
                .replace("{company_name}", company_name)
            )
        async with sem:
            return await gen_fn(
                image_bytes=s["image_bytes"],
                voiceover_text=s["voiceover_text"],
                scene_number=s["scene_number"],
                company_name=company_name,
                brand_context=brand_context,
                prompt_override=scene_prompt,
            )

    clips = await asyncio.gather(
        *[_gen_clip(s) for s in scenes], return_exceptions=True
    )

    clip_results = {}
    for scene, clip in zip(scenes, clips):
        sn = scene["scene_number"]
        if isinstance(clip, Exception):
            print(f"  Scene {sn}: FAILED ({clip})")
            clip_results[sn] = None
        elif clip is None:
            print(f"  Scene {sn}: FAILED (no video returned)")
            clip_results[sn] = None
        else:
            size_kb = len(clip) / 1024
            print(f"  Scene {sn}: OK ({size_kb:.0f} KB)")
            clip_results[sn] = clip
            clip_path = os.path.join(output_dir, f"scene_{sn}_clip.mp4")
            with open(clip_path, "wb") as f:
                f.write(clip)

    valid_scenes = [
        s for s in scenes if clip_results.get(s["scene_number"]) is not None
    ]
    if not valid_scenes:
        print("\nERROR: All clip generations failed. Cannot proceed.")
        return

    scripts = [s["voiceover_text"] for s in valid_scenes]

    # ── Step 2: Tagline lookup + voiceovers (parallel) ──
    print(
        f"\nStep 2/7: Looking up tagline & generating voiceovers"
        f" ({voice_name}, {voice_emotion})..."
    )

    async def _noop_tagline():
        return ""

    tagline, voiceovers = await asyncio.gather(
        (
            lookup_company_tagline(company_name)
            if company_name
            else _noop_tagline()
        ),
        generate_all_voiceovers(scripts, voice_name, voice_emotion),
    )
    if tagline:
        print(f"  Tagline: {tagline}")
    for s, vo in zip(valid_scenes, voiceovers):
        status = f"OK ({len(vo)} bytes)" if vo else "FAILED"
        print(f'  Scene {s["scene_number"]}: {status}')

    # ── Step 3: Trim clips to voiceover duration + mix VO ──
    print("\nStep 3/7: Trimming clips & mixing voiceover...")
    pad_before = 0.5
    pad_after = 0.5
    assembled_clips = []
    for s, vo in zip(valid_scenes, voiceovers):
        sn = s["scene_number"]
        clip = clip_results[sn]
        if vo is not None:
            clip = trim_clip_to_voiceover(clip, vo, pad_before, pad_after)
        mixed = mix_scene_audio(clip, vo, None, vo_delay=pad_before)
        assembled_clips.append(mixed)
        mixed_path = os.path.join(output_dir, f"scene_{sn}_with_vo.mp4")
        with open(mixed_path, "wb") as f:
            f.write(mixed)
        print(f"  Scene {sn}: OK ({len(mixed) // 1024} KB)")

    # ── Step 4: Logo setup ──
    print("\nStep 4/7: Setting up logo...")
    logo_clean = None
    if logo_path:
        try:
            logo_raw = load_image_bytes(logo_path)
            logo_clean = remove_logo_background(logo_raw)
            print("  Logo: OK")
        except (
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OSError,
            RuntimeError,
        ) as e:
            print(f"  Logo load failed: {e}")

    # ── Step 5: Generate background music ──
    music_bytes = None
    if enable_music:
        print("\nStep 5/7: Generating background music with Lyria...")
        music_bytes = await generate_background_music(
            company_name, scripts, brand_context
        )
        if music_bytes:
            print(f"  Music: OK ({len(music_bytes) // 1024} KB)")
            music_path = os.path.join(output_dir, "background_music.mp3")
            with open(music_path, "wb") as f:
                f.write(music_bytes)
        else:
            print("  Music: FAILED (continuing without music)")
    else:
        print("\nStep 5/7: Skipping music (disabled)")

    # ── Step 5.5: Generate Outro Clip ──
    print("\nStep 5.5/7: Generating cinematic outro clip...")
    if assembled_clips:
        last_clip = assembled_clips[-1]
        outro_clip = create_outro_clip(last_clip, logo_clean, tagline, None)
        if outro_clip:
            assembled_clips.append(outro_clip)
            print("  Outro: OK")
        else:
            print("  Outro: FAILED")

    # ── Step 6: Dissolve scene clips ──
    print("\nStep 6/7: Concatenating clips with dissolve transitions...")
    final_video = concatenate_scenes_with_dissolve(assembled_clips)

    if final_video is None:
        print("  ERROR: Concatenation failed.")
        return

    if music_bytes and enable_music:
        print("  Adding background music at 35%...")
        final_video = add_background_music_to_final(
            final_video, music_bytes, 0.35
        )

    # ── Step 7: Logo + tagline overlay ──
    print("\nStep 7/7: Overlaying logo & tagline...")
    if logo_clean or tagline:
        final_video = overlay_logo_and_tagline_on_video(
            final_video,
            logo_clean,
            tagline,
            opacity=0.8,
            scale=0.12,
            margin=30,
        )
        print("  Overlay: OK")
    else:
        print("  Overlay: Skipped (no logo or tagline)")

    final_path = os.path.join(output_dir, "final_video_ad.mp4")
    with open(final_path, "wb") as f:
        f.write(final_video)

    elapsed = time.time() - start_time

    # ── Summary ──
    print(f'\n{"="*60}')
    print(f"DONE in {elapsed:.0f}s")
    print(f'{"="*60}')
    print(f'\n{"Scene":<10} {"Status":<10} {"Clip":<30} {"VO":<10}')
    print(f'{"-"*60}')
    for s in scenes:
        sn = s["scene_number"]
        clip = clip_results.get(sn)
        status = "OK" if clip else "FAILED"
        clip_file = f"scene_{sn}_clip.mp4" if clip else "-"
        vo_status = "OK" if s in valid_scenes else "-"
        print(f"Scene {sn:<5} {status:<10} {clip_file:<30} {vo_status:<10}")

    print(f"\nModel: {model_label}")
    print(f"Final video: {final_path}")
    print(f"Size: {len(final_video) / (1024 * 1024):.1f} MB")
    print(f"Scenes: {len(valid_scenes)}/{len(scenes)} succeeded")
    if music_bytes:
        print("Music: background_music.mp3")


def main():
    parser = argparse.ArgumentParser(
        description="Video Ads Agent — GE Integration (spreadsheet-driven)"
    )
    parser.add_argument(
        "--template", action="store_true", help="Generate a blank CSV template"
    )
    parser.add_argument(
        "--scenes",
        type=int,
        default=3,
        help="Number of scenes for template (default: 3)",
    )
    parser.add_argument(
        "--spreadsheet", help="Path to completed CSV spreadsheet"
    )
    parser.add_argument("--company", default="", help="Company/brand name")
    parser.add_argument(
        "--brand-context", default="", help="Brand context description"
    )
    all_voices = GEMINI_TTS_VOICES["male"] + GEMINI_TTS_VOICES["female"]
    parser.add_argument(
        "--model",
        choices=["omni", "veo"],
        default="omni",
        help="Video model: omni (fast) or veo (high-quality cinematic)",
    )
    parser.add_argument(
        "--voice",
        default="Charon",
        choices=all_voices,
        help="Gemini TTS voice name for consistent"
        " voiceover (default: Charon)",
    )
    parser.add_argument(
        "--emotion",
        default="Energetic",
        choices=VOICE_EMOTIONS,
        help="Voice emotion/style (default: Energetic)",
    )
    parser.add_argument(
        "--music",
        choices=["on", "off"],
        default="on",
        help="Background music on/off",
    )
    parser.add_argument(
        "--logo",
        default="",
        help="Path to brand logo (PNG). Background auto-removed if needed.",
    )
    parser.add_argument(
        "--prompt-file",
        default="",
        help="Path to text file containing custom video prompt."
        " Use {scene_number}, {voiceover_text},"
        " {company_name} as placeholders.",
    )
    parser.add_argument(
        "--dump-prompt",
        action="store_true",
        help="Print the default video generation prompt and exit. Save"
        " to a file and edit, then pass via --prompt-file.",
    )
    parser.add_argument(
        "--output",
        default="output",
        help="Output directory or template file path",
    )

    args = parser.parse_args()

    if args.dump_prompt:
        prompt_fn = (
            build_omni_prompt if args.model == "omni" else build_veo_prompt
        )
        prompt = prompt_fn(
            scene_number=1,
            voiceover_text="{voiceover_text}",
            company_name=args.company or "{company_name}",
            brand_context=args.brand_context,
        ).replace("Scene 1:", "Scene {scene_number}:")
        print(prompt)
        print("\n# Save this to a file and pass via: --prompt-file prompt.txt")
        return

    if args.template:
        output_path = (
            args.output
            if args.output.endswith(".csv")
            else os.path.join(args.output, "template.csv")
        )
        if not args.output.endswith(".csv"):
            os.makedirs(args.output, exist_ok=True)
        generate_template_csv(args.scenes, output_path)
        return

    if not args.spreadsheet:
        parser.error("Provide --spreadsheet or --template")

    print(f"Loading spreadsheet: {args.spreadsheet}")
    scenes = parse_spreadsheet(args.spreadsheet)
    if not scenes:
        print("ERROR: No valid scenes found in spreadsheet.")
        sys.exit(1)

    print(f"Loaded {len(scenes)} scenes")

    prompt_template = ""
    if args.prompt_file:
        with open(args.prompt_file, "r", encoding="utf-8") as f:
            prompt_template = f.read().strip()
        print(f"Using custom prompt from: {args.prompt_file}")

    asyncio.run(
        run_pipeline(
            scenes=scenes,
            company_name=args.company,
            brand_context=args.brand_context,
            voice_name=args.voice,
            voice_emotion=args.emotion,
            enable_music=args.music == "on",
            output_dir=args.output,
            logo_path=args.logo,
            video_model=args.model,
            prompt_template=prompt_template,
        )
    )


if __name__ == "__main__":
    main()
