# Copyright 2026 Google LLC
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

"""Google Nest Thermostat Demo — Streamlit Chat UI with pre-generated assets.

Provides marketing agent workflows and interactive UI.
"""

import os
import sys

# Add paths — works both standalone (nest_demo/) and from parent (LayoAgent/)
_this_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_this_dir)
# Try local streamlit_demo first (self-contained), then parent
for _base in [_this_dir, _root]:
    _sd = os.path.join(_base, "streamlit_demo")
    if os.path.exists(os.path.join(_sd, "lj_marketing_agent")):
        sys.path.insert(0, os.path.join(_sd, "lj_marketing_agent"))
        sys.path.insert(0, os.path.join(_sd, "adk_common"))
        sys.path.insert(0, _sd)
        break
sys.path.insert(0, _this_dir)
sys.path.insert(0, _root)

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


import asyncio
import base64
import re
import streamlit as st
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types
from lj_marketing_agent.agent import root_agent
from adk_common.utils import utils_agents

APP_NAME = "nest_demo"
USER_ID = "demo_user"

WORKFLOW_STEPS = [
    {"key": "product_selection", "label": "Product Selection", "icon": "1"},
    {"key": "trend_research", "label": "Trend Research", "icon": "2"},
    {"key": "campaign_setup", "label": "Campaign Setup", "icon": "3"},
    {"key": "personalization", "label": "Personalization", "icon": "4"},
    {"key": "asset_sheets", "label": "Asset Sheets", "icon": "5"},
    {"key": "text_ads", "label": "Text Ads (RSA)", "icon": "6"},
    {"key": "image_ads", "label": "Image Ads", "icon": "7"},
    {"key": "video_ads", "label": "Video Ads", "icon": "8"},
    {"key": "publish", "label": "Publish to Google Ads", "icon": "9"},
]

TOOL_TO_STEP = {
    "identify_inventory_opportunities": "product_selection",
    "get_product_by_sku": "product_selection",
    "display_product_image": "product_selection",
    "extract_product_from_url": "product_selection",
    "_demo_extract_product": "product_selection",
    "trend_spotter": "trend_research",
    "search_trends": "trend_research",
    "demo_trend_research": "trend_research",
    "setup_campaign_from_sku": "campaign_setup",
    "setup_product_campaign": "campaign_setup",
    "get_campaign_idea": "campaign_setup",
    "save_selected_campaign": "campaign_setup",
    "get_selected_brief": "campaign_setup",
    "set_customer_persona": "personalization",
    "clear_customer_persona": "personalization",
    "check_existing_assets": "personalization",
    "_demo_check_existing_assets": "personalization",
    "get_asset_sheet": "asset_sheets",
    "_demo_get_asset_sheet": "asset_sheets",
    "save_selected_asset_sheet": "asset_sheets",
    "generate_text_ad": "text_ads",
    "_demo_generate_text_ad": "text_ads",
    "get_image_ads_for_audience": "image_ads",
    "get_video_ads_for_audience": "video_ads",
    "_demo_get_video_ads": "video_ads",
    "publish_to_google_ads": "publish",
    "_demo_publish_to_google_ads": "publish",
    "delete_asset_from_gcs": None,
}

st.set_page_config(
    page_title="Google Nest Demo", layout="wide", page_icon=":robot_face:"
)


def _set_bg_logo():
    for path in [
        os.path.join(os.path.dirname(__file__), "logo.jpg"),
        "logo.jpg",
        "/app/logo.jpg",
    ]:
        if os.path.exists(path):
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            st.markdown(
                f"""
            <style>
            .stApp {{
                background-image: url("data:image/jpeg;base64,{b64}");
                background-size: 60%;
                background-position: center center;
                background-repeat: no-repeat;
                background-attachment: fixed;
            }}
            .stApp::before {{
                content: "";
                position: fixed;
                top: 0; left: 0; right: 0; bottom: 0;
                background: rgba(0, 0, 0, 0.85);
                z-index: 0;
            }}
            .stApp > div {{
                position: relative;
                z-index: 1;
            }}
            </style>
            """,
                unsafe_allow_html=True,
            )
            break


_set_bg_logo()

if "session_service" not in st.session_state:
    st.session_state.session_service = InMemorySessionService()
    st.session_state.runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=st.session_state.session_service,
    )
    st.session_state.session_id = None
    st.session_state.messages = []
    st.session_state.rendered_gcs_files = set()
    st.session_state.completed_steps = set()
    st.session_state.current_step = None
    st.session_state.current_tool = None


