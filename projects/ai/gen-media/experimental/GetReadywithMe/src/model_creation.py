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

# Model Creation Module - PRELOADED + GENERATION VERSION
# Combines preloaded models with generation capabilities
"""Model creation module with preloaded models and generation."""

import concurrent.futures
import io
import os
import time
from datetime import datetime

import streamlit as st
from google import genai
from google.genai import types
from PIL import Image, ImageDraw


class ModelCreationTab:
    """Model Gallery with Preloaded Models and Generation"""

    def __init__(
        self, storage_client, genai_client,
        gemini3_client=None, project_id=None
    ):
        self.storage_client = storage_client
        self.genai_client = genai_client
        self.project_id = project_id or "layodemo"
        self.bucket_name = os.getenv(
            "GCS_BUCKET_NAME", "lj-vto-demo"
        )
        self.gallery_prefix = (
            "beauty/vto/models/"
        )

        # Parallel processing settings
        self.max_workers = 5

        # Initialize session state for button management
        if "generating_models" not in st.session_state:
            st.session_state.generating_models = False

        # Use provided gemini3_client or create one
        if gemini3_client:
            self.gemini3_client = gemini3_client
        else:
            os.environ["GOOGLE_CLOUD_PROJECT"] = (
                self.project_id
            )
            self.gemini3_client = genai.Client(
                vertexai=True,
                project=self.project_id,
                location="global"
            )

        # Preloaded model paths from GCS bucket
        self.preloaded_models = [
            {
                "name": "Model 1",
                "path": (
                    "beauty/vto/models/"
                    "model_01_20260120_103259.png"
                ),
                "description": "",
                "id": "model_20260120_103259"
            },
            {
                "name": "Model 2",
                "path": (
                    "beauty/vto/models/"
                    "model_02_20260120_103301.png"
                ),
                "description": "",
                "id": "model_20260120_103301"
            },
            {
                "name": "Model 3",
                "path": (
                    "beauty/vto/models/"
                    "model_03_20260120_103303.png"
                ),
                "description": "",
                "id": "model_20260120_103303"
            },
            {
                "name": "Model 4",
                "path": (
                    "beauty/vto/models/"
                    "model_04_20260120_103305.png"
                ),
                "description": "",
                "id": "model_20260120_103305"
            },
            {
                "name": "Model 5",
                "path": (
                    "beauty/vto/models/"
                    "model_05_20260120_103257.png"
                ),
                "description": "",
                "id": "model_20260120_103257"
            }
        ]

        # Diverse model specifications for generation
        self.model_specs = [
            {
                "id": "model_01",
                "ethnicity": "East Asian",
                "age": "22",
                "type": "Athletic",
                "hair": "Black straight bob",
                "skin": "Light golden",
            },
            {
                "id": "model_02",
                "ethnicity": "African",
                "age": "45",
                "type": "Very Obese/Plus-size",
                "hair": "Natural afro gray-black mix",
                "skin": "Deep ebony",
            },
            {
                "id": "model_03",
                "ethnicity": "Caucasian",
                "age": "35",
                "type": "Overweight",
                "hair": "Blonde wavy shoulder-length",
                "skin": "Fair with freckles",
            },
            {
                "id": "model_04",
                "ethnicity": "South Asian",
                "age": "55",
                "type": "Skinny/Thin",
                "hair": "Salt and pepper long straight",
                "skin": "Medium brown",
            },
            {
                "id": "model_05",
                "ethnicity": "Latin American",
                "age": "28",
                "type": "Muscular/Fit",
                "hair": "Dark brown curly",
                "skin": "Warm caramel",
            },
        ]

        # Initialize session state for models
        if "generated_models" not in st.session_state:
            st.session_state.generated_models = []

        # Initialize session state for custom model
        if "custom_model_result" not in st.session_state:
            st.session_state.custom_model_result = None

    def load_preloaded_model(self, model_info):
        """Load a preloaded model from GCS or local"""
        try:
            # Try loading from GCS first
            bucket = self.storage_client.bucket(
                self.bucket_name
            )
            blob = bucket.blob(model_info["path"])

            if blob.exists():
                image_bytes = blob.download_as_bytes()
                return image_bytes, model_info
            else:
                # Fallback to a generated placeholder
                img = Image.new(
                    "RGB", (512, 768), color="white"
                )
                draw = ImageDraw.Draw(img)
                text = (
                    f"{model_info["name"]}"
                    f"\n{model_info["id"]}"
                )
                draw.text(
                    (256, 384), text,
                    fill="black", anchor="mm"
                )
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format="PNG")
                return (
                    img_byte_arr.getvalue(), model_info
                )

        except (
            ConnectionError, TimeoutError, OSError
        ) as e:
            st.warning(
                f"Could not load model "
                f"{model_info["name"]}: {str(e)}"
            )
            img = Image.new(
                "RGB", (512, 768), color="lightgray"
            )
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format="PNG")
            return img_byte_arr.getvalue(), model_info

    def generate_model_prompt(self, spec):
        """Generate prompt for model creation"""
        age = spec["age"]
        ethnicity = spec["ethnicity"]
        skin = spec["skin"]
        body_type = spec["type"]
        hair = spec["hair"]

        body_spec_lines = []
        if body_type == "Athletic":
            body_spec_lines.append(
                "- Athletic: Very fit with visible"
                " muscle definition, toned physique"
            )
        if "Obese" in body_type:
            body_spec_lines.append(
                "- Very Obese/Plus-size: Extremely"
                " heavy body type, 300+ lbs"
                " appearance, very large frame"
            )
        if body_type == "Overweight":
            body_spec_lines.append(
                "- Overweight: Fuller figure, soft"
                " rounded body, moderately heavy"
            )
        if "Skinny" in body_type:
            body_spec_lines.append(
                "- Skinny/Thin: Very thin frame,"
                " minimal body mass, lean appearance"
            )
        if "Muscular" in body_type:
            body_spec_lines.append(
                "- Muscular/Fit: Strong build with"
                " defined muscles and athletic"
                " physique"
            )
        body_specs = "\n        ".join(body_spec_lines)

        return (
            f"\n        A full-body studio photo of"
            f" a {age} year old {ethnicity} woman"
            f" with {skin} skin and a {body_type}"
            f" build, {hair}.\n\n"
            "        OUTFIT (EXACT SAME STYLE FOR"
            " ALL MODELS):\n"
            "        Outfit: plain white t-shirt"
            " (NOT tucked in), classic black jeans,"
            " and white sneakers (same style for"
            " all).\n\n"
            "        CRITICAL REQUIREMENTS:\n"
            "        Background: plain white; neutral"
            " lighting; front-facing; natural"
            " posture; no accessories, logos, text,"
            " or props.\n\n"
            "        BODY TYPE SPECIFICATIONS:\n"
            f"        {body_specs}\n\n"
            "        IMPORTANT STYLING:\n"
            "        - Make sure all models are"
            " styled the same way\n"
            "        - White t-shirt must hang"
            " naturally over jeans, NOT tucked in\n"
            "        - Full body must be visible"
            " from head to toe\n"
            "        - Professional fashion catalog"
            " photography\n"
            "        - Plain solid white background\n"
            "        - Even, neutral studio lighting"
            " with no harsh shadows\n\n"
            "        Keep the person's ethnicity,"
            " age, body type, skin tone, and hair"
            " exactly as described above.\n"
            "        "
        )

    def generate_single_model(
        self, spec, custom_prompt=None
    ):
        """Generate a single model using Gemini 3"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if custom_prompt:
                    prompt = custom_prompt
                else:
                    prompt = self.generate_model_prompt(
                        spec
                    )

                response = (
                    self.gemini3_client
                    .models.generate_content(
                        model=(
                            "gemini-3-pro-image-preview"
                        ),
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0,
                            top_p=0.95,
                            response_modalities=[
                                "IMAGE"
                            ],
                            safety_settings=[
                                types.SafetySetting(
                                    category=(
                                        "HARM_CATEGORY"
                                        "_HATE_SPEECH"
                                    ),
                                    threshold="OFF"
                                ),
                                types.SafetySetting(
                                    category=(
                                        "HARM_CATEGORY"
                                        "_DANGEROUS"
                                        "_CONTENT"
                                    ),
                                    threshold="OFF"
                                ),
                                types.SafetySetting(
                                    category=(
                                        "HARM_CATEGORY"
                                        "_SEXUALLY"
                                        "_EXPLICIT"
                                    ),
                                    threshold="OFF"
                                ),
                                types.SafetySetting(
                                    category=(
                                        "HARM_CATEGORY"
                                        "_HARASSMENT"
                                    ),
                                    threshold="OFF"
                                )
                            ],
                            image_config=(
                                types.ImageConfig(
                                    aspect_ratio="3:4",
                                    image_size="1K",
                                    output_mime_type=(
                                        "image/png"
                                    ),
                                )
                            ),
                        ),
                    )
                )

                # Extract image
                if response and response.candidates:
                    candidate = response.candidates[0]
                    if (
                        candidate.content
                        and candidate.content.parts
                    ):
                        parts = (
                            candidate.content.parts
                        )
                        for part in parts:
                            if (
                                part.inline_data
                                and part.inline_data.data
                            ):
                                return {
                                    "success": True,
                                    "data": (
                                        part
                                        .inline_data
                                        .data
                                    ),
                                    "spec": spec,
                                }

                return {
                    "success": False,
                    "error": "No image generated",
                }

            except (
                ConnectionError,
                TimeoutError,
                RuntimeError,
            ) as e:
                err_str = str(e)
                if (
                    "429" in err_str
                    and attempt < max_retries - 1
                ):
                    wait_time = (attempt + 1) * 5
                    eth = spec.get(
                        "ethnicity", "unknown"
                    )
                    print(
                        f"[RETRY] Rate limited"
                        f" generating {eth}"
                        f" model. Waiting"
                        f" {wait_time}s (attempt"
                        f" {attempt + 1}"
                        f"/{max_retries})"
                    )
                    time.sleep(wait_time)
                    continue
                return {
                    "success": False,
                    "error": err_str,
                }

    def generate_models_parallel(self):
        """Generate 5 diverse models in parallel"""
        results = []

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:
            future_to_spec = {
                executor.submit(
                    self.generate_single_model, spec
                ): spec
                for spec in self.model_specs
            }

            for future in (
                concurrent.futures.as_completed(
                    future_to_spec
                )
            ):
                spec = future_to_spec[future]
                try:
                    result = future.result(timeout=30)
                    if result["success"]:
                        eth = spec["ethnicity"]
                        btype = spec["type"]
                        results.append({
                            "image": result["data"],
                            "spec": spec,
                            "name": (
                                f"{eth} {btype} Model"
                            ),
                            "id": spec["id"],
                        })
                    else:
                        eth = spec["ethnicity"]
                        err = result.get(
                            "error", "Unknown error"
                        )
                        st.error(
                            f"Failed to generate"
                            f" {eth} model: {err}"
                        )
                except (
                    concurrent.futures.TimeoutError,
                    ConnectionError,
                    RuntimeError,
                ) as e:
                    eth = spec["ethnicity"]
                    st.error(
                        f"Failed to generate"
                        f" {eth} model: {str(e)}"
                    )

        return results

    def render(self):
        """Render the Model Creation tab"""

        # Header
        st.markdown(
            "### Model Gallery\n"
            "<p style='color: #666;"
            " margin-bottom: 2rem;'>\n"
            "Select fashion models for"
            " virtual try-on\n"
            "</p>",
            unsafe_allow_html=True,
        )

        # Create sub-tabs
        subtab1, subtab2, subtab3 = st.tabs(
            [
                "Model Gallery",
                "Generate 5 Models",
                "Custom Model",
            ]
        )

        # Tab 1: Model Gallery (Preloaded)
        with subtab1:
            st.markdown("#### Available Models")

            cols = st.columns(5)

            if (
                "generated_models"
                not in st.session_state
            ):
                st.session_state.generated_models = []

            for idx, model_info in enumerate(
                self.preloaded_models
            ):
                col = cols[idx]

                with col:
                    with st.container():
                        image_bytes, info = (
                            self.load_preloaded_model(
                                model_info
                            )
                        )

                        st.image(
                            Image.open(
                                io.BytesIO(image_bytes)
                            ),
                            caption=(
                                f"{info["name"]}"
                            ),
                            use_container_width=True,
                        )

                        model_data = {
                            "image": image_bytes,
                            "name": info["name"],
                            "id": info["id"],
                            "timestamp": (
                                datetime.now()
                                .isoformat()
                            ),
                        }

                        model_exists = any(
                            m.get("id") == info["id"]
                            for m in (
                                st.session_state
                                .generated_models
                            )
                        )

                        if not model_exists:
                            st.session_state \
                                .generated_models \
                                .append(model_data)

                        mid = info["id"]
                        if st.button(
                            "Select",
                            key=(
                                "select_model_"
                                f"{mid}"
                            ),
                        ):
                            name = info["name"]
                            st.success(
                                f"Selected {name}"
                            )
                            st.session_state \
                                .selected_model = (
                                    model_data
                                )

            if (
                len(
                    st.session_state
                    .generated_models
                ) == 0
            ):
                for model_info in (
                    self.preloaded_models
                ):
                    image_bytes, info = (
                        self.load_preloaded_model(
                            model_info
                        )
                    )
                    st.session_state \
                        .generated_models.append({
                            "image": image_bytes,
                            "name": info["name"],
                            "id": info["id"],
                            "timestamp": (
                                datetime.now()
                                .isoformat()
                            ),
                        })

        # Tab 2: Generate 5 Models
        with subtab2:
            st.markdown(
                "#### Generate Diverse Fashion Models"
            )

            if (
                "generated_5_models"
                not in st.session_state
            ):
                st.session_state \
                    .generated_5_models = []

            generating = (
                st.session_state.generating_models
            )
            if st.button(
                "Generate 5 Models",
                key="generate_5_models",
                disabled=generating,
            ):
                st.session_state \
                    .generating_models = True
                st.session_state \
                    .generated_5_models = []

                with st.spinner(
                    "Generating 5 models"
                    " in parallel..."
                ):
                    progress_bar = st.progress(
                        0,
                        text="Starting generation...",
                    )

                    generated = (
                        self
                        .generate_models_parallel()
                    )

                    if generated:
                        for idx, model_data in (
                            enumerate(generated)
                        ):
                            progress_bar.progress(
                                (idx + 1) / 5,
                                text=(
                                    f"Processing"
                                    f" {idx + 1}/5"
                                    " models..."
                                ),
                            )

                            timestamp = (
                                datetime.now()
                                .strftime(
                                    "%Y%m%d_%H%M%S"
                                )
                            )
                            mid = model_data["id"]
                            filename = (
                                f"model_{mid}"
                                f"_{timestamp}.png"
                            )
                            gcs_path = (
                                self.gallery_prefix
                                + filename
                            )

                            bucket = (
                                self.storage_client
                                .bucket(
                                    self.bucket_name
                                )
                            )
                            blob = bucket.blob(
                                gcs_path
                            )
                            blob.upload_from_string(
                                model_data["image"],
                                content_type=(
                                    "image/png"
                                ),
                            )

                            mname = (
                                model_data["name"]
                            )
                            mid = model_data["id"]
                            st.session_state \
                                .generated_models \
                                .append({
                                    "image": (
                                        model_data[
                                            "image"
                                        ]
                                    ),
                                    "name": mname,
                                    "id": (
                                        f"{mid}"
                                        f"_{timestamp}"
                                    ),
                                    "timestamp": (
                                        datetime.now()
                                        .isoformat()
                                    ),
                                })

                        progress_bar.progress(
                            1.0,
                            text=(
                                "All models generated"
                                " successfully!"
                            ),
                        )
                        count = len(generated)
                        st.success(
                            f"Generated {count}"
                            " diverse models!"
                        )

                        st.session_state \
                            .generated_5_models = (
                                generated
                            )

                st.session_state \
                    .generating_models = False

            stored = st.session_state.get(
                "generated_5_models"
            )
            if stored:
                st.markdown("##### Generated Models")
                cols = st.columns(5)
                for idx, model in enumerate(stored):
                    with cols[idx % 5]:
                        st.image(
                            Image.open(
                                io.BytesIO(
                                    model["image"]
                                )
                            ),
                            caption=model["name"],
                            use_container_width=True,
                        )

        # Tab 3: Custom Model
        with subtab3:
            st.markdown("#### Create Custom Model")

            with st.form("custom_model_form"):
                col1, col2 = st.columns(2)

                with col1:
                    age = st.selectbox(
                        "Age",
                        [
                            "18", "22", "28",
                            "35", "45", "55", "65",
                        ],
                    )
                    ethnicity = st.selectbox(
                        "Ethnicity",
                        [
                            "Asian", "African",
                            "Caucasian",
                            "Latin American",
                            "Middle Eastern",
                            "South Asian",
                        ],
                    )
                    body_type = st.selectbox(
                        "Body Type",
                        [
                            "Slim", "Athletic",
                            "Average", "Curvy",
                            "Plus-size",
                        ],
                    )

                with col2:
                    hair_color = st.selectbox(
                        "Hair Color",
                        [
                            "Black", "Brown",
                            "Blonde", "Red",
                            "Gray", "White",
                        ],
                    )
                    hair_style = st.selectbox(
                        "Hair Style",
                        [
                            "Straight", "Wavy",
                            "Curly", "Afro",
                            "Braided", "Short",
                        ],
                    )

                additional_details = st.text_area(
                    "Additional Details (optional)",
                    placeholder=(
                        "Add any specific"
                        " requirements..."
                    ),
                )

                submit = st.form_submit_button(
                    "Generate Custom Model"
                )

                if submit:
                    extra = (
                        additional_details
                        if additional_details
                        else ""
                    )
                    custom_prompt = (
                        "\n"
                        "                    "
                        "A full-body studio photo"
                        f" of a {age} year old"
                        f" {ethnicity} woman with"
                        f" a {body_type} build and"
                        f" {hair_color}"
                        f" {hair_style} hair.\n\n"
                        "                    "
                        "OUTFIT (EXACT SAME STYLE"
                        " FOR ALL MODELS):\n"
                        "                    "
                        "Outfit: plain white"
                        " t-shirt (NOT tucked in),"
                        " classic black jeans, and"
                        " white sneakers (same"
                        " style for all).\n\n"
                        f"                    "
                        f"{extra}\n\n"
                        "                    "
                        "CRITICAL REQUIREMENTS:\n"
                        "                    "
                        "Background: plain white;"
                        " neutral lighting;"
                        " front-facing; natural"
                        " posture; full body"
                        " visible.\n\n"
                        "                    "
                        "IMPORTANT STYLING:\n"
                        "                    "
                        "- White t-shirt must hang"
                        " naturally over jeans,"
                        " NOT tucked in\n"
                        "                    "
                        "- Full body must be"
                        " visible from head"
                        " to toe\n"
                        "                    "
                        "- Professional fashion"
                        " catalog photography\n"
                        "                    "
                        "- Plain solid white"
                        " background\n"
                        "                    "
                        "- Even, neutral studio"
                        " lighting with no harsh"
                        " shadows\n"
                        "                    "
                    )

                    with st.spinner(
                        "Generating custom model..."
                    ):
                        spec = {
                            "id": "custom",
                            "ethnicity": ethnicity,
                            "age": age,
                            "type": body_type,
                        }
                        result = (
                            self
                            .generate_single_model(
                                spec, custom_prompt
                            )
                        )

                        if result["success"]:
                            timestamp = (
                                datetime.now()
                                .strftime(
                                    "%Y%m%d_%H%M%S"
                                )
                            )
                            filename = (
                                "model_custom_"
                                f"{timestamp}.png"
                            )
                            gcs_path = (
                                self.gallery_prefix
                                + filename
                            )

                            bucket = (
                                self.storage_client
                                .bucket(
                                    self.bucket_name
                                )
                            )
                            blob = bucket.blob(
                                gcs_path
                            )
                            blob.upload_from_string(
                                result["data"],
                                content_type=(
                                    "image/png"
                                ),
                            )

                            st.session_state \
                                .custom_model_result \
                                = result["data"]

                            st.session_state \
                                .generated_models \
                                .append({
                                    "image": (
                                        result["data"]
                                    ),
                                    "name": (
                                        "Custom"
                                        f" {ethnicity}"
                                        " Model"
                                    ),
                                    "id": (
                                        "custom_"
                                        f"{timestamp}"
                                    ),
                                    "timestamp": (
                                        datetime.now()
                                        .isoformat()
                                    ),
                                })

                            st.success(
                                "Custom model"
                                " generated"
                                " successfully!"
                            )
                        else:
                            err = result.get(
                                "error",
                                "Unknown error",
                            )
                            st.error(
                                "Failed to"
                                f" generate: {err}"
                            )

            # Display custom model if generated
            custom_result = (
                st.session_state.custom_model_result
            )
            if custom_result:
                st.markdown(
                    "##### Generated Custom Model"
                )
                col1, col2, _col3 = st.columns(  # pylint: disable=unused-variable
                    [3, 2, 3]
                )
                with col2:
                    st.image(
                        Image.open(
                            io.BytesIO(custom_result)
                        ),
                        caption="Custom Model",
                        use_container_width=True,
                    )
