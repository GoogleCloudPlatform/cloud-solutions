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

"""Script 1: Interactive Streamlit UI for Video Ads Agent.

Run:
    streamlit run video_ads_agent/streamlit_video_ads.py
"""

import asyncio
import base64
import io
import os
import sys
import threading
import time

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from video_ads_agent.agent import (
    MAX_WORDS_OMNI,
    MAX_WORDS_VEO,
    CHIRP3_HD_VOICES,
    build_omni_prompt,
    build_veo_prompt,
    generate_scene_video,
    generate_scene_video_veo,
    generate_all_voiceover_scripts,
    generate_all_voiceovers,
    generate_voice_preview,
    generate_background_music,
    lookup_company_tagline,
    generate_title_card,
    probe_video_resolution,
    trim_clip_to_voiceover,
    mix_scene_audio,
    concatenate_scenes_with_dissolve,
    hard_concat_clips,
    add_background_music_to_final,
    remove_logo_background,
    overlay_logo_on_video,
)


def _inline_video(video_bytes: bytes):
    """Render video via base64 data URI — bypasses Streamlit's media file server."""
    b64 = base64.b64encode(video_bytes).decode()
    st.markdown(
        f'<video controls width="100%" style="border-radius:8px;background:#000;">'
        f'<source src="data:video/mp4;base64,{b64}" type="video/mp4">'
        f'</video>',
        unsafe_allow_html=True,
    )


st.set_page_config(
    page_title="Video Ads Studio",
    layout="wide",
    page_icon=":movie_camera:",
)

st.markdown("""
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
""", unsafe_allow_html=True)

st.title("Video Ads Studio")
st.caption("Create multi-scene video advertisements with AI")


class _LogCapture:
    """Context manager that captures stdout (print statements from pipeline functions)."""
    def __enter__(self):
        self._buf = io.StringIO()
        self._orig = sys.stdout
        sys.stdout = self
        return self

    def write(self, s):
        self._orig.write(s)
        self._buf.write(s)

    def flush(self):
        self._orig.flush()

    def __exit__(self, *_):
        sys.stdout = self._orig
        st.session_state.session_logs += self._buf.getvalue()