def _update_step(tool_name):
    step = TOOL_TO_STEP.get(tool_name)
    if step:
        st.session_state.current_step = step
        st.session_state.current_tool = tool_name


def _complete_current_step():
    if st.session_state.current_step:
        st.session_state.completed_steps.add(st.session_state.current_step)


# ---- SIDEBAR ----
with st.sidebar:
    st.markdown("#### Campaign Workflow")

    for step in WORKFLOW_STEPS:
        key = step["key"]
        label = step["label"]
        if key in st.session_state.completed_steps:
            st.markdown(f"&ensp; :white_check_mark: **{label}**")
        elif key == st.session_state.current_step:
            st.markdown(f"&ensp; :arrow_forward: **:orange[{label}]**")
        else:
            st.markdown(f"&ensp; :white_circle: {label}")

    st.markdown("---")
    if st.session_state.current_tool:
        st.markdown(f"**Active:** `{st.session_state.current_tool}`")

    st.markdown("---")
    st.markdown("#### Session")
    if st.session_state.session_id:
        st.caption(f"ID: {st.session_state.session_id[:12]}...")
    if st.button("New Demo", use_container_width=True):
        st.session_state.session_id = None
        st.session_state.messages = []
        st.session_state.rendered_gcs_files = set()
        st.session_state.completed_steps = set()
        st.session_state.current_step = None
        st.session_state.current_tool = None
        if "_pending_product_image" in st.session_state:
            del st.session_state["_pending_product_image"]
        if "_logo_hint_shown" in st.session_state:
            del st.session_state["_logo_hint_shown"]
        if "_option1_started" in st.session_state:
            del st.session_state["_option1_started"]
        st.session_state._needs_greeting = True
        st.rerun()


# ---- MAIN ----
st.title("Personalized Marketing Ads Agent")

if not st.session_state.messages:
    st.session_state._needs_greeting = True


async def _ensure_session():
    if st.session_state.session_id is None:
        session = await st.session_state.session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
        )
        st.session_state.session_id = session.id
    return st.session_state.session_id


def _load_media_from_session(session):
    """Load product image from session state — same as main Cloud Run app."""
    media = []
    if not session or not session.state:
        return media
    state = session.state
    product_image_uri = state.get("PRODUCT_IMAGE_URI", "")
    if not product_image_uri:
        product_data = state.get("product", {})
        if isinstance(product_data, dict):
            media_data = product_data.get("media", {})
            if isinstance(media_data, dict):
                product_image_uri = media_data.get("main_image_url", "")
    if product_image_uri:
        uri_key = f"product_{product_image_uri}"
        if uri_key not in st.session_state.rendered_gcs_files:
            st.session_state.rendered_gcs_files.add(uri_key)
            try:
                img_bytes, _ = utils_agents.download_bytes_from_reference(
                    product_image_uri
                )
                if img_bytes:
                    media.append(
                        {"type": "image", "content": img_bytes, "mime": "image/png"}
                    )
            except Exception:
                pass
    return media


