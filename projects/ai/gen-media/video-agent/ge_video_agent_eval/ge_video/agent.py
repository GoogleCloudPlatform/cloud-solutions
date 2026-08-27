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
Video Ads Agent — Multi-scene video ad generation with Omni + TTS + Lyria."""

import asyncio
import base64
import collections
import gc
import io
import json
import os
import platform
import random
import re
import shutil
import subprocess
import tempfile
import time as _time
import traceback
import urllib.request

from dotenv import load_dotenv

try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None

try:
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
except ImportError:
    Image = ImageDraw = ImageEnhance = ImageFilter = ImageFont = None

try:
    from vertexai.generative_models import Part
except ImportError:
    Part = None

from google import genai
from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext
from google.genai import types

try:
    from google.api_core.client_options import ClientOptions
    from google.cloud import storage, texttospeech
except ImportError:
    ClientOptions = storage = texttospeech = None

from ge_video_agent_eval.adk_common.dtos.generated_media import GeneratedMedia
from ge_video_agent_eval.adk_common.utils import utils_agents, utils_gcs

# Proper Architectural Pattern: Leverage pre-compiled binaries via imageio.
# Agent Engine installs this at build-time in container image.
# This prevents build-time egress errors and runtime crashes!
_FFMPEG_INITIALIZED = False
_FFMPEG_EXE = "ffmpeg"
_FFPROBE_EXE = "ffprobe"


def initialize_ffmpeg_if_needed():
    global _FFMPEG_INITIALIZED, _FFMPEG_EXE, _FFPROBE_EXE
    if _FFMPEG_INITIALIZED:
        return
    if not shutil.which("ffmpeg"):
        if imageio_ffmpeg is not None:
            _FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
        ffmpeg_dir = os.path.dirname(_FFMPEG_EXE)
        _FFPROBE_EXE = os.path.join(ffmpeg_dir, "ffprobe")
        if not os.path.exists(_FFPROBE_EXE):
            _FFPROBE_EXE = _FFMPEG_EXE
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ["PATH"]
    _FFMPEG_INITIALIZED = True


def probe_media_duration(file_path: str, default: float = 8.0) -> float:
    """Accurately probe audio or video duration using ffprobe or ffmpeg
    stderr parsing."""
    initialize_ffmpeg_if_needed()
    if not os.path.exists(file_path):
        return default

    # Method 1: ffprobe if available as a distinct binary
    if (
        _FFPROBE_EXE
        and _FFPROBE_EXE != _FFMPEG_EXE
        and os.path.exists(_FFPROBE_EXE)
    ):
        try:
            res = subprocess.run(
                [
                    _FFPROBE_EXE,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    file_path,
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                val = float(res.stdout.strip())
                if val > 0.1:
                    return val
        except (
            ValueError,
            RuntimeError,
            KeyError,
            TypeError,
            OSError,
            IOError,
        ):
            pass

    # Method 2: ffmpeg -i parsing (standard in all imageio_ffmpeg environments!)
    try:
        res = subprocess.run(
            [_FFMPEG_EXE, "-i", file_path],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        match = re.search(
            r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", res.stderr
        )
        if match:
            h, m, s = match.groups()
            val = int(h) * 3600 + int(m) * 60 + float(s)
            if val > 0.1:
                return val
    except (ValueError, RuntimeError, KeyError, TypeError, OSError, IOError):
        pass

    return default


def check_video_has_audio(vid_path: str) -> bool:
    """Check if video file contains an audio stream."""
    initialize_ffmpeg_if_needed()
    try:
        res = subprocess.run(
            [_FFMPEG_EXE, "-i", vid_path],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return "Audio:" in res.stderr
    except (ValueError, RuntimeError, KeyError, TypeError, OSError, IOError):
        return True


load_dotenv()

GOOGLE_CLOUD_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
if not GOOGLE_CLOUD_PROJECT:
    try:
        GOOGLE_CLOUD_PROJECT = subprocess.check_output(
            ["gcloud", "config", "get-value", "project"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (ValueError, RuntimeError, KeyError, TypeError, OSError, IOError):
        GOOGLE_CLOUD_PROJECT = ""
GOOGLE_CLOUD_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
OMNI_VIDEO_MODEL = "gemini-omni-flash-preview"
VEO_VIDEO_MODEL = os.environ.get(
    "VIDEO_GENERATION_MODEL", "veo-3.1-generate-001"
)
LYRIA_MODEL = "lyria-3-pro-preview"

GEMINI_TTS_VOICES = {
    "female": [
        "Aoede",
        "Achernar",
        "Autonoe",
        "Callirrhoe",
        "Despina",
        "Erinome",
        "Gacrux",
        "Kore",
        "Laomedeia",
        "Leda",
        "Pulcherrima",
        "Sulafat",
        "Vindemiatrix",
        "Zephyr",
    ],
    "male": [
        "Charon",
        "Achird",
        "Algenib",
        "Algieba",
        "Alnilam",
        "Enceladus",
        "Fenrir",
        "Iapetus",
        "Orus",
        "Puck",
        "Rasalgethi",
        "Sadachbia",
        "Sadaltager",
        "Schedar",
        "Umbriel",
        "Zubenelgenubi",
    ],
}

VOICE_EMOTIONS = [
    "Energetic",
    "Professional",
    "Warm",
    "Excited",
    "Calm",
    "Confident",
    "Inspiring",
    "Dramatic",
]
VOICE_PREVIEW_TEXT = (
    "Welcome to our brand story. Experience the difference today."
)

MAX_WORDS_OMNI = 12
MAX_WORDS_VEO = 12
CLIP_DURATION = 8.0


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

    # Download Roboto to /tmp if no local fonts exist (for Cloud environments)
    fallback_path = "/tmp/Roboto-Regular.ttf"
    if not os.path.exists(fallback_path):
        try:
            url = (
                "https://github.com/googlefonts/roboto/raw/main/src/hinted/"
                "Roboto-Regular.ttf"
            )
            urllib.request.urlretrieve(url, fallback_path)
            return fallback_path
        except (
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OSError,
            RuntimeError,
        ) as e:
            print(f"[Font] Failed to download font: {e}")

    return fallback_path if os.path.exists(fallback_path) else ""


FONT_PATH = _find_font()


# ============================================================
# Voiceover Script + Tagline Generation (Gemini + Google Search)
# ============================================================


async def generate_all_voiceover_scripts(
    scene_images: dict[int, bytes],
    company_name: str,
    brand_context: str = "",
    max_words: int = MAX_WORDS_OMNI,
) -> tuple[dict[int, str], str, list[int]]:
    """Generate voiceovers, tagline, and scene order in one Gemini call.

    Uses Google Search grounding to research company, then generates
    diverse scripts for each scene image, finds/creates tagline, and
    determines best scene order for a compelling ad narrative.

    Returns:
        Tuple of (scripts_dict, tagline, order).
    """
    client = genai.Client(
        vertexai=True,
        project=GOOGLE_CLOUD_PROJECT,
        location="global",
    )

    sorted_scenes = sorted(scene_images.keys())
    n = len(sorted_scenes)

    context_block = (
        f"\nBrand context: {brand_context}\n" if brand_context else ""
    )

    prompt = (
        f"You are a premium copywriter for {company_name}.\n\n"
        f"First, search for {company_name} to learn the brand, products, "
        "and slogan.\n\n"
        f"{context_block}"
        f"I am providing {n} scene images for a video advertisement.\n"
        "For each scene, write a SHORT voiceover narrator line.\n\n"
        "IMPORTANT — Determine best SCENE ORDER for ad narrative:\n"
        "- Arrange scenes to tell a logical story.\n"
        "- Order should feel like a professional commercial.\n\n"
        "RULES for each script:\n"
        f"- 6 to {max_words} words\n"
        "- Each script must use DIFFERENT vocabulary.\n"
        "- Evoke feeling and emotion, not literal image description\n"
        f"- Reference the {company_name} brand naturally\n"
        "- Premium, warm, cinematic tone\n"
        "- Vary sentence structure and word choice\n\n"
        "Return a JSON object with format (no markdown, no code fence):\n"
        f'{{"tagline": "official tagline for {company_name}", '
        '"order": [2, 1, 3, ...], '
        f'"scripts": {{"1": "script for scene 1", ...}}}}\n\n'
        'The "order" array is optimal sequence for ad.\n'
        f"Scene numbers are: {sorted_scenes}"
    )

    image_parts = [
        types.Part.from_bytes(data=scene_images[i], mime_type="image/png")
        for i in sorted_scenes
    ]

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-3.5-flash",
            contents=[prompt, *image_parts],
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.8,
                safety_settings=[
                    types.SafetySetting(
                        category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_DANGEROUS_CONTENT",
                        threshold="OFF",
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        threshold="OFF",
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_HARASSMENT", threshold="OFF"
                    ),
                ],
            ),
        )
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        data = json.loads(raw)
        tagline = (
            data.get("tagline", f"Experience {company_name}").strip().strip('"')
        )
        raw_scripts = data.get("scripts", {})
        raw_order = data.get("order", sorted_scenes)
        order = (
            [int(x) for x in raw_order if int(x) in sorted_scenes]
            if raw_order
            else sorted_scenes
        )
        if set(order) != set(sorted_scenes):
            order = sorted_scenes

        scripts = {}
        for scene_num in sorted_scenes:
            text = (
                raw_scripts.get(str(scene_num), "")
                .strip()
                .strip('"')
                .strip("'")
            )
            words = text.split()
            if len(words) > max_words:
                text = " ".join(words[:max_words])
            scripts[scene_num] = text
            print(f"[Gemini] Scene {scene_num} script: {text}")

        print(f"[Gemini] Tagline: {tagline}")
        print(f"[Gemini] Optimal scene order: {order}")
        return scripts, tagline, order

    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OSError,
        RuntimeError,
    ) as e:
        print(f"[Gemini] Script generation failed: {e}")
        return (
            {i: "" for i in sorted_scenes},
            f"Experience {company_name}",
            sorted_scenes,
        )


async def lookup_company_tagline(company_name: str) -> str:
    """Look up company official tagline using Gemini with Google Search."""
    client = genai.Client(
        vertexai=True,
        project=GOOGLE_CLOUD_PROJECT,
        location="global",
    )
    prompt = (
        f"What is the official tagline or slogan for {company_name}? "
        "Search for it and return ONLY the tagline text — nothing else. "
        "If no official tagline exists, create a short, compelling one."
    )
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-3.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.3,
                safety_settings=[
                    types.SafetySetting(
                        category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_DANGEROUS_CONTENT",
                        threshold="OFF",
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        threshold="OFF",
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_HARASSMENT", threshold="OFF"
                    ),
                ],
            ),
        )
        tagline = response.text.strip().strip('"').strip("'")
        print(f"[Gemini] Tagline for {company_name}: {tagline}")
        return tagline
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OSError,
        RuntimeError,
    ) as e:
        print(f"[Gemini] Tagline lookup failed: {e}")
        return f"Experience {company_name}"


# ============================================================
# Intro / Outro Title Card Generation (FFmpeg)
# ============================================================


def generate_title_card(
    text_line1: str,
    text_line2: str = "",
    duration: float = 3.0,
    width: int = 1920,
    height: int = 1080,
    logo_bytes: bytes | None = None,
    fade_in: bool = True,
    fade_out: bool = True,
    background_image_bytes: bytes | None = None,
) -> bytes | None:
    """Generate title card clip using Pillow text rendering + ffmpeg."""
    try:
        if background_image_bytes:
            bg = Image.open(
                io.BytesIO(background_image_bytes, "r", encoding="utf-8")
            ).convert("RGB")
            bg = bg.resize((width, height), Image.LANCZOS)
            bg = bg.filter(ImageFilter.GaussianBlur(radius=12))
            bg = ImageEnhance.Brightness(bg).enhance(0.7)
        else:
            bg = Image.new("RGB", (width, height), color=(26, 26, 26))

        draw = ImageDraw.Draw(bg)

        font_path = FONT_PATH
        try:
            title_font = (
                ImageFont.truetype(font_path, 80)
                if font_path
                else ImageFont.load_default()
            )
            sub_font = (
                ImageFont.truetype(font_path, 36)
                if font_path
                else ImageFont.load_default()
            )
        except (OSError, IOError):
            title_font = ImageFont.load_default()
            sub_font = ImageFont.load_default()

        bbox1 = draw.textbbox((0, 0), text_line1, font=title_font)
        tw1 = bbox1[2] - bbox1[0]
        y1 = height // 2 - 70 if text_line2 else height // 2 - 40
        draw.text(
            ((width - tw1) // 2, y1), text_line1, fill="white", font=title_font
        )

        if text_line2:
            bbox2 = draw.textbbox((0, 0), text_line2, font=sub_font)
            tw2 = bbox2[2] - bbox2[0]
            draw.text(
                ((width - tw2) // 2, height // 2 + 50),
                text_line2,
                fill=(200, 200, 200),
                font=sub_font,
            )

        if logo_bytes:
            try:
                logo = Image.open(
                    io.BytesIO(logo_bytes, "r", encoding="utf-8")
                ).convert("RGBA")
                logo_h = height // 6
                logo_w = int(logo.width * (logo_h / logo.height))
                logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
                x_pos = (width - logo_w) // 2
                y_pos = height // 6 - logo_h // 2
                bg.paste(logo, (x_pos, y_pos), logo)
            except (
                ValueError,
                TypeError,
                KeyError,
                AttributeError,
                OSError,
                RuntimeError,
            ) as e:
                print(f"[TitleCard] Logo overlay failed: {e}")

        card_path_png = os.path.join(tempfile.mkdtemp(), "card.png")
        bg.save(card_path_png, format="PNG")

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "card.mp4")

            fade_filter = ""
            if fade_in or fade_out:
                parts = []
                if fade_in:
                    parts.append("fade=t=in:st=0:d=1.0")
                if fade_out:
                    parts.append(f"fade=t=out:st={duration - 1.0}:d=1.0")
                fade_filter = f'-vf {",".join(parts)}'

            cmd = [
                _FFMPEG_EXE,
                "-y",
                "-loop",
                "1",
                "-t",
                f"{duration}",
                "-i",
                card_path_png,
                "-f",
                "lavfi",
                "-i",
                f"anullsrc=r=48000:cl=stereo:d={duration}",
            ]
            if fade_filter:
                cmd.extend(
                    [
                        "-vf",
                        ",".join(
                            (["fade=t=in:st=0:d=1.0"] if fade_in else [])
                            + (
                                [f"fade=t=out:st={duration - 1.0}:d=1.0"]
                                if fade_out
                                else []
                            )
                        ),
                    ]
                )
            cmd.extend(
                [
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    "-pix_fmt",
                    "yuv420p",
                    "-r",
                    "30",
                    "-c:a",
                    "aac",
                    "-ar",
                    "48000",
                    "-ac",
                    "2",
                    "-b:a",
                    "192k",
                    "-t",
                    f"{duration}",
                    "-shortest",
                    "-movflags",
                    "+faststart",
                    out_path,
                ]
            )

            result = subprocess.run(
                cmd, capture_output=True, timeout=30, check=False
            )
            if result.returncode == 0:
                with open(out_path, "rb") as f:
                    print(f"[TitleCard] OK: {text_line1}")
                    return f.read()
            print(f"[TitleCard] ffmpeg failed: {result.stderr.decode()[-500:]}")
            return None
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OSError,
        RuntimeError,
    ) as e:
        print(f"[TitleCard] Error: {e}")
        return None


def _escape_ffmpeg_text(text: str) -> str:
    """Escape special characters for ffmpeg drawtext filter."""
    return text.replace("'", "'\\''").replace(":", "\\:").replace("%", "%%")


# ============================================================
# Utility: Strip audio from video
# ============================================================


def _strip_audio(video_bytes: bytes) -> bytes:
    """Remove audio track from video bytes, returning video-only."""
    try:
        ffmpeg_exe = _FFMPEG_EXE
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OSError,
        RuntimeError,
    ):
        ffmpeg_exe = "ffmpeg"
    with tempfile.TemporaryDirectory() as tmpdir:
        in_path = os.path.join(tmpdir, "in.mp4")
        out_path = os.path.join(tmpdir, "out.mp4")
        with open(in_path, "wb") as f:
            f.write(video_bytes)
        result = subprocess.run(
            [
                ffmpeg_exe,
                "-y",
                "-i",
                in_path,
                "-an",
                "-c:v",
                "copy",
                "-movflags",
                "+faststart",
                out_path,
            ],
            capture_output=True,
            timeout=30,
            check=False,
        )
        if result.returncode == 0:
            with open(out_path, "rb") as f:
                return f.read()
    return video_bytes


# ============================================================
# Omni Video Generation
# ============================================================


def build_omni_prompt(
    scene_number: int,
    voiceover_text: str,
    company_name: str = "",
    brand_context: str = "",
) -> str:
    """Build default Omni prompt with strict physical rigidity."""
    brand_line = f" for {company_name}" if company_name else ""
    context_block = (
        f"\nBrand context: {brand_context}\n" if brand_context else ""
    )
    return (
        f"Create ONE SINGLE 8-second video clip{brand_line} from image.\n\n"
        f"Scene {scene_number}: {voiceover_text}\n"
        f"{context_block}\n"
        "CRITICAL — ONE CLIP, ONE SHOT:\n"
        "- Output ONE continuous 8-second clip — NO cuts, NO transitions\n"
        "- Entire 8s must be SINGLE unbroken take of same scene\n"
        "- Do NOT split into multiple clips or show different angles\n\n"
        "REAL-WORLD PHYSICAL LOGIC & SPATIAL NON-COLLISION:\n"
        "- Obey fundamental real-world physics, spatial mechanics, and common "
        "sense.\n"
        "- Solid objects (people, vehicles, elevators, doors, furniture) "
        "CANNOT occupy the same space, collide impossibly, or phase through "
        "geometry.\n"
        "- ELEVATOR HOISTWAY ISOLATION: In atriums and towers, every glass "
        "elevator capsule MUST travel strictly within its own "
        "isolated vertical "
        "track. NEVER spawn multiple elevators colliding, overlapping, or "
        "sharing the same vertical shaft!\n"
        "- All moving mechanisms must operate on separate, independent "
        "pathways with ZERO clipping.\n"
        "- All static architecture, walls, headboards, beds, and furniture "
        "MUST REMAIN 100% RIGID and STILL with ZERO liquid warping.\n"
        "- Wall murals and artwork are 100% STATIC PIGMENTED SURFACES on solid "
        "walls (NO changing depicted art).\n"
        "- Background views outside windows must remain 100% persistent (NO "
        "spontaneous trees or objects popping in).\n\n"
        "FULL STORYBOARD FRAMING & ZERO FOREGROUND/CEILING CROPPING:\n"
        "- Preserve the FULL vertical and horizontal composition of the "
        "reference photo without cropping.\n"
        "- Foreground assets (fountains, pools, lobby floor) and ceiling "
        "architecture (skylights, trusses) MUST remain fully visible.\n\n"
        "STRICT CLOSED-WORLD VISUAL GROUNDING — ZERO MADE-UP ASSETS:\n"
        "- The reference image defines 100% of the visible scene assets.\n"
        "- Show ONLY what is physically visible in reference image — add "
        "NOTHING new.\n"
        "- Do NOT add new people, actors, animals, furniture, decor, or "
        "objects.\n"
        "- Do NOT modify or hallucinate any details outside the reference "
        "photo.\n"
        "- Match reference image exactly in subject identity, count, and "
        "position.\n\n"
        "STEADY FRONT-MOVING FORWARD PAN-IN (MAINTAINING ALL DETAILS):\n"
        "- ALWAYS maintain a smooth, steady front-moving "
        "forward pan-in / dolly "
        "glide that travels gracefully into the scene.\n"
        "- 100% DETAIL PRESERVATION: Maintain ALL visible assets, palm trees, "
        "sun loungers, umbrella furniture, and poolside geometry with ZERO "
        "warping, melting, or disappearing.\n"
        "- CALM SWIMMING POOL FLUID REALISM: In swimming pools, water must be "
        "TRANQUIL, CALM, AND CRYSTAL CLEAR with micro-reflections and gentle "
        "surface glinting. ABSOLUTELY ZERO violent sloshing, ZERO unnatural "
        "churning, and ZERO artificial waves in the pool surface!\n"
        "- INDOOR SUITES & BEDROOMS: Strict indoor room containment — camera "
        "remains 100% inside the suite with gentle ambient "
        "warmth (ZERO flying out "
        "the window, ZERO diving to ground level).\n"
        "- INDOOR ATRIUMS & LOBBIES: Steady wide tracking shot "
        "with smooth elevator "
        "ascents on isolated vertical tracks.\n"
        "- PRESERVE PERSPECTIVE: Maintain the client-approved "
        "reference framing "
        "and composition — zero mid-clip cuts, zero abrupt angle jumps.\n\n"
        "LOCKED FOCAL PLANE & ZERO MID-CLIP REFOCUSING:\n"
        "- ONE single unbroken focal plane from 0.0s to 8.0s\n"
        "- ZERO mid-clip refocusing, lens hunting, or focal pulsing\n"
        "- ZERO secondary cuts, angle changes, or mid-shot shifts\n"
        "- Constant steady camera velocity without sudden stops or jerks\n\n"
        "SENSIBLE REAL-WORLD MOTION IN EVERY SCENARIO & SURROUNDING:\n"
        "- Indoor rooms (bedrooms, suites): Air is still and calm. Solids are "
        "100% rigid. Curtains and bedding rest naturally under gravity with "
        "ZERO violent flapping or phantom drafts.\n"
        "- Indoor atriums & public spaces: Glass elevators move smoothly on "
        "isolated vertical hoistways without colliding; fountains spray "
        "naturally following gravity; pedestrians walk on floor planes.\n"
        "- Outdoor resort spaces: Organic fluid dynamics only (gentle breeze "
        "through foliage, soft water ripples, ocean waves, "
        "sunlight glinting).\n"
        "- Cinema camera inertia: Camera moves with physical weight and smooth "
        "continuous glide — zero abrupt jumps, zero deep zooms, zero mid-clip "
        "cuts.\n\n"
        "Photorealistic, 1080p high sharpness. Warm lighting. Silent. 16:9."
    )


async def generate_scene_video(
    image_bytes: bytes,
    voiceover_text: str,
    scene_number: int,
    company_name: str = "",
    brand_context: str = "",
    prompt_override: str = "",
) -> bytes | None:
    """Generate a single scene clip using Omni. Visual only, no audio."""
    initialize_ffmpeg_if_needed()

    try:
        img = Image.open(
            io.BytesIO(image_bytes, "r", encoding="utf-8")
        ).convert("RGB")
        img = img.resize((1920, 1080), Image.Resampling.LANCZOS)
        print(
            f"[Omni] Scene {scene_number}: Lanczos super-resolution "
            f"scaled to full 1080p (1920x1080)"
        )
        img = img.filter(
            ImageFilter.UnsharpMask(radius=1.5, percent=125, threshold=2)
        )
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()
    except (ValueError, RuntimeError, KeyError, TypeError, OSError, IOError):
        pass
    client = genai.Client(
        vertexai=True,
        project=GOOGLE_CLOUD_PROJECT,
        location="global",
        http_options=types.HttpOptions(
            timeout=600_000,
            headers={"Api-Revision": "2026-05-20"},
        ),
    )

    brand_line = f" for {company_name}" if company_name else ""

    default_prompt = build_omni_prompt(
        scene_number, voiceover_text, company_name, brand_context
    )
    prompts = (
        [prompt_override]
        if prompt_override
        else [
            default_prompt,
            (
                f"ONE continuous clip{brand_line}.\n"
                f"Scene {scene_number}: {voiceover_text}\n"
                "SINGLE SHOT — no cuts, no transitions.\n"
                "Show ONLY what is in reference image — add NOTHING.\n"
                "- Slow contained camera (Ken Burns zoom/drift)\n"
                "- Natural motion: wind, water, light, breathing\n"
                "- Static objects stay still\n"
                "Silent. 16:9."
            ),
            (
                "Single 8-second clip. One continuous shot, no cuts. "
                "Slow Ken Burns camera within frame. Natural motion. "
                "Show ONLY reference image contents. Silent. 16:9."
            ),
        ]
    )

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    max_attempts = 5
    for attempt in range(max_attempts):
        prompt = prompts[min(attempt, len(prompts) - 1)]
        try:
            interaction = await asyncio.to_thread(
                client.interactions.create,
                model=OMNI_VIDEO_MODEL,
                input=[
                    {"type": "text", "text": prompt},
                    {
                        "type": "image",
                        "mime_type": "image/png",
                        "data": image_b64,
                    },
                ],
            )
            for step in interaction.steps:
                stype = step["type"] if isinstance(step, dict) else step.type
                if stype == "model_output":
                    scontents = (
                        step["content"]
                        if isinstance(step, dict)
                        else step.content
                    )
                    for content in scontents:
                        data = (
                            content.get("data")
                            if isinstance(content, dict)
                            else getattr(content, "data", None)
                        )
                        if data:
                            if isinstance(data, str):
                                data = base64.b64decode(data)
                            data = _strip_audio(data)
                            print(
                                f"[Omni] Scene {scene_number}:"
                                f" success, {len(data):,} bytes"
                            )
                            return data
        except (
            ValueError,
            RuntimeError,
            KeyError,
            TypeError,
            OSError,
            IOError,
        ) as e:
            err_str = str(e)
            is_timeout = (
                "timed out" in err_str.lower() or "timeout" in err_str.lower()
            )
            is_content_block = (
                "prohibited_content" in err_str or "blocked" in err_str.lower()
            )
            is_429 = (
                "429" in err_str
                or "RESOURCE_EXHAUSTED" in err_str
                or "too_many_requests" in err_str
            )
            if is_timeout:
                error_type = "TIMEOUT"
            elif is_content_block:
                error_type = "CONTENT_FILTER"
            elif is_429:
                error_type = "RATE_LIMIT"
            else:
                error_type = "ERROR"
            print(
                f"[Omni] Scene {scene_number} attempt"
                f" {attempt + 1}/{max_attempts} {error_type}"
            )
            if is_content_block and attempt < max_attempts - 1:
                print(f"[Omni] Scene {scene_number}: retrying...")
                await asyncio.sleep(3)
                continue
            if is_429 and attempt < max_attempts - 1:
                backoff = (2**attempt) * 15 + random.uniform(0, 5)
                print(
                    f"[Omni] Scene {scene_number}: rate"
                    f" limited, waiting {backoff:.0f}s"
                )
                await asyncio.sleep(backoff)
                continue
        if attempt < max_attempts - 1:
            await asyncio.sleep(3)

    print(f"[Omni] Scene {scene_number}: all {max_attempts} attempts failed")
    return None


# ============================================================
# Veo Video Generation
# ============================================================


def build_veo_prompt(
    scene_number: int,
    voiceover_text: str,
    company_name: str = "",
    brand_context: str = "",
    clip_duration: int = 8,
) -> str:
    """Build default Veo prompt with strict physical rigidity."""
    brand_line = f" for {company_name}" if company_name else ""
    context_block = (
        f"\nBrand context: {brand_context}\n" if brand_context else ""
    )
    return (
        f"Create ONE SINGLE {clip_duration}-second"
        f" clip{brand_line} from image.\n\n"
        f"Scene {scene_number}: {voiceover_text}\n"
        f"{context_block}\n"
        "CRITICAL — ONE CLIP, ONE SHOT:\n"
        f"- Output ONE continuous {clip_duration}s"
        f" clip — no cuts, no scene changes\n"
        "- Entire clip must be SINGLE unbroken take of same scene\n\n"
        "STRICT CLOSED-WORLD VISUAL GROUNDING — ZERO MADE-UP ASSETS:\n"
        "- The reference image defines 100% of the visible scene assets\n"
        "- Show ONLY what is visible in the reference image — add NOTHING new\n"
        "- Do NOT add new people, actors, animals, furniture, or decor\n"
        "- Do NOT remove, move, or hallucinate anything outside the photo\n"
        "- Match reference image exactly in subject identity and position\n\n"
        "SCENARIO-ADAPTIVE CINEMATIC CAMERA DYNAMICS:\n"
        f"- Outdoor pool & resort spaces: Smooth elegant "
        f"continuous forward glide across water ripples and "
        f"garden breeze\n"
        f"- Indoor rooms: Strict indoor room containment — stay "
        f"100% inside suite (no window flythroughs)\n"
        f"- Maintain exact {clip_duration}s reference framing "
        f"without abrupt cuts or angle switches\n\n"
        "LOCKED FOCAL PLANE & ZERO MID-CLIP REFOCUSING:\n"
        f"- Output ONE single unbroken focal plane "
        f"from 0.0s to {clip_duration}.0s\n"
        "- ZERO mid-clip refocusing, lens hunting, or focal pulsing\n"
        "- ZERO secondary cuts, angle changes, or mid-shot shifts\n"
        "- Constant steady camera velocity without sudden stops or jerks\n\n"
        "SENSIBLE REAL-WORLD MOTION IN EVERY SCENARIO & SURROUNDING:\n"
        "- Indoor rooms (bedrooms, suites): Air is still and calm. Solids are "
        "100% rigid. Curtains and bedding rest naturally under gravity with "
        "ZERO violent flapping or phantom drafts.\n"
        "- Indoor atriums & public spaces: Glass elevators move smoothly on "
        "isolated vertical hoistways without colliding; fountains spray "
        "naturally following gravity; pedestrians walk on floor planes.\n"
        "- Outdoor resort spaces: Organic fluid dynamics only (gentle breeze "
        "through foliage, soft water ripples, ocean waves, "
        "sunlight glinting).\n"
        "- Cinema camera inertia: Camera moves with physical weight and smooth "
        "continuous glide — zero abrupt jumps, zero deep zooms, zero mid-clip "
        "cuts.\n\n"
        f"Photorealistic. Warm lighting. Silent. No"
        f" text overlays. 16:9. {clip_duration}s."
    )


async def generate_scene_video_veo(
    image_bytes: bytes,
    voiceover_text: str,
    scene_number: int,
    company_name: str = "",
    brand_context: str = "",
    clip_duration: int = 8,
    prompt_override: str = "",
    submit_only: bool = False,
) -> bytes | str | None:
    """Generate a single scene video clip using Veo. Visual only, no audio."""
    client = genai.Client(
        vertexai=True,
        project=GOOGLE_CLOUD_PROJECT,
        location="global",
        http_options=types.HttpOptions(timeout=600_000),
    )

    prompt = (
        prompt_override
        if prompt_override
        else build_veo_prompt(
            scene_number,
            voiceover_text,
            company_name,
            brand_context,
            clip_duration,
        )
    )

    veo_config = types.GenerateVideosConfig(
        number_of_videos=1,
        duration_seconds=clip_duration,
        aspect_ratio="16:9",
        generate_audio=False,
        person_generation="allow_all",
    )

    # Veo requires JPEG/PNG and 16:9 aspect ratio — convert and crop via Pillow
    try:
        img = Image.open(
            io.BytesIO(image_bytes, "r", encoding="utf-8")
        ).convert("RGB")
        w, h = img.size
        target_ratio = 16 / 9
        current_ratio = w / h
        if abs(current_ratio - target_ratio) > 0.05:
            if current_ratio > target_ratio:
                new_w = int(h * target_ratio)
                left = (w - new_w) // 2
                img = img.crop((left, 0, left + new_w, h))
            else:
                new_h = int(w / target_ratio)
                top = (h - new_h) // 2
                img = img.crop((0, top, w, top + new_h))
            print(
                f"[Veo] Scene {scene_number}: cropped"
                f" to 16:9 ({img.size[0]}x{img.size[1]})"
            )
        if img.size[0] < 1280 or img.size[1] < 720:
            img = img.resize((1920, 1080), Image.Resampling.LANCZOS)
            print(
                f"[Veo] Scene {scene_number}: Lanczos super-resolution "
                f"upscaled to 1080p (1920x1080)"
            )
        img = img.filter(
            ImageFilter.UnsharpMask(radius=1.5, percent=125, threshold=2)
        )
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        image_bytes = buf.getvalue()
        print(
            f"[Veo] Scene {scene_number}: image ready"
            f" as JPEG ({len(image_bytes):,} bytes)"
        )
    except ImportError:
        print(
            f"[Veo] Scene {scene_number}: Pillow"
            f" not available, sending image as-is"
        )
    except (ValueError, TypeError, KeyError, AttributeError, OSError) as e:
        print(f"[Veo] Scene {scene_number}: image conversion warning: {e}")

    max_polls = 90
    for attempt in range(3):
        try:
            print(
                f"[Veo] Scene {scene_number}: submitting"
                f" {clip_duration}s clip (attempt {attempt + 1}/3)..."
            )
            operation = client.models.generate_videos(
                model=VEO_VIDEO_MODEL,
                prompt=prompt,
                image=types.Image(
                    image_bytes=image_bytes, mime_type="image/jpeg"
                ),
                config=veo_config,
            )

            if submit_only:
                return getattr(operation, "name", None) or str(operation)

            for _ in range(max_polls):
                if operation.done:
                    break
                await asyncio.sleep(10)
                operation = client.operations.get(operation)

            if not operation.done:
                print(
                    f"[Veo] Scene {scene_number}:"
                    f" timed out after {max_polls * 10}s"
                )
                continue

            if operation.error:
                print(
                    f"[Veo] Scene {scene_number}:"
                    f" operation error: {operation.error}"
                )
                continue

            if (
                not operation.response
                or not operation.response.generated_videos
            ):
                print(f"[Veo] Scene {scene_number}: no videos in response")
                continue

            generated = operation.response.generated_videos[0]
            if not generated.video or not generated.video.video_bytes:
                print(
                    f"[Veo] Scene {scene_number}: generated video has no bytes"
                )
                continue

            print(
                f"[Veo] Scene {scene_number}: success,"
                f" {len(generated.video.video_bytes):,} bytes"
            )
            return generated.video.video_bytes

        except (
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OSError,
            RuntimeError,
        ) as e:
            print(
                f"[Veo] Scene {scene_number} attempt"
                f" {attempt + 1}/3 failed: {e}"
            )
            is_429 = "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)
            if is_429 and attempt < 2:
                backoff = (2**attempt) * 5 + random.uniform(0, 3)
                await asyncio.sleep(backoff)
                continue
        if attempt < 2:
            await asyncio.sleep(3)

    print(f"[Veo] Scene {scene_number}: all attempts failed")
    return None


async def check_scene_video_veo(operation_name: str) -> bytes | str | None:
    """Check the status of a Veo generation operation.
    Returns bytes if done, 'RUNNING' if still going, or None if failed.
    """
    client = genai.Client(
        vertexai=True,
        project=GOOGLE_CLOUD_PROJECT,
        location="global",
    )
    try:
        operation = client.operations.get(operation_name)
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OSError,
        RuntimeError,
    ) as e:
        print(f"[Veo] Operation get failed: {e}")
        return None

    if not operation.done:
        return "RUNNING"

    if operation.error:
        print(f"[Veo] Operation {operation_name} error: {operation.error}")
        return None

    if not operation.response or not operation.response.generated_videos:
        print(f"[Veo] Operation {operation_name}: no videos in response")
        return None

    generated = operation.response.generated_videos[0]
    if not generated.video or not generated.video.video_bytes:
        print(f"[Veo] Operation {operation_name}: generated video has no bytes")
        return None

    return generated.video.video_bytes


# ============================================================
# TTS Voiceover
# ============================================================


def _build_tts_prompt(script: str, emotion: str = "Energetic") -> str:
    """Build TTS prompt instructing voice to speak with emotion."""
    emotion_lower = emotion.lower()
    style_map = {
        "energetic": "Speak with HIGH ENERGY — upbeat and dynamic.",
        "professional": "Speak in a polished, clear, authoritative tone.",
        "warm": "Speak warmly and conversationally — friendly and inviting.",
        "excited": "Speak with EXCITEMENT — convey passion and thrill.",
        "calm": "Speak calmly and soothingly — serene and measured.",
        "confident": "Speak with confidence and conviction — bold and clear.",
        "inspiring": "Speak with inspiration — uplifting and motivational.",
        "dramatic": "Speak with dramatic flair — cinematic, with pauses.",
    }
    style = style_map.get(
        emotion_lower,
        f"Speak with a {emotion} tone.",
    )
    return (
        f"Say the following in a video ad voiceover style. {style}\n\n"
        f'"{script}"'
    )


async def generate_voiceover(
    script: str,
    voice_name: str = "Charon",
    emotion: str = "Energetic",
    speaking_rate: float = 1.0,
) -> bytes | None:
    """Generate voiceover audio using Gemini TTS.

    Args:
        script: Text to speak.
        voice_name: Gemini TTS voice name (e.g. "Charon", "Aoede").
        emotion: Voice emotion/style.
        speaking_rate: Speed of the voice.
    """
    try:
        pass
    except ImportError:
        print("[TTS] google-cloud-texttospeech not installed")
        return None

    tts_location = os.environ.get("GOOGLE_CLOUD_REGION", GOOGLE_CLOUD_LOCATION)
    api_endpoint = (
        f"{tts_location}-texttospeech.googleapis.com"
        if tts_location != "global"
        else "texttospeech.googleapis.com"
    )

    tts_client = texttospeech.TextToSpeechClient(
        client_options=ClientOptions(
            api_endpoint=api_endpoint, quota_project_id=GOOGLE_CLOUD_PROJECT
        )
    )

    tts_prompt = _build_tts_prompt(script, emotion)

    def _synthesize():
        return tts_client.synthesize_speech(
            input=texttospeech.SynthesisInput(text=tts_prompt),
            voice=texttospeech.VoiceSelectionParams(
                language_code="en-US",
                name=voice_name,
                model_name="gemini-3.1-flash-tts-preview",
            ),
            audio_config=texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                speaking_rate=speaking_rate,
            ),
        )

    for attempt in range(3):
        try:
            response = await asyncio.to_thread(_synthesize)
            if response.audio_content:
                print(
                    f"[Gemini TTS] Voiceover generated ({emotion}):"
                    f" {len(response.audio_content)} bytes"
                )
                return response.audio_content
        except (
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OSError,
            RuntimeError,
        ) as e:
            print(f"[Gemini TTS] Attempt {attempt + 1}/3 failed: {e}")
        if attempt < 2:
            await asyncio.sleep(2)
    print(f"[Gemini TTS] All attempts failed: {script[:30]}...")
    return None


async def generate_all_voiceovers(
    scripts: list[str],
    voice_name: str = "Charon",
    emotion: str = "Energetic",
    speaking_rate: float = 1.0,
) -> list[bytes | None]:
    """Generate voiceover audio for all scenes in parallel."""
    tasks = [
        generate_voiceover(
            s, voice_name, emotion=emotion, speaking_rate=speaking_rate
        )
        for s in scripts
    ]
    return await asyncio.gather(*tasks, return_exceptions=False)


async def generate_voice_preview(
    voice_name: str, emotion: str = "Energetic", speaking_rate: float = 1.0
) -> bytes | None:
    """Generate TTS sample so user can preview voice."""
    return await generate_voiceover(
        VOICE_PREVIEW_TEXT,
        voice_name,
        emotion=emotion,
        speaking_rate=speaking_rate,
    )


# ============================================================
# Lyria Background Music
# ============================================================


async def generate_background_music(
    company_name: str,
    scene_descriptions: list[str],
    brand_context: str = "",
    prompt_override: str = "",
) -> bytes | None:
    """Generate background music using Lyria."""
    client = genai.Client(
        vertexai=True,
        project=GOOGLE_CLOUD_PROJECT,
        location="global",
    )

    scenes_summary = " | ".join(
        f"Scene {i+1}: {d}" for i, d in enumerate(scene_descriptions)
    )

    brand_hint = ""
    if company_name:
        brand_lower = company_name.lower()
        if any(
            w in brand_lower
            for w in [
                "hotel",
                "resort",
                "hyatt",
                "marriott",
                "hilton",
                "spa",
                "luxury",
            ]
        ):
            brand_hint = "Mood: luxury hospitality — serene. Resort ad.\n"
        elif any(
            w in brand_lower
            for w in ["tech", "google", "apple", "microsoft", "ai", "cloud"]
        ):
            brand_hint = "Mood: innovation — modern. Tech product launch.\n"
        elif any(
            w in brand_lower
            for w in ["car", "auto", "bmw", "mercedes", "audi", "ford"]
        ):
            brand_hint = "Mood: automotive luxury — sleek. Premium car ad.\n"
        elif any(
            w in brand_lower for w in ["food", "restaurant", "kitchen", "chef"]
        ):
            brand_hint = "Mood: culinary warmth — inviting. Food ad.\n"

    if prompt_override:
        prompt = prompt_override
    else:
        prompt = (
            f"Create a cinematic instrumental background music"
            f" track for a {company_name} video advertisement.\n\n"
            f"The ad tells this story across"
            f" {len(scene_descriptions)} scenes:\n"
            f"{scenes_summary}\n\n"
            f"{brand_hint}"
            "Music direction:\n"
            "- Analyze the scene scripts above — match "
            "the emotional journey they describe\n"
            "- Open softly, build through the middle "
            "scenes, crescendo at the finale\n"
            "- Premium, cinematic quality — like "
            "a real TV commercial soundtrack\n"
            "- Strictly instrumental — piano, strings, subtle percussion\n"
            "- The music should feel like it was "
            "composed specifically for this brand\n"
        )
        if brand_context:
            prompt += f"\nBrand context: {brand_context}\n"

    for attempt in range(3):
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=LYRIA_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO", "TEXT"],
                    safety_settings=[
                        types.SafetySetting(
                            category="HARM_CATEGORY_HATE_SPEECH",
                            threshold="OFF",
                        ),
                        types.SafetySetting(
                            category="HARM_CATEGORY_DANGEROUS_CONTENT",
                            threshold="OFF",
                        ),
                        types.SafetySetting(
                            category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                            threshold="OFF",
                        ),
                        types.SafetySetting(
                            category="HARM_CATEGORY_HARASSMENT",
                            threshold="OFF",
                        ),
                    ],
                ),
            )
            for part in response.parts:
                if part.inline_data and part.inline_data.data:
                    return part.inline_data.data
        except (
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OSError,
            RuntimeError,
        ) as e:
            print(f"[Lyria] Music attempt {attempt + 1}/3 failed: {e}")
            is_429 = "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)
            if is_429 and attempt < 2:
                backoff = (2**attempt) * 3 + random.uniform(0, 2)
                await asyncio.sleep(backoff)
                continue
        if attempt < 2:
            await asyncio.sleep(2)
    print("[Lyria] All music generation attempts failed")
    return None


# ============================================================
# FFmpeg Utilities
# ============================================================


def _probe_duration(file_path: str, fallback: float = 8.0) -> float:
    """Get media duration in seconds via ffmpeg."""
    try:
        ffmpeg_exe = _FFMPEG_EXE
    except (ImportError, AttributeError, ValueError):
        ffmpeg_exe = "ffmpeg"

    probe = subprocess.run(
        [ffmpeg_exe, "-i", file_path],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", probe.stderr)
    if match:
        hours, minutes, seconds = map(float, match.groups())
        return hours * 3600 + minutes * 60 + seconds
    return fallback


def trim_clip_to_voiceover(
    video_bytes: bytes,
    voiceover_bytes: bytes,
    pad_before: float = 2.0,
    pad_after: float = 2.0,
) -> bytes:
    """Trim a video clip to match voiceover duration + padding.

    The clip is trimmed so the total length = pad_before +
    voiceover_duration + pad_after.
    Voiceover starts at pad_before seconds into the clip.
    If the clip is shorter than the target, it is not trimmed.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        vid_path = os.path.join(tmpdir, "video.mp4")
        vo_path = os.path.join(tmpdir, "vo.wav")
        out_path = os.path.join(tmpdir, "trimmed.mp4")

        with open(vid_path, "wb") as f:
            f.write(video_bytes)
        with open(vo_path, "wb") as f:
            f.write(voiceover_bytes)

        video_duration = _probe_duration(vid_path, 8.0)
        vo_duration = _probe_duration(vo_path, 5.0)

        target_duration = pad_before + vo_duration + pad_after

        if target_duration >= video_duration:
            return video_bytes

        cmd = [
            _FFMPEG_EXE,
            "-y",
            "-i",
            vid_path,
            "-t",
            f"{target_duration:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-an",
            "-movflags",
            "+faststart",
            out_path,
        ]
        result = subprocess.run(
            cmd, capture_output=True, timeout=60, check=False
        )
        if result.returncode == 0:
            with open(out_path, "rb") as f:
                return f.read()
        return video_bytes