# ── Session State Init ──────────────────────────────────────
for key, default in {
    "scene_clips": {},       # {scene_number: bytes}
    "scene_voiceovers": {},  # {scene_number: bytes}
    "ai_scripts": {},        # {scene_number: str} — AI-generated voiceover scripts
    "scene_order": [],       # optimal scene order from Gemini
    "tagline": "",           # company tagline from Google Search
    "music_bytes": None,
    "final_video": None,
    "generating": False,
    "assembling": False,
    "session_logs": "",      # captured pipeline logs
    "custom_prompt": "",     # user-saved custom video generation prompt
    "clips_model": "",       # which model generated current clips
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── Sidebar: Settings ──────────────────────────────────────
with st.sidebar:
    st.header("Settings")

    video_model = st.radio(
        "Video Model",
        ["Omni", "Veo"],
        horizontal=True,
        help="Omni (bouncybohr): fast real-time generation. "
             "Veo: high-quality cinematic generation.",
    )

    if video_model == "Omni":
        st.caption("Omni: 8s clips, max 15 words/scene")
        max_words = MAX_WORDS_OMNI
    else:
        st.caption("Veo: 8s clips, max 12 words/scene")
        max_words = MAX_WORDS_VEO

    num_scenes = st.number_input(
        "Number of Scenes",
        min_value=1,
        max_value=15,
        value=3,
        step=1,
        help="Choose how many scenes your video ad will have. Each scene = one video clip.",
    )

    st.divider()

    st.subheader("Narrator Voice")
    voice_gender_filter = st.radio(
        "Voice Type",
        ["Male", "Female"],
        horizontal=True,
    )

    voice_options = CHIRP3_HD_VOICES[voice_gender_filter.lower()]
    selected_voice = st.selectbox(
        "Voice Name",
        voice_options,
        index=voice_options.index("Charon") if voice_gender_filter == "Male" else 0,
        help="Chirp3-HD voice — same voice used for ALL scenes for consistency.",
    )

    if st.button("Preview Voice", use_container_width=True):
        with st.spinner(f"Generating preview for {selected_voice}..."):
            preview = asyncio.run(generate_voice_preview(selected_voice))
            if preview:
                st.audio(preview, format="audio/mp3")
            else:
                st.error("Preview failed. Check terminal for TTS errors.")

    enable_music = st.toggle("Background Music", value=True)

    if enable_music:
        st.caption("Lyria instrumental music at 35% volume")
    else:
        st.caption("No background music")

    st.divider()

    st.subheader("Company Info")
    company_name = st.text_input("Company / Brand Name *", value="", placeholder="e.g. Hyatt, Google, BMW")
    if not company_name:
        st.warning("Company name is required")

    DEFAULT_LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "google_logo.png")

    if "use_default_logo" not in st.session_state:
        st.session_state.use_default_logo = True

    logo_file = st.file_uploader(
        "Brand Logo (PNG/JPG)",
        type=["png", "jpg", "jpeg"],
        help="Upload your logo, or use the default Google logo below.",
    )
    logo_bytes = None
    if logo_file:
        st.session_state.use_default_logo = False
        logo_raw = logo_file.getvalue()
        logo_bytes = remove_logo_background(logo_raw)
        st.image(logo_bytes, width=80, caption="Logo (background removed)")
    elif st.session_state.use_default_logo and os.path.exists(DEFAULT_LOGO_PATH):
        with open(DEFAULT_LOGO_PATH, "rb") as f:
            logo_raw = f.read()
        logo_bytes = remove_logo_background(logo_raw)
        st.image(logo_bytes, width=80, caption="Default logo (Google)")
        if st.button("Remove Default Logo", use_container_width=True):
            st.session_state.use_default_logo = False
            st.rerun()

    brand_context = st.text_area(
        "Brand Context (optional)",
        value="",
        placeholder="Brief description of brand style, target audience, product category...",
        height=80,
    )



# ── Scene Input Table ──────────────────────────────────────
st.header("Scene Setup")

scene_images = {}
scene_voiceovers_text = {}
valid_scenes = []
scenes_over_word_limit = set()

SCENE_PLACEHOLDERS = [
    "e.g. Have fun in the sun and indulge in the social vibes",
    "e.g. Our fully renovated hotel lets you make the most of your stay",
    "e.g. With a gorgeous swimming pool oasis",
    "e.g. 516 sophisticated hotel rooms and suites",
    "e.g. Experience luxury dining with breathtaking ocean views",
    "e.g. Unwind in our world-class spa and wellness center",
    "e.g. Create unforgettable memories with your loved ones",
    "e.g. Where every detail is designed for your comfort",
    "e.g. Step into a world of timeless elegance",
    "e.g. Your perfect getaway starts right here",
]

# Pre-populate voiceover text areas from AI-generated scripts BEFORE widgets render
if st.session_state.ai_scripts:
    for scene_num, script in st.session_state.ai_scripts.items():
        key = f"vo_{scene_num}"
        if script:
            st.session_state[key] = script
    st.session_state.ai_scripts = {}

cols_header = st.columns([1, 3, 4])
cols_header[0].markdown("**Scene**")
cols_header[1].markdown("**Scene Image**")
cols_header[2].markdown("**Voiceover Script** *(fill in or use AI to generate)*")

for i in range(1, int(num_scenes) + 1):
    cols = st.columns([1, 3, 4])

    with cols[0]:
        st.markdown(f"### Scene {i}")

    with cols[1]:
        uploaded = st.file_uploader(
            f"Image for Scene {i}",
            type=["png", "jpg", "jpeg", "webp"],
            key=f"img_{i}",
            label_visibility="collapsed",
        )
        if uploaded:
            scene_images[i] = uploaded.getvalue()
            st.image(uploaded, width=150)

    with cols[2]:
        placeholder = SCENE_PLACEHOLDERS[(i - 1) % len(SCENE_PLACEHOLDERS)]
        vo_text = st.text_area(
            f"Voiceover for Scene {i}",
            key=f"vo_{i}",
            height=80,
            placeholder=placeholder,
            label_visibility="collapsed",
        )
        word_count = len(vo_text.split()) if vo_text.strip() else 0
        if word_count > max_words:
            st.error(f"{word_count}/{max_words} words — reduce to {max_words} words before generating")
            scenes_over_word_limit.add(i)
        elif vo_text.strip():
            st.caption(f"{word_count}/{max_words} words")

        scene_voiceovers_text[i] = vo_text.strip()

    if i in scene_images and scene_voiceovers_text.get(i):
        valid_scenes.append(i)

    st.divider()

