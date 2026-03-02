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

# VTO Comprehensive Application -  Version
# All features use real-time API calls - no pre-stored content
"""VTO comprehensive application with real-time API calls."""

import os
import time
import uuid

import streamlit as st
from beauty_demo import BeautyDemoTab
from google import genai
from google.api_core import exceptions as api_exceptions
from google.cloud import storage
from google.genai import types
from google.genai.types import (
    GenerateVideosConfig,
)
from google.genai.types import Image as GenAIImage
from google.genai.types import (
    ProductImage,
    RecontextImageConfig,
    RecontextImageSource,
)

# Import modules for each feature
from model_creation import ModelCreationTab
from multi_tryon import MultiTryOnTab
from single_vto import SingleVTOTab
from size_fit import SizeFitTab

# ======================
# Configuration
# ======================
st.set_page_config(
    page_title="Get Ready With Me",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Google Cloud Configuration
_default_project = os.getenv(
    "GOOGLE_CLOUD_PROJECT", "layodemo"
)
PROJECT_ID = os.getenv(
    "GCP_PROJECT_ID", _default_project
)
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "lj-vto-demo")

# Apply custom CSS
_CSS = """\
<style>
    /* Main header styling */
    .main-header {
        background: linear-gradient(
            135deg, #667eea 0%, #764ba2 100%
        );
        padding: 2rem;
        border-radius: 20px;
        margin-bottom: 2rem;
        text-align: center;
        box-shadow:
            0 10px 30px rgba(0,0,0,0.1);
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #f0f2f6;
        padding: 0.5rem;
        border-radius: 15px;
    }

    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: white;
        border-radius: 10px;
        padding-left: 20px;
        padding-right: 20px;
        font-weight: 600;
        font-size: 14px;
        color: #1e293b;
        box-shadow:
            0 2px 5px rgba(0,0,0,0.05);
        transition: all 0.3s ease;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(
            135deg, #667eea 0%, #764ba2 100%
        );
        color: white !important;
        box-shadow:
            0 4px 15px rgba(102,126,234,0.4);
    }

    /* Button styling */
    .stButton > button {
        background: linear-gradient(
            135deg, #667eea 0%, #764ba2 100%
        );
        color: white;
        border: none;
        padding: 0.5rem 2rem;
        border-radius: 25px;
        font-weight: bold;
        transition: all 0.3s ease;
        box-shadow:
            0 4px 15px rgba(102,126,234,0.2);
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow:
            0 6px 20px rgba(102,126,234,0.3);
    }

    /* Success message styling */
    .success-message {
        background: linear-gradient(
            135deg, #00b894, #00cec9
        );
        color: white;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        font-weight: bold;
        text-align: center;
        box-shadow:
            0 4px 15px rgba(0,184,148,0.2);
    }

    /* Card styling */
    .feature-card {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow:
            0 5px 15px rgba(0,0,0,0.08);
        margin-bottom: 1rem;
        transition: all 0.3s ease;
    }

    .feature-card:hover {
        transform: translateY(-5px);
        box-shadow:
            0 10px 25px rgba(0,0,0,0.15);
    }

    /* Progress bar styling */
    .stProgress > div > div > div > div {
        background: linear-gradient(
            135deg, #667eea 0%, #764ba2 100%
        );
    }

    /* Metric styling */
    [data-testid="metric-container"] {
        background: linear-gradient(
            135deg,
            #667eea15 0%,
            #764ba215 100%
        );
        padding: 1rem;
        border-radius: 10px;
        border:
            1px solid rgba(102,126,234,0.2);
    }

    /* Real-time badge */
    .realtime-badge {
        background: linear-gradient(
            135deg, #ff6b6b 0%, #ffd93d 100%
        );
        color: white;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: bold;
        display: inline-block;
        margin-left: 1rem;
        animation: pulse 2s infinite;
    }

    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
    }
</style>
"""
st.markdown(_CSS, unsafe_allow_html=True)