async def _run_agent(user_message: str):
    session_id = await _ensure_session()
    content = genai_types.Content(
        role="user",
        parts=[genai_types.Part.from_text(text=user_message)],
    )

    gcs_image_urls = re.findall(
        r"gs://[^\s]+\.(?:png|jpg|jpeg)", user_message, re.IGNORECASE
    )
    https_image_urls = re.findall(
        r"https://storage\.googleapis\.com/[^\s]+\.(?:png|jpg|jpeg)",
        user_message,
        re.IGNORECASE,
    )
    for url in gcs_image_urls + https_image_urls:
        if "logo" not in url.lower():
            st.session_state.setdefault("_pending_product_image", url)

    responses = []
    async for event in st.session_state.runner.run_async(
        user_id=USER_ID,
        session_id=session_id,
        new_message=content,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    tool_name = part.function_call.name
                    print(f"[DEMO SIDEBAR] Tool called: {tool_name}")
                    _update_step(tool_name)
                    _complete_current_step()
                    if hasattr(part.function_call, "args") and part.function_call.args:
                        args = part.function_call.args
                        if isinstance(args, dict):
                            for k, v in args.items():
                                if k == "sku" and v:
                                    st.session_state["_last_sku"] = v
                elif hasattr(part, "function_response") and part.function_response:
                    resp_data = part.function_response
                    if hasattr(resp_data, "response") and isinstance(
                        resp_data.response, dict
                    ):
                        r = resp_data.response
                        if "product_summary" in r:
                            pname = r.get("product_summary", {}).get("product_name", "")
                            if pname:
                                st.session_state["_gcs_output_folder"] = pname.replace(
                                    " ", "_"
                                )[:40]
                elif part.text:
                    responses.append({"type": "text", "content": part.text})
                elif part.inline_data and part.inline_data.data:
                    mime = part.inline_data.mime_type or ""
                    data = part.inline_data.data
                    if "image" in mime:
                        responses.append(
                            {"type": "image", "content": data, "mime": mime}
                        )
                    elif "video" in mime:
                        responses.append(
                            {"type": "video", "content": data, "mime": mime}
                        )

    # Mark current step complete
    _complete_current_step()
    st.session_state.current_tool = None

    # Display pending product image (from user message GCS/HTTPS URLs)
    pending_img = st.session_state.get("_pending_product_image")
    if pending_img and pending_img not in st.session_state.rendered_gcs_files:
        has_product_text = any(
            r["type"] == "text"
            and (
                "selected product" in r["content"].lower()
                or "here is your" in r["content"].lower()
            )
            for r in responses
        )
        if has_product_text:
            st.session_state.rendered_gcs_files.add(pending_img)
            try:
                img_bytes, _ = utils_agents.download_bytes_from_reference(pending_img)
                if img_bytes:
                    responses.insert(
                        0, {"type": "image", "content": img_bytes, "mime": "image/png"}
                    )
            except Exception:
                pass

    # Load product image from session state (same as main Cloud Run app)
    try:
        session = await st.session_state.session_service.get_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=session_id,
        )
        if session and session.state:
            if not any(r["type"] == "image" for r in responses):
                gcs_media = _load_media_from_session(session)
                responses.extend(gcs_media)

            # Scan GCS for newly generated assets (non-Nest real generation)
            output_folder = getattr(_agent_mod, "OUTPUT_FOLDER", "generated")
            if output_folder and output_folder != "generated":
                try:
                    from google.cloud import storage as gcs_storage
                    import datetime

                    storage_client = gcs_storage.Client(
                        project=os.getenv("GOOGLE_CLOUD_PROJECT")
                    )
                    bucket = storage_client.bucket(
                        os.getenv("GOOGLE_CLOUD_BUCKET_ARTIFACTS")
                    )
                    now = datetime.datetime.now(datetime.timezone.utc)
                    blobs = list(
                        bucket.list_blobs(prefix=f"{output_folder}/", max_results=50)
                    )
                    new_blobs = [
                        b
                        for b in blobs
                        if b.updated and (now - b.updated).total_seconds() < 120
                    ]
                    for blob in new_blobs:
                        gcs_key = f"gs://{bucket.name}/{blob.name}"
                        if gcs_key in st.session_state.rendered_gcs_files:
                            continue
                        name = blob.name.split("/")[-1]
                        if (
                            name.startswith("_")
                            or name.startswith("keyframe_")
                            or name.startswith("clip_act")
                            or name.endswith(".json")
                            or name.startswith("background_music")
                        ):
                            continue
                        if name.endswith(".png") or name.endswith(".jpg"):
                            st.session_state.rendered_gcs_files.add(gcs_key)
                            data = blob.download_as_bytes()
                            if data:
                                responses.append(
                                    {
                                        "type": "image",
                                        "content": data,
                                        "mime": "image/png",
                                    }
                                )
                        elif name.endswith(".mp4"):
                            st.session_state.rendered_gcs_files.add(gcs_key)
                            data = blob.download_as_bytes()
                            if data:
                                responses.append(
                                    {
                                        "type": "video",
                                        "content": data,
                                        "mime": "video/mp4",
                                    }
                                )
                except Exception:
                    pass
    except Exception:
        pass

    return responses


def _render_item(item):
    if item["type"] == "text":
        st.markdown(item["content"])
    elif item["type"] == "image":
        img_b64 = (
            base64.b64encode(item["content"]).decode()
            if isinstance(item["content"], bytes)
            else ""
        )
        if img_b64:
            st.markdown(
                f'<img src="data:image/png;base64,{img_b64}" width="500" style="margin-bottom:20px; border-radius:8px;">',
                unsafe_allow_html=True,
            )
        else:
            st.image(item["content"], width=400)
    elif item["type"] == "video":
        if isinstance(item["content"], bytes):
            vid_b64 = base64.b64encode(item["content"]).decode()
            st.markdown(
                f'<video controls width="600"><source src="data:video/mp4;base64,{vid_b64}" type="video/mp4"></video>',
                unsafe_allow_html=True,
            )
        else:
            st.video(item["content"])


