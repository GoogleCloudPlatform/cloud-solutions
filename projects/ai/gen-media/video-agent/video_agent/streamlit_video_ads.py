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

"""Script 1: Interactive Streamlit UI for Video Ads Agent.

Run:
    streamlit run streamlit_video_ads.py
"""

import asyncio
import base64
import hashlib
import io
import json
import os
import sys
import threading
import time

import streamlit as st
from dotenv import load_dotenv
from google.cloud import storage
from video_ads_agent.agent import (
    CLIP_DURATION,
    GEMINI_TTS_VOICES,
    MAX_WORDS_OMNI,
    MAX_WORDS_VEO,
    VOICE_EMOTIONS,
    add_background_music_to_final,
    concatenate_scenes_with_dissolve,
    create_outro_clip,
    generate_all_voiceover_scripts,
    generate_all_voiceovers,
    generate_background_music,
    generate_scene_video,
    generate_scene_video_veo,
    generate_voice_preview,
    generate_voiceover,
    lookup_company_tagline,
    mix_scene_audio,
    overlay_logo_and_tagline_on_video,
    remove_logo_background,
    trim_clip_to_voiceover,
)

load_dotenv()

# ── Project Management Helpers ───────────────────────────────


def _get_bucket():
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        return None
    bucket_name = f"{project_id}-video-ads-projects"
    try:
        client = storage.Client(project=project_id)
        bucket = client.bucket(bucket_name)
        if not bucket.exists():
            bucket.create(location="us-central1")
        return bucket
    except (
        ValueError,
        TypeError,
        RuntimeError,
        KeyError,
        AttributeError,
        OSError,
        IOError,
    ) as err:
        print(f"Failed to access/create GCS bucket {bucket_name}: {err}")
        return None


def _list_projects():
    bucket = _get_bucket()
    if bucket:
        blobs = bucket.list_blobs(prefix="projects/")
        return sorted(
            [
                blob.name.replace("projects/", "").replace(".json", "")
                for blob in blobs
                if blob.name.endswith(".json")
            ]
        )

    if not os.path.exists(PROJECTS_DIR):
        return []
    return sorted(
        f.replace(".json", "")
        for f in os.listdir(PROJECTS_DIR)
        if f.endswith(".json")
    )


def _save_project(name: str):
    refresh_c = st.session_state.get("refresh_counter", 0)
    num_scenes_saved = st.session_state.get("_num_scenes", 3)
    data = {
        "scene_clips_b64": {
            str(k): base64.b64encode(v).decode()
            for k, v in st.session_state.scene_clips.items()
            if v and int(k) <= num_scenes_saved
        },
        "scene_voiceovers_b64": {
            str(k): base64.b64encode(v).decode()
            for k, v in st.session_state.scene_voiceovers.items()
            if v and int(k) <= num_scenes_saved
        },
        "persisted_images_b64": {
            str(k): base64.b64encode(v).decode()
            for k, v in st.session_state.persisted_images.items()
            if v and int(k) <= num_scenes_saved
        },
        "final_video_b64": (
            base64.b64encode(st.session_state.final_video).decode()
            if st.session_state.final_video
            else None
        ),
        "music_bytes_b64": (
            base64.b64encode(st.session_state.music_bytes).decode()
            if st.session_state.music_bytes
            else None
        ),
        "tagline": st.session_state.tagline,
        "scene_order": st.session_state.scene_order,
        "custom_prompt": st.session_state.custom_prompt,
        "custom_scene_prompts": st.session_state.custom_scene_prompts,
        "lyria_prompt": st.session_state.lyria_prompt,
        "clips_model": st.session_state.clips_model,
        "voiceover_texts": {
            str(i): st.session_state.get(f"vo_{i}_{refresh_c}", "")
            for i in range(1, num_scenes_saved + 1)
        },
        "scene_descriptions": {
            str(i): st.session_state.get(f"desc_{i}_{refresh_c}", "")
            for i in range(1, num_scenes_saved + 1)
        },
        "settings": {
            "company_name": st.session_state.get("_company_name", ""),
            "brand_context": st.session_state.get("_brand_context", ""),
            "video_model": st.session_state.get("_video_model", "Omni"),
            "voice_name": st.session_state.get("_voice_name", "Charon"),
            "voice_emotion": st.session_state.get("_voice_emotion", "Warm"),
            "enable_music": st.session_state.get("_enable_music", True),
            "num_scenes": st.session_state.get("_num_scenes", 3),
        },
    }

    bucket = _get_bucket()
    if bucket:
        blob = bucket.blob(f"projects/{name}.json")
        blob.upload_from_string(
            json.dumps(data), content_type="application/json"
        )
    else:
        path = os.path.join(PROJECTS_DIR, f"{name}.json")
        with open(path, "w", encoding="utf-8") as f_out:
            json.dump(data, f_out)

    st.session_state.current_project = name
    st.session_state.unsaved_changes = False


def _delete_project(name: str):
    bucket = _get_bucket()
    if bucket:
        blob = bucket.blob(f"projects/{name}.json")
        if blob.exists():
            blob.delete()
    else:
        path = os.path.join(PROJECTS_DIR, f"{name}.json")
        if os.path.exists(path):
            os.remove(path)

    if st.session_state.get("current_project", "") == name:
        st.session_state.current_project = ""
        st.session_state.unsaved_changes = False