total_scenes = int(num_scenes)
all_scenes_complete = len(valid_scenes) == total_scenes
all_valid = bool(company_name) and all_scenes_complete and len(scenes_over_word_limit) == 0

# Show detailed status so user knows exactly what's needed
missing_images = [i for i in range(1, total_scenes + 1) if i not in scene_images]
missing_scripts = [i for i in range(1, total_scenes + 1) if not scene_voiceovers_text.get(i)]

if scenes_over_word_limit:
    st.error(f"Scene(s) {', '.join(str(s) for s in sorted(scenes_over_word_limit))} exceed the {max_words}-word limit. Fix before generating.")
elif not company_name:
    st.warning("Enter a Company Name in the sidebar.")
elif missing_images and missing_scripts:
    st.info(f"Missing images: Scene(s) {', '.join(str(s) for s in missing_images)}. Missing scripts: Scene(s) {', '.join(str(s) for s in missing_scripts)}.")
elif missing_images:
    st.info(f"Upload image(s) for Scene(s) {', '.join(str(s) for s in missing_images)}.")
elif missing_scripts:
    st.info(f"Add voiceover script(s) for Scene(s) {', '.join(str(s) for s in missing_scripts)}. Type your own or use AI Generate below.")
else:
    st.success(f"All {total_scenes} scene(s) ready — review prompt below, then Generate Clips.")

# ── AI Generate All Voiceover Scripts (aligned under Voiceover column) ──
has_any_image = len(scene_images) > 0
if has_any_image:
    ai_cols = st.columns([1, 3, 4])
    with ai_cols[2]:
        if st.button(
            "AI Generate All Voiceover Scripts",
            help="Uses Gemini + Google Search to research the company and generate voiceover scripts for every scene that has an image uploaded.",
        ):
            if not company_name:
                st.warning("Enter a Company Name in the sidebar before generating scripts.")
            else:
                with st.spinner(f"Researching {company_name} & generating scripts for {len(scene_images)} scene(s)..."), _LogCapture():
                    scripts, tagline, scene_order = asyncio.run(generate_all_voiceover_scripts(
                        scene_images=scene_images,
                        company_name=company_name,
                        brand_context=brand_context,
                        max_words=max_words,
                    ))
                    for scene_num, script in scripts.items():
                        if script:
                            st.session_state.ai_scripts[scene_num] = script
                    if tagline:
                        st.session_state.tagline = tagline
                    if scene_order:
                        st.session_state.scene_order = scene_order
                    filled = sum(1 for s in scripts.values() if s)
                    if filled > 0:
                        st.rerun()
                    else:
                        st.error("No scripts generated. Check terminal.")


# ── Editable Video Prompt ─────────────────────────────────
st.header("Generate & Preview")

if video_model == "Omni":
    default_prompt = build_omni_prompt(
        scene_number=1, voiceover_text="<voiceover script>",
        company_name=company_name or "<company>",
        brand_context=brand_context,
    )
else:
    default_prompt = build_veo_prompt(
        scene_number=1, voiceover_text="<voiceover script>",
        company_name=company_name or "<company>",
        brand_context=brand_context,
    )