# ---- CHAT INPUT HELPERS ----


def _clean_option1_text(text):
    """Fix quantities and strip regeneration offers for option 1 responses."""
    t = text
    if "campaign concept" in t.lower():
        t = t.replace("(1, 2, 3, or 4)", "(1, 2, or 3)")
    if "segment" in t.lower():
        t = t.replace("(1, 2, 3, or 4)", "(1 or 2)")
        t = t.replace("(1, 2, or 3)", "(1 or 2)")
    if "asset sheet" in t.lower():
        t = t.replace("(1, 2, or 3)", "(1, 2, 3, or 4)")
        t = t.replace("(1, 2, 3)", "(1, 2, 3, or 4)")
    if "image ad" in t.lower():
        t = t.replace("(1 or 2)", "(1, 2, 3, or 4)")
        t = t.replace("(1, 2, or 3)", "(1, 2, 3, or 4)")
        t = t.replace("(1, 2, 3)", "(1, 2, 3, or 4)")
    cleaned = []
    for line in t.split("\n"):
        low = line.lower()
        if "regenerate" in low:
            continue
        if "if not" in low and ("tell me" in low or "happy" in low or "change" in low):
            continue
        if "processing time" in low:
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def _filter_standalone_logos(agent_parts):
    """For option 1: remove stray logo images without ad context."""
    if not st.session_state.get("_option1_started"):
        return agent_parts
    has_ad_text = any(
        r.get("type") == "text"
        and any(
            w in r["content"].lower()
            for w in [
                "image ad",
                "asset sheet",
                "product details",
                "product extraction",
                "here is your product",
                "auto-extracted",
            ]
        )
        for r in agent_parts
    )
    has_video = any(r.get("type") == "video" for r in agent_parts)
    if has_video and not has_ad_text:
        return [p for p in agent_parts if p.get("type") != "image"]
    if not has_ad_text:
        return [
            p
            for p in agent_parts
            if not (
                p.get("type") == "image"
                and isinstance(p.get("content"), bytes)
                and len(p["content"]) < 200000
            )
        ]
    return agent_parts


# ---- DISPLAY CHAT HISTORY ----

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        for item in msg["parts"]:
            _render_item(item)

# Auto-greeting — static, no agent call (prevents looping)
if st.session_state.get("_needs_greeting"):
    del st.session_state["_needs_greeting"]
    greeting = (
        "Hi! I'm **Personalized Marketing Ads Agent**, your Marketing Campaign Director. "
        "I create high-impact marketing campaigns with image and video ads for any product.\n\n"
        "Here are three ways to get started:\n\n"
        '1. **"Paste a product URL"** — Share any product page link and I\'ll auto-extract all product details and build a campaign.\n'
        '2. **"Show me inventory opportunities"** — I\'ll query the product database to find products needing a marketing boost.\n'
        '3. **"I have a product to market"** — You provide the product details manually.\n\n'
        "Which path would you like to take?"
    )
    with st.chat_message("assistant"):
        st.markdown(greeting)
    st.session_state.messages.append(
        {"role": "assistant", "parts": [{"type": "text", "content": greeting}]}
    )


# ---- CHAT INPUT HANDLER ----

if user_input := st.chat_input("Type your message..."):
    st.session_state.messages.append(
        {"role": "user", "parts": [{"type": "text", "content": user_input}]}
    )
    with st.chat_message("user"):
        st.markdown(user_input)

    stripped = user_input.strip()
    agent_input = user_input
    if stripped in ("1", "2", "3") and len(st.session_state.messages) <= 2:
        agent_input = {
            "1": "I want to paste a product URL",
            "2": "Show me inventory opportunities",
            "3": "I want to provide my product details manually — brand name, product name, and description. Do not ask for a URL.",
        }.get(stripped, user_input)

    with st.chat_message("assistant"):
        with st.spinner("Generating..."):
            responses = asyncio.run(_run_agent(agent_input))

        agent_parts = []
        for resp in responses:
            _render_item(resp)
            agent_parts.append(resp)

            agent_parts = _filter_standalone_logos(agent_parts)

            if not agent_parts:
                st.markdown("*(Processing...)*")
                agent_parts = [{"type": "text", "content": "*(Processing...)*"}]

            st.session_state.messages.append(
                {"role": "assistant", "parts": agent_parts}
            )