def get_default_system_prompt(v_model: str, c_name: str, b_ctx: str) -> str:
    duration = CLIP_DURATION
    brand_line = f" for {c_name}" if c_name else ""
    context_block = f"\nBrand context: {b_ctx}\n" if b_ctx else ""

    rules = (
        "CRITICAL — ONE CLIP, ONE SHOT:\n"
        f"- Output exactly ONE continuous {duration}-second clip — "
        "absolutely NO cuts, NO transitions, NO scene changes\n"
        f"- The entire {duration} seconds must be a SINGLE unbroken take of "
        "the same scene\n"
        "- Do NOT split into multiple clips or show different angles\n\n"
        "IMAGE FIDELITY — SHOW ONLY WHAT IS IN THE IMAGE:\n"
        "- Focus ONLY on the content visible in the reference image\n"
        "- Do NOT add, duplicate, or modify ANY details (windows, doors, "
        "balconies, furniture, objects)\n"
        "- Do NOT add any new objects, people,"
        " animals, vehicles, or elements\n"
        "- Do NOT remove, move, or change anything from the image\n"
        "- Every element must match the reference image exactly in number "
        "and position\n\n"
        "CAMERA — CONTAINED WITHIN THE IMAGE:\n"
        "- Slow, subtle camera movement: gentle zoom-in, very slow push, "
        "or slight drift\n"
        "- NEVER move the camera beyond the edges of the reference image\n"
        "- Do NOT reveal any new areas — stay within what the image shows\n"
        "- Ken Burns style: contained, elegant, slow movement\n\n"
        "NATURAL MOTION:\n"
        "- Trees swaying, leaves rustling, water rippling, clouds drifting\n"
        "- Curtains fluttering, candle flames, light shimmering\n"
        "- People: natural breathing, blinking, subtle movement\n"
        "- Static objects stay still (furniture, buildings, signs)\n\n"
        "Photorealistic. Warm lighting. Silent. No text overlays. 16:9."
    )
    if v_model == "Veo":
        rules += f" {duration} seconds."

    return (
        f"Create ONE SINGLE {duration}-second video clip{brand_line} "
        f"from the reference image.\n{context_block}\n{rules}"
    )


def _clear_session():
    defaults = {
        "scene_clips": {},
        "scene_voiceovers": {},
        "final_video": None,
        "music_bytes": None,
        "ai_scripts": {},
        "ai_scene_descriptions": {},
        "scene_order": [],
        "tagline": "",
        "custom_prompt": "",
        "custom_scene_prompts": {},
        "lyria_prompt": "",
        "clips_model": "",
        "session_logs": "",
        "voice_preview_bytes": None,
        "current_project": "",
        "persisted_images": {},
        "_company_name": "",
        "_brand_context": "",
        "final_scene_order": [],
        "_num_scenes": 4,
        "_video_model": "Omni",
        "_voice_name": "Charon",
        "_voice_emotion": "Warm",
    }

    for k_name, default_val in defaults.items():
        st.session_state[k_name] = default_val

    refresh_cnt = st.session_state.get("refresh_counter", 0)
    dynamic_keys_to_clear = [f"logo_uploader_{refresh_cnt}"]
    for idx in range(1, 10):
        dynamic_keys_to_clear.extend(
            [
                f"img_{idx}_{refresh_cnt}",
                f"vo_{idx}_{refresh_cnt}",
                f"desc_{idx}_{refresh_cnt}",
            ]
        )

    st.session_state["company_name_input"] = ""
    for k_item in dynamic_keys_to_clear:
        if k_item in st.session_state:
            del st.session_state[k_item]

    st.session_state.generating = False
    st.session_state.assembling = False
    st.session_state.unsaved_changes = False
    st.session_state.refresh_counter = refresh_cnt + 1


def _load_project(name: str):
    bucket = _get_bucket()
    if bucket:
        blob = bucket.blob(f"projects/{name}.json")
        if not blob.exists():
            return False
        data = json.loads(blob.download_as_string())
    else:
        path = os.path.join(PROJECTS_DIR, f"{name}.json")
        if not os.path.exists(path):
            return False
        with open(path, "r", encoding="utf-8") as f_in:
            data = json.load(f_in)

    _clear_session()

    st.session_state.scene_clips = {
        int(k): base64.b64decode(v)
        for k, v in data.get("scene_clips_b64", {}).items()
    }
    st.session_state.scene_voiceovers = {
        int(k): base64.b64decode(v)
        for k, v in data.get("scene_voiceovers_b64", {}).items()
    }
    st.session_state.persisted_images = {
        int(k): base64.b64decode(v)
        for k, v in data.get("persisted_images_b64", {}).items()
    }
    st.session_state.tagline = data.get("tagline", "")
    st.session_state.scene_order = data.get("scene_order", [])
    st.session_state.custom_prompt = data.get("custom_prompt", "")
    st.session_state.custom_scene_prompts = data.get("custom_scene_prompts", {})
    st.session_state.lyria_prompt = data.get("lyria_prompt", "")
    st.session_state.clips_model = data.get("clips_model", "")

    final_video_b64 = data.get("final_video_b64")
    st.session_state.final_video = (
        base64.b64decode(final_video_b64) if final_video_b64 else None
    )

    music_bytes_b64 = data.get("music_bytes_b64")
    st.session_state.music_bytes = (
        base64.b64decode(music_bytes_b64) if music_bytes_b64 else None
    )

    ref_cnt = st.session_state.get("refresh_counter", 0)
    voiceover_texts = data.get("voiceover_texts", {})
    if "num_scenes" in data.get("settings", {}):
        st.session_state["_num_scenes"] = data["settings"]["num_scenes"]
    elif voiceover_texts:
        st.session_state["_num_scenes"] = len(voiceover_texts)

    for k, v in voiceover_texts.items():
        st.session_state[f"vo_{k}_{ref_cnt}"] = v
    for k, v in data.get("scene_descriptions", {}).items():
        st.session_state[f"desc_{k}_{ref_cnt}"] = v

    settings = data.get("settings", {})
    st.session_state["_company_name"] = settings.get("company_name", "")
    st.session_state["company_name_input"] = settings.get("company_name", "")
    st.session_state["_brand_context"] = settings.get("brand_context", "")
    st.session_state["_video_model"] = settings.get("video_model", "Omni")
    st.session_state["_voice_name"] = settings.get("voice_name", "Charon")
    st.session_state["_voice_emotion"] = settings.get("voice_emotion", "Warm")
    if st.session_state.get("_voice_emotion") == "Energetic":
        st.session_state["_voice_emotion"] = "Warm"
    st.session_state["_enable_music"] = settings.get("enable_music", True)
    if "_num_scenes" not in st.session_state:
        st.session_state["_num_scenes"] = settings.get("num_scenes", 3)

    st.session_state.current_project = name
    st.session_state.unsaved_changes = False
    return True