# ============================================================
# FFmpeg Audio Mixing
# ============================================================


def mix_scene_audio(
    video_bytes: bytes,
    voiceover_bytes: bytes | None,
    music_bytes: bytes | None,
    music_volume: float = 0.35,
    vo_delay: float = 0.5,
) -> bytes:
    """
    Mix voiceover (100%) and background music onto a video clip using ffmpeg.

    Voiceover starts at vo_delay seconds into the clip (the "padding before"
    window).
    """
    if not voiceover_bytes and not music_bytes:
        with tempfile.TemporaryDirectory() as tmpdir:
            vid_path = os.path.join(tmpdir, "video.mp4")
            out_path = os.path.join(tmpdir, "output.mp4")
            with open(vid_path, "wb") as f:
                f.write(video_bytes)
            cmd = [
                _FFMPEG_EXE,
                "-y",
                "-i",
                vid_path,
                "-f",
                "lavfi",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                out_path,
            ]
            result = subprocess.run(cmd, capture_output=True, check=False)
            if result.returncode == 0 and os.path.exists(out_path):
                with open(out_path, "rb") as f:
                    return f.read()
        return video_bytes

    with tempfile.TemporaryDirectory() as tmpdir:
        vid_path = os.path.join(tmpdir, "video.mp4")
        vo_path = os.path.join(tmpdir, "vo.wav")
        music_path = os.path.join(tmpdir, "music.wav")
        out_path = os.path.join(tmpdir, "output.mp4")

        with open(vid_path, "wb") as f:
            f.write(video_bytes)

        video_duration = _probe_duration(vid_path, 8.0)

        inputs = ["-i", vid_path]

        if voiceover_bytes:
            with open(vo_path, "wb") as f:
                f.write(voiceover_bytes)
            inputs.extend(["-i", vo_path])

        if music_bytes:
            with open(music_path, "wb") as f:
                f.write(music_bytes)
            inputs.extend(["-i", music_path])

        filter_complex = ""
        mix_inputs = []
        audio_idx = 1

        if voiceover_bytes:
            filter_complex += (
                f"[{audio_idx}:a]aresample=48000,volume=1.5,"
                f"adelay={int(vo_delay * 1000)}|{int(vo_delay * 1000)},apad,"
                f"atrim=0:{video_duration},asetpts=PTS-STARTPTS[vo];"
            )
            mix_inputs.append("[vo]")
            audio_idx += 1

        if music_bytes:
            filter_complex += (
                f"[{audio_idx}:a]atrim=0:{video_duration},asetpts=PTS-STARTPTS,"
                f"aresample=48000,volume={music_volume},"
                "afade=t=in:st=0:d=1.0,"
                f"afade=t=out:st={video_duration - 0.5}:d=0.5[music];"
            )
            mix_inputs.append("[music]")
            audio_idx += 1

        if len(mix_inputs) == 1:
            filter_complex = filter_complex.rstrip(";")
            label = mix_inputs[0].strip("[]")
            filter_complex = filter_complex.replace(f"[{label}]", "[aout]")
        else:
            filter_complex += (
                f'{"".join(mix_inputs)}amix=inputs={len(mix_inputs)}'
                ":duration=longest:dropout_transition=0[aout]"
            )

        cmd = [
            _FFMPEG_EXE,
            "-y",
            *inputs,
            "-filter_complex",
            filter_complex,
            "-map",
            "0:v",
            "-map",
            "[aout]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            out_path,
        ]

        print(
            f"[MixAudio] Running ffmpeg with filter: {filter_complex[:200]}..."
        )
        result = subprocess.run(
            cmd, capture_output=True, timeout=120, check=False
        )
        if result.returncode == 0:
            with open(out_path, "rb") as f:
                mixed = f.read()
                print(
                    f"[MixAudio] Success: {len(mixed):,}"
                    f" bytes (original: {len(video_bytes):,})"
                )
                return mixed
        print(f"[MixAudio] FAILED: {result.stderr.decode()[-300:]}")
        return video_bytes