with st.expander("Video Generation Prompt (editable)", expanded=False):
    st.caption(
        "This prompt is sent to the video model for each scene. "
        "Edit to fine-tune camera motion, style, or constraints. "
        "Scene number and voiceover text are substituted per scene."
    )

    effective_prompt = st.session_state.custom_prompt if st.session_state.custom_prompt else default_prompt
    edited_prompt = st.text_area(
        f"{video_model} Prompt",
        value=effective_prompt,
        height=300,
        key="prompt_editor",
        label_visibility="collapsed",
    )

    btn_cols = st.columns(2)
    with btn_cols[0]:
        if st.button("Save Prompt", use_container_width=True):
            st.session_state.custom_prompt = edited_prompt.strip()
            st.success("Prompt saved.")
            st.rerun()
    with btn_cols[1]:
        if st.button("Reset to Default", use_container_width=True):
            st.session_state.custom_prompt = ""
            if "prompt_editor" in st.session_state:
                del st.session_state["prompt_editor"]
            st.rerun()

    if st.session_state.custom_prompt:
        st.info("Using saved custom prompt for all scenes.")
    else:
        st.caption("Using default prompt. Edit above and click Save to customize.")

prompt_override = st.session_state.custom_prompt

# Safety: reset stuck generating flag
if st.session_state.generating:
    st.warning("Previous generation may have been interrupted.")
    if st.button("Reset", key="reset_generating"):
        st.session_state.generating = False
        st.rerun()

# Warn if switching models with existing clips
if (st.session_state.scene_clips
        and st.session_state.clips_model
        and st.session_state.clips_model != video_model):
    st.info(
        f"Clips were generated with **{st.session_state.clips_model}**. "
        f"Switching to **{video_model}** will re-generate all clips. "
        f"Scene images and scripts are kept."
    )

generate_clicked = st.button(
    "Generate Clips",
    disabled=not all_valid or st.session_state.generating,
    use_container_width=True,
)