PROJECTS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "projects"
)
os.makedirs(PROJECTS_DIR, exist_ok=True)


def _inline_video(video_bytes: bytes):
    """Render video via base64 data URI."""

    b64 = base64.b64encode(video_bytes).decode()
    vid_hash = hashlib.md5(video_bytes).hexdigest()[:8]
    html_str = (
        f'<video id="vid_{vid_hash}" '
        f'src="data:video/mp4;base64,{b64}" '
        'controls width="100%" '
        'style="border-radius:8px;background:#000;"></video>'
    )
    st.markdown(
        html_str,
        unsafe_allow_html=True,
    )


st.set_page_config(
    page_title="Creative Video Studio",
    layout="wide",
    page_icon=":movie_camera:",
)

# ── Session State Init ──────────────────────────────────────
for key, default in {
    "scene_clips": {},
    "scene_voiceovers": {},
    "ai_scripts": {},
    "ai_scene_descriptions": {},
    "scene_order": [],
    "tagline": "",
    "music_bytes": None,
    "final_video": None,
    "generating": False,
    "assembling": False,
    "session_logs": "",
    "custom_prompt": "",
    "custom_scene_prompts": {},
    "lyria_prompt": "",
    "clips_model": "",
    "persisted_images": {},
    "voice_preview_bytes": None,
    "prev_voice": None,
    "prev_emotion": None,
    "current_project": "",
    "unsaved_changes": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ── Handle Sharable Links via Query Params ──────────
if "project" in st.query_params:
    qp_proj = st.query_params["project"]
    if st.session_state.current_project != qp_proj:
        if qp_proj in _list_projects():
            _load_project(qp_proj)

st.markdown(
    """
<style>
button[kind="secondary"], button[kind="primary"] {
    background-color: #4285F4 !important;
    color: white !important;
    border: none !important;
}
button[kind="secondary"]:hover, button[kind="primary"]:hover {
    background-color: #3367D6 !important;
}
</style>
""",
    unsafe_allow_html=True,
)

st.title("Creative Video Studio")
st.caption("Create multi-scene video advertisements with AI")


class _LogCapture:
    """Context manager that captures stdout (print statements)."""

    def __enter__(self):
        self._buf = io.StringIO()
        self._orig = sys.stdout
        sys.stdout = self
        return self

    def write(self, text_str):
        self._orig.write(text_str)
        self._buf.write(text_str)

    def flush(self):
        self._orig.flush()

    def __exit__(self, *_):
        sys.stdout = self._orig
        st.session_state.session_logs += self._buf.getvalue()


with st.sidebar:
    # ── Project Management ────────────────────────────
    st.subheader("Projects")

    projects = _list_projects()
    if st.session_state.get("current_project", ""):
        st.caption(f"Current: **{st.session_state.current_project}**")
        if st.session_state.unsaved_changes:
            st.warning("Unsaved changes!")

    with st.form("save_brand_form", border=False):
        project_name = st.text_input(
            "Brand Name",
            value=st.session_state.get("current_project", ""),
            placeholder="e.g. Hyatt",
        )
        save_clicked = st.form_submit_button(
            "Save Brand", use_container_width=True
        )
        if save_clicked and project_name:
            _save_project(project_name.strip())
            st.query_params["project"] = project_name.strip()
            if "_force_refresh" in st.session_state:
                del st.session_state["_force_refresh"]
            st.success(f"Saved: {project_name}")
            st.rerun()

    with st.popover("Load Brand", use_container_width=True):
        if projects:
            for p in projects:
                p_col1, p_col2 = st.columns([4, 1])
                with p_col1:
                    if st.button(
                        p,
                        key=f"load_{p}",
                        use_container_width=True,
                        type="tertiary",
                    ):
                        if _load_project(p):
                            st.query_params["project"] = p
                            st.success(f"Loaded: {p}")
                            st.rerun()
                        else:
                            st.error("Project not found")
                with p_col2:
                    if st.button(
                        "✕",
                        key=f"delete_{p}",
                        help="Delete project",
                        use_container_width=True,
                        type="primary",
                    ):
                        _delete_project(p)
                        if st.query_params.get("project") == p:
                            del st.query_params["project"]
                        st.rerun()
        else:
            st.caption("No saved projects")

    st.divider()
    st.header("Settings")

    video_model = st.radio(
        "Video Model :movie_camera:",
        ["Omni", "Veo"],
        horizontal=True,
        key="_video_model",
        help="Omni (bouncybohr): fast real-time generation. "
        "Veo: high-quality cinematic generation.",
    )

    if video_model == "Omni":
        st.caption(f"Omni: {CLIP_DURATION}s clips, max 12 words/scene")
        max_words = MAX_WORDS_OMNI
    else:
        st.caption(f"Veo: {CLIP_DURATION}s clips, max 12 words/scene")
        max_words = MAX_WORDS_VEO

    enable_music = True
    st.session_state["_enable_music"] = True

    st.divider()
    st.subheader("Company Info")
    company_name = st.text_input(
        "Company / Brand Name *",
        value=st.session_state.get("_company_name", ""),
        placeholder="e.g. Hyatt, Google, BMW",
        key="company_name_input",
    )
    st.session_state["_company_name"] = company_name
    if not company_name:
        st.warning("Company name is required")

    DEFAULT_LOGO_PATH = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "google_logo.png"
    )

    logo_file = st.file_uploader(
        "Brand Logo (PNG/JPG) (optional)",
        type=["png", "jpg", "jpeg"],
        key="logo_uploader",
        help="Upload your logo (Google logo is used by default).",
    )
    logo_bytes = None

    if logo_file:
        logo_raw = logo_file.getvalue()
        logo_bytes = remove_logo_background(logo_raw)
        st.image(
            logo_bytes, width=80, caption="Uploaded Logo (background removed)"
        )
    else:
        st.info("Google logo will be used as default.")
        if os.path.exists(DEFAULT_LOGO_PATH):
            with open(DEFAULT_LOGO_PATH, "rb") as f:
                logo_raw = f.read()
            logo_bytes = remove_logo_background(logo_raw)

    brand_context = ""
    st.session_state["_brand_context"] = brand_context

    st.divider()

    if "refresh_counter" not in st.session_state:
        st.session_state.refresh_counter = 0

    def on_refresh():
        if st.session_state.unsaved_changes:
            st.session_state["_force_refresh"] = True
        else:
            if "project" in st.query_params:
                del st.query_params["project"]
            _clear_session()

    st.button(
        "Refresh / New Session", use_container_width=True, on_click=on_refresh
    )

    @st.dialog("Unsaved Changes")
    def confirm_discard_dialog():
        st.warning("Unsaved changes! Starting new session will discard them.")

        def on_discard():
            del st.session_state["_force_refresh"]
            if "project" in st.query_params:
                del st.query_params["project"]
            _clear_session()

        st.button(
            "Discard Changes",
            type="primary",
            on_click=on_discard,
            use_container_width=True,
        )

        if st.button("Cancel", use_container_width=True):
            del st.session_state["_force_refresh"]
            st.rerun()

    if st.session_state.get("_force_refresh"):
        confirm_discard_dialog()