# ============================================================
# Image Format Normalization & Logo Background Removal
# ============================================================


def ensure_png_bytes(image_bytes: bytes) -> bytes:
    """
    Convert WebP, JPEG, or any format image bytes to clean PNG bytes using
    Pillow.

    Guarantees that video generation models (Veo/Omni) and ffmpeg receive
    valid PNG formatted image bytes, avoiding black frames or format issues.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes, "r", encoding="utf-8"))
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.mode else "RGB")
        out_buf = io.BytesIO()
        img.save(out_buf, format="PNG")
        return out_buf.getvalue()
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OSError,
        RuntimeError,
    ) as e:
        print(f"[Image Conversion] Failed to convert image to PNG: {e}")
        return image_bytes


def remove_logo_background(logo_bytes: bytes) -> bytes:
    """Remove background from a logo image, making it transparent.

    Uses Pillow to detect the dominant corner color and make it transparent.
    Works well for logos on solid white/black/colored backgrounds.
    """
    if Image is None:
        print("[Logo] Pillow not available, returning logo as-is")
        return logo_bytes

    img = Image.open(io.BytesIO(logo_bytes, "r", encoding="utf-8")).convert(
        "RGBA"
    )

    if img.mode == "RGBA":
        alpha = img.getchannel("A")
        non_opaque = sum(1 for p in alpha.getdata() if p < 250)
        if non_opaque > (img.width * img.height * 0.05):
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()

    pixels = img.load()
    corners = [
        pixels[0, 0],
        pixels[img.width - 1, 0],
        pixels[0, img.height - 1],
        pixels[img.width - 1, img.height - 1],
    ]
    bg_color = collections.Counter(tuple(c[:3]) for c in corners).most_common(
        1
    )[0][0]

    tolerance = 30
    data = img.getdata()
    new_data = []
    for pixel in data:
        r, g, b, _ = pixel
        if (
            abs(r - bg_color[0]) < tolerance
            and abs(g - bg_color[1]) < tolerance
            and abs(b - bg_color[2]) < tolerance
        ):
            new_data.append((r, g, b, 0))
        else:
            new_data.append(pixel)
    img.putdata(new_data)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ============================================================
# Logo Overlay
# ============================================================


def create_outro_clip(
    base_clip_bytes: bytes,
    logo_bytes: bytes | None,
    tagline: str,
    voiceover_bytes: bytes | None,
) -> bytes | None:
    """
    Create an outro clip by darkening the base clip, adding enlarged logo in
    center, and tagline at bottom."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vid_path = os.path.join(tmpdir, "video.mp4")
        out_path = os.path.join(tmpdir, "output.mp4")

        with open(vid_path, "wb") as f:
            f.write(base_clip_bytes)

        last_frame_path = os.path.join(tmpdir, "last_frame.jpg")
        subprocess.run(
            [
                _FFMPEG_EXE,
                "-y",
                "-sseof",
                "-0.1",
                "-i",
                vid_path,
                "-vframes",
                "1",
                "-update",
                "1",
                last_frame_path,
            ],
            capture_output=True,
            check=False,
        )
        if not os.path.exists(last_frame_path):
            # Fallback to the first frame if sseof fails
            subprocess.run(
                [
                    _FFMPEG_EXE,
                    "-y",
                    "-i",
                    vid_path,
                    "-vframes",
                    "1",
                    last_frame_path,
                ],
                capture_output=True,
                check=False,
            )

        inputs = ["-loop", "1", "-i", last_frame_path]
        filter_complex = (
            "[0:v]colorchannelmixer=rr=0.3:gg=0.3:bb=0.3,gblur=sigma=15[dark];"
        )

        logo_idx = -1
        if logo_bytes:
            logo_path = os.path.join(tmpdir, "logo.png")
            with open(logo_path, "wb") as f:
                f.write(logo_bytes)
            inputs.extend(["-i", logo_path])
            logo_idx = inputs.count("-i") - 1

        vo_idx = -1
        if voiceover_bytes:
            vo_path = os.path.join(tmpdir, "vo.wav")
            with open(vo_path, "wb") as f:
                f.write(voiceover_bytes)
            inputs.extend(["-i", vo_path])
            vo_idx = inputs.count("-i") - 1

        # The user requested the outro to be exactly 4.0 seconds long, no
        # dynamic trimming.
        out_duration = 4.0

        curr_v = "[dark]"
        if logo_idx > 0:
            filter_complex += f"[{logo_idx}:v]scale=400:-1,format=rgba[logo];"
            filter_complex += f"{curr_v}[logo]overlay=(W-w)/2:(H-h)/2-50[v1];"
            curr_v = "[v1]"

        if tagline:
            tagline_path = os.path.join(tmpdir, "outro_tagline.png")
            try:
                try:
                    font = ImageFont.truetype(_find_font(), 52)
                except (
                    ValueError,
                    TypeError,
                    KeyError,
                    AttributeError,
                    OSError,
                    RuntimeError,
                ):
                    font = ImageFont.load_default()

                # Create a temporary image just to measure text
                temp_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
                temp_draw = ImageDraw.Draw(temp_img)
                try:
                    bbox = temp_draw.textbbox((0, 0), tagline, font=font)
                    text_w = bbox[2] - bbox[0]
                    text_h = bbox[3] - bbox[1]
                except (
                    ValueError,
                    TypeError,
                    KeyError,
                    AttributeError,
                    OSError,
                    RuntimeError,
                ):
                    text_w, text_h = 800, 52

                pad_x, pad_y = 36, 20
                img_w = text_w + pad_x * 2
                img_h = text_h + pad_y * 2

                img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)
                draw.text(
                    (pad_x, pad_y),
                    tagline,
                    fill=(255, 255, 255, 255),
                    font=font,
                    stroke_width=2,
                    stroke_fill=(0, 0, 0, 255),
                )
                img.save(tagline_path)

                inputs.extend(["-i", tagline_path])
                tagline_idx = inputs.count("-i") - 1
                filter_complex += (
                    f"{curr_v}[{tagline_idx}:v]overlay=(W-w)/2:H-h-120[v2];"
                )
                curr_v = "[v2]"
            except (
                ValueError,
                TypeError,
                KeyError,
                AttributeError,
                OSError,
                RuntimeError,
            ) as e:
                print(f"[Outro] Failed to generate tagline image: {e}")

        filter_complex += f"{curr_v}format=yuv420p[vout]"

        if vo_idx > 0:
            filter_complex += f";[{vo_idx}:a]apad,atrim=0:{out_duration}[aout]"
        else:
            # Must always have an audio track for concatenate filter to work
            filter_complex += (
                f";anullsrc=r=48000:cl=stereo,atrim=0:{out_duration}[aout]"
            )

        cmd = [
            _FFMPEG_EXE,
            "-y",
            *inputs,
            "-filter_complex",
            filter_complex,
            "-map",
            "[vout]",
            "-map",
            "[aout]",
        ]
        cmd.extend(
            [
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-c:a",
                "aac",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-b:a",
                "192k",
                "-t",
                str(out_duration),
            ]
        )

        cmd.extend(["-movflags", "+faststart", out_path])

        result = subprocess.run(
            cmd, capture_output=True, timeout=120, check=False
        )
        if result.returncode == 0:
            with open(out_path, "rb") as f:
                return f.read()
        print(f"[Outro] FFmpeg error: {result.stderr.decode()[-500:]}")
        return None


def overlay_logo_and_tagline_on_video(
    video_bytes: bytes,
    logo_bytes: bytes | None,
    tagline: str = "",
    opacity: float = 0.8,
    scale: float = 0.12,
    margin: int = 20,
) -> bytes:
    """Overlay a logo (with transparent background) on the top-right corner.
    (Tagline overlay is disabled because GCP ffmpeg lacks libfreetype).

    Args:
        video_bytes: The video to overlay onto.
        logo_bytes: PNG logo image (ideally with transparent background).
        tagline: Tagline text to display at the bottom center.
        opacity: Logo opacity (0.0 = invisible, 1.0 = fully opaque).
        scale: Logo size as a fraction of video width (0.12 = 12%).
        margin: Pixel margin from top-right corner.
    """
    if not logo_bytes and not tagline:
        return video_bytes

    with tempfile.TemporaryDirectory() as tmpdir:
        vid_path = os.path.join(tmpdir, "video.mp4")
        out_path = os.path.join(tmpdir, "output.mp4")

        with open(vid_path, "wb") as f:
            f.write(video_bytes)

        cmd = [_FFMPEG_EXE, "-y", "-i", vid_path]
        filter_complex = ""
        inputs_count = 1

        if logo_bytes:
            logo_path = os.path.join(tmpdir, "logo.png")
            with open(logo_path, "wb") as f:
                f.write(logo_bytes)
            cmd.extend(["-i", logo_path])
            logo_idx = inputs_count
            inputs_count += 1
        else:
            logo_idx = -1

        if tagline:
            tagline_path = os.path.join(tmpdir, "tagline.png")
            try:
                try:
                    font = ImageFont.truetype(_find_font(), 36)
                except (
                    ValueError,
                    TypeError,
                    KeyError,
                    AttributeError,
                    OSError,
                    RuntimeError,
                ):
                    font = ImageFont.load_default()

                # Create a temporary image just to measure text
                temp_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
                temp_draw = ImageDraw.Draw(temp_img)
                try:
                    bbox = temp_draw.textbbox((0, 0), tagline, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                except (
                    ValueError,
                    TypeError,
                    KeyError,
                    AttributeError,
                    OSError,
                    RuntimeError,
                ):
                    text_width, text_height = 600, 36

                pad_x, pad_y = 28, 14
                img_w = text_width + pad_x * 2
                img_h = text_height + pad_y * 2

                img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)

                # Draw black stroke/drop-shadow border for clean legibility
                for offset_x, offset_y in [
                    (-2, -2),
                    (2, -2),
                    (-2, 2),
                    (2, 2),
                    (0, -2),
                    (0, 2),
                    (-2, 0),
                    (2, 0),
                    (1, 2),
                    (2, 3),
                ]:
                    draw.text(
                        (pad_x + offset_x, pad_y + offset_y),
                        tagline,
                        fill=(0, 0, 0, 240),
                        font=font,
                    )
                # Draw crisp opaque white text
                draw.text(
                    (pad_x, pad_y),
                    tagline,
                    fill=(255, 255, 255, 255),
                    font=font,
                )

                img.save(tagline_path)
                cmd.extend(["-i", tagline_path])
                tagline_idx = inputs_count
                inputs_count += 1
            except (
                ValueError,
                TypeError,
                KeyError,
                AttributeError,
                OSError,
                RuntimeError,
            ) as e:
                print(f"Failed to generate tagline image: {e}")
                tagline_idx = -1
        else:
            tagline_idx = -1

        duration = probe_media_duration(vid_path, 24.0)

        # Maintain tagline across all scenes until outro card (duration - 4.0s)
        # where the outro card already displays large centered branding
        if duration > 4.5:
            enable_expr = f":enable='lt(t,{duration - 4.0})'"
        else:
            enable_expr = ""

        if logo_idx > 0 and tagline_idx > 0:
            filter_complex += (
                f"[{logo_idx}:v]scale=iw*{scale}:-1,format=rgba,"
                f"colorchannelmixer=aa={opacity}[logo];"
                f"[0:v][logo]overlay=W-w-{margin}:{margin}{enable_expr}[v1];"
                f"[v1][{tagline_idx}:v]overlay=(W-w)/2:H-h-60{enable_expr}[out]"
            )
        elif logo_idx > 0:
            filter_complex += (
                f"[{logo_idx}:v]scale=iw*{scale}:-1,format=rgba,"
                f"colorchannelmixer=aa={opacity}[logo];"
                f"[0:v][logo]overlay=W-w-{margin}:{margin}{enable_expr}[out]"
            )
        elif tagline_idx > 0:
            filter_complex += (
                f"[0:v][{tagline_idx}:v]overlay="
                f"(W-w)/2:H-h-60{enable_expr}[out]"
            )
        else:
            return video_bytes

        cmd.extend(
            [
                "-filter_complex",
                filter_complex,
                "-map",
                "[out]",
                "-map",
                "0:a?",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "28",
                "-c:a",
                "copy",
                "-movflags",
                "+faststart",
                out_path,
            ]
        )

        result = subprocess.run(
            cmd, capture_output=True, timeout=120, check=False
        )
        if result.returncode == 0:
            with open(out_path, "rb") as f:
                print("[Overlay] Logo/Tagline applied OK")
                return f.read()
        print(f"[Overlay] ffmpeg failed: {result.stderr.decode()[-500:]}")
        return video_bytes