if generate_clicked and all_valid:
    st.session_state.generating = True
    st.session_state.scene_clips = {}
    st.session_state.final_video = None
    st.session_state.scene_voiceovers = {}
    st.session_state.music_bytes = None
    st.session_state.clips_model = video_model

    progress = st.progress(0, text=f"Generating {total_scenes} clips with {video_model}...")

    gen_fn = generate_scene_video if video_model == "Omni" else generate_scene_video_veo
    MAX_CONCURRENT = 4
    total = len(valid_scenes)
    done_count = [0]
    result_holder = [None]
    log_buf = io.StringIO()

    def _bg_generate():
        async def _generate_all():
            sem = asyncio.Semaphore(MAX_CONCURRENT)

            async def _gen(scene_num):
                scene_prompt = ""
                if prompt_override:
                    scene_prompt = prompt_override.replace(
                        "<voiceover script>", scene_voiceovers_text[scene_num]
                    ).replace("Scene 1:", f"Scene {scene_num}:")
                async with sem:
                    result = await gen_fn(
                        image_bytes=scene_images[scene_num],
                        voiceover_text=scene_voiceovers_text[scene_num],
                        scene_number=scene_num,
                        company_name=company_name,
                        brand_context=brand_context,
                        prompt_override=scene_prompt,
                    )
                    done_count[0] += 1
                    return result

            results = await asyncio.gather(
                *[_gen(i) for i in valid_scenes],
                return_exceptions=True,
            )

            clips = {}
            for scene_num, result in zip(valid_scenes, results):
                clips[scene_num] = None if isinstance(result, Exception) else result
            return clips

        orig_stdout = sys.stdout
        sys.stdout = log_buf
        try:
            result_holder[0] = asyncio.run(_generate_all())
        except Exception as e:
            print(f"[Gen] Fatal error: {e}")
            result_holder[0] = {s: None for s in valid_scenes}
        finally:
            sys.stdout = orig_stdout

    thread = threading.Thread(target=_bg_generate, daemon=True)
    thread.start()

    while thread.is_alive():
        pct = min(int((done_count[0] / total) * 95), 95)
        progress.progress(pct, text=f"Generated {done_count[0]}/{total} clips with {video_model}...")
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
    st.caption("Review each clip. Click 'Regenerate' to re-create any scene you're not happy with.")

    for scene_num in sorted(st.session_state.scene_clips.keys()):
        clip = st.session_state.scene_clips[scene_num]
        cols = st.columns([3, 1])

        with cols[0]:
            if clip is not None:
                _inline_video(clip)
                st.caption(
                    f"Scene {scene_num} — "
                    f"\"{scene_voiceovers_text.get(scene_num, '')}\""
                )
            else:
                st.error(f"Scene {scene_num} — Generation failed. (Hint: A safety filter may have blocked the request. Try editing the prompt/image by clicking Regenerate to retry.)")

        with cols[1]:
            st.markdown(f"**Scene {scene_num}**")
            regen_blocked = scene_num in scenes_over_word_limit
            if regen_blocked:
                st.warning(f"Fix word limit first")
            if st.button(f"Regenerate", key=f"regen_{scene_num}", disabled=regen_blocked):
                if scene_num in scene_images and scene_voiceovers_text.get(scene_num):
                    regen_fn = generate_scene_video if video_model == "Omni" else generate_scene_video_veo
                    regen_prompt = ""
                    saved_prompt = st.session_state.get("custom_prompt", "")
                    if saved_prompt:
                        regen_prompt = saved_prompt.replace(
                            "<voiceover script>", scene_voiceovers_text[scene_num]
                        ).replace("Scene 1:", f"Scene {scene_num}:")
                    with st.spinner(f"Regenerating Scene {scene_num} with {video_model}..."):
                        new_clip = asyncio.run(
                            regen_fn(
                                image_bytes=scene_images[scene_num],
                                voiceover_text=scene_voiceovers_text[scene_num],
                                scene_number=scene_num,
                                company_name=company_name,
                                brand_context=brand_context,
                                prompt_override=regen_prompt,
                            )
                        )
                        st.session_state.scene_clips[scene_num] = new_clip
                        st.session_state.final_video = None
                        st.rerun()
                else:
                    st.warning("Missing image or voiceover for this scene")

        st.divider()

    # ── Scene Order ──────────────────────────────────────────
    st.header("Final Video Ad")

    valid_scene_nums = sorted(
        k for k in st.session_state.scene_clips.keys()
        if st.session_state.scene_clips[k] is not None
    )

    failed_count = sum(
        1 for v in st.session_state.scene_clips.values() if v is None
    )
    if failed_count > 0:
        st.warning(
            f"{failed_count} scene(s) failed to generate. "
            f"Try regenerating them before creating the final video."
        )

    # Let user reorder scenes before assembly
    ai_order = st.session_state.get("scene_order", [])
    default_order = [s for s in ai_order if s in valid_scene_nums] if ai_order else valid_scene_nums
    for s in valid_scene_nums:
        if s not in default_order:
            default_order.append(s)

    if len(valid_scene_nums) > 1:
        st.subheader("Scene Order")
        st.caption("Drag to reorder scenes for the final ad. AI suggested order is pre-filled.")
        order_options = [f"Scene {s}" for s in default_order]
        reordered = st.multiselect(
            "Scene order (remove and re-add to reorder)",
            options=[f"Scene {s}" for s in valid_scene_nums],
            default=order_options,
            label_visibility="collapsed",
        )
        final_order = [int(s.split()[-1]) for s in reordered] if reordered else default_order
    else:
        final_order = valid_scene_nums

    valid_clips = [st.session_state.scene_clips[k] for k in final_order]

    assemble_clicked = st.button(
        "Create Final Video Ad",
        disabled=len(valid_clips) == 0 or st.session_state.assembling,
        use_container_width=True,
        type="primary",
    )

    if assemble_clicked and valid_clips:
        st.session_state.assembling = True

        async def _assemble():
            status = st.status("Assembling final video...", expanded=True)

            scripts = [scene_voiceovers_text.get(k, "") for k in final_order]

            # Step 1: Voiceovers + tagline + Lyria music — all in parallel
            tagline = st.session_state.get("tagline", "")
            parallel_tasks = [generate_all_voiceovers(scripts, selected_voice)]
            if not tagline and company_name:
                status.update(label=f"Researching {company_name}, voiceovers & music in parallel...")
                parallel_tasks.append(lookup_company_tagline(company_name))
            else:
                status.update(label=f"Generating voiceovers & music in parallel...")
                parallel_tasks.append(asyncio.coroutine(lambda: tagline)() if False else asyncio.sleep(0, result=tagline))
            if enable_music:
                parallel_tasks.append(generate_background_music(company_name, scripts, brand_context))
            else:
                parallel_tasks.append(asyncio.sleep(0, result=None))

            results = await asyncio.gather(*parallel_tasks)
            voiceovers = results[0]
            tagline = results[1] or ""
            music = results[2]
            st.session_state.tagline = tagline

            if tagline:
                st.write(f"Tagline: *{tagline}*")
            vo_ok = sum(1 for v in voiceovers if v is not None)
            vo_fail = len(voiceovers) - vo_ok
            if vo_fail > 0:
                st.warning(f"Voiceover: {vo_ok}/{len(voiceovers)} succeeded, {vo_fail} failed.")
            else:
                st.write(f"All {vo_ok} voiceovers generated with voice: {selected_voice}")
            if enable_music and music is None:
                st.warning("Background music generation failed. Continuing without music.")

            # Step 2: Trim clips & mix voiceover (parallel via threads)
            status.update(label="Trimming clips & mixing voiceover...")
            pad_before = 0.5
            pad_after = 0.5

            def _trim_and_mix(clip, vo):
                if vo is not None:
                    clip = trim_clip_to_voiceover(clip, vo, pad_before, pad_after)
                return mix_scene_audio(clip, vo, None, vo_delay=pad_before)

            assembled_clips = await asyncio.gather(
                *[asyncio.to_thread(_trim_and_mix, clip, vo)
                  for clip, vo in zip(valid_clips, voiceovers)]
            )
            assembled_clips = list(assembled_clips)

            # Step 3: Title cards at scene clip resolution + dissolve — in parallel
            status.update(label="Creating title cards & dissolving scenes...")
            clip_w, clip_h = probe_video_resolution(assembled_clips[0])
            intro_bg = scene_images.get(final_order[0]) if final_order else None
            outro_bg = scene_images.get(final_order[-1]) if final_order else None

            intro_card, outro_card, scenes_video = await asyncio.gather(
                asyncio.to_thread(generate_title_card,
                    company_name or "Video Ad", "", 3.0, clip_w, clip_h,
                    logo_bytes, True, False, intro_bg),
                asyncio.to_thread(generate_title_card,
                    company_name or "", tagline or "", 3.0, clip_w, clip_h,
                    logo_bytes, False, True, outro_bg),
                asyncio.to_thread(concatenate_scenes_with_dissolve, assembled_clips),
            )

            # Step 4: Hard-join intro + scenes + outro
            status.update(label="Joining intro, scenes & outro...")
            final_parts = []
            if intro_card:
                final_parts.append(intro_card)
            if scenes_video:
                final_parts.append(scenes_video)
            if outro_card:
                final_parts.append(outro_card)
            final = hard_concat_clips(final_parts) if len(final_parts) > 1 else (final_parts[0] if final_parts else None)

            # Step 5: Music overlay + logo overlay
            if final and music and enable_music:
                status.update(label="Adding background music at 35%...")
                final = add_background_music_to_final(final, music, 0.35)
            if final and logo_bytes:
                status.update(label="Overlaying logo...")
                final = overlay_logo_on_video(final, logo_bytes)

            status.update(label="Done!", state="complete")
            return final

        with _LogCapture():
            final = asyncio.run(_assemble())
        st.session_state.final_video = final
        st.session_state.assembling = False


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


# ── Session Logs ──────────────────────────────────────────
if st.session_state.session_logs:
    with st.expander("Pipeline Logs", expanded=False):
        import html as _html
        _escaped = _html.escape(st.session_state.session_logs).replace("\n", "<br>")
        st.markdown(
            '<div style="max-height:400px;overflow-y:auto;background:#0e1117;padding:1em;border-radius:4px;">'
            f'<p style="font-family:monospace;font-size:0.85em;color:#FAFAFA;margin:0;line-height:1.6;">'
            f'{_escaped}</p></div>',
            unsafe_allow_html=True,
        )
        if st.button("Clear Logs", key="clear_logs"):
            st.session_state.session_logs = ""
            st.rerun()