# ── Scene Input Table ──────────────────────────────────────
col_scene_header, col_scene_num, col_dec, col_val, col_inc, _ = st.columns(
    [2, 3, 1, 1, 1, 3], vertical_alignment="center"
)
with col_scene_header:
    st.header("Scene Setup")
with col_scene_num:
    st.markdown("**Number of Scenes** *(max 4)*")

current_scenes = st.session_state.get("_num_scenes", 4)
with col_dec:
    if st.button(
        "➖",
        key="dec_scenes",
        disabled=current_scenes <= 1,
        use_container_width=True,
    ):
        st.session_state["_num_scenes"] = current_scenes - 1
        st.rerun()
with col_val:
    div_html = (
        "<div style='text-align: center; font-size: 1.4rem; "
        f"font-weight: bold;'>{current_scenes}</div>"
    )
    st.markdown(
        div_html,
        unsafe_allow_html=True,
    )
with col_inc:
    if st.button(
        "➕",
        key="inc_scenes",
        disabled=current_scenes >= 4,
        use_container_width=True,
    ):
        st.session_state["_num_scenes"] = current_scenes + 1
        st.rerun()

num_scenes = current_scenes

scene_images = {}
scene_voiceovers_text = {}
scene_descriptions = {}
valid_scenes = []
scenes_over_word_limit = set()

SCENE_PLACEHOLDERS = [
    "e.g. Have fun in the sun and indulge in the social vibes",
    "e.g. Our fully renovated hotel lets you make the most of your stay",
    "e.g. With a gorgeous swimming pool oasis",
    "e.g. 516 sophisticated hotel rooms and suites",
]

DESC_PLACEHOLDERS = [
    "e.g. Aerial drone shot sweeping over the resort pool at golden hour",
    "e.g. Slow push into the hotel lobby with warm ambient lighting",
    "e.g. Wide shot of the pool area with"
    " people relaxing, gentle camera drift",
    "e.g. Interior suite shot, morning light streaming through curtains",
]

# Pre-populate voiceovers from AI scripts BEFORE render
if st.session_state.get("ai_scripts"):
    rc = st.session_state.get("refresh_counter", 0)
    for scene_num, script in st.session_state.ai_scripts.items():
        key = f"vo_{scene_num}_{rc}"
        if script:
            st.session_state[key] = script
    st.session_state.ai_scripts = {}

if st.session_state.get("ai_scene_descriptions"):
    rc = st.session_state.get("refresh_counter", 0)
    for scene_num, desc in st.session_state.ai_scene_descriptions.items():
        key = f"desc_{scene_num}_{rc}"
        if desc:
            st.session_state[key] = desc
    st.session_state.ai_scene_descriptions = {}

cols_header = st.columns([1, 2, 3, 3])
cols_header[0].markdown("**Scene**")
cols_header[1].markdown("**Scene Image**")
cols_header[2].markdown(
    "**Voiceover Script** *(fill in or use AI to generate)*"
)
cols_header[3].markdown(
    "**Scene Direction** *(optional: describe how to create the video)*"
)

for i in range(1, int(num_scenes) + 1):
    cols = st.columns([1, 2, 3, 3])

    with cols[0]:
        st.markdown(f"### Scene {i}")

    with cols[1]:
        rc = st.session_state.get("refresh_counter", 0)

        if i in st.session_state.persisted_images:
            scene_images[i] = st.session_state.persisted_images[i]
            st.image(st.session_state.persisted_images[i], width=150)
            if st.button(
                "Replace Image", key=f"replace_img_{i}_{rc}", type="tertiary"
            ):
                del st.session_state.persisted_images[i]
                if f"img_{i}_{rc}" in st.session_state:
                    del st.session_state[f"img_{i}_{rc}"]
                st.session_state.unsaved_changes = True
                st.rerun()
        else:
            uploaded = st.file_uploader(
                f"Image for Scene {i}",
                type=["png", "jpg", "jpeg", "webp"],
                key=f"img_{i}_{rc}",
                label_visibility="collapsed",
            )
            if uploaded:
                img_bytes = uploaded.getvalue()
                st.session_state.persisted_images[i] = img_bytes
                st.session_state.unsaved_changes = True
                st.rerun()

    with cols[2]:
        rc = st.session_state.get("refresh_counter", 0)
        placeholder = SCENE_PLACEHOLDERS[(i - 1) % len(SCENE_PLACEHOLDERS)]
        vo_text = st.text_area(
            f"Voiceover for Scene {i}",
            key=f"vo_{i}_{rc}",
            height=80,
            placeholder=placeholder,
            label_visibility="collapsed",
        )
        word_count = len(vo_text.split()) if vo_text.strip() else 0
        if word_count > max_words:
            st.error(f"{word_count}/{max_words} words — reduce word count")
            scenes_over_word_limit.add(i)
        elif vo_text.strip():
            st.caption(f"{word_count}/{max_words} words")

        scene_voiceovers_text[i] = vo_text.strip()

    with cols[3]:
        rc = st.session_state.get("refresh_counter", 0)
        desc_placeholder = DESC_PLACEHOLDERS[(i - 1) % len(DESC_PLACEHOLDERS)]
        desc_text = st.text_area(
            f"Direction for Scene {i}",
            key=f"desc_{i}_{rc}",
            height=80,
            placeholder=desc_placeholder,
            label_visibility="collapsed",
        )
        scene_descriptions[i] = desc_text.strip()

    if i in scene_images and scene_voiceovers_text.get(i):
        valid_scenes.append(i)

    st.divider()