# ============================================================
# FFmpeg Hard Concatenation (no transitions)
# ============================================================


def probe_video_resolution(video_bytes: bytes) -> tuple[int, int]:
    """Probe a video's resolution. Returns (width, height), "
    "defaults to (1920, 1080)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "probe.mp4")
        with open(path, "wb") as f:
            f.write(video_bytes)
        try:
            res = subprocess.run(
                [_FFMPEG_EXE, "-i", path],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            match = re.search(r"Video:.*?(\d{3,4})x(\d{3,4})", res.stderr)
            if match:
                w, h = match.groups()
                return int(w), int(h)
        except (
            ValueError,
            RuntimeError,
            KeyError,
            TypeError,
            OSError,
            IOError,
        ):
            pass
    return 1920, 1080


def hard_concat_clips(clip_bytes_list: list[bytes]) -> bytes | None:
    """Concatenate video clips using the ffmpeg concat demuxer.

    All clips must have matching resolution, codecs, and stream layout.
    Use probe_video_resolution + generate_title_card(width, height) upstream
    to ensure title cards match scene clip dimensions.
    """
    if not clip_bytes_list:
        return None
    if len(clip_bytes_list) == 1:
        return clip_bytes_list[0]

    with tempfile.TemporaryDirectory() as tmpdir:
        clip_paths = []
        for i, clip in enumerate(clip_bytes_list):
            path = os.path.join(tmpdir, f"clip_{i}.mp4")
            with open(path, "wb") as f:
                f.write(clip)
            clip_paths.append(path)

        list_file = os.path.join(tmpdir, "concat.txt")
        with open(list_file, "w", encoding="utf-8") as f:
            for p in clip_paths:
                f.write(f"file '{p}'\n")

        out_path = os.path.join(tmpdir, "output.mp4")
        # Attempt 1: Fast stream copy (zero re-encoding RAM)
        cmd_copy = [
            _FFMPEG_EXE,
            "-v",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_file,
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            out_path,
        ]
        result_copy = subprocess.run(
            cmd_copy, capture_output=True, timeout=60, check=False
        )
        if (
            result_copy.returncode == 0
            and os.path.exists(out_path)
            and os.path.getsize(out_path) > 0
        ):
            with open(out_path, "rb") as f:
                return f.read()

        # Attempt 2: Re-encode with limited threads and ultrafast preset
        cmd = [
            _FFMPEG_EXE,
            "-v",
            "warning",
            "-y",
            "-threads",
            "2",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_file,
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "28",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
            "-c:a",
            "aac",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            out_path,
        ]
        result = subprocess.run(
            cmd, capture_output=True, timeout=180, check=False
        )
        if result.returncode == 0 and os.path.exists(out_path):
            with open(out_path, "rb") as f:
                return f.read()
        print(
            f"[Concat] Failed: {result.stderr.decode(errors="replace")[-500:]}"
        )
        return None


# ============================================================
# FFmpeg Video Concatenation with Dissolve
# ============================================================


def concatenate_scenes_with_dissolve(
    clip_bytes_list: list[bytes],
    dissolve_duration: float = 0.5,
) -> bytes | None:
    """
    Concatenate video clips with dissolve (crossfade) transitions using
    ffmpeg xfade.
    Uses an iterative approach (combining 2 clips at a time) to prevent FFmpeg
    OOM crashes caused by chaining multiple xfade filters
    in a single filtergraph.
    """
    if not clip_bytes_list:
        return None
    if len(clip_bytes_list) == 1:
        return clip_bytes_list[0]

    def xfade_two_clips(
        clip1_bytes: bytes, clip2_bytes: bytes, out_path: str
    ) -> bool:
        with tempfile.TemporaryDirectory() as td:
            c1_path = os.path.join(td, "c1.mp4")
            c2_path = os.path.join(td, "c2.mp4")
            with open(c1_path, "wb") as f:
                f.write(clip1_bytes)
            with open(c2_path, "wb") as f:
                f.write(clip2_bytes)

            c1_dur = probe_media_duration(c1_path, 8.0)
            c2_dur = probe_media_duration(c2_path, 8.0)

            if c1_dur < 1.0 or c2_dur < 1.0:
                filter_complex = (
                    "[0:v]scale=1920:1080:"
                    "force_original_aspect_ratio=decrease,"
                    "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p,"
                    "setsar=1,fps=30[v0];"
                    "[1:v]scale=1920:1080:"
                    "force_original_aspect_ratio=decrease,"
                    "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p,"
                    "setsar=1,fps=30[v1];"
                    "[0:a]aformat=sample_rates=48000:"
                    "channel_layouts=stereo[a0];"
                    "[1:a]aformat=sample_rates=48000:"
                    "channel_layouts=stereo[a1];"
                    "[v0][a0][v1][a1]concat=n=2:v=1:a=1[vout][aout]"
                )
                subprocess.run(
                    [
                        _FFMPEG_EXE,
                        "-v",
                        "warning",
                        "-y",
                        "-threads",
                        "2",
                        "-i",
                        c1_path,
                        "-i",
                        c2_path,
                        "-filter_complex",
                        filter_complex,
                        "-map",
                        "[vout]",
                        "-map",
                        "[aout]",
                        "-c:v",
                        "libx264",
                        "-c:a",
                        "aac",
                        "-preset",
                        "ultrafast",
                        out_path,
                    ],
                    capture_output=True,
                    check=False,
                )
                return (
                    os.path.exists(out_path) and os.path.getsize(out_path) > 0
                )

            offset = max(0.0, c1_dur - dissolve_duration)

            # Single-pass xfade with synchronized video and audio
            single_pass_filter = (
                f"[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
                f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,"
                f"format=yuv420p,setsar=1,fps=30[v0];"
                f"[1:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
                f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,"
                f"format=yuv420p,setsar=1,fps=30[v1];"
                f"[v0][v1]xfade=transition=fade:duration={dissolve_duration}:"
                f"offset={offset:.3f}[vout];"
                f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo[a0];"
                f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo[a1];"
                f"[a0][a1]acrossfade=d={dissolve_duration}[aout]"
            )

            cmd_single = [
                _FFMPEG_EXE,
                "-v",
                "warning",
                "-y",
                "-threads",
                "2",
                "-i",
                c1_path,
                "-i",
                c2_path,
                "-filter_complex",
                single_pass_filter,
                "-map",
                "[vout]",
                "-map",
                "[aout]",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "26",
                "-c:a",
                "aac",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                out_path,
            ]

            try:
                res = subprocess.run(
                    cmd_single, capture_output=True, timeout=60, check=False
                )
                if (
                    res.returncode == 0
                    and os.path.exists(out_path)
                    and os.path.getsize(out_path) > 0
                ):
                    return True
            except (
                ValueError,
                RuntimeError,
                KeyError,
                TypeError,
                OSError,
                IOError,
            ) as e:
                print(f"[Dissolve] Single-pass xfade warning: {e}", flush=True)

            # Robust fallback: standard concat with stereo audio
            filter_complex = (
                "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
                "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,"
                "format=yuv420p,setsar=1,fps=30[v0];"
                "[1:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
                "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,"
                "format=yuv420p,setsar=1,fps=30[v1];"
                "[0:a]aformat=sample_rates=48000:channel_layouts=stereo[a0];"
                "[1:a]aformat=sample_rates=48000:channel_layouts=stereo[a1];"
                "[v0][a0][v1][a1]concat=n=2:v=1:a=1[vout][aout]"
            )
            res = subprocess.run(
                [
                    _FFMPEG_EXE,
                    "-v",
                    "warning",
                    "-y",
                    "-threads",
                    "2",
                    "-i",
                    c1_path,
                    "-i",
                    c2_path,
                    "-filter_complex",
                    filter_complex,
                    "-map",
                    "[vout]",
                    "-map",
                    "[aout]",
                    "-c:v",
                    "libx264",
                    "-c:a",
                    "aac",
                    "-preset",
                    "ultrafast",
                    out_path,
                ],
                capture_output=True,
                check=False,
            )
            if (
                res.returncode == 0
                and os.path.exists(out_path)
                and os.path.getsize(out_path) > 0
            ):
                return True

            # Ultimate fallback: stream copy concat
            list_f = os.path.join(td, "c_list.txt")
            with open(list_f, "w", encoding="utf-8") as lf:
                lf.write(f"file '{c1_path}'\nfile '{c2_path}'\n")
            res_c = subprocess.run(
                [
                    _FFMPEG_EXE,
                    "-v",
                    "error",
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    list_f,
                    "-c",
                    "copy",
                    out_path,
                ],
                capture_output=True,
                check=False,
            )
            return (
                res_c.returncode == 0
                and os.path.exists(out_path)
                and os.path.getsize(out_path) > 0
            )

    current_clip = clip_bytes_list[0]
    with tempfile.TemporaryDirectory() as main_td:
        for i, next_clip in enumerate(clip_bytes_list[1:]):
            out_path = os.path.join(main_td, f"step_{i}.mp4")
            success = xfade_two_clips(current_clip, next_clip, out_path)
            if not success or not os.path.exists(out_path):
                print(
                    f"[Assembly] Iterative assembly failed at step {i}",
                    flush=True,
                )
                return None
            with open(out_path, "rb") as f:
                current_clip = f.read()

    return current_clip


def add_background_music_to_final(
    video_bytes: bytes,
    music_bytes: bytes,
    music_volume: float = 0.20,
) -> bytes:
    """
    Layer background music at subtle volume across the full final video,
    preserving full voiceover clarity and volume.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        vid_path = os.path.join(tmpdir, "video.mp4")
        music_path = os.path.join(tmpdir, "music.wav")
        out_path = os.path.join(tmpdir, "output.mp4")

        with open(vid_path, "wb") as f:
            f.write(video_bytes)
        with open(music_path, "wb") as f:
            f.write(music_bytes)

        video_duration = probe_media_duration(vid_path, 24.0)
        has_audio = check_video_has_audio(vid_path)

        if has_audio:
            filter_complex = (
                f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo,"
                f"volume=1.4[vo];"
                f"[1:a]atrim=0:{video_duration},asetpts=PTS-STARTPTS,"
                f"aresample=48000,volume={music_volume},"
                "afade=t=in:st=0:d=1.0,"
                f"afade=t=out:st={max(0, video_duration - 1.5)}:d=1.5[music];"
                f"[vo][music]amix=inputs=2:duration=first:dropout_transition=0:"
                f"normalize=0,"
                f"atrim=0:{video_duration},asetpts=PTS-STARTPTS[aout]"
            )
        else:
            filter_complex = (
                f"[1:a]atrim=0:{video_duration},asetpts=PTS-STARTPTS,"
                f"aresample=48000,volume={music_volume},"
                "afade=t=in:st=0:d=1.0,"
                f"afade=t=out:st={max(0, video_duration - 1.5)}:d=1.5[aout]"
            )

        cmd = [
            _FFMPEG_EXE,
            "-v",
            "warning",
            "-y",
            "-threads",
            "2",
            "-i",
            vid_path,
            "-stream_loop",
            "-1",
            "-i",
            music_path,
            "-filter_complex",
            filter_complex,
            "-map",
            "0:v",
            "-map",
            "[aout]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-t",
            str(video_duration),
            "-movflags",
            "+faststart",
            out_path,
        ]

        result = subprocess.run(
            cmd, capture_output=True, timeout=120, check=False
        )
        if result.returncode == 0 and os.path.exists(out_path):
            with open(out_path, "rb") as f:
                return f.read()
        return video_bytes


# ============================================================
# Full Pipeline
# ============================================================


async def generate_video_ad(
    scenes: list[dict],
    company_name: str = "",
    brand_context: str = "",
    voice_name: str = "Charon",
    video_model: str = "omni",
    enable_music: bool = True,
    music_volume: float = 0.35,
    logo_bytes: bytes | None = None,
) -> dict:
    """Full video ad pipeline.

    Args:
        scenes: List of dicts with image_bytes, voiceover_text, scene_number.
        company_name: Brand/company name.
        brand_context: Additional brand context for music generation.
        voice_name: Chirp3-HD voice name (e.g. "Charon", "Aoede"). See
        GEMINI_TTS_VOICES.
        video_model: "omni" or "veo".
        enable_music: Whether to add Lyria background music.
        music_volume: Volume level for background music (0.0 to 1.0).
        logo_bytes: Optional PNG logo to overlay on top-right corner of final
        video.

    Returns:
        Dict with scene_clips (list of bytes), final_video (bytes), and status
        info.
    """
    gen_fn = (
        generate_scene_video
        if video_model == "omni"
        else generate_scene_video_veo
    )

    # Step 1: Generate all scene video clips in parallel (visual only)
    clip_tasks = [
        gen_fn(
            image_bytes=s["image_bytes"],
            voiceover_text=s["voiceover_text"],
            scene_number=s["scene_number"],
            company_name=company_name,
            brand_context=brand_context,
        )
        for s in scenes
    ]
    scene_clips = await asyncio.gather(*clip_tasks, return_exceptions=False)

    # Step 2: Generate voiceovers in parallel
    scripts = [s["voiceover_text"] for s in scenes]
    voiceovers = await generate_all_voiceovers(scripts, voice_name)

    # Step 3: Generate background music if enabled
    music_bytes = None
    if enable_music:
        music_bytes = await generate_background_music(
            company_name,
            scripts,
            brand_context,
        )

    pad_before = 0.5
    pad_after = 0.5
    mixed_clips = []
    for clip, vo in zip(scene_clips, voiceovers):
        if clip is None:
            mixed_clips.append(None)
            continue
        if vo is not None:
            clip = trim_clip_to_voiceover(clip, vo, pad_before, pad_after)
        mixed = mix_scene_audio(clip, vo, None, vo_delay=pad_before)
        mixed_clips.append(mixed)

    # Step 5: Concatenate with dissolve transitions
    valid_clips = [c for c in mixed_clips if c is not None]
    if not valid_clips:
        return {"status": "error", "details": "No video clips were generated."}

    final_video = concatenate_scenes_with_dissolve(valid_clips)
    if final_video is None:
        return {"status": "error", "details": "Failed to concatenate clips."}

    # Step 6: Layer background music across full video
    if music_bytes and enable_music:
        final_video = add_background_music_to_final(
            final_video, music_bytes, music_volume
        )

    # Step 7: Overlay logo on top-right corner
    if logo_bytes:
        final_video = overlay_logo_and_tagline_on_video(final_video, logo_bytes)

    return {
        "status": "success",
        "scene_clips": mixed_clips,
        "final_video": final_video,
        "num_scenes": len(scenes),
        "music_enabled": enable_music,
    }


# ============================================================
# GE / Agent Engine Integration — Tool Wrappers
# ============================================================

GOOGLE_CLOUD_BUCKET_ARTIFACTS = os.environ.get(
    "GOOGLE_CLOUD_BUCKET_ARTIFACTS", ""
)


async def list_voices(
    _tool_context: ToolContext,
    gender: str = "",
) -> dict:
    """
    List all available Chirp3-HD voices for voiceover. Optionally filter by
    gender.

    Args:
        gender: Filter by "male" or "female". Leave empty to show all voices.
    """
    print(f"[Tool] list_voices called, gender={gender}", flush=True)
    gender = gender.strip().lower()
    if gender in ("male", "m"):
        voices = {"male": GEMINI_TTS_VOICES["male"]}
    elif gender in ("female", "f"):
        voices = {"female": GEMINI_TTS_VOICES["female"]}
    else:
        voices = GEMINI_TTS_VOICES

    return {
        "voices": voices,
        "recommended": {"male": "Charon", "female": "Aoede"},
        "tip": "Call preview_voice with a voice name to hear a sample.",
    }