# ======================
# Session State Management
# ======================
def cleanup_previous_session_outputs():
    """Delete previous session outputs and enforce limits."""
    try:
        client = storage.Client(project=PROJECT_ID)
        bucket = client.bucket(BUCKET_NAME)

        # Clean up output directories
        prefixes = [
            "outputs/single_vto/",
            "outputs/beauty_demo/",
        ]
        for prefix in prefixes:
            blobs = list(
                bucket.list_blobs(prefix=prefix)
            )
            for blob in blobs:
                if not blob.name.endswith("/"):
                    blob.delete()

        # Protect preloaded model and face files
        preloaded_filenames = {
            "model_01_20260120_103259.png",
            "model_02_20260120_103301.png",
            "model_03_20260120_103303.png",
            "model_04_20260120_103305.png",
            "model_05_20260120_103257.png",
            "face_01_20260120_113301.png",
            "face_02_20260120_113301.png",
            "face_03_20260120_113301.png",
            "face_04_20260120_113301.png",
            "face_05_20260120_113301.png",
        }

        # Clean up non-preloaded model/face files
        models_prefix = "beauty/vto/models/"
        all_blobs = list(
            bucket.list_blobs(prefix=models_prefix)
        )

        for blob in all_blobs:
            if blob.name.endswith("/"):
                continue
            filename = blob.name.split("/")[-1]
            # Skip preloaded files
            if filename in preloaded_filenames:
                continue
            # Delete extra model_* or face_* files
            if filename.startswith(
                "model_"
            ) or filename.startswith("face_"):
                blob.delete()

    except (
        api_exceptions.GoogleAPICallError,
        api_exceptions.RetryError,
        ValueError,
        OSError,
    ):
        pass  # Don't block app startup

def init_session_state():
    """Initialize all session state variables"""
    if "initialized" not in st.session_state:
        st.session_state.initialized = True
        st.session_state.storage_client = None
        st.session_state.genai_client = None
        st.session_state.gemini3_client = None
        st.session_state.generated_models = []
        st.session_state.vto_results = []
        st.session_state.beauty_results = []
        st.session_state.complete_results = []

        # Clean up previous session outputs from GCS
        cleanup_previous_session_outputs()

# ======================
# Client Management
# ======================
@st.cache_resource
def get_storage_client():
    """Get Google Cloud Storage client"""
    return storage.Client(project=PROJECT_ID)

@st.cache_resource
def get_genai_client():
    """Get Google GenAI client for general use"""
    return genai.Client(
        vertexai=True,
        project=PROJECT_ID,
        location=LOCATION,
    )

@st.cache_resource
def get_gemini3_client():
    """Get Gemini 3 client for image generation"""
    return genai.Client(
        vertexai=True,
        project=PROJECT_ID,
        location="global",
    )

# ======================
#  API Functions
# ======================
def perform_virtual_tryon(
    model_bytes, garment_bytes, genai_client
):
    """Perform virtual try-on using the VTO API."""
    try:
        # Create GenAI Image objects from bytes
        person_image = GenAIImage(
            image_bytes=model_bytes
        )
        product_img = GenAIImage(
            image_bytes=garment_bytes
        )

        # Call recontext_image API
        response = genai_client.models.recontext_image(
            model="virtual-try-on-001",
            source=RecontextImageSource(
                person_image=person_image,
                product_images=[
                    ProductImage(
                        product_image=product_img
                    )
                ],
            ),
            config=RecontextImageConfig(
                output_mime_type="image/jpeg",
                number_of_images=1,
                safety_filter_level=(
                    "BLOCK_LOW_AND_ABOVE"
                ),
            ),
        )

        # Extract result image
        generated = response.generated_images
        if generated and len(generated) > 0:
            result_image = generated[0].image
            if hasattr(result_image, "image_bytes"):
                return result_image.image_bytes
            if hasattr(result_image, "_image_bytes"):
                # pylint: disable=protected-access
                return result_image._image_bytes
            return result_image

        return None

    except (
        api_exceptions.GoogleAPICallError,
        api_exceptions.RetryError,
        ValueError,
        OSError,
    ) as e:
        st.error(f"VTO API Error: {e}")
        return None