total_scenes = int(num_scenes)
all_scenes_complete = len(valid_scenes) == total_scenes
all_valid = (
    bool(company_name)
    and all_scenes_complete
    and len(scenes_over_word_limit) == 0
)

# Show detailed status
missing_images = [
    i for i in range(1, total_scenes + 1) if i not in scene_images
]
missing_scripts = [
    i for i in range(1, total_scenes + 1) if not scene_voiceovers_text.get(i)
]

if scenes_over_word_limit:
    s_lim_str = ", ".join(str(s) for s in sorted(scenes_over_word_limit))
    st.error(f"Scene(s) {s_lim_str} exceed the {max_words}-word limit.")
elif not company_name:
    st.warning("Enter a Company Name in the sidebar.")
elif missing_images and missing_scripts:
    m_img_str = ", ".join(str(s) for s in missing_images)
    m_scr_str = ", ".join(str(s) for s in missing_scripts)
    st.info(f"Missing images: {m_img_str}. Missing scripts: {m_scr_str}.")
elif missing_images:
    m_img_str = ", ".join(str(s) for s in missing_images)
    st.info(f"Upload image(s) for Scene(s) {m_img_str}.")
elif missing_scripts:
    m_scr_str = ", ".join(str(s) for s in missing_scripts)
    st.info(f"Add voiceover script(s) for Scene(s) {m_scr_str}.")
else:
    st.success(f"All {total_scenes} scene(s) ready — Generate Clips below.")


# ── AI Generate All Voiceover Scripts + Scene Descriptions ──
has_any_image = len(scene_images) > 0
has_user_descriptions = any(scene_descriptions.get(i) for i in scene_images)

ai_cols = st.columns([1, 1, 2, 2])
with ai_cols[2]:
    btn_help = (
        "Upload an image for every scene to enable AI generation."
        if missing_images
        else "Uses Gemini + Google Search to generate scripts."
    )
    if st.button(
        "AI Generate Scripts & Directions",
        help=btn_help,
        use_container_width=True,
        disabled=bool(missing_images),
    ):
        if not company_name:
            st.warning("Enter a Company Name in the sidebar before generating.")
        else:
            if not logo_file:
                st.toast("Google logo will be used as default.", icon="ℹ️")
            spinner_msg = (
                f"Researching {company_name} & generating scripts "
                f"for {len(scene_images)} scene(s)..."
            )
            with st.spinner(spinner_msg), _LogCapture():

                async def run_both():
                    t1 = await generate_all_voiceover_scripts(
                        scene_images=scene_images,
                        company_name=company_name,
                        brand_context=brand_context,
                        max_words=max_words,
                    )
                    t2 = await generate_all_voiceover_scripts(
                        scene_images=scene_images,
                        company_name=company_name,
                        brand_context=brand_context
                        + " Focus on CAMERA DIRECTIONS: describe shot "
                        "type, camera movement, lighting, and mood.",
                        max_words=30,
                    )
                    return t1, t2

                results = asyncio.run(run_both())
                vo_res, desc_res = results

                scripts, tagline, scene_order = vo_res
                for scene_num, script in scripts.items():
                    if script:
                        st.session_state.ai_scripts[scene_num] = script
                if tagline:
                    st.session_state.tagline = tagline
                if scene_order:
                    st.session_state.scene_order = scene_order

                desc_scripts, _, _ = desc_res
                for scene_num, desc in desc_scripts.items():
                    if desc:
                        st.session_state.ai_scene_descriptions[scene_num] = desc

                filled_vo = sum(1 for s in scripts.values() if s)
                filled_desc = sum(1 for s in desc_scripts.values() if s)
                if filled_vo > 0 or filled_desc > 0:
                    st.session_state.unsaved_changes = True
                    st.rerun()
                else:
                    st.error("No content generated. Check terminal.")


# ── Generate Video Clips ──────────────────────────
st.header("Generate Video Clips")

# Safety: reset stuck generating flag
if st.session_state.generating:
    st.warning("Previous generation may have been interrupted.")
    if st.button("Reset", key="reset_generating"):
        st.session_state.generating = False
        st.rerun()

# Warn if switching models with existing clips
if (
    st.session_state.scene_clips
    and st.session_state.clips_model
    and st.session_state.clips_model != video_model
):
    st.info(
        f"Clips were generated with **{st.session_state.clips_model}**. "
        f"Switching to **{video_model}** will re-generate all clips. "
        "Scene images and scripts are kept."
    )

prompt_override = st.session_state.custom_prompt

generate_clicked = st.button(
    "Generate Clips",
    disabled=not all_valid or st.session_state.generating,
    use_container_width=True,
)