def _create_voice_card_png(voice_name: str, number: int, gender: str) -> bytes:
    """Create a styled PNG card for an individual voice preview video frame."""
    w, h = 320, 180
    img = Image.new("RGB", (w, h), color=(30, 30, 40))
    draw = ImageDraw.Draw(img)

    try:
        font_path = _find_font()
        title_font = (
            ImageFont.truetype(font_path, 28)
            if font_path
            else ImageFont.load_default()
        )
        sub_font = (
            ImageFont.truetype(font_path, 16)
            if font_path
            else ImageFont.load_default()
        )
    except (OSError, IOError):
        title_font = ImageFont.load_default()
        sub_font = ImageFont.load_default()

    accent = (100, 180, 255) if gender == "male" else (255, 130, 180)
    draw.rectangle([(0, 0), (w, 4)], fill=accent)
    draw.rectangle([(0, h - 4), (w, h)], fill=accent)

    title = f"{number}. {voice_name}"
    bbox = draw.textbbox((0, 0), title, font=title_font)
    tw = bbox[2] - bbox[0]
    draw.text(((w - tw) // 2, 50), title, fill="white", font=title_font)

    label = f"{gender.capitalize()} Voice"
    bbox2 = draw.textbbox((0, 0), label, font=sub_font)
    lw = bbox2[2] - bbox2[0]
    draw.text(((w - lw) // 2, 95), label, fill=(180, 180, 180), font=sub_font)

    play_hint = "Press play to listen"
    bbox3 = draw.textbbox((0, 0), play_hint, font=sub_font)
    pw = bbox3[2] - bbox3[0]
    draw.text(((w - pw) // 2, 130), play_hint, fill=accent, font=sub_font)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _create_voice_catalog_png(gender: str) -> bytes:
    """
    Create a compact grid catalog image showing all voices for the given
    gender."""
    voices = GEMINI_TTS_VOICES[gender]
    cols = 4
    rows = (len(voices) + cols - 1) // cols

    cell_w, cell_h = 210, 52
    pad = 8
    header_h = 48

    w = cols * cell_w + (cols + 1) * pad
    h = header_h + rows * cell_h + (rows + 1) * pad + 4

    img = Image.new("RGB", (w, h), color=(25, 25, 35))
    draw = ImageDraw.Draw(img)

    font_path = _find_font()
    try:
        header_font = (
            ImageFont.truetype(font_path, 22)
            if font_path
            else ImageFont.load_default()
        )
        num_font = (
            ImageFont.truetype(font_path, 18)
            if font_path
            else ImageFont.load_default()
        )
        name_font = (
            ImageFont.truetype(font_path, 16)
            if font_path
            else ImageFont.load_default()
        )
    except (OSError, IOError):
        header_font = ImageFont.load_default()
        num_font = ImageFont.load_default()
        name_font = ImageFont.load_default()

    accent = (100, 180, 255) if gender == "male" else (255, 130, 180)

    draw.rectangle([(0, 0), (w, 3)], fill=accent)
    title_text = f"{gender.capitalize()} Voices"
    draw.text((pad, 10), title_text, fill="white", font=header_font)
    hint = "Type number to preview"
    bbox_h = draw.textbbox((0, 0), hint, font=name_font)
    draw.text(
        (w - (bbox_h[2] - bbox_h[0]) - pad, 14),
        hint,
        fill=(130, 130, 140),
        font=name_font,
    )

    for i, voice in enumerate(voices):
        row = i // cols
        col = i % cols
        x = pad + col * (cell_w + pad)
        y = header_h + pad + row * (cell_h + pad)

        draw.rectangle(
            [(x, y), (x + cell_w, y + cell_h)],
            fill=(40, 40, 55),
            outline=(60, 60, 80),
        )

        num = str(i + 1)
        draw.rectangle(
            [(x + 6, y + 10), (x + 36, y + cell_h - 10)], fill=accent
        )
        bbox_n = draw.textbbox((0, 0), num, font=num_font)
        nw = bbox_n[2] - bbox_n[0]
        draw.text((x + 21 - nw // 2, y + 13), num, fill="white", font=num_font)

        draw.text((x + 44, y + 15), voice, fill="white", font=name_font)

    draw.rectangle([(0, h - 3), (w, h)], fill=accent)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _wrap_mp3_as_mp4(mp3_bytes: bytes, card_png_bytes: bytes) -> bytes | None:
    """
    Combine a static PNG card with MP3 audio into an MP4 video using
    FFmpeg."""
    initialize_ffmpeg_if_needed()
    with tempfile.TemporaryDirectory() as tmpdir:
        card_path = os.path.join(tmpdir, "card.png")
        mp3_path = os.path.join(tmpdir, "audio.mp3")
        out_path = os.path.join(tmpdir, "preview.mp4")

        with open(card_path, "wb") as f:
            f.write(card_png_bytes)
        with open(mp3_path, "wb") as f:
            f.write(mp3_bytes)

        cmd = [
            _FFMPEG_EXE,
            "-y",
            "-loop",
            "1",
            "-i",
            card_path,
            "-i",
            mp3_path,
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-ar",
            "44100",
            "-ac",
            "2",
            "-shortest",
            "-movflags",
            "+faststart",
            out_path,
        ]
        result = subprocess.run(
            cmd, capture_output=True, timeout=30, check=False
        )
        if result.returncode != 0:
            print(f"FFmpeg wrap error: {result.stderr.decode()[-300:]}")
            return None

        with open(out_path, "rb") as f:
            return f.read()


def _load_voice_preview_mp4(
    gender: str, number: int, voice_name: str
) -> bytes | None:
    """
    Load a voice preview MP4 — from GCS cache or by wrapping the MP3
    on-the-fly."""
    # Try pre-built MP4 first
    for mp4_path in [
        f"video_ads/previews/{gender}/{number}_{voice_name}.mp4",
        f"video_ads/previews/{number}_{voice_name}.mp4",
    ]:
        try:
            return utils_gcs.download_blob_to_bytes(
                GOOGLE_CLOUD_BUCKET_ARTIFACTS, mp4_path
            )
        except (
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OSError,
            RuntimeError,
        ):
            pass

    # Fall back: download MP3 and wrap as MP4 on-the-fly
    for mp3_path in [
        f"video_ads/previews/{number}_{voice_name}.mp3",
        f"video_ads/previews/{gender}/{number}_{voice_name}.mp3",
    ]:
        try:
            mp3_bytes = utils_gcs.download_blob_to_bytes(
                GOOGLE_CLOUD_BUCKET_ARTIFACTS, mp3_path
            )
            if mp3_bytes:
                card_png = _create_voice_card_png(voice_name, number, gender)
                mp4_bytes = _wrap_mp3_as_mp4(mp3_bytes, card_png)
                if mp4_bytes:
                    print(
                        f"Voice preview {voice_name}: wrapped MP3→MP4"
                        f" on-the-fly ({len(mp4_bytes)//1024} KB)"
                    )
                    return mp4_bytes
        except (
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OSError,
            RuntimeError,
        ) as e:
            print(
                f"Voice preview {voice_name}: MP3"
                f" load failed from {mp3_path}: {e}"
            )

    return None


async def preview_voice(
    tool_context: ToolContext,
    voice_name: str,
    gender: str = "",
    emotion: str = "Energetic",
    speaking_rate: float = 1.0,
) -> dict:
    """
    Preview a single voice inline. Accepts a voice name or number. Downloads
    from GCS, wraps as MP4, and displays as inline artifact.

    Args:
        voice_name: The voice name (e.g. "Charon") or number (e.g. "5") to
        preview.
        gender: Required when using a number. "male" or "female".
        emotion: Emotion or style for the voice (e.g., "Energetic", Default is
        "Professional"). "Energetic".
        speaking_rate: Voice speed (e.g., 1.0).
    """
    # Support numeric lookup: "5" → voice #5
    if voice_name.strip().isdigit():
        num = int(voice_name.strip())
        gender = (
            (gender or tool_context.state.get("va_voice_gender", ""))
            .strip()
            .lower()
        )
        if gender not in ("male", "female"):
            return {
                "status": "error",
                "details": (
                    "Provide gender ('male' or"
                    " 'female') when using a number."
                ),
            }
        voices = GEMINI_TTS_VOICES[gender]
        if num < 1 or num > len(voices):
            return {
                "status": "error",
                "details": (
                    f"Number {num} out of range. {gender} has"
                    f" {len(voices)} voices (1-{len(voices)})."
                ),
            }
        voice_name = voices[num - 1]
        number = num
    else:
        all_voices = GEMINI_TTS_VOICES["male"] + GEMINI_TTS_VOICES["female"]
        if voice_name not in all_voices:
            return {
                "status": "error",
                "details": (
                    f"Unknown voice '{voice_name}'. Use"
                    f" list_voices to see available voices."
                ),
            }
        gender = "male" if voice_name in GEMINI_TTS_VOICES["male"] else "female"
        voices = GEMINI_TTS_VOICES[gender]
        number = voices.index(voice_name) + 1

    mp4_bytes = None
    if emotion.lower() == "energetic" and speaking_rate == 1.0:
        mp4_bytes = _load_voice_preview_mp4(gender, number, voice_name)

    if not mp4_bytes:
        mp3_bytes = await generate_voice_preview(
            voice_name, emotion=emotion, speaking_rate=speaking_rate
        )
        if mp3_bytes:
            card_png = _create_voice_card_png(voice_name, number, gender)
            mp4_bytes = _wrap_mp3_as_mp4(mp3_bytes, card_png)

    if not mp4_bytes:
        return {
            "status": "error",
            "details": (
                f"Voice preview failed for {voice_name}"
                f" with emotion '{emotion}'."
            ),
        }

    preview_media = GeneratedMedia(
        filename=f"voice_preview_{number}_{voice_name}.mp4",
        mime_type="video/mp4",
        media_bytes=mp4_bytes,
    )
    await utils_agents.save_to_artifact_and_render_asset(
        asset=preview_media,
        context=tool_context,
        save_in_gcs=False,
        save_in_artifacts=True,
    )

    return {
        "status": "played",
        "voice_name": voice_name,
        "number": number,
        "gender": gender,
    }


async def preview_all_voices(
    tool_context: ToolContext,
    gender: str,
) -> dict:
    """
    Show a formatted text list of available voices for the selected gender,
    then let the user type a number to hear individual previews.

    Args:
        gender: "male" or "female".
    """
    gender = gender.strip().lower()
    if gender not in ("male", "female"):
        return {
            "status": "error",
            "details": "Gender must be 'male' or 'female'.",
        }

    tool_context.state["va_voice_gender"] = gender
    voices = GEMINI_TTS_VOICES[gender]

    voice_lines = [f"{i + 1} - {v}" for i, v in enumerate(voices)]
    recommended = "Charon" if gender == "male" else "Aoede"
    rec_num = voices.index(recommended) + 1 if recommended in voices else 1

    return {
        "status": "completed",
        "gender": gender,
        "total_voices": len(voices),
        "voice_list": voice_lines,
        "formatted_catalog": "\n".join(voice_lines),
        "recommended": f"{rec_num} - {recommended}",
        "instruction": f"Here are all the {gender} voices:\n\n"
        + "\n".join(voice_lines)
        + f"\n\nType a number (1-{len(voices)}) to hear a voice preview. "
        f"I recommend {rec_num} {recommended}.",
        "next_step": (
            f"Type a number to preview, or type"
            f" '{rec_num}' for {recommended}."
        ),
        "CRITICAL_RULE_FOR_AGENT": (
            "If the user types a number or asks for a preview, you MUST"
            " immediately call the `preview_voice` "
            "tool. Do NOT skip this tool call!"
        ),
    }


async def load_images_from_bucket(
    tool_context: ToolContext,
    bucket_uri: str,
) -> dict:
    """
    List all images from a GCS bucket, display them numbered inline for user
    to review.

    Skips logo files and subfolder contents. Shows images for user to confirm
    before assigning to scenes.
    After this, the agent should ask the user to confirm or remove images by
    number.

    Args:
        bucket_uri: GCS URI of the bucket or folder (e.g. "gs://my-bucket" or "gs://my-bucket/images/").
    """
    session_folder = tool_context.state.get(
        "va_session_folder", "video_ads/default"
    )

    gs_uri = utils_gcs.normalize_to_gs_bucket_uri(bucket_uri)
    bucket_name, prefix = utils_gcs.parse_gcs_url(gs_uri)

    storage_client = storage.Client(project=GOOGLE_CLOUD_PROJECT)
    blobs = storage_client.list_blobs(
        bucket_name, prefix=prefix if prefix else None, delimiter="/"
    )

    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}
    SKIP_KEYWORDS = {"logo", "icon", "favicon", "watermark"}
    image_blobs = []
    for blob in blobs:
        if blob.name.endswith("/"):
            continue
        if "/" in blob.name.replace(prefix or "", "", 1).lstrip("/"):
            continue
        ext = os.path.splitext(blob.name)[1].lower()
        if ext not in IMAGE_EXTENSIONS:
            continue
        name_lower = os.path.splitext(os.path.basename(blob.name))[0].lower()
        if any(kw in name_lower for kw in SKIP_KEYWORDS):
            continue
        image_blobs.append(blob)

    if not image_blobs:
        fmts = ", ".join(IMAGE_EXTENSIONS)
        return {
            "status": "error",
            "details": (
                f"No scene image files found in {bucket_uri}. Supported"
                f" formats: {fmts}"
            ),
        }

    image_blobs.sort(key=lambda b: b.name)

    candidates = []
    for i, blob in enumerate(image_blobs):
        number = i + 1
        image_uri = f"gs://{bucket_name}/{blob.name}"

        try:
            image_bytes = blob.download_as_bytes()
        except (
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OSError,
            RuntimeError,
        ) as e:
            candidates.append(
                {
                    "number": number,
                    "name": blob.name,
                    "status": "failed",
                    "error": str(e),
                }
            )
            continue

        image_media = GeneratedMedia(
            filename=f"{number}_{os.path.basename(blob.name)}",
            mime_type=blob.content_type or "image/png",
            media_bytes=image_bytes,
        )
        await utils_agents.save_to_artifact_and_render_asset(
            asset=image_media,
            context=tool_context,
            gcs_folder=session_folder,
            save_in_gcs=False,
            save_in_artifacts=True,
        )

        candidates.append(
            {
                "number": number,
                "name": blob.name,
                "uri": image_uri,
                "status": "previewed",
            }
        )

    tool_context.state["va_image_candidates"] = [
        {"number": c["number"], "name": c["name"], "uri": c.get("uri", "")}
        for c in candidates
        if c["status"] == "previewed"
    ]

    return {
        "status": "previewed",
        "images_found": len(candidates),
        "images": [
            {"number": c["number"], "name": c["name"]} for c in candidates
        ],
        "next_step": (
            "Images are displayed above with numbers. Ask "
            "the user: 'All images look good for video"
            " generation? Type **all** to use all, or type "
            "the numbers to **remove** (e.g. remove 3, 5).'"
        ),
    }


async def confirm_images(
    tool_context: ToolContext,
    remove_numbers: list[int] | None = None,
) -> dict:
    """
    Confirm which images to use for scenes after user reviews the previews
    from load_images_from_bucket.

    Args:
        remove_numbers: List of image numbers to SKIP (e.g. [3, 5]). Pass empty
        list or None to use all.
    """
    print(f"[Tool] confirm_images called, remove={remove_numbers}", flush=True)
    candidates = tool_context.state.get("va_image_candidates", [])
    if not candidates:
        return {
            "status": "error",
            "details": (
                "No image candidates found. Call"
                " load_images_from_bucket first."
            ),
        }

    remove_set = set(remove_numbers or [])
    kept = [c for c in candidates if c["number"] not in remove_set]

    if not kept:
        return {
            "status": "error",
            "details": "All images were removed. Provide images again.",
        }

    num_scenes = tool_context.state.get("va_num_scenes", len(kept))
    if len(kept) != num_scenes:
        tool_context.state["va_num_scenes"] = len(kept)

    session_folder = tool_context.state.get(
        "va_session_folder", "video_ads/default"
    )
    stored = []
    for i, candidate in enumerate(kept):
        scene_number = i + 1
        try:
            image_bytes = utils_gcs.download_bytes_from_gcs(candidate["uri"])
            if not image_bytes:
                stored.append(
                    {"scene_number": scene_number, "status": "failed"}
                )
                continue
        except (
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OSError,
            RuntimeError,
        ) as e:
            stored.append(
                {
                    "scene_number": scene_number,
                    "status": "failed",
                    "error": str(e),
                }
            )
            continue

        dest_filename = f"scene_{scene_number}.png"
        dest_uri = utils_gcs.upload_to_gcs(
            bucket_path=f"{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{session_folder}",
            file_bytes=image_bytes,
            destination_blob_name=dest_filename,
        )
        tool_context.state[f"va_scene_{scene_number}_image_uri"] = dest_uri
        stored.append(
            {
                "scene_number": scene_number,
                "status": "stored",
                "source": candidate["name"],
            }
        )

    try:
        del tool_context.state["va_image_candidates"]
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OSError,
        RuntimeError,
    ):
        tool_context.state["va_image_candidates"] = []

    return {
        "status": "completed",
        "scenes_assigned": len([s for s in stored if s["status"] == "stored"]),
        "num_scenes": len(kept),
        "scenes": stored,
        "removed": list(remove_set) if remove_set else None,
        "next_step": (
            "All scene images assigned. Now generate voiceover scripts — say"
            " **`'ai'`** for AI-generated or provide "
            "your own as 1- ..., 2- ..., etc."
        ),
    }


async def save_uploaded_image(
    tool_context: ToolContext,
    scene_number: int,
    image_data_base64: str = "",
    filename: str = "uploaded_image.png",
) -> dict:
    """
    Save an image that was uploaded directly in the chat to GCS and assign it
    to a scene.

    Use this when the user uploads images directly instead of providing GCS
    URIs.

    Args:
        scene_number: Scene number (1-based) to assign this image to.
        image_data_base64: Base64-encoded image data.
        filename: Original filename or artifact identifier of the uploaded
        image.
    """
    num_scenes = tool_context.state.get("va_num_scenes", 3)
    if scene_number < 1 or scene_number > num_scenes:
        return {
            "status": "error",
            "details": f"Scene number must be between 1 and {num_scenes}",
        }

    session_folder = tool_context.state.get(
        "va_session_folder", "video_ads/default"
    )
    image_bytes = None

    if image_data_base64:
        try:
            image_bytes = base64.b64decode(image_data_base64)
        except (
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OSError,
            RuntimeError,
        ) as e:
            print(f"[Save Uploaded Image] Base64 decode error: {e}")

    if not image_bytes and filename:
        try:
            res = await utils_agents.load_resource(filename, tool_context)
            if res and res.media_bytes:
                image_bytes = res.media_bytes
        except (
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OSError,
            RuntimeError,
        ) as e:
            print(
                f"[Save Uploaded Image] load_resource error for {filename}: {e}"
            )

    if not image_bytes:
        return {
            "status": "error",
            "details": f"Could not load image data for scene {scene_number}.",
        }

    # Normalize image to clean PNG (converts WebP, JPEG, etc. to clean RGB PNG)
    image_bytes = ensure_png_bytes(image_bytes)

    dest_filename = f"scene_{scene_number}.png"
    gcs_uri = utils_gcs.upload_to_gcs(
        bucket_path=f"{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{session_folder}",
        file_bytes=image_bytes,
        destination_blob_name=dest_filename,
    )
    tool_context.state[f"va_scene_{scene_number}_image_uri"] = gcs_uri

    image_media = GeneratedMedia(
        filename=f"scene_{scene_number}_image.png",
        mime_type="image/png",
        media_bytes=image_bytes,
    )
    await utils_agents.save_to_artifact_and_render_asset(
        asset=image_media,
        context=tool_context,
        gcs_folder=session_folder,
        save_in_gcs=True,
        save_in_artifacts=True,
    )

    stored_count = sum(
        1
        for i in range(1, num_scenes + 1)
        if tool_context.state.get(f"va_scene_{i}_image_uri")
    )
    return {
        "status": "stored",
        "scene_number": scene_number,
        "images_stored": f"{stored_count}/{num_scenes}",
        "next_step": (
            "All images stored. Now provide voiceover scripts."
            if stored_count == num_scenes
            else "Provide images for remaining scenes."
        ),
    }


DEFAULT_LOGO_GCS_URI = (
    "gs://your-project-id-video-ads-artifacts/google_logo.png"
)


async def show_default_logo(tool_context: ToolContext) -> dict:
    """
    Display the default logo so the user can see it before choosing. Shows
    the logo inline."""
    session_folder = tool_context.state.get(
        "va_session_folder", "video_ads/default"
    )
    try:
        logo_bytes = utils_gcs.download_bytes_from_gcs(DEFAULT_LOGO_GCS_URI)
        if not logo_bytes:
            return {
                "status": "error",
                "details": "Could not download default logo.",
            }

        logo_media = GeneratedMedia(
            filename="default_logo.png",
            mime_type="image/png",
            media_bytes=logo_bytes,
        )
        await utils_agents.save_to_artifact_and_render_asset(
            asset=logo_media,
            context=tool_context,
            gcs_folder=session_folder,
            save_in_gcs=False,
            save_in_artifacts=True,
        )
        return {
            "status": "displayed",
            "logo_uri": DEFAULT_LOGO_GCS_URI,
            "next_step": "Say 'default' to use this logo, or provide your own logo GCS path (e.g. gs://bucket/logo.png).",
        }
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OSError,
        RuntimeError,
    ) as e:
        return {
            "status": "error",
            "details": f"Failed to load default logo: {e}",
        }


async def store_logo(
    tool_context: ToolContext,
    logo_gcs_uri: str = "",
    logo_data_base64: str = "",
    filename: str = "",
    use_default: bool = False,
) -> dict:
    """Store the brand logo for the final video overlay.

    Call this when the user chooses the default logo, provides a GCS URI for a
    logo, or uploads a logo file directly in chat.

    Args:
        logo_gcs_uri: GCS URI (e.g. gs://bucket/logo.png), HTTP URL, or logo
        uploaded filename/artifact identifier.
        logo_data_base64: Base64-encoded logo image data if uploaded directly
        in chat.
        filename: Original filename of the uploaded logo image.
        use_default: If True, use the default Google logo.
    """
    session_folder = tool_context.state.get(
        "va_session_folder", "video_ads/default"
    )

    if use_default:
        tool_context.state["va_logo_uri"] = DEFAULT_LOGO_GCS_URI
        return {
            "status": "stored",
            "logo_uri": DEFAULT_LOGO_GCS_URI,
            "is_default": True,
        }

    logo_bytes = None

    if logo_data_base64:
        try:
            logo_bytes = base64.b64decode(logo_data_base64)
        except (
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OSError,
            RuntimeError,
        ) as e:
            print(f"[Store Logo] Base64 decode failed: {e}")

    target_uri = logo_gcs_uri or filename
    if not logo_bytes and target_uri:
        if (
            target_uri.startswith("gs://")
            or target_uri.startswith("http://")
            or target_uri.startswith("https://")
        ):
            try:
                logo_bytes, _ = utils_agents.download_bytes_from_reference(
                    target_uri
                )
            except (
                ValueError,
                TypeError,
                KeyError,
                AttributeError,
                OSError,
                RuntimeError,
            ) as e:
                print(
                    f"[Store Logo] Download from"
                    f" reference {target_uri} failed: {e}"
                )

    if not logo_bytes and target_uri:
        try:
            res = await utils_agents.load_resource(target_uri, tool_context)
            if res and res.media_bytes:
                logo_bytes = res.media_bytes
        except (
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OSError,
            RuntimeError,
        ) as e:
            print(f"[Store Logo] load_resource for {target_uri} failed: {e}")

    if not logo_bytes:
        for cand in [
            "uploaded_logo.png",
            "logo.png",
            "image.png",
            "input_file_0.png",
            "user_file.png",
        ]:
            try:
                res = await utils_agents.load_resource(cand, tool_context)
                if res and res.media_bytes:
                    logo_bytes = res.media_bytes
                    break
            except (
                ValueError,
                TypeError,
                KeyError,
                AttributeError,
                OSError,
                RuntimeError,
            ):
                pass

    if not logo_bytes:
        return {
            "status": "error",
            "details": (
                "Could not retrieve logo image bytes. Please ensure"
                " the logo file was uploaded or provide a valid GCS URI."
            ),
        }

    logo_bytes = ensure_png_bytes(logo_bytes)

    dest_filename = "brand_logo.png"
    gcs_uri = utils_gcs.upload_to_gcs(
        bucket_path=f"{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{session_folder}",
        file_bytes=logo_bytes,
        destination_blob_name=dest_filename,
    )
    tool_context.state["va_logo_uri"] = gcs_uri

    logo_media = GeneratedMedia(
        filename="brand_logo.png",
        mime_type="image/png",
        media_bytes=logo_bytes,
    )
    await utils_agents.save_to_artifact_and_render_asset(
        asset=logo_media,
        context=tool_context,
        gcs_folder=session_folder,
        save_in_gcs=False,
        save_in_artifacts=True,
    )

    return {
        "status": "stored",
        "logo_uri": gcs_uri,
        "is_default": False,
        "next_step": "Logo stored successfully.",
    }


async def setup_video_ad(
    tool_context: ToolContext,
    company_name: str,
    num_scenes: int = 3,
    brand_context: str = "",
    voice_name: str = "Charon",
    voice_emotion: str = "Energetic",
    video_model: str = "omni",
    enable_music: bool = True,
) -> dict:
    """
    Initialize a new video ad project. Call this first to set up the session.

    Args:
        company_name: The brand/company name for the video ad (required).
        num_scenes: Number of scenes (1-15, default 3).
        brand_context: Additional brand context or description.
        voice_name: Chirp3-HD voice name for voiceover (e.g. Charon, Aoede).
        video_model: Video generation model — "omni" (fast) or "veo"
        (cinematic).
        enable_music: Whether to add Lyria background music (default True).
    """
    print(
        f"[Tool] setup_video_ad called: company={company_name},"
        f" scenes={num_scenes}, model={video_model}",
        flush=True,
    )
    num_scenes = max(1, min(num_scenes, 12))

    session_id = utils_agents.get_or_create_unique_session_id(tool_context)
    session_folder = f"video_ads/{session_id}"

    tool_context.state["va_company_name"] = company_name
    tool_context.state["va_num_scenes"] = num_scenes
    tool_context.state["va_brand_context"] = brand_context
    tool_context.state["va_voice_name"] = voice_name
    tool_context.state["va_voice_emotion"] = voice_emotion
    tool_context.state["va_video_model"] = video_model
    tool_context.state["va_enable_music"] = enable_music
    tool_context.state["va_session_folder"] = session_folder

    max_words = MAX_WORDS_OMNI if video_model == "omni" else MAX_WORDS_VEO

    return {
        "status": "ready",
        "company_name": company_name,
        "num_scenes": num_scenes,
        "video_model": video_model,
        "voice_name": voice_name,
        "enable_music": enable_music,
        "max_words_per_script": max_words,
        "next_step": (
            f"Now provide {num_scenes} scene images "
            f"using store_scene_image (GCS URIs like"
            f" gs://bucket/path/image.png), then "
            f"voiceover scripts using store_scene_script."
        ),
    }


async def store_scene_image(
    tool_context: ToolContext,
    scene_number: int,
    image_gcs_uri: str,
) -> dict:
    """Store a scene image from a GCS URI. The image will be displayed inline.

    Args:
        scene_number: Scene number (1-based).
        image_gcs_uri: GCS URI of the scene image (e.g. gs://bucket/path/image.png).
    """
    num_scenes = tool_context.state.get("va_num_scenes", 3)
    if scene_number < 1 or scene_number > num_scenes:
        return {
            "status": "error",
            "details": f"Scene number must be between 1 and {num_scenes}",
        }

    session_folder = tool_context.state.get(
        "va_session_folder", "video_ads/default"
    )

    try:
        image_bytes = utils_gcs.download_bytes_from_gcs(image_gcs_uri)
        if not image_bytes:
            return {
                "status": "error",
                "details": f"Could not download image from {image_gcs_uri}",
            }
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OSError,
        RuntimeError,
    ) as e:
        return {"status": "error", "details": f"Failed to download image: {e}"}

    # Normalize image format to clean PNG
    image_bytes = ensure_png_bytes(image_bytes)

    dest_filename = f"scene_{scene_number}.png"
    gcs_uri = utils_gcs.upload_to_gcs(
        bucket_path=f"{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{session_folder}",
        file_bytes=image_bytes,
        destination_blob_name=dest_filename,
    )

    tool_context.state[f"va_scene_{scene_number}_image_uri"] = gcs_uri

    image_media = GeneratedMedia(
        filename=f"scene_{scene_number}_image.png",
        mime_type="image/png",
        media_bytes=image_bytes,
    )
    await utils_agents.save_to_artifact_and_render_asset(
        asset=image_media,
        context=tool_context,
        gcs_folder=session_folder,
        save_in_gcs=True,
        save_in_artifacts=True,
    )

    stored_count = sum(
        1
        for i in range(1, num_scenes + 1)
        if tool_context.state.get(f"va_scene_{i}_image_uri")
    )
    return {
        "status": "stored",
        "scene_number": scene_number,
        "images_stored": f"{stored_count}/{num_scenes}",
        "next_step": (
            "All images stored. Now provide voiceover scripts."
            if stored_count == num_scenes
            else "Provide images for remaining scenes."
        ),
    }


async def store_scene_script(
    tool_context: ToolContext,
    scene_number: int,
    voiceover_script: str,
) -> dict:
    """Store a voiceover script for a scene.

    Args:
        scene_number: Scene number (1-based).
        voiceover_script: The voiceover text for this scene (6-15 words
        recommended).
    """
    num_scenes = tool_context.state.get("va_num_scenes", 3)
    if scene_number < 1 or scene_number > num_scenes:
        return {
            "status": "error",
            "details": f"Scene number must be between 1 and {num_scenes}",
        }

    video_model = tool_context.state.get("va_video_model", "omni")
    max_words = MAX_WORDS_OMNI if video_model == "omni" else MAX_WORDS_VEO
    word_count = len(voiceover_script.split())

    tool_context.state[f"va_scene_{scene_number}_script"] = voiceover_script

    stored_count = sum(
        1
        for i in range(1, num_scenes + 1)
        if tool_context.state.get(f"va_scene_{i}_script")
    )
    warning = (
        f" WARNING: {word_count} words exceeds recommended max of {max_words}."
        if word_count > max_words
        else ""
    )

    return {
        "status": "stored",
        "scene_number": scene_number,
        "word_count": word_count,
        "max_words": max_words,
        "scripts_stored": f"{stored_count}/{num_scenes}",
        "warning": warning if warning else None,
        "next_step": (
            "All scripts stored. Ready to generate "
            "clips with generate_all_clips."
            if stored_count == num_scenes
            else "Provide scripts for remaining scenes."
        ),
    }


async def generate_ai_scripts(tool_context: ToolContext) -> dict:
    """
    Generate voiceover scripts for all scenes using AI (Gemini with Google
    Search).

    Requires scene images to be stored first via store_scene_image.
    Generates scripts, company tagline, and optimal scene order.
    """
    print("[Tool] generate_ai_scripts called", flush=True)
    num_scenes = tool_context.state.get("va_num_scenes", 3)
    company_name = tool_context.state.get("va_company_name", "")
    brand_context = tool_context.state.get("va_brand_context", "")
    video_model = tool_context.state.get("va_video_model", "omni")
    max_words = MAX_WORDS_OMNI if video_model == "omni" else MAX_WORDS_VEO

    scene_images = {}
    missing = []
    for i in range(1, num_scenes + 1):
        uri = tool_context.state.get(f"va_scene_{i}_image_uri")
        if uri:
            try:
                img_bytes = utils_gcs.download_bytes_from_gcs(uri)
                if img_bytes:
                    scene_images[i] = img_bytes
                else:
                    missing.append(i)
            except (
                ValueError,
                TypeError,
                KeyError,
                AttributeError,
                OSError,
                RuntimeError,
            ):
                missing.append(i)
        else:
            missing.append(i)

    if missing:
        return {
            "status": "error",
            "details": (
                f"Missing images for scenes: {missing}."
                f" Use store_scene_image first."
            ),
        }

    scripts, tagline, order = await generate_all_voiceover_scripts(
        scene_images, company_name, brand_context, max_words
    )

    for scene_num, script in scripts.items():
        tool_context.state[f"va_scene_{scene_num}_script"] = script

    tool_context.state["va_tagline"] = tagline
    tool_context.state["va_scene_order"] = order

    return {
        "status": "generated",
        "tagline": tagline,
        "scene_order": order,
        "scripts": {str(k): v for k, v in scripts.items()},
        "next_step": (
            "You MUST output all the generated scripts to the "
            "user right now in a numbered list! Ask the user"
            " to review them. Do NOT proceed or call generate_all_clips "
            "until the user explicitly approves them."
        ),
    }


async def generate_scene_clip(
    tool_context: ToolContext, scene_number: int
) -> dict:
    """
    Generate a video clip for a single scene. The clip will be displayed
    inline.

    Args:
        scene_number: Scene number (1-based) to generate.
    """
    num_scenes = tool_context.state.get("va_num_scenes", 3)
    if scene_number < 1 or scene_number > num_scenes:
        return {
            "status": "error",
            "details": f"Scene number must be between 1 and {num_scenes}",
        }

    image_uri = tool_context.state.get(f"va_scene_{scene_number}_image_uri")
    script = tool_context.state.get(f"va_scene_{scene_number}_script")
    if not image_uri:
        return {
            "status": "error",
            "details": (
                f"No image stored for scene {scene_number}."
                f" Use store_scene_image first."
            ),
        }
    if not script:
        return {
            "status": "error",
            "details": (
                f"No script stored for scene {scene_number}. Use"
                f" store_scene_script or generate_ai_scripts first."
            ),
        }

    company_name = tool_context.state.get("va_company_name", "")
    brand_context = tool_context.state.get("va_brand_context", "")
    video_model = tool_context.state.get("va_video_model", "omni")
    session_folder = tool_context.state.get(
        "va_session_folder", "video_ads/default"
    )

    try:
        image_bytes = utils_gcs.download_bytes_from_gcs(image_uri)
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OSError,
        RuntimeError,
    ) as e:
        return {
            "status": "error",
            "details": f"Could not load scene image: {e}",
        }

    print(
        f"[Tool] generate_scene_clip called:"
        f" scene={scene_number}, model={video_model}",
        flush=True,
    )

    if video_model == "omni":
        clip_bytes = await generate_scene_video(
            image_bytes=image_bytes,
            voiceover_text=script,
            scene_number=scene_number,
            company_name=company_name,
            brand_context=brand_context,
        )
        if not clip_bytes:
            return {
                "status": "failed",
                "scene_number": scene_number,
                "details": "Video generation failed after all retries.",
            }

        clip_filename = f"scene_{scene_number}_clip.mp4"
        clip_uri = utils_gcs.upload_to_gcs(
            bucket_path=f"{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{session_folder}",
            file_bytes=clip_bytes,
            destination_blob_name=clip_filename,
        )
        tool_context.state[f"va_scene_{scene_number}_clip_uri"] = clip_uri

        clip_media = GeneratedMedia(
            filename=f"scene_{scene_number}_clip.mp4",
            mime_type="video/mp4",
            gcs_uri=clip_uri,
            media_bytes=clip_bytes,
        )
        await utils_agents.save_to_artifact_and_render_asset(
            asset=clip_media,
            context=tool_context,
            gcs_folder=session_folder,
            save_in_gcs=False,
            save_in_artifacts=True,
        )
        clip_uri = tool_context.state.get(f"va_scene_{scene_number}_clip_uri")
        link = f"\n[View New Clip]({clip_uri})" if clip_uri else ""
        return {
            "status": "generated",
            "scene_number": scene_number,
            "size_kb": len(clip_bytes) // 1024,
            "model": video_model,
            "message": f"Clip generated successfully.{link}",
        }
    else:
        op_name = await generate_scene_video_veo(
            image_bytes=image_bytes,
            voiceover_text=script,
            scene_number=scene_number,
            company_name=company_name,
            brand_context=brand_context,
            submit_only=True,
        )
        if not op_name:
            return {
                "status": "failed",
                "scene_number": scene_number,
                "details": "Veo submission failed.",
            }
        tool_context.state[f"va_scene_{scene_number}_veo_op"] = op_name
        return {
            "status": "generating",
            "scene_number": scene_number,
            "model": "veo",
            "operation": op_name,
            "next_step": (
                "Veo clip is generating in the background (~4-5"
                " minutes). Use check_veo_status to see when it is done."
            ),
        }


async def generate_all_clips(tool_context: ToolContext) -> dict:
    """Generate video clips for all scenes in parallel (max 4 concurrent).

    Requires all scene images and scripts to be stored first.
    Each generated clip will be displayed inline.
    When generating clips, you can choose a voice_emotion from: Energetic,
    Professional, Warm, Excited, Calm, Confident, Inspiring, Dramatic.
    """
    _tool_start = _time.time()
    t_str = _time.strftime("%H:%M:%S")
    print(
        f"[GenerateClips] >>>>>> TOOL ENTRY at {t_str} <<<<<<",
        flush=True,
    )

    num_scenes = tool_context.state.get("va_num_scenes", 3)
    company_name = tool_context.state.get("va_company_name", "")
    brand_context = tool_context.state.get("va_brand_context", "")
    video_model = tool_context.state.get("va_video_model", "omni")
    session_folder = tool_context.state.get(
        "va_session_folder", "video_ads/default"
    )
    print(
        f"[GenerateClips] Config: model={video_model},"
        f" scenes={num_scenes}, session={session_folder}",
        flush=True,
    )

    scenes_data = []
    missing_images = []
    missing_scripts = []
    for i in range(1, num_scenes + 1):
        image_uri = tool_context.state.get(f"va_scene_{i}_image_uri")
        script = tool_context.state.get(f"va_scene_{i}_script")

        if not image_uri:
            candidate_img = f"gs://{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{session_folder}/scene_{i}.png"
            try:
                ib = utils_gcs.download_bytes_from_gcs(candidate_img)
                if ib:
                    image_uri = candidate_img
                    tool_context.state[f"va_scene_{i}_image_uri"] = image_uri
            except (
                ValueError,
                TypeError,
                KeyError,
                AttributeError,
                OSError,
                RuntimeError,
            ):
                pass

        if not image_uri:
            missing_images.append(i)
        if not script:
            missing_scripts.append(i)
        if image_uri and script:
            scenes_data.append(
                {"scene_number": i, "image_uri": image_uri, "script": script}
            )

    if missing_images:
        print(
            f"[GenerateClips] FAIL: missing images for scenes {missing_images}",
            flush=True,
        )
        return {
            "status": "error",
            "details": f"Missing images for scenes: {missing_images}",
        }
    if missing_scripts:
        print(
            f"[GenerateClips] FAIL: missing"
            f" scripts for scenes {missing_scripts}",
            flush=True,
        )
        return {
            "status": "error",
            "details": f"Missing scripts for scenes: {missing_scripts}",
        }

    gen_fn = (
        generate_scene_video
        if video_model == "omni"
        else generate_scene_video_veo
    )
    voice_name = tool_context.state.get("va_voice_name", "Charon")
    scripts = [s["script"] for s in scenes_data]
    tagline = tool_context.state.get("va_tagline", "")
    brand_context = tool_context.state.get("va_brand_context", "")

    session_folder = tool_context.state.get(
        "va_session_folder", "video_ads/default"
    )

    voice_emotion = tool_context.state.get("va_voice_emotion", "Energetic")

    # Background fire-and-forget for TTS and Lyria (upload directly to GCS)
    async def _bg_tts():
        try:
            print("[GenerateClips BG] Starting background TTS...", flush=True)
            vo_list = await generate_all_voiceovers(
                scripts, voice_name, emotion=voice_emotion
            )
            if vo_list:
                for s, vo in zip(scenes_data, vo_list):
                    if vo:
                        vo_uri = utils_gcs.upload_to_gcs(
                            f"{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{session_folder}",
                            vo,
                            f'scene_{s["scene_number"]}_vo.mp3',
                        )
                        tool_context.state[
                            f'va_scene_{s["scene_number"]}_vo_uri'
                        ] = vo_uri
            print("[GenerateClips BG] TTS complete.", flush=True)
        except (
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OSError,
            RuntimeError,
        ) as e:
            print(f"[GenerateClips BG ERROR] TTS: {e}", flush=True)

    async def _bg_lyria():
        try:
            print("[GenerateClips BG] Starting background Lyria...", flush=True)
            m_bytes = await generate_background_music(
                company_name, scripts, brand_context
            )
            if m_bytes:
                m_uri = utils_gcs.upload_to_gcs(
                    f"{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{session_folder}",
                    m_bytes,
                    "background_music.wav",
                )
                tool_context.state["va_music_uri"] = m_uri
            print("[GenerateClips BG] Lyria complete.", flush=True)
        except (
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OSError,
            RuntimeError,
        ) as e:
            print(f"[GenerateClips BG ERROR] Lyria: {e}", flush=True)

    print(
        "[GenerateClips] Starting TTS + Lyria + "
        "clips ALL in parallel (TTS/Lyria in BG)...",
        flush=True,
    )
    tts_task = asyncio.create_task(_bg_tts())
    lyria_task = asyncio.create_task(_bg_lyria())

    if not tagline and company_name:
        tagline_task = asyncio.create_task(lookup_company_tagline(company_name))
    else:
        tagline_task = None

    print(
        f"[GenerateClips] Clip generation for {len(scenes_data)} scenes with"
        f" '{video_model}' (elapsed: {_time.time()-_tool_start:.1f}s)...",
        flush=True,
    )
    MAX_CONCURRENT = 4
    sem = asyncio.Semaphore(MAX_CONCURRENT)

    async def _gen_one(s):
        async with sem:
            sn = s["scene_number"]
            img_uri = s["image_uri"]
            print(
                f"[GenerateClips Scene {sn}] Fetching image from"
                f" {img_uri}..."
            )
            try:
                image_bytes = utils_gcs.download_bytes_from_gcs(s["image_uri"])
                print(
                    f"[GenerateClips Scene {sn}] Image"
                    f" fetched: {len(image_bytes):,} bytes"
                )
            except (
                ValueError,
                TypeError,
                KeyError,
                AttributeError,
                OSError,
                RuntimeError,
            ) as e:
                print(
                    f"[GenerateClips Scene {sn} ERROR]"
                    f" Image download failed: {e}"
                )
                return {
                    "scene_number": sn,
                    "status": "failed",
                    "error": f"Image download failed: {e}",
                }

            kwargs = {
                "image_bytes": image_bytes,
                "voiceover_text": s["script"],
                "scene_number": sn,
                "company_name": company_name,
                "brand_context": brand_context,
            }

            print(
                f"[GenerateClips Scene {sn}] Calling"
                f" video model '{video_model}'...",
                flush=True,
            )
            initialize_ffmpeg_if_needed()

            if video_model == "veo":
                print(
                    f"[GenerateClips Scene {sn}] Submitting Veo async task...",
                    flush=True,
                )
                lro_name = await gen_fn(
                    **kwargs, clip_duration=8, submit_only=True
                )
                if lro_name:
                    tool_context.state[f"va_scene_{sn}_veo_lro"] = lro_name
                    print(
                        f"[GenerateClips Scene {sn}]"
                        f" Veo LRO stored: {lro_name}",
                        flush=True,
                    )
                    return {"scene_number": sn, "status": "submitted"}
                else:
                    return {
                        "scene_number": sn,
                        "status": "failed",
                        "error": "Veo submission failed",
                    }

            clip_res = await gen_fn(**kwargs)

            if not clip_res:
                print(
                    f"[GenerateClips Scene {sn} ERROR]"
                    f" Model video generation returned None",
                    flush=True,
                )
                return {
                    "scene_number": sn,
                    "status": "failed",
                    "error": "Generation failed",
                }

            clip_bytes = clip_res
            clip_size = len(clip_bytes)

            print(
                f"[GenerateClips Scene {sn}] Video generated!"
                f" Size: {clip_size:,} bytes. Uploading to GCS...",
                flush=True,
            )
            clip_filename = f"scene_{sn}_clip.mp4"
            clip_uri = utils_gcs.upload_to_gcs(
                bucket_path=f"{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{session_folder}",
                file_bytes=clip_bytes,
                destination_blob_name=clip_filename,
            )
            tool_context.state[f"va_scene_{sn}_clip_uri"] = clip_uri
            print(
                f"[GenerateClips Scene {sn}] Uploaded clip to {clip_uri}",
                flush=True,
            )

            del clip_bytes, clip_res, image_bytes

            clip_media = GeneratedMedia(
                filename=f"scene_{sn}_clip.mp4",
                mime_type="video/mp4",
                gcs_uri=clip_uri,
            )
            await utils_agents.save_to_artifact_and_render_asset(
                asset=clip_media,
                context=tool_context,
                gcs_folder=session_folder,
                save_in_gcs=False,
                save_in_artifacts=True,
            )
            print(
                f"[GenerateClips Scene {sn}] Artifact registered successfully.",
                flush=True,
            )

            return {
                "scene_number": sn,
                "status": "generated",
                "size_kb": clip_size // 1024,
                "url": clip_uri,
            }

    results = await asyncio.gather(
        *[_gen_one(s) for s in scenes_data], return_exceptions=True
    )

    gc.collect()
    _clips_elapsed = _time.time() - _tool_start
    print(
        f"[GenerateClips] GC collected. Clip"
        f" generation took {_clips_elapsed:.1f}s total",
        flush=True,
    )

    scene_results = []
    for r in results:
        if isinstance(r, Exception):
            print(
                f"[GenerateClips ERROR] Task"
                f" exception: {type(r).__name__}: {r}",
                flush=True,
            )
            scene_results.append({"status": "failed", "error": str(r)})
        else:
            scene_results.append(r)

    succeeded = sum(
        1
        for r in scene_results
        if r.get("status") in ("generated", "submitted")
    )
    print(
        f"[GenerateClips COMPLETE] {succeeded}/{num_scenes}"
        f" clips succeeded/submitted in {_clips_elapsed:.1f}s",
        flush=True,
    )

    if succeeded == 0:
        print(
            "[GenerateClips] FAIL: all clips failed, returning error",
            flush=True,
        )
        tts_task.cancel()
        lyria_task.cancel()
        return {
            "status": "error",
            "details": "All clips failed. Check image URIs and try again.",
        }

    submitted = any(r.get("status") == "submitted" for r in scene_results)

    # Do not wait for Lyria or TTS to finish (they run in background)
    if tagline_task:
        try:
            tagline = await tagline_task
            tool_context.state["va_tagline"] = tagline
        except (
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OSError,
            RuntimeError,
        ):
            tagline = f"Experience {company_name}"
            tool_context.state["va_tagline"] = tagline
    print(f"[GenerateClips] Tagline: '{tagline}'", flush=True)

    tool_context.state["va_audio_precomputed"] = True

    _total_elapsed = _time.time() - _tool_start
    print(
        f"[GenerateClips] >>>>>> RETURNING ({succeeded}/{num_scenes}"
        f" clips, BG audio running, {_total_elapsed:.1f}s) <<<<<<",
        flush=True,
    )

    if submitted:
        return {
            "status": "running",
            "succeeded": succeeded,
            "total": num_scenes,
            "scenes": scene_results,
            "next_step": (
                "Veo video generation has started in the "
                "background. It takes about 4-5 minutes."
                " Tell the user to wait, and then use the "
                "check_veo_status tool to check progress."
            ),
        }

    return {
        "status": "completed",
        "succeeded": succeeded,
        "total": num_scenes,
        "scenes": scene_results,
        "next_step": (
            "All clips generated successfully! The clips have been "
            "attached as UI artifacts. Ask the user to review the"
            " clips above, and say **good** to assemble the final "
            "video ad, or **regenerate scene N** to redo any clip."
        ),
    }


async def regenerate_scene_clip(
    tool_context: ToolContext, scene_number: int
) -> dict:
    """
    Regenerate the video clip for a specific scene. The new clip replaces the
    previous one.

    Args:
        scene_number: Scene number (1-based) to regenerate.
    """
    print(
        f"[Tool] regenerate_scene_clip called, scene={scene_number}",
        flush=True,
    )
    return await generate_scene_clip(tool_context, scene_number)


async def regenerate_final_video(tool_context: ToolContext) -> dict:
    """
    Re-run the final video assembly pipeline (TTS, dissolve transitions,
    title cards, logo) and display the updated final video."""
    print("[Tool] regenerate_final_video called", flush=True)
    tool_context.state["va_assembly_prepared"] = False
    return await assemble_final_video(tool_context)


async def switch_model_and_regenerate(
    tool_context: ToolContext,
    target_model: str = "",
) -> dict:
    """
    Switch video model (Omni <-> Veo), regenerate all scene clips under the
    new model, and assemble a comparative final video ad.

    Args:
        target_model: Target model ("omni" or "veo"). If omitted, toggles omni
        between and veo.
    """
    print(
        "[ModelSwitch] >>> switch_model_and_regenerate CALLED <<<", flush=True
    )
    tool_context.state["va_assembly_prepared"] = False
    current_model = tool_context.state.get("va_video_model", "omni")
    new_model = (
        target_model.lower().strip()
        if target_model
        else ("veo" if current_model == "omni" else "omni")
    )
    if new_model not in ("omni", "veo"):
        new_model = "veo" if current_model == "omni" else "omni"

    tool_context.state["va_video_model"] = new_model
    print(
        f"[Model Switch] Switching video model"
        f" from {current_model} to {new_model}"
    )

    # Regenerate clips with new model — generate_all_clips waits for
    # clips inline (both Omni and Veo), then returns for separate assembly call
    final_res = await generate_all_clips(tool_context)
    if isinstance(final_res, dict) and final_res.get("status") == "completed":
        final_res["is_comparative_run"] = True
        final_res["model_switched_to"] = new_model
        final_res["next_step"] = (
            f"Here is your comparative video ad"
            f" generated with {new_model.upper()}! "
            "Thank you for creating video ads with the Video Ads Agent. "
            "Would you like to create another ad for another campaign?"
        )
    return final_res


async def prepare_assembly(tool_context: ToolContext) -> dict:
    """
    Prepare scene clips for final assembly: generate TTS voiceovers, trim
    clips to voiceover duration, mix audio, and upload processed clips to GCS.

    Call this BEFORE assemble_final_video. Processes one scene at a time to
    minimize memory usage.
    """
    prep_start = _time.time()
    print("[PrepAssembly] >>> prepare_assembly CALLED <<<", flush=True)
    try:
        initialize_ffmpeg_if_needed()
        print(f"[PrepAssembly] ffmpeg initialized: {_FFMPEG_EXE}", flush=True)
        num_scenes = tool_context.state.get("va_num_scenes", 3)
        company_name = tool_context.state.get("va_company_name", "")
        voice_name = tool_context.state.get("va_voice_name", "Charon")
        session_folder = tool_context.state.get(
            "va_session_folder", "video_ads/default"
        )
        tagline = tool_context.state.get("va_tagline", "")
        scene_order = tool_context.state.get("va_scene_order")
        print(
            f"[PrepAssembly] Config: scenes={num_scenes},"
            f" voice={voice_name}, session={session_folder}",
            flush=True,
        )

        ordered_scenes = (
            scene_order if scene_order else list(range(1, num_scenes + 1))
        )
        print(f"[PrepAssembly] Scene order: {ordered_scenes}", flush=True)
        pad_before = 0.5
        # Resolve tagline
        t0 = _time.time()
        if not tagline and company_name:
            print(
                f"[PrepAssembly] Looking up tagline for '{company_name}'...",
                flush=True,
            )
            try:
                tagline = await lookup_company_tagline(company_name)
            except (
                ValueError,
                TypeError,
                KeyError,
                AttributeError,
                OSError,
                RuntimeError,
            ) as e:
                print(f"[PrepAssembly] Tagline lookup failed: {e}", flush=True)
                tagline = f"Experience {company_name}"
        tool_context.state["va_tagline"] = tagline
        print(
            f"[PrepAssembly] Tagline resolved:"
            f" '{tagline}' ({_time.time() - t0:.1f}s)",
            flush=True,
        )

        # Process each scene ONE AT A TIME to keep memory low
        for idx, sn in enumerate(ordered_scenes):
            scene_start = _time.time()
            print(
                f"[PrepAssembly] === Scene {sn}"
                f" ({idx+1}/{len(ordered_scenes)}) ===",
                flush=True,
            )

            clip_uri = tool_context.state.get(f"va_scene_{sn}_clip_uri")
            script = tool_context.state.get(f"va_scene_{sn}_script", "")
            print(f"[PrepAssembly] Scene {sn}: clip_uri={clip_uri}", flush=True)
            print(
                f"[PrepAssembly] Scene {sn}: script='{script[:60]}...'",
                flush=True,
            )

            if not clip_uri:
                print(
                    f"[PrepAssembly] Scene {sn}: SKIP - no clip URI in state",
                    flush=True,
                )
                continue

            # Download clip
            t0 = _time.time()
            print(
                f"[PrepAssembly] Scene {sn}: downloading clip from GCS...",
                flush=True,
            )
            clip_bytes = utils_gcs.download_bytes_from_gcs(clip_uri)
            if not clip_bytes:
                print(
                    f"[PrepAssembly] Scene {sn}: FAIL"
                    f" - clip download returned None",
                    flush=True,
                )
                continue
            print(
                f"[PrepAssembly] Scene {sn}: clip downloaded"
                f" ({len(clip_bytes):,} bytes, {_time.time() - t0:.1f}s)",
                flush=True,
            )

            # Get TTS — use pre-computed from GCS if available, else generate
            t0 = _time.time()
            vo_uri = tool_context.state.get(
                f"va_scene_{sn}_vo_uri",
                f"gs://{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{session_folder}/scene_{sn}_vo.mp3",
            )
            vo_bytes = None
            if vo_uri:
                print(
                    f"[PrepAssembly] Scene {sn}: downloading"
                    f" pre-computed TTS from {vo_uri}...",
                    flush=True,
                )
                vo_bytes = utils_gcs.download_bytes_from_gcs(vo_uri)
                if vo_bytes:
                    print(
                        f"[PrepAssembly] Scene {sn}: TTS from GCS"
                        f" ({len(vo_bytes):,} bytes, {_time.time() - t0:.1f}s)",
                        flush=True,
                    )
            if not vo_bytes and script:
                emotion = tool_context.state.get(
                    "va_voice_emotion", "Energetic"
                )
                print(
                    f"[PrepAssembly] Scene {sn}: generating TTS with"
                    f" voice '{voice_name}' and emotion '{emotion}'...",
                    flush=True,
                )
                vo_bytes = await generate_voiceover(
                    script, voice_name, emotion=emotion
                )
                if vo_bytes:
                    print(
                        f"[PrepAssembly] Scene {sn}: TTS generated"
                        f" ({len(vo_bytes):,} bytes, {_time.time() - t0:.1f}s)",
                        flush=True,
                    )
            if not vo_bytes:
                print(
                    f"[PrepAssembly] Scene {sn}: no TTS"
                    f" available ({_time.time() - t0:.1f}s)",
                    flush=True,
                )

            # Mix voiceover audio onto full-length scene clip
            t0 = _time.time()
            print(
                (
                    f"[PrepAssembly] Scene {sn}: "
                    "mixing voiceover audio onto full clip..."
                ),
                flush=True,
            )
            clip_bytes = mix_scene_audio(
                clip_bytes, vo_bytes, None, vo_delay=pad_before
            )
            print(
                f"[PrepAssembly] Scene {sn}: audio mixed"
                f" ({len(clip_bytes):,} bytes, {_time.time() - t0:.1f}s)",
                flush=True,
            )
            if vo_bytes:
                del vo_bytes

            # Upload processed clip to GCS
            t0 = _time.time()
            processed_name = f"scene_{sn}_processed.mp4"
            print(
                f"[PrepAssembly] Scene {sn}: uploading"
                f" processed clip as {processed_name}...",
                flush=True,
            )
            processed_uri = utils_gcs.upload_to_gcs(
                bucket_path=f"{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{session_folder}",
                file_bytes=clip_bytes,
                destination_blob_name=processed_name,
            )
            tool_context.state[f"va_scene_{sn}_processed_uri"] = processed_uri
            print(
                f"[PrepAssembly] Scene {sn}: uploaded to"
                f" {processed_uri} ({_time.time() - t0:.1f}s)",
                flush=True,
            )
            print(
                f"[PrepAssembly] Scene {sn}: COMPLETE"
                f" in {_time.time() - scene_start:.1f}s",
                flush=True,
            )

            del clip_bytes
            gc.collect()

        tool_context.state["va_assembly_prepared"] = True
        total = _time.time() - prep_start
        print(
            f"[PrepAssembly] ALL SCENES PREPARED in"
            f" {total:.1f}s. Ready for assemble_final_video.",
            flush=True,
        )

        return {
            "status": "prepared",
            "scenes_processed": len(ordered_scenes),
            "duration_seconds": round(total, 1),
            "next_step": (
                "Audio preparation complete. Now call"
                " assemble_final_video to create the final video."
            ),
        }
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OSError,
        RuntimeError,
    ) as e:
        traceback.print_exc()
        elapsed = _time.time() - prep_start
        print(
            f"[PrepAssembly FATAL] {type(e).__name__}:"
            f" {e} (after {elapsed:.1f}s)",
            flush=True,
        )
        return {"status": "error", "details": f"Preparation failed: {e}"}


async def assemble_final_video(tool_context: ToolContext) -> dict:
    """Assemble the final video ad from prepared scene clips.

    If prepare_assembly has not been called yet, this will call it first.
    Pipeline: download processed clips → title cards → concat → background →
    music logo overlay.
    The final video will be displayed inline.
    """
    gc.collect()
    print("[Assembly] >>> assemble_final_video CALLED <<<", flush=True)

    if not tool_context.state.get("va_assembly_prepared"):
        print(
            "[Assembly] NOT PREPARED — auto-calling prepare_assembly first",
            flush=True,
        )
        prep_result = await prepare_assembly(tool_context)
        if prep_result.get("status") != "prepared":
            print(
                f"[Assembly] prepare_assembly failed: {prep_result}",
                flush=True,
            )
            return prep_result

    try:
        initialize_ffmpeg_if_needed()
        print(f"[Assembly] ffmpeg ready: {_FFMPEG_EXE}", flush=True)

        num_scenes = tool_context.state.get("va_num_scenes", 3)
        company_name = tool_context.state.get("va_company_name", "")
        brand_context = tool_context.state.get("va_brand_context", "")
        enable_music = tool_context.state.get("va_enable_music", True)
        session_folder = tool_context.state.get(
            "va_session_folder", "video_ads/default"
        )
        tagline = tool_context.state.get("va_tagline", "")
        scene_order = tool_context.state.get("va_scene_order")
        ordered_scenes = (
            scene_order if scene_order else list(range(1, num_scenes + 1))
        )
        scripts = [
            tool_context.state.get(f"va_scene_{sn}_script", "")
            for sn in ordered_scenes
        ]
        print(
            f"[Assembly] Config: scenes={ordered_scenes},"
            f" music={enable_music}, session={session_folder}",
            flush=True,
        )

        pipeline_start = _time.time()

        # Step 1/6: Download processed clips (already have TTS + audio mixed)
        t0 = _time.time()
        print(
            f"[Assembly 1/6] Downloading {len(ordered_scenes)}"
            f" processed clips from GCS...",
            flush=True,
        )
        assembled_clips = []
        total_clip_bytes = 0
        for sn in ordered_scenes:
            uri = tool_context.state.get(f"va_scene_{sn}_processed_uri")
            source = "processed"
            if not uri:
                uri = tool_context.state.get(f"va_scene_{sn}_clip_uri")
                source = "raw"
            if not uri:
                print(
                    f"[Assembly 1/6] Scene {sn}: NO"
                    f" URI found in state, skipping",
                    flush=True,
                )
                continue
            print(
                f"[Assembly 1/6] Scene {sn}: downloading"
                f" {source} clip from {uri}...",
                flush=True,
            )
            cb = utils_gcs.download_bytes_from_gcs(uri)
            if cb:
                assembled_clips.append(cb)
                total_clip_bytes += len(cb)
                print(
                    f"[Assembly 1/6] Scene {sn}: OK ({len(cb):,} bytes)",
                    flush=True,
                )
            else:
                print(
                    f"[Assembly 1/6] Scene {sn}: download returned None!",
                    flush=True,
                )
        gc.collect()
        print(
            f"[Assembly 1/6] DONE: {len(assembled_clips)} clips,"
            f" {total_clip_bytes:,} total bytes ({_time.time() - t0:.1f}s)",
            flush=True,
        )

        if not assembled_clips:
            return {
                "status": "error",
                "details": "No clips available for assembly.",
            }
        # Step 2/6: Create Outro Clip
        logo_uri = tool_context.state.get("va_logo_uri")
        logo_bytes = None
        if logo_uri:
            try:
                logo_bytes = utils_gcs.download_bytes_from_gcs(logo_uri)
                if logo_bytes:
                    print(
                        "[Assembly 2/6] Logo downloaded "
                        "for outro. Removing background...",
                        flush=True,
                    )
                    logo_bytes = remove_logo_background(logo_bytes)
            except (
                ValueError,
                TypeError,
                KeyError,
                AttributeError,
                OSError,
                RuntimeError,
            ) as e:
                print(f"[Assembly 2/6] WARNING: Logo failed: {e}", flush=True)

        if company_name and tagline and assembled_clips:
            print("[Assembly 2/6] Creating outro clip...", flush=True)
            outro_text = f"{company_name}. {tagline}."
            outro_vo = await generate_voiceover(
                script=outro_text,
                voice_name=tool_context.state.get("va_voice_name", "Charon"),
                emotion=tool_context.state.get("va_voice_emotion", "Warm"),
            )
            outro_clip = create_outro_clip(
                base_clip_bytes=assembled_clips[-1],
                logo_bytes=logo_bytes,
                tagline=tagline,
                voiceover_bytes=outro_vo,
            )
            if outro_clip:
                assembled_clips.append(outro_clip)
                print("[Assembly 2/6] Outro clip appended.", flush=True)

        # Step 3/6: Concatenate with dissolve transitions
        t0 = _time.time()
        print(
            f"[Assembly 3/6] Concatenating {len(assembled_clips)}"
            f" clips with dissolve transitions...",
            flush=True,
        )
        final_video = concatenate_scenes_with_dissolve(assembled_clips)
        del assembled_clips
        gc.collect()

        if not final_video:
            print(
                "[Assembly 3/6] FAIL: dissolve concat returned None",
                flush=True,
            )
            return {"status": "error", "details": "Concatenation failed."}
        print(
            f"[Assembly 3/6] DONE: {len(final_video):,}"
            f" bytes ({_time.time() - t0:.1f}s)",
            flush=True,
        )

        # Step 4/6: Background music — use pre-computed from GCS if available
        t0 = _time.time()
        if enable_music:
            music_uri = tool_context.state.get("va_music_uri")
            music_bytes = None
            music_uri = tool_context.state.get(
                "va_music_uri",
                f"gs://{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{session_folder}/background_music.wav",
            )
            music_bytes = None
            if music_uri:
                print(
                    f"[Assembly 4/6] Downloading pre-computed"
                    f" Lyria music from {music_uri}...",
                    flush=True,
                )
                music_bytes = utils_gcs.download_bytes_from_gcs(music_uri)
                if music_bytes:
                    print(
                        f"[Assembly 4/6] Music from GCS ({len(music_bytes):,}"
                        f" bytes, {_time.time() - t0:.1f}s)",
                        flush=True,
                    )
            if not music_bytes:
                print(
                    "[Assembly 4/6] Generating Lyria "
                    "background music (no pre-computed)...",
                    flush=True,
                )
                try:
                    music_bytes = await generate_background_music(
                        company_name, scripts, brand_context
                    )
                except (
                    ValueError,
                    TypeError,
                    KeyError,
                    AttributeError,
                    OSError,
                    RuntimeError,
                ) as e:
                    print(
                        f"[Assembly 4/6] Lyria generation failed: {e}",
                        flush=True,
                    )
            if music_bytes:
                print("[Assembly 4/6] Mixing music at 35%...", flush=True)
                t1 = _time.time()
                final_video = add_background_music_to_final(
                    final_video, music_bytes, 0.35
                )
                print(
                    f"[Assembly 4/6] Music mixed ({_time.time() - t1:.1f}s)",
                    flush=True,
                )
                del music_bytes
                gc.collect()
            else:
                print("[Assembly 4/6] No music available", flush=True)
        else:
            print("[Assembly 4/6] SKIP: music disabled", flush=True)
        print(f"[Assembly 4/6] DONE ({_time.time() - t0:.1f}s)", flush=True)

        # Step 5/6: Logo overlay
        t0 = _time.time()
        logo_uri = tool_context.state.get("va_logo_uri")
        tagline = tool_context.state.get("va_tagline", "")
        if logo_uri or tagline:
            logo_bytes = None
            if logo_uri:
                try:
                    logo_bytes = utils_gcs.download_bytes_from_gcs(logo_uri)
                    if logo_bytes:
                        print(
                            f"[Assembly 5/6] Logo downloaded "
                            f"({len(logo_bytes):,}"
                            f" bytes). Removing background...",
                            flush=True,
                        )
                        logo_bytes = remove_logo_background(logo_bytes)
                except (
                    ValueError,
                    TypeError,
                    KeyError,
                    AttributeError,
                    OSError,
                    RuntimeError,
                ) as e:
                    print(
                        f"[Assembly 5/6] WARNING: Logo failed: {e}", flush=True
                    )

            print(
                "[Assembly 5/6] Overlaying logo/tagline on video...",
                flush=True,
            )
            final_video = overlay_logo_and_tagline_on_video(
                final_video,
                logo_bytes=logo_bytes,
                tagline=tagline,
                opacity=0.8,
                scale=0.12,
                margin=30,
            )
            if logo_bytes:
                del logo_bytes
                gc.collect()
        else:
            print("[Assembly 5/6] SKIP: no logo URI or tagline", flush=True)

        # Step 6/6: Upload + display final video (match working reference
        # pattern)
        t0 = _time.time()
        final_size = len(final_video)
        print(
            f"[Assembly 6/6] Uploading final video ({final_size:,} bytes)...",
            flush=True,
        )
        final_uri = utils_gcs.upload_to_gcs(
            bucket_path=f"{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{session_folder}",
            file_bytes=final_video,
            destination_blob_name="final_video_ad.mp4",
        )
        tool_context.state["va_final_video_uri"] = final_uri
        print(
            f"[Assembly 6/6] Uploaded to"
            f" {final_uri} ({_time.time() - t0:.1f}s)",
            flush=True,
        )

        print(
            f"[Assembly] Creating GeneratedMedia"
            f" artifact (media_bytes={final_size:,}B)...",
            flush=True,
        )
        final_media = GeneratedMedia(
            filename="final_video_ad.mp4",
            mime_type="video/mp4",
            media_bytes=final_video,
        )
        print(
            "[Assembly] Calling save_to_artifact_and_render_asset "
            "(save_in_gcs=True)...",
            flush=True,
        )
        t_artifact = _time.time()
        await utils_agents.save_to_artifact_and_render_asset(
            asset=final_media,
            context=tool_context,
            gcs_folder=session_folder,
            save_in_gcs=True,
            save_in_artifacts=True,
        )
        print(
            f"[Assembly] Artifact saved and rendered"
            f" ({_time.time()-t_artifact:.1f}s)",
            flush=True,
        )
        del final_video
        gc.collect()

        elapsed = _time.time() - pipeline_start
        print(
            f"[Assembly] >>>>>> ASSEMBLY COMPLETE — total"
            f" {elapsed:.1f}s, final video {final_size:,} bytes <<<<<<",
            flush=True,
        )
        current_model = tool_context.state.get("va_video_model", "omni")
        other_model = "veo" if current_model == "omni" else "omni"

        # Clear preparation flag so next assembly re-prepares
        tool_context.state["va_assembly_prepared"] = False

        # Generate direct authenticated GCS link (https://storage.cloud.google.com/...)
        https_link = utils_gcs.normalize_to_authenticated_url(final_uri)

        return {
            "status": "success",
            "final_video_gcs_uri": final_uri,
            "duration_seconds": round(elapsed, 1),
            "size_mb": round(final_size / (1024 * 1024), 1),
            "scenes": len(ordered_scenes),
            "tagline": tagline,
            "music": "enabled" if enable_music else "disabled",
            "current_model": current_model,
            "other_model": other_model,
            "next_step": (
                "Your video ad is complete! You can view "
                "or download the final video here:\n"
                f"**[Click here to view Final Video Ad]({https_link})**\n\n"
                "What would you like to do next?\n"
                "- **Regenerate final video**: Type "
                "`regenerate final video` to rebuild.\n"
                f"- **Compare with {other_model.capitalize()}**: Type"
                f" `{other_model}` to create a comparative version.\n"
                "- **Wrap up**: Type `done` if you are satisfied."
            ),
        }
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OSError,
        RuntimeError,
    ) as e:
        traceback.print_exc()
        print(f"[Assembly FATAL] {type(e).__name__}: {e}", flush=True)
        return {"status": "error", "details": f"Assembly error: {e}"}


async def add_music_to_video(tool_context: ToolContext) -> dict:
    """
    Add Lyria background music to the final assembled video. Call this after
    assemble_final_video.

    Downloads the final video from GCS, generates background music with Lyria,
    mixes it in, and uploads the updated video.
    """
    print("[AddMusic] >>> add_music_to_video CALLED <<<", flush=True)
    try:
        initialize_ffmpeg_if_needed()
        company_name = tool_context.state.get("va_company_name", "")
        brand_context = tool_context.state.get("va_brand_context", "")
        session_folder = tool_context.state.get(
            "va_session_folder", "video_ads/default"
        )
        num_scenes = tool_context.state.get("va_num_scenes", 3)
        scene_order = tool_context.state.get("va_scene_order")
        ordered_scenes = (
            scene_order if scene_order else list(range(1, num_scenes + 1))
        )
        scripts = [
            tool_context.state.get(f"va_scene_{sn}_script", "")
            for sn in ordered_scenes
        ]

        final_uri = tool_context.state.get("va_final_video_uri")
        if not final_uri:
            return {
                "status": "error",
                "details": (
                    "No final video found. Run" " assemble_final_video first."
                ),
            }

        print("[AddMusic] Downloading final video...", flush=True)
        final_video = utils_gcs.download_bytes_from_gcs(final_uri)
        if not final_video:
            return {
                "status": "error",
                "details": "Could not download final video from GCS.",
            }

        print("[AddMusic] Generating Lyria background music...", flush=True)
        music_bytes = await generate_background_music(
            company_name, scripts, brand_context
        )
        if not music_bytes:
            return {
                "status": "warning",
                "details": (
                    "Music generation failed. Video"
                    " remains without background music."
                ),
            }

        print("[AddMusic] Mixing music into video...", flush=True)
        final_video = add_background_music_to_final(
            final_video, music_bytes, 0.35
        )
        del music_bytes
        gc.collect()

        print(
            f"[AddMusic] Uploading updated video"
            f" ({len(final_video):,} bytes)...",
            flush=True,
        )
        final_uri = utils_gcs.upload_to_gcs(
            bucket_path=f"{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{session_folder}",
            file_bytes=final_video,
            destination_blob_name="final_video_ad.mp4",
        )
        tool_context.state["va_final_video_uri"] = final_uri

        final_media = GeneratedMedia(
            filename="final_video_ad.mp4",
            mime_type="video/mp4",
            gcs_uri=final_uri,
        )
        await utils_agents.save_to_artifact_and_render_asset(
            asset=final_media,
            context=tool_context,
            gcs_folder=session_folder,
            save_in_gcs=False,
            save_in_artifacts=True,
        )
        if hasattr(utils_gcs, "normalize_to_public_url"):
            https_link = utils_gcs.normalize_to_public_url(final_uri)
        else:
            https_link = final_uri.replace(
                "gs://", "https://storage.googleapis.com/"
            )

        return {
            "status": "success",
            "final_video_gcs_uri": final_uri,
            "size_mb": round(len(final_video) / (1024 * 1024), 1),
            "next_step": (
                f"Background music added! Your video "
                f"ad is complete. You can view or"
                f" download it here:\n**[Click here to "
                f"view Final Video Ad]({https_link})**"
            ),
        }
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OSError,
        RuntimeError,
    ) as e:
        traceback.print_exc()
        print(f"[AddMusic FATAL] {type(e).__name__}: {e}", flush=True)
        return {"status": "error", "details": f"Music addition failed: {e}"}