def apply_beauty_products(  # pylint: disable=unused-argument
    model_bytes, beauty_selections, genai_client
):
    """Apply beauty products using Gemini."""
    try:
        # Build prompt for beauty application
        prompt_parts = [
            "Apply the following makeup "
            "products to this person:"
        ]

        lipstick = beauty_selections.get("lipstick")
        if lipstick:
            prompt_parts.append(
                f"- Lipstick: {lipstick}"
            )
        blush = beauty_selections.get("blush")
        if blush:
            prompt_parts.append(
                f"- Blush: {blush} (apply subtly)"
            )
        eyeshadow = beauty_selections.get("eyeshadow")
        if eyeshadow:
            prompt_parts.append(
                f"- Eyeshadow: {eyeshadow}"
            )

        prompt_parts.extend([
            "Make the makeup clearly visible "
            "but professional.",
            "Maintain the person's identity "
            "and pose.",
            "Keep the background and clothing "
            "unchanged.",
        ])

        prompt = "\n".join(prompt_parts)

        # Use Gemini 3 Pro for beauty application
        gemini3_client = get_gemini3_client()

        image_part = types.Part.from_bytes(
            data=model_bytes,
            mime_type="image/png",
        )
        response = gemini3_client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=[
                image_part,
                types.Part.from_text(text=prompt),
            ],
            config=types.GenerateContentConfig(
                temperature=0.3,
                response_modalities=["IMAGE"],
                safety_settings=[
                    types.SafetySetting(
                        category=(
                            "HARM_CATEGORY_HATE_SPEECH"
                        ),
                        threshold="OFF",
                    ),
                    types.SafetySetting(
                        category=(
                            "HARM_CATEGORY_"
                            "DANGEROUS_CONTENT"
                        ),
                        threshold="OFF",
                    ),
                    types.SafetySetting(
                        category=(
                            "HARM_CATEGORY_"
                            "SEXUALLY_EXPLICIT"
                        ),
                        threshold="OFF",
                    ),
                    types.SafetySetting(
                        category=(
                            "HARM_CATEGORY_HARASSMENT"
                        ),
                        threshold="OFF",
                    ),
                ],
            ),
        )

        candidates = response.candidates
        if candidates and candidates[0].content.parts:
            for part in candidates[0].content.parts:
                inline = part.inline_data
                if inline and inline.data:
                    return inline.data

        return None

    except (
        api_exceptions.GoogleAPICallError,
        api_exceptions.RetryError,
        ValueError,
        OSError,
    ) as e:
        st.error(f"Beauty API Error: {e}")
        return None

def generate_motion_video(image_bytes, genai_client):
    """Generate runway walk video using Veo API"""
    try:
        # Save image temporarily to GCS
        storage_client = get_storage_client()
        bucket = storage_client.bucket(BUCKET_NAME)
        temp_path = f"temp/vto_{uuid.uuid4()}.png"
        temp_blob = bucket.blob(temp_path)
        temp_blob.upload_from_string(
            image_bytes, content_type="image/png"
        )

        video_prompt = (
            "Create a smooth video of the model"
            " walking towards the camera on a"
            " fashion runway. "
            "Show natural fabric motion and"
            " flow as the model walks with"
            " confidence. "
            "Keep the model facing forward"
            " throughout. "
            "Preserve all details from the"
            " reference image. "
            "Clean white runway background."
        )

        # Generate video using Veo
        gcs_uri = (
            f"gs://{BUCKET_NAME}/{temp_path}"
        )
        op = genai_client.models.generate_videos(
            model="veo-3.0-generate-001",
            prompt=video_prompt,
            image=GenAIImage(
                gcs_uri=gcs_uri,
                mime_type="image/png",
            ),
            config=GenerateVideosConfig(
                aspect_ratio="9:16",
                resolution="1080p",
                duration_seconds=6,
                enhance_prompt=True,
                generate_audio=False,
                number_of_videos=1,
            ),
        )

        # Wait for video generation
        max_wait = 180  # 3 minutes
        wait_time = 0
        while not op.done and wait_time < max_wait:
            time.sleep(10)
            wait_time += 10
            op = genai_client.operations.get(op)

        # Clean up temp image
        try:
            temp_blob.delete()
        except (
            api_exceptions.GoogleAPICallError,
            api_exceptions.NotFound,
            OSError,
        ):
            pass

        # Return video if successful
        result = op.result
        if result and result.generated_videos:
            video = result.generated_videos[0]
            return video.video.video_bytes

        return None

    except (
        api_exceptions.GoogleAPICallError,
        api_exceptions.RetryError,
        ValueError,
        OSError,
    ) as e:
        st.error(
            f"Video Generation Error: {e}"
        )
        return None