if generate_clicked and all_valid:
    if not logo_file:
        st.toast("Google logo will be used as default.", icon="ℹ️")
    st.session_state.generating = True
    st.session_state.scene_clips = {}
    st.session_state.final_video = None
    st.session_state.scene_voiceovers = {}
    st.session_state.music_bytes = None
    st.session_state.clips_model = video_model
    st.session_state.unsaved_changes = True

    progress = st.progress(
        0, text=f"Generating {total_scenes} clips with {video_model}..."
    )

    gen_fn = (
        generate_scene_video
        if video_model == "Omni"
        else generate_scene_video_veo
    )
    MAX_CONCURRENT = 4
    total = len(valid_scenes)
    done_count = [0]
    result_holder = [None]
    log_buf = io.StringIO()

    def _bg_generate():
        async def _generate_all():
            sem = asyncio.Semaphore(MAX_CONCURRENT)

            async def _gen(s_idx):
                prompt_sys = st.session_state.custom_prompt
                if not prompt_sys:
                    prompt_sys = get_default_system_prompt(
                        video_model, company_name, brand_context
                    )

                prompt_sc = st.session_state.custom_scene_prompts.get(
                    str(s_idx), ""
                )
                if not prompt_sc:
                    prompt_sc = f"Scene {s_idx}: {scene_voiceovers_text[s_idx]}"
                    if scene_descriptions.get(s_idx):
                        s_desc = scene_descriptions[s_idx]
                        prompt_sc += f"\n\nScene Direction: {s_desc}"

                final_prompt = prompt_sys + "\n\n" + prompt_sc

                async with sem:
                    res_val = await gen_fn(
                        image_bytes=scene_images[s_idx],
                        voiceover_text=scene_voiceovers_text[s_idx],
                        scene_number=s_idx,
                        company_name=company_name,
                        brand_context=brand_context,
                        prompt_override=final_prompt,
                    )
                    done_count[0] += 1
                    return res_val

            raw_results = await asyncio.gather(
                *[_gen(i) for i in valid_scenes],
                return_exceptions=True,
            )

            gen_clips = {}
            for s_idx, res_val in zip(valid_scenes, raw_results):
                gen_clips[s_idx] = (
                    None if isinstance(res_val, Exception) else res_val
                )
            return gen_clips

        orig_stdout = sys.stdout
        sys.stdout = log_buf
        try:
            result_holder[0] = asyncio.run(_generate_all())
        except (
            ValueError,
            RuntimeError,
            TypeError,
            KeyError,
            AttributeError,
            OSError,
            IOError,
        ) as err:
            print(f"[Gen] Fatal error: {err}")
            result_holder[0] = {s: None for s in valid_scenes}
        finally:
            sys.stdout = orig_stdout

    from streamlit.runtime.scriptrunner import add_script_run_ctx

    thread = threading.Thread(target=_bg_generate, daemon=True)
    add_script_run_ctx(thread)
    thread.start()

    while thread.is_alive():
        pct = min(int((done_count[0] / total) * 95), 95)
        progress.progress(
            pct,
            text=f"Generated {done_count[0]}/{total} clips...",
        )
        time.sleep(3)

    thread.join()
    st.session_state.session_logs += log_buf.getvalue()

    clips = result_holder[0] or {}
    st.session_state.scene_clips = clips
    st.session_state.generating = False
    ok = sum(1 for v in clips.values() if v is not None)
    progress.progress(100, text=f"Done — {ok}/{total} clips generated")
    time.sleep(0.5)