# ============================================================
# Before-model callback: strip large inline media from history
# ============================================================

_MAX_INLINE_BYTES = 50_000
_KEEP_RECENT_CONTENTS = 8
_MAX_OLD_PART_CHARS = 200


def _strip_large_inline_data(*args, **kwargs) -> None:
    """Aggressively trim conversation history to keep context small.

    1. Strip inline data > 50KB from ALL turns.
    2. For turns older than the most recent 8 content entries, truncate
       large text parts to 200 chars.
    """
    try:
        llm_request = kwargs.get("llm_request")
        if llm_request is None:
            for arg in args:
                if hasattr(arg, "contents"):
                    llm_request = arg
                    break
        if (
            not llm_request
            or not hasattr(llm_request, "contents")
            or not llm_request.contents
        ):
            return

        total = len(llm_request.contents)
        old_cutoff = max(0, total - _KEEP_RECENT_CONTENTS)
        stripped_inline = 0
        truncated_text = 0

        for idx, content in enumerate(llm_request.contents):
            if (
                not content
                or not hasattr(content, "parts")
                or not content.parts
            ):
                continue
            is_old = idx < old_cutoff
            cleaned = []

            for part in content.parts:
                try:
                    is_stripped_or_truncated = False
                    if (
                        part
                        and hasattr(part, "inline_data")
                        and part.inline_data
                        and hasattr(part.inline_data, "data")
                        and part.inline_data.data
                    ):
                        data_len = len(part.inline_data.data)
                        if data_len > _MAX_INLINE_BYTES:
                            mime = (
                                getattr(
                                    part.inline_data, "mime_type", "unknown"
                                )
                                or "unknown"
                            )
                            replacement_text = (
                                f"[stripped {mime} {data_len:,}B]"
                            )
                            if Part is not None and hasattr(Part, "from_text"):
                                cleaned.append(Part.from_text(replacement_text))
                            elif hasattr(part, "__class__"):
                                try:
                                    cleaned.append(
                                        part.__class__(text=replacement_text)
                                    )
                                except (
                                    ValueError,
                                    RuntimeError,
                                    KeyError,
                                    TypeError,
                                    OSError,
                                    IOError,
                                ):
                                    cleaned.append(part)
                            else:
                                cleaned.append(part)
                            stripped_inline += 1
                            is_stripped_or_truncated = True

                    if (
                        not is_stripped_or_truncated
                        and is_old
                        and part
                        and hasattr(part, "text")
                        and part.text
                    ):
                        text_len = len(part.text)
                        if text_len > _MAX_OLD_PART_CHARS:
                            replacement_text = (
                                part.text[:_MAX_OLD_PART_CHARS]
                                + f"... [truncated {text_len:,} chars]"
                            )
                            if Part is not None and hasattr(Part, "from_text"):
                                cleaned.append(Part.from_text(replacement_text))
                            elif hasattr(part, "__class__"):
                                try:
                                    cleaned.append(
                                        part.__class__(text=replacement_text)
                                    )
                                except (
                                    ValueError,
                                    RuntimeError,
                                    KeyError,
                                    TypeError,
                                    OSError,
                                    IOError,
                                ):
                                    cleaned.append(part)
                            else:
                                cleaned.append(part)
                            truncated_text += 1
                            is_stripped_or_truncated = True

                    if not is_stripped_or_truncated:
                        cleaned.append(part)
                except (
                    ValueError,
                    TypeError,
                    KeyError,
                    AttributeError,
                    OSError,
                    RuntimeError,
                ) as ex:
                    print(
                        f"[BeforeModel] ERROR inside part loop: {ex}",
                        flush=True,
                    )
                    cleaned.append(part)

            del content.parts[:]
            content.parts.extend(cleaned)

        print(
            (
                f"[BeforeModel] {total} contents, "
                f"stripped_inline={stripped_inline}, truncated={truncated_text}"
            ),
            flush=True,
        )
    except (
        ValueError,
        RuntimeError,
        KeyError,
        TypeError,
        OSError,
        IOError,
    ) as e:
        print(f"[BeforeModel] ERROR in callback: {e}", flush=True)