# ======================
# Main Application
# ======================
def main():
    """Main application entry point."""
    init_session_state()

    # Animated header
    _header = """\
    <div class="main-header">
        <h1 style="color: white;
            font-size: 3rem;
            margin-bottom: 0.5rem;">
            Get Ready With Me
        </h1>
        <p style="color: rgba(255,255,255,0.9);
            font-size: 1.3rem; margin: 0;">
            AI-Powered Virtual Try-On
            &amp; Beauty Platform
        </p>
        <p style="color: rgba(255,255,255,0.8);
            font-size: 1rem;
            margin-top: 1rem;">
            Powered by Gemini 3 Pro,
            Google VTO API, Veo 3.0
        </p>
    </div>
    """
    st.markdown(_header, unsafe_allow_html=True)

    # Create tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Model Creation",
        "Single Product VTO",
        "Multi Try-On",
        "Beauty Demo",
        "Size & Fit"
    ])

    # Get clients
    storage_client = get_storage_client()
    genai_client = get_genai_client()
    gemini3_client = get_gemini3_client()

    # Tab 1: Model Creation
    with tab1:
        st.markdown("## Model Creation")

        model_tab = ModelCreationTab(
            storage_client=storage_client,
            genai_client=genai_client,
            gemini3_client=gemini3_client,
            project_id=PROJECT_ID
        )
        model_tab.render()

    # Tab 2: Single Product VTO
    with tab2:
        st.markdown(
            "## Single Product Virtual Try-On"
        )
        st.info(
            "Upload model and garment for "
            "instant virtual try-on."
        )

        # Ensure generated_models is available
        if "generated_models" not in st.session_state:
            st.session_state.generated_models = []

        single_vto = SingleVTOTab(
            storage_client=storage_client,
            genai_client=genai_client,
            gemini3_client=gemini3_client,
            project_id=PROJECT_ID
        )
        single_vto.render()

    # Tab 3: Multi Try-On
    with tab3:
        st.markdown("## Multi Virtual Try-On")

        # Ensure generated_models is available
        if "generated_models" not in st.session_state:
            st.session_state.generated_models = []

        multi_tryon = MultiTryOnTab(
            storage_client=storage_client,
            genai_client=genai_client,
            project_id=PROJECT_ID
        )
        multi_tryon.render()

    # Tab 4: Beauty Demo - Makeup Application
    with tab4:
        st.markdown(
            "## Beauty Demo - Makeup Try-On"
        )

        beauty_demo = BeautyDemoTab(
            storage_client=storage_client,
            genai_client=genai_client,
            gemini3_client=gemini3_client,
            project_id=PROJECT_ID
        )
        beauty_demo.render()

    # Tab 5: Size & Fit
    with tab5:
        st.markdown("## Size & Fit")

        size_fit = SizeFitTab(
            storage_client=storage_client,
            genai_client=genai_client,
            gemini3_client=gemini3_client,
            project_id=PROJECT_ID
        )
        size_fit.render()

    # Footer
    st.markdown("---")
    _footer = """\
    <div style="text-align: center;
        color: #7f8c8d; padding: 2rem;">
        <p style="font-size: 0.9rem;
            margin-top: 0.5rem;">
            Get Ready With Me |
            Model Generation |
            Virtual Try-On |
            Beauty | Size &amp; Fit
        </p>
    </div>
    """
    st.markdown(
        _footer, unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