# ── Preview & Regenerate ───────────────────────────────────
if st.session_state.scene_clips:
    st.subheader("Preview Clips")
    st.caption("Review each clip. Click 'Regenerate' to recreate.")

    @st.dialog("Review Prompt before Regenerating")
    def regenerate_dialog(sc_n):
        st.write(f"Edit the exact prompt sent to the AI for **Scene {sc_n}**.")
        dialog_sys = st.session_state.custom_prompt
        if not dialog_sys:
            dialog_sys = get_default_system_prompt(
                video_model, company_name, brand_context
            )

        dialog_sc = st.session_state.custom_scene_prompts.get(str(sc_n), "")
        if not dialog_sc:
            dialog_sc = f'Scene {sc_n}: {scene_voiceovers_text.get(sc_n, "")}'
            if scene_descriptions.get(sc_n):
                dialog_sc += f"\n\nScene Direction: {scene_descriptions[sc_n]}"

        edited_prompt = st.text_area(
            "Scene Prompt",
            value=dialog_sc,
            height=150,
            label_visibility="collapsed",
        )

        if st.button(
            "Generate New Clip", type="primary", use_container_width=True
        ):
            st.session_state.custom_scene_prompts[str(sc_n)] = (
                edited_prompt.strip()
            )
            st.session_state.regen_trigger = sc_n
            st.rerun()

    regen_trigger = st.session_state.get("regen_trigger")
    if regen_trigger:
        regen_sc_num = regen_trigger
        del st.session_state["regen_trigger"]
        if regen_sc_num in scene_images and scene_voiceovers_text.get(
            regen_sc_num
        ):
            regen_fn = (
                generate_scene_video
                if video_model == "Omni"
                else generate_scene_video_veo
            )
            p_sys = st.session_state.custom_prompt
            if not p_sys:
                p_sys = get_default_system_prompt(
                    video_model, company_name, brand_context
                )

            p_sc = st.session_state.custom_scene_prompts.get(
                str(regen_sc_num), ""
            )
            regen_prompt = p_sys + "\n\n" + p_sc

            with st.spinner(
                f"Regenerating Scene {regen_sc_num} ({video_model})..."
            ):
                new_clip = asyncio.run(
                    regen_fn(
                        image_bytes=scene_images[regen_sc_num],
                        voiceover_text=scene_voiceovers_text[regen_sc_num],
                        scene_number=regen_sc_num,
                        company_name=company_name,
                        brand_context=brand_context,
                        prompt_override=regen_prompt,
                    )
                )
                st.session_state.scene_clips[regen_sc_num] = new_clip
                st.session_state.final_video = None
                st.session_state.unsaved_changes = True
                st.rerun()
        else:
            st.warning("Missing image or voiceover for this scene")

    for scene_num in sorted(st.session_state.scene_clips.keys()):
        clip = st.session_state.scene_clips[scene_num]
        cols = st.columns([3, 1])

        with cols[0]:
            if clip is not None:
                _inline_video(clip)
                st.caption(
                    f"Scene {scene_num} — "
                    f'"{scene_voiceovers_text.get(scene_num, "")}"'
                )
            else:
                err_msg = (
                    f"Scene {scene_num} — Generation failed. "
                    "(Hint: A safety filter may have blocked the request. "
                    "Try editing the prompt/image by clicking Regenerate.)"
                )
                st.error(err_msg)

        with cols[1]:
            st.markdown(f"**Scene {scene_num}**")

            regen_blocked = scene_num in scenes_over_word_limit
            if regen_blocked:
                st.warning("Fix word limit first")
            if st.button(
                "Regenerate", key=f"regen_{scene_num}", disabled=regen_blocked
            ):
                regenerate_dialog(scene_num)

        st.divider()

    # ── Scene Order ──────────────────────────────────────────
    st.header("Final Video Ad")

    valid_scene_nums = sorted(
        k
        for k in st.session_state.scene_clips.keys()
        if st.session_state.scene_clips[k] is not None
    )

    failed_count = sum(
        1 for v in st.session_state.scene_clips.values() if v is None
    )
    if failed_count > 0:
        st.warning(
            f"{failed_count} scene(s) failed to generate. "
            "Try regenerating them before creating the final video."
        )

    # Let user reorder scenes before assembly
    ai_order = st.session_state.get("scene_order", [])
    default_order = (
        [s for s in ai_order if s in valid_scene_nums]
        if ai_order
        else valid_scene_nums
    )
    for s in valid_scene_nums:
        if s not in default_order:
            default_order.append(s)

    if "final_scene_order" not in st.session_state or set(
        st.session_state.final_scene_order
    ) != set(valid_scene_nums):
        st.session_state.final_scene_order = default_order

    if len(valid_scene_nums) > 1:
        st.subheader("Scene Order")
        st.caption("Use the **↓** button to push a scene down in the sequence.")

        new_order = list(st.session_state.final_scene_order)
        for i, scene_num in enumerate(st.session_state.final_scene_order):
            cols = st.columns([1, 11])
            with cols[0]:
                if st.button(
                    "↓",
                    key=f"down_{scene_num}",
                    disabled=(i == len(new_order) - 1),
                    use_container_width=True,
                ):
                    new_order[i], new_order[i + 1] = (
                        new_order[i + 1],
                        new_order[i],
                    )
                    st.session_state.final_scene_order = new_order
                    st.rerun()
            with cols[1]:
                text_snippet = scene_voiceovers_text.get(scene_num, "")
                if len(text_snippet) > 60:
                    text_snippet = text_snippet[:60] + "..."
                sc_html = (
                    f"<div style='padding-top: 8px;'><b>Scene {scene_num}</b> "
                    f"— <i>{text_snippet}</i></div>"
                )
                st.markdown(
                    sc_html,
                    unsafe_allow_html=True,
                )

        final_order = st.session_state.final_scene_order
    else:
        final_order = valid_scene_nums

    rc = st.session_state.get("refresh_counter", 0)
    valid_clips = [st.session_state.scene_clips[k] for k in final_order]

    st.subheader("Narrator Voice")
    st.caption("Select and preview the voice for your final video ad.")

    is_assembling = st.session_state.assembling

    v_col1, v_col2, v_col3, v_col4, v_col5 = st.columns([1, 1, 1, 1, 1])
    with v_col1:
        voice_gender_filter = st.radio(
            "Voice Type",
            ["Male", "Female"],
            horizontal=True,
            disabled=is_assembling,
        )

    voice_options = GEMINI_TTS_VOICES[voice_gender_filter.lower()]
    if st.session_state.get("_voice_name") not in voice_options:
        if voice_gender_filter.lower() == "female" and "Aoede" in voice_options:
            st.session_state["_voice_name"] = "Aoede"
        elif (
            voice_gender_filter.lower() == "male" and "Charon" in voice_options
        ):
            st.session_state["_voice_name"] = "Charon"
        else:
            st.session_state["_voice_name"] = voice_options[0]

    with v_col2:
        selected_voice = st.selectbox(
            "Voice Name",
            voice_options,
            key="_voice_name",
            help="Gemini TTS voice used for ALL scenes.",
            disabled=is_assembling,
        )

    with v_col3:
        try:
            default_emotion_idx = VOICE_EMOTIONS.index("Warm")
        except ValueError:
            default_emotion_idx = 0

        if "emotion_forced_warm" not in st.session_state:
            st.session_state["_voice_emotion"] = "Warm"
            st.session_state.emotion_forced_warm = True

        selected_emotion = st.selectbox(
            "Voice Emotion",
            VOICE_EMOTIONS,
            key="_voice_emotion",
            help="Emotion/style for the narrator voice.",
            disabled=is_assembling,
        )

    with v_col4:
        selected_speed = st.slider(
            "Voice Speed",
            min_value=0.7,
            max_value=2.0,
            value=st.session_state.get("_voice_speed", 1.0),
            step=0.05,
            help="1.0 is normal speed.",
            disabled=is_assembling,
        )
        st.session_state["_voice_speed"] = selected_speed

    with v_col5:
        st.write("")  # Spacer
        st.write("")  # Spacer
        if st.button(
            "Preview Voice", use_container_width=True, disabled=is_assembling
        ):
            with st.spinner("Previewing..."):
                preview = asyncio.run(
                    generate_voice_preview(
                        selected_voice, selected_emotion, selected_speed
                    )
                )
                if preview:
                    st.session_state.voice_preview_bytes = preview
                    st.session_state.play_preview_trigger = True
                    st.rerun()
                else:
                    st.error("Preview failed.")

    st.session_state.prev_voice = selected_voice
    st.session_state.prev_emotion = selected_emotion

    if st.session_state.voice_preview_bytes:
        do_autoplay = st.session_state.get("play_preview_trigger", False)
        aud_b64 = base64.b64encode(
            st.session_state.voice_preview_bytes
        ).decode()
        st.audio(
            f"data:audio/mpeg;base64,{aud_b64}",
            format="audio/mpeg",
            autoplay=do_autoplay,
        )
        if do_autoplay:
            st.session_state.play_preview_trigger = False

    st.divider()

    if st.session_state.assembling:
        st.warning(
            "Previous assembly may have been interrupted"
            " or is currently stuck."
        )
        if st.button("Reset Assembly State", key="reset_assembling"):
            st.session_state.assembling = False
            st.rerun()

    assemble_clicked = st.button(
        "Create Final Video Ad",
        disabled=len(valid_clips) == 0 or st.session_state.assembling,
        use_container_width=True,
        type="primary",
    )

    if assemble_clicked and valid_clips:
        if not logo_file:
            st.toast("Google logo will be used as default.", icon="ℹ️")
        st.session_state.assembling = True

        async def _assemble():
            status = st.status("Assembling final video...", expanded=True)

            all_vo_scripts = [
                scene_voiceovers_text.get(k, "") for k in final_order
            ]

            # Step 1: Voiceovers + tagline + Lyria music — all in parallel
            brand_tag = st.session_state.get("tagline", "")
            parallel_tasks = [
                generate_all_voiceovers(
                    all_vo_scripts,
                    selected_voice,
                    selected_emotion,
                    selected_speed,
                )
            ]
            if not brand_tag and company_name:
                status.update(label=f"Researching {company_name}...")
                parallel_tasks.append(lookup_company_tagline(company_name))
            else:
                status.update(
                    label="Generating voiceovers & music in parallel..."
                )
                parallel_tasks.append(asyncio.sleep(0, result=brand_tag))
            if enable_music:
                lyria_prompt = st.session_state.lyria_prompt
                parallel_tasks.append(
                    generate_background_music(
                        company_name,
                        all_vo_scripts,
                        brand_context,
                        prompt_override=lyria_prompt,
                    )
                )
            else:
                parallel_tasks.append(asyncio.sleep(0, result=None))

            res_gathered = await asyncio.gather(*parallel_tasks)
            voiceovers = res_gathered[0]
            brand_tag = res_gathered[1] or ""
            music = res_gathered[2]
            st.session_state.tagline = brand_tag

            if brand_tag:
                st.write(f"Tagline: *{brand_tag}*")
            vo_ok = sum(1 for v in voiceovers if v is not None)
            vo_fail = len(voiceovers) - vo_ok
            if vo_fail > 0:
                st.warning(f"Voiceover: {vo_ok}/{len(voiceovers)} succeeded.")
            else:
                st.write(f"All {vo_ok} voiceovers generated ({selected_voice})")
            if enable_music and music is None:
                st.warning("Music generation failed. Continuing.")

            # Step 2: Trim clips & mix voiceover (parallel via threads)
            status.update(label="Trimming clips & mixing voiceover...")
            pad_before = 0.5
            pad_after = 0.5

            def _trim_and_mix(c_in, vo):
                if vo is not None:
                    c_in = trim_clip_to_voiceover(
                        c_in, vo, pad_before, pad_after
                    )
                return mix_scene_audio(c_in, vo, None, vo_delay=pad_before)

            assembled_clips = await asyncio.gather(
                *[
                    asyncio.to_thread(_trim_and_mix, c_item, vo)
                    for c_item, vo in zip(valid_clips, voiceovers)
                ]
            )
            assembled_clips = list(assembled_clips)

            if company_name and brand_tag and valid_clips:
                status.update(label="Creating outro clip...")
                outro_text = f"{company_name}. {brand_tag}."
                outro_vo = await generate_voiceover(
                    outro_text,
                    selected_voice,
                    selected_emotion,
                    selected_speed,
                )
                last_clip = valid_clips[-1]
                outro_clip = await asyncio.to_thread(
                    create_outro_clip,
                    last_clip,
                    logo_bytes,
                    brand_tag,
                    outro_vo,
                )
                if outro_clip:
                    assembled_clips.append(outro_clip)

            # Step 3: Dissolve scenes together
            status.update(label="Dissolving scenes together...")
            scenes_video = await asyncio.to_thread(
                concatenate_scenes_with_dissolve, assembled_clips
            )

            final_ad = scenes_video

            # Step 4: Music overlay
            if final_ad and music and enable_music:
                status.update(label="Adding background music at 35%...")
                final_ad = add_background_music_to_final(final_ad, music, 0.35)

            # Step 5: Logo overlay
            if final_ad and (logo_bytes or brand_tag):
                status.update(label="Overlaying logo and tagline...")
                final_ad = overlay_logo_and_tagline_on_video(
                    final_ad,
                    logo_bytes,
                    brand_tag,
                    opacity=0.8,
                    scale=0.12,
                    margin=30,
                )

            status.update(label="Done!", state="complete")
            return final_ad

        with _LogCapture():
            final = asyncio.run(_assemble())
        st.session_state.final_video = final
        st.session_state.assembling = False
        st.session_state.unsaved_changes = True