# ============================================================
# ADK Agent Definition
# ============================================================


async def check_veo_status(
    tool_context: ToolContext, _check_now: bool = True
) -> dict:
    """
    Check the status of Veo clip generation in the background. Call this when
    checking if Veo generation is done.

    Args:
        check_now: Set to True to check the status now.
    """
    num_scenes = tool_context.state.get("va_num_scenes", 4)
    session_folder = tool_context.state.get(
        "va_session_folder", "video_ads/default"
    )

    results = []
    all_done = True
    any_found = False
    any_failed = False

    for sn in range(1, num_scenes + 1):
        op_name = tool_context.state.get(f"va_scene_{sn}_veo_op")
        if not op_name:
            continue

        any_found = True
        print(
            f"[CheckVeo] Checking status for Scene {sn} operation {op_name}...",
            flush=True,
        )
        clip_res = await check_scene_video_veo(op_name)

        if clip_res == "RUNNING":
            all_done = False
            results.append({"scene": sn, "status": "running"})
            print(f"[CheckVeo Scene {sn}] Still running", flush=True)
            continue

        if not clip_res:
            any_failed = True
            results.append({"scene": sn, "status": "failed"})
            tool_context.state[f"va_scene_{sn}_veo_op"] = ""
            print(
                f"[CheckVeo Scene {sn}] FAILED - operation returned None",
                flush=True,
            )
            continue

        if isinstance(clip_res, bytes):
            clip_bytes = clip_res
            print(
                f"[CheckVeo Scene {sn}] Video generated! Size:"
                f" {len(clip_bytes):,} bytes. Uploading to GCS..."
            )
            clip_filename = f"scene_{sn}_clip.mp4"
            clip_uri = utils_gcs.upload_to_gcs(
                bucket_path=f"{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{session_folder}",
                file_bytes=clip_bytes,
                destination_blob_name=clip_filename,
            )
            tool_context.state[f"va_scene_{sn}_clip_uri"] = clip_uri

            tool_context.state[f"va_scene_{sn}_veo_op"] = ""

            clip_media = GeneratedMedia(
                filename=f"scene_{sn}_clip.mp4",
                mime_type="video/mp4",
                gcs_uri=clip_uri,
            )
            await utils_agents.save_to_artifact_and_render_asset(
                asset=clip_media,
                context=tool_context,
                gcs_folder=session_folder,
                save_in_gcs=False,
                save_in_artifacts=True,
            )
            results.append({"scene": sn, "status": "completed"})
            print(f"[CheckVeo Scene {sn}] Artifact registered successfully.")

    if not any_found:
        has_clips = any(
            tool_context.state.get(f"va_scene_{sn}_clip_uri")
            for sn in range(1, num_scenes + 1)
        )
        if has_clips:
            return {
                "status": "finished",
                "message": "All clips already completed and stored.",
                "next_step": (
                    "Now call assemble_final_video"
                    " to create the final video ad."
                ),
            }
        return {
            "status": "not_started",
            "message": (
                "No active Veo operations found and no clips stored."
                " Generate clips first with generate_all_clips."
            ),
        }

    if all_done and not any_failed:
        completed = [r["scene"] for r in results if r["status"] == "completed"]
        links = "\n".join(
            [
                f"- Scene {sn}: [View"
                f" Clip]({tool_context.state.get(f'va_scene_{sn}_clip_uri')})"
                for sn in completed
                if tool_context.state.get(f"va_scene_{sn}_clip_uri")
            ]
        )
        return {
            "status": "finished",
            "message": "All Veo clips finished generating.",
            "next_step": (
                f"All Veo clips are ready!\n\nClips:"
                f"\n{links}\n\nAsk the user to"
                f" review the clips. If they look "
                f"good, call assemble_final_video."
            ),
        }
    elif all_done and any_failed:
        failed_scenes = [r["scene"] for r in results if r["status"] == "failed"]
        completed = [r["scene"] for r in results if r["status"] == "completed"]
        if completed:
            links = "\n".join(
                [
                    f"- Scene {sn}:"
                    f" {tool_context.state.get(f'va_scene_{sn}_clip_uri')}"
                    for sn in completed
                ]
            )
            return {
                "status": "partial",
                "message": (
                    f"{len(completed)} clips done,"
                    f" scenes {failed_scenes} failed."
                ),
                "next_step": (
                    f"Checked Veo status. Partial clips ready:\n{links}\n\nCall"
                    f" assemble_final_video to assemble "
                    f"with the available clips."
                ),
            }
        return {
            "status": "partial_failure",
            "message": (
                f"All scenes failed: {failed_scenes}. Try"
                f" regenerating with regenerate_scene_clip."
            ),
            "failed_scenes": failed_scenes,
        }
    else:
        running = [r["scene"] for r in results if r["status"] == "running"]
        return {
            "status": "running",
            "scenes_still_running": running,
            "message": (
                f"Veo clips for scenes {running} are still generating. Tell"
                f" the user to wait another 1-2 minutes and check again."
            ),
        }


root_agent = Agent(
    name="video_ads_agent",
    model="gemini-3.1-pro-preview",
    instruction=open(
        os.path.join(os.path.dirname(__file__), "prompt.md"),
        encoding="utf-8",
    ).read(),
    description=(
        "Multi-scene Video Ads Agent — generates video clips with Omni or Veo, "
        "voiceover with TTS, background music with Lyria, and assembles "
        "a final video ad with dissolve transitions. Displays all media inline."
    ),
    tools=[
        list_voices,
        preview_voice,
        preview_all_voices,
        setup_video_ad,
        show_default_logo,
        store_logo,
        load_images_from_bucket,
        confirm_images,
        save_uploaded_image,
        store_scene_image,
        store_scene_script,
        generate_ai_scripts,
        generate_scene_clip,
        generate_all_clips,
        check_veo_status,
        regenerate_scene_clip,
        regenerate_final_video,
        switch_model_and_regenerate,
        prepare_assembly,
        assemble_final_video,
        add_music_to_video,
    ],
)