# ── Display Final Video ────────────────────────────────────
if st.session_state.final_video is not None:
    st.subheader("Your Video Ad")

    vid_col, dl_col = st.columns([3, 1])
    with vid_col:
        _inline_video(st.session_state.final_video)
    with dl_col:
        size_mb = len(st.session_state.final_video) / (1024 * 1024)
        st.caption(f"{size_mb:.1f} MB")
        st.download_button(
            "Download",
            data=st.session_state.final_video,
            file_name="video_ad_final.mp4",
            mime="video/mp4",
        )
        if st.session_state.get("current_project", ""):
            st.caption(f"Project: {st.session_state.current_project}")
        if st.session_state.unsaved_changes:
            st.warning("Remember to save your project!")
            if st.button("Save Now", use_container_width=True):
                if st.session_state.get("current_project", ""):
                    _save_project(st.session_state.current_project)
                    st.success("Saved!")
                    st.rerun()
                else:
                    st.warning("Enter a project name in the sidebar first.")


# ── Session Logs ──────────────────────────────────────────
if st.session_state.session_logs:
    with st.expander("Pipeline Logs", expanded=False):
        import html as _html

        _escaped = _html.escape(st.session_state.session_logs).replace(
            "\n", "<br>"
        )
        div_pre = (
            '<div style="max-height:400px;overflow-y:auto;'
            'background:#0e1117;padding:1em;border-radius:4px;">'
        )
        p_pre = (
            '<p style="font-family:monospace;font-size:0.85em;'
            'color:#FAFAFA;margin:0;line-height:1.6;">'
        )
        st.markdown(
            f"{div_pre}{p_pre}{_escaped}</p></div>",
            unsafe_allow_html=True,
        )
        if st.button("Clear Logs", key="clear_logs"):
            st.session_state.session_logs = ""
            st.rerun()
