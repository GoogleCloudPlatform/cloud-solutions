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

# Beauty Demo Module - Makeup Application
# Live makeup effects with face models and VTO integration
"""Beauty Demo - Makeup Application with face models and VTO."""

import concurrent.futures
import io
import os
import time
import uuid

import streamlit as st
from gcs_utils import (
    generate_unique_path,
    save_to_gcs,
)
from google.genai import types
from PIL import Image


class BeautyDemoTab:
    """Beauty Demo - Makeup Application with Face Models"""

    def __init__(
        self, storage_client, genai_client,
        gemini3_client=None, project_id=None
    ):
        self.storage_client = storage_client
        self.genai_client = genai_client
        self.project_id = project_id or "layodemo"
        self.bucket_name = os.getenv("GCS_BUCKET_NAME", "lj-vto-demo")
        # Limit concurrency to avoid API rate limits
        self.max_workers = 2

        # Preloaded face models from GCS
        self.preloaded_faces = [
            {
                "name": "Face 1",
                "path": "beauty/vto/models/face_01_20260120_113301.png",
                "description": "",
                "id": "face_20260120_113301_1"
            },
            {
                "name": "Face 2",
                "path": "beauty/vto/models/face_02_20260120_113301.png",
                "description": "",
                "id": "face_20260120_113301_2"
            },
            {
                "name": "Face 3",
                "path": "beauty/vto/models/face_03_20260120_113301.png",
                "description": "",
                "id": "face_20260120_113301_3"
            },
            {
                "name": "Face 4",
                "path": "beauty/vto/models/face_04_20260120_113301.png",
                "description": "",
                "id": "face_20260120_113301_4"
            },
            {
                "name": "Face 5",
                "path": "beauty/vto/models/face_05_20260120_113301.png",
                "description": "",
                "id": "face_20260120_113301_5"
            }
        ]

        # Use provided gemini3_client or create one
        if gemini3_client:
            self.gemini3_client = gemini3_client
        else:
            from google import genai  # pylint: disable=import-outside-toplevel
            os.environ["GOOGLE_CLOUD_PROJECT"] = (
                self.project_id
            )
            self.gemini3_client = genai.Client(
                vertexai=True,
                project=self.project_id,
                location="global"
            )

        # Initialize session state for beauty
        if "beauty_selected_models" not in st.session_state:
            st.session_state.beauty_selected_models = []
        if "beauty_results" not in st.session_state:
            st.session_state.beauty_results = {}
        if "beauty_selections" not in st.session_state:
            st.session_state.beauty_selections = {
                "lipstick": None,
                "blush": None,
                "eyeshadow": None
            }
        if "beauty_makeup_types" not in st.session_state:
            st.session_state.beauty_makeup_types = []
        if "beauty_current_index" not in st.session_state:
            st.session_state.beauty_current_index = 0
        if "beauty_all_combinations" not in st.session_state:
            st.session_state.beauty_all_combinations = []
        if "beauty_showing_results" not in st.session_state:
            st.session_state.beauty_showing_results = False
        if "beauty_generated_faces" not in st.session_state:
            st.session_state.beauty_generated_faces = []

    def load_preloaded_face(self, face_info):
        """Load a preloaded face model from GCS"""
        try:
            bucket = self.storage_client.bucket(self.bucket_name)
            blob = bucket.blob(face_info["path"])

            if blob.exists():
                image_bytes = blob.download_as_bytes()
                return image_bytes, face_info
            # Create placeholder if not found
            # pylint: disable=import-outside-toplevel
            from PIL import Image as PILImage  # pylint: disable=reimported
            from PIL import ImageDraw
            img = PILImage.new(
                "RGB", (512, 512), color="white"
            )
            draw = ImageDraw.Draw(img)
            draw.text(
                (256, 256), face_info["name"],
                fill="black", anchor="mm"
            )
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format="PNG")
            return img_byte_arr.getvalue(), face_info

        except (OSError, ValueError, KeyError):
            # Return placeholder on error
            # pylint: disable=import-outside-toplevel
            from PIL import Image as PILImage  # pylint: disable=reimported
            img = PILImage.new(
                "RGB", (512, 512), color="lightgray"
            )
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format="PNG")
            return img_byte_arr.getvalue(), face_info

    def load_face_models_from_gallery(self):
        """Load face models from preloaded collection"""
        face_models = []

        # Load all preloaded face models
        for face_info in self.preloaded_faces:
            image_bytes, info = self.load_preloaded_face(face_info)

            # Resize for display
            resized_bytes = self.resize_image_for_display(
                image_bytes
            )

            info_path = info["path"]
            gcs_path = (
                f"gs://{self.bucket_name}/{info_path}"
            )
            face_models.append({
                "id": info["id"],
                "name": info["name"],
                "image_bytes": resized_bytes,
                "original_bytes": image_bytes,
                "gcs_path": gcs_path
            })

        # Return 5 preloaded face models
        return face_models[:5]

    def generate_face_model(self, prompt):
        """Generate a face model using Gemini 3 Pro"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Generate face model with diversity
                safety = [
                    types.SafetySetting(
                        category=(
                            "HARM_CATEGORY_HATE_SPEECH"
                        ),
                        threshold="OFF"
                    ),
                    types.SafetySetting(
                        category=(
                            "HARM_CATEGORY_DANGEROUS_CONTENT"
                        ),
                        threshold="OFF"
                    ),
                    types.SafetySetting(
                        category=(
                            "HARM_CATEGORY_SEXUALLY_EXPLICIT"
                        ),
                        threshold="OFF"
                    ),
                    types.SafetySetting(
                        category=(
                            "HARM_CATEGORY_HARASSMENT"
                        ),
                        threshold="OFF"
                    )
                ]
                img_cfg = types.ImageConfig(
                    aspect_ratio="1:1",
                    image_size="1K",
                    output_mime_type="image/png",
                )
                config = types.GenerateContentConfig(
                    temperature=0.9,
                    response_modalities=["IMAGE"],
                    candidate_count=1,
                    safety_settings=safety,
                    image_config=img_cfg,
                )
                response = (
                    self.gemini3_client.models
                    .generate_content(
                        model=(
                            "gemini-3-pro-image-preview"
                        ),
                        contents=[
                            types.Part.from_text(
                                text=prompt
                            )
                        ],
                        config=config,
                    )
                )

                # Extract result image
                if response and response.candidates:
                    candidate = response.candidates[0]
                    if (candidate.content
                            and candidate.content.parts):
                        for part in (
                            candidate.content.parts
                        ):
                            if (part.inline_data
                                    and part.inline_data.data):
                                return (
                                    part.inline_data.data
                                )

                return None

            except (
                ConnectionError,
                TimeoutError,
                RuntimeError,
                ValueError,
            ) as e:
                if (
                    "429" in str(e)
                    and attempt < max_retries - 1
                ):
                    wait_time = (attempt + 1) * 5
                    print(
                        f"[RETRY] Rate limited. "
                        f"Waiting {wait_time}s "
                        f"(attempt "
                        f"{attempt + 1}/"
                        f"{max_retries})"
                    )
                    time.sleep(wait_time)
                    continue
                st.error(
                    "Error generating face model:"
                    f" {str(e)}"
                )
                return None

    def generate_beauty_video(
        self, image_bytes, product_desc
    ):
        """Generate a cinematic video using Veo."""
        try:
            # Beauty makeup video prompt
            video_prompt = (
                "Create a smooth video of this "
                "person showcasing her "
                f"{product_desc}. "
                "CRITICAL: Maintain the EXACT SAME "
                "framing, zoom level, and "
                "composition as the input image. "
                "Do NOT zoom in or crop differently"
                " from the reference image. "
                "She turns her head slightly with "
                "elegant, graceful movements, "
                "allowing the light to catch the "
                "makeup perfectly. "
                "Keep her facial expression neutral"
                " and composed - no excessive "
                "smiling, just a subtle, natural "
                "expression. "
                "The face should remain exactly as "
                "in the input image - minimal "
                "expression changes. "
                "Soft, professional studio lighting"
                " emphasizes the makeup colors and"
                " finish. "
                "Keep all movements subtle and "
                "sophisticated. "
                "Preserve all details from the "
                "reference image including pose, "
                "clothing, and background."
            )

            # Pre-process image to 9:16 aspect ratio
            img = Image.open(io.BytesIO(image_bytes))

            # Target 9:16 canvas (1080x1920)
            target_ratio = 9 / 16
            current_ratio = img.width / img.height

            if current_ratio > target_ratio:
                # Wider than 9:16 - scale by width
                new_width = 1080
                scale = new_width / img.width
                new_height = int(img.height * scale)
            else:
                # Taller or equal - scale by height
                new_height = 1920
                scale = new_height / img.height
                new_width = int(img.width * scale)

            # Resize image to fit within canvas
            img_resized = img.resize(
                (new_width, new_height),
                Image.Resampling.LANCZOS
            )

            # Create 9:16 canvas with white bg
            canvas = Image.new(
                "RGB", (1080, 1920), "white"
            )

            # Center image on canvas (no cropping)
            paste_x = (1080 - new_width) // 2
            paste_y = (1920 - new_height) // 2
            canvas.paste(
                img_resized, (paste_x, paste_y)
            )

            # Convert back to bytes
            output = io.BytesIO()
            canvas.save(
                output, format="PNG", optimize=False
            )
            processed_bytes = output.getvalue()

            # Save processed image to GCS
            bucket = self.storage_client.bucket(
                self.bucket_name
            )
            temp_path = (
                f"temp/beauty_{uuid.uuid4()}.png"
            )
            temp_blob = bucket.blob(temp_path)
            temp_blob.upload_from_string(
                processed_bytes,
                content_type="image/png"
            )

            # Output directory for video
            output_gcs_uri = (
                f"gs://{self.bucket_name}"
                "/outputs/beauty_demo/try-on/videos/"
            )

            # Generate video using Veo 3.0
            # pylint: disable=import-outside-toplevel
            from google.genai.types import GenerateVideosConfig
            from google.genai.types import Image as GenAIImage

            img_gcs_uri = (
                f"gs://{self.bucket_name}/{temp_path}"
            )
            op = self.genai_client.models.generate_videos(
                model="veo-3.0-generate-001",
                prompt=video_prompt,
                image=GenAIImage(
                    gcs_uri=img_gcs_uri,
                    mime_type="image/png"
                ),
                config=GenerateVideosConfig(
                    aspect_ratio="9:16",
                    output_gcs_uri=output_gcs_uri,
                    number_of_videos=1,
                    person_generation="allow_all",
                ),
            )

            # Wait for video generation
            max_wait = 300  # 5 minutes
            wait_time = 0
            while (
                not op.done and wait_time < max_wait
            ):
                time.sleep(15)
                wait_time += 15
                op = (
                    self.genai_client.operations.get(
                        op
                    )
                )

            # Clean up temp image
            try:
                temp_blob.delete()
            except OSError:
                pass

            if not op.done:
                print(
                    "[DEBUG] Beauty video: "
                    "operation timed out after 300s"
                )
                return None

            # Return video if successful
            if (
                op.response
                and op.result
                and op.result.generated_videos
            ):
                video_uri = (
                    op.result.generated_videos[0]
                    .video.uri
                )
                # Download video from GCS
                bucket_prefix = (
                    f"gs://{self.bucket_name}/"
                )
                video_gcs_path = video_uri.replace(
                    bucket_prefix, ""
                )
                video_blob = bucket.blob(
                    video_gcs_path
                )
                video_bytes = (
                    video_blob.download_as_bytes()
                )

                return {
                    "status": "success",
                    "video_bytes": video_bytes,
                    "gcs_path": video_gcs_path
                }

            # Log failure details
            has_resp = hasattr(op, "response")
            has_result = op.result is not None
            print(
                f"[DEBUG] Beauty video failed: "
                f"done={op.done}, "
                f"has_response={has_resp}, "
                f"has_result={has_result}"
            )
            error_msg = None
            if hasattr(op, "error") and op.error:
                print(
                    "[DEBUG] Beauty video error:"
                    f" {op.error}"
                )
                if isinstance(op.error, dict):
                    error_msg = op.error.get(
                        "message", ""
                    )
                else:
                    error_msg = str(op.error)
            return {
                "status": "error",
                "error": error_msg
            }

        except (
            ConnectionError,
            TimeoutError,
            RuntimeError,
            ValueError,
            OSError,
        ) as e:
            print(
                "[DEBUG] Beauty video exception:"
                f" {str(e)}"
            )
            return {
                "status": "error",
                "error": str(e)
            }

    def _get_closest_aspect_ratio(
        self, width, height
    ):
        """Find the closest supported aspect ratio."""
        ratio = width / height
        supported = {
            "1:1": 1.0,
            "3:4": 0.75,
            "4:3": 1.333,
            "9:16": 0.5625,
            "16:9": 1.778,
        }
        closest = min(
            supported.items(),
            key=lambda x: abs(x[1] - ratio)
        )
        return closest[0]

    def apply_makeup_realtime(
        self, model_bytes, makeup_selections,
        eye_state="open"
    ):
        """Apply makeup using Gemini 3 Pro.

        Args:
            model_bytes: Face image bytes
            makeup_selections: Dict of selected products
            eye_state: "open" or "closed" eyes
        """
        # pylint: disable=import-outside-toplevel
        import threading
        import time  # pylint: disable=reimported,redefined-outer-name
        start_time = time.time()

        try:
            thread_id = (
                threading.current_thread().name
            )
            print(
                f"[DEBUG] Thread {thread_id}: "
                "Starting makeup application "
                f"(eye_state: {eye_state})"
            )
            print(
                f"[DEBUG] Thread {thread_id}: "
                f"Makeup selections: "
                f"{makeup_selections}"
            )
            print(
                f"[DEBUG] Thread {thread_id}: "
                f"Model bytes size: "
                f"{len(model_bytes)} bytes"
            )

            # Detect input image aspect ratio
            input_img = Image.open(
                io.BytesIO(model_bytes)
            )
            input_aspect = (
                self._get_closest_aspect_ratio(
                    input_img.width, input_img.height
                )
            )
            print(
                f"[DEBUG] Thread {thread_id}: "
                f"Input image: "
                f"{input_img.width}x"
                f"{input_img.height}, "
                f"closest aspect: {input_aspect}"
            )

            # Get bucket for loading product images
            bucket = self.storage_client.bucket(
                self.bucket_name
            )

            # Build prompt for makeup application
            _prompt_parts = []  # pylint: disable=unused-variable
            product_images = []

            # Check what products are selected
            has_lipstick = bool(
                makeup_selections.get("lipstick")
                and isinstance(
                    makeup_selections["lipstick"], str
                )
            )
            has_blush = bool(
                makeup_selections.get("blush")
                and isinstance(
                    makeup_selections["blush"], str
                )
            )
            has_eyeshadow = bool(
                makeup_selections.get("eyeshadow")
                and isinstance(
                    makeup_selections["eyeshadow"],
                    str
                )
            )

            print(
                f"[DEBUG] Thread {thread_id}: "
                f"Has lipstick: {has_lipstick}, "
                f"Has blush: {has_blush}, "
                f"Has eyeshadow: {has_eyeshadow}"
            )

            # Load product images
            if has_lipstick:
                color = makeup_selections.get(
                    "lipstick"
                )
                icon_path = (
                    f"beauty/lipstick/{color}"
                    "/icon.png"
                )
                icon_blob = bucket.blob(icon_path)

                if icon_blob.exists():
                    lipstick_icon = (
                        icon_blob.download_as_bytes()
                    )
                    product_images.append(
                        ("lipstick_icon",
                         lipstick_icon)
                    )
                    print(
                        "[DEBUG] Loaded lipstick "
                        f"icon from {icon_path}"
                    )

                    ref_path = (
                        f"beauty/lipstick/{color}"
                        "/img1.png"
                    )
                    ref_blob = bucket.blob(
                        ref_path
                    )
                    if ref_blob.exists():
                        lipstick_ref = (
                            ref_blob
                            .download_as_bytes()
                        )
                        product_images.append(
                            ("lipstick_ref",
                             lipstick_ref)
                        )
                        print(
                            "[DEBUG] Loaded lipstick"
                            " reference from "
                            f"{ref_path}"
                        )
                    else:
                        print(
                            "[WARNING] No img1.png"
                            " for lipstick color:"
                            f" {color}"
                        )
                else:
                    print(
                        "[ERROR] Could not find "
                        "lipstick icon for "
                        f"color: {color}"
                    )

            if has_blush:
                color = makeup_selections.get(
                    "blush"
                )
                icon_path = (
                    f"beauty/blush/{color}/icon.png"
                )
                icon_blob = bucket.blob(icon_path)

                if icon_blob.exists():
                    blush_icon = (
                        icon_blob.download_as_bytes()
                    )
                    product_images.append(
                        ("blush_icon", blush_icon)
                    )
                    print(
                        "[DEBUG] Loaded blush "
                        f"icon from {icon_path}"
                    )

                    ref_path = (
                        f"beauty/blush/{color}"
                        "/img1.png"
                    )
                    ref_blob = bucket.blob(
                        ref_path
                    )
                    if ref_blob.exists():
                        blush_ref = (
                            ref_blob
                            .download_as_bytes()
                        )
                        product_images.append(
                            ("blush_ref", blush_ref)
                        )
                        print(
                            "[DEBUG] Loaded blush"
                            " reference from "
                            f"{ref_path}"
                        )
                    else:
                        print(
                            "[WARNING] No img1.png"
                            " for blush color:"
                            f" {color}"
                        )
                else:
                    print(
                        "[ERROR] Could not find "
                        "blush icon for "
                        f"color: {color}"
                    )

            if has_eyeshadow:
                color = makeup_selections.get(
                    "eyeshadow"
                )
                icon_path = (
                    f"beauty/eyeshadow/{color}"
                    "/icon.png"
                )
                icon_blob = bucket.blob(icon_path)

                if icon_blob.exists():
                    eyeshadow_icon = (
                        icon_blob.download_as_bytes()
                    )
                    product_images.append(
                        ("eyeshadow_icon",
                         eyeshadow_icon)
                    )
                    print(
                        "[DEBUG] Loaded eyeshadow"
                        f" icon from {icon_path}"
                    )

                    ref_path = (
                        f"beauty/eyeshadow/{color}"
                        "/img1.png"
                    )
                    ref_blob = bucket.blob(
                        ref_path
                    )
                    if ref_blob.exists():
                        eyeshadow_ref = (
                            ref_blob
                            .download_as_bytes()
                        )
                        product_images.append(
                            ("eyeshadow_ref",
                             eyeshadow_ref)
                        )
                        print(
                            "[DEBUG] Loaded "
                            "eyeshadow reference "
                            f"from {ref_path}"
                        )
                    else:
                        print(
                            "[WARNING] No img1.png"
                            " for eyeshadow color:"
                            f" {color}"
                        )
                else:
                    print(
                        "[ERROR] Could not find "
                        "eyeshadow icon for "
                        f"color: {color}"
                    )

            # Create prompt based on selection
            # Add dimension info for framing
            dim_instruction = (
                "The output MUST match the exact "
                "same framing and composition as "
                f"Image 1 ({input_img.width}x"
                f"{input_img.height} pixels). "
                "Do NOT zoom in or reframe."
            )

            if (
                has_lipstick
                and has_blush
                and has_eyeshadow
            ):
                # All 3 products - combined prompt
                prompt = (
                    "MODIFY the face in Image 1 by"
                    " adding ALL three makeup "
                    "products. DO NOT generate a "
                    "new face - ONLY modify the "
                    "provided face in Image 1.\n\n"
                    "IMAGES PROVIDED:\n"
                    "1. THE FACE TO MODIFY - This "
                    "is the ONLY face you should "
                    "use. Add makeup to THIS EXACT"
                    " FACE.\n"
                    "2-4. Product swatches showing"
                    " exact colors for lipstick, "
                    "blush, and eyeshadow\n\n"
                    "CRITICAL INSTRUCTIONS:\n"
                    "- You MUST use the face from "
                    "Image 1 - DO NOT generate a "
                    "different person\n"
                    "- ONLY add makeup to the face"
                    " in Image 1, keeping "
                    "everything else identical\n"
                    f"- {dim_instruction}\n"
                    "- The top of the head, hair, "
                    "and all body parts visible in"
                    " Image 1 MUST remain fully "
                    "visible\n\n"
                    "APPLY ALL THREE PRODUCTS:\n\n"
                    "LIPSTICK (from product "
                    "image 2):\n"
                    "- Use exact color from "
                    "lipstick product image\n"
                    "- Natural saturation with "
                    "clean, defined edges\n"
                    "- Must be clearly visible\n\n"
                    "BLUSH (from product "
                    "image 3):\n"
                    "- Use exact color from blush "
                    "product image\n"
                    "- Apply subtly on cheeks "
                    "(20-30% opacity)\n"
                    "- Natural, healthy glow\n\n"
                    "EYESHADOW (from product "
                    "image 4):\n"
                    "- Use exact color from "
                    "eyeshadow product image\n"
                    "- Apply ONLY on UPPER EYELIDS"
                    " - absolutely NO eyeshadow "
                    "below the eyes or on "
                    "lower lids\n"
                    "- DO NOT apply any color "
                    "under the eyes, on the lower"
                    " lash line, or on the "
                    "brow bone\n"
                    "- Visible with professional "
                    "blending (40-50% opacity)\n\n"
                    "PRESERVE:\n"
                    f"- {dim_instruction}\n"
                    "- The top of the head, hair, "
                    "and all body parts visible in"
                    " Image 1 MUST remain fully "
                    "visible\n"
                    "- Background, clothing, hair,"
                    " expression - all identical\n"
                    "- Face structure and features"
                    " unchanged\n"
                    "- Keep ALL clothing, "
                    "accessories, shoes, handbags "
                    "EXACTLY as shown\n"
                    "- Do NOT alter outfit, dress,"
                    " or any accessories"
                )

            elif (
                has_blush
                and makeup_selections.get("blush")
            ):
                # Blush only
                blush_color = (
                    makeup_selections.get("blush")
                )
                prompt = (
                    "CRITICAL FIRST STEP - ANALYZE"
                    " THE REFERENCE IMAGE:\n"
                    "Carefully study the reference"
                    " and understand:\n"
                    "- The SHEER, TRANSPARENT "
                    "quality - skin shows through "
                    "naturally\n"
                    "- How LIGHT and DELICATE the "
                    "application is - barely "
                    "there\n"
                    "- The IMPERCEPTIBLE EDGES - "
                    "impossible to see where blush"
                    " ends\n"
                    "- The NATURAL FLUSH appearance"
                    " - from within, not on top\n"
                    "- The SUBTLE intensity - "
                    "never thick, heavy, or "
                    "dense\n\n"
                    "IMAGES PROVIDED:\n"
                    "1. Model face - apply blush "
                    "here\n"
                    "2. Product icon - "
                    f"{blush_color} exact color "
                    "reference\n"
                    "3. Reference image "
                    "(img1.png) - ANALYZE for its "
                    "sheer, natural, seamless "
                    "application\n\n"
                    "PROFESSIONAL REQUIREMENTS - "
                    "MATCH REFERENCE SHEERNESS:\n\n"
                    "1. BILATERAL APPLICATION "
                    "(MANDATORY):\n"
                    "   + Apply on BOTH cheeks "
                    "with perfect symmetry\n"
                    "   + Match reference "
                    "placement exactly\n"
                    "   + Identical coverage on "
                    "left and right cheeks\n"
                    "   + Professional mirror-"
                    "image precision\n\n"
                    "2. PROFESSIONAL "
                    "APPLICATION:\n"
                    "   + Color: EXACT "
                    f"{blush_color} match to "
                    "product icon\n"
                    "   + Opacity: 10-20% MAXIMUM"
                    " - skin must show through\n"
                    "   + Blending: IMPERCEPTIBLE"
                    " edges - no visible "
                    "boundaries\n"
                    "   + Natural gradual fade "
                    "into skin\n"
                    "   + Appears from within, "
                    "not sitting on top\n\n"
                    "3. PRESERVATION:\n"
                    f"   + {dim_instruction}\n"
                    "   + The top of the head, "
                    "hair, and all body parts "
                    "visible in Image 1 MUST "
                    "remain fully visible\n"
                    "   + Face structure "
                    "unchanged\n"
                    "   + Background, hair, "
                    "clothing identical\n"
                    "   + Keep ALL clothing, "
                    "accessories, shoes, handbags"
                    " EXACTLY as shown\n"
                    "   + Natural skin texture "
                    "visible through blush\n\n"
                    "CRITICAL: Apply SHEER, "
                    "TRANSPARENT blush on both "
                    "cheeks with imperceptible "
                    "edges matching reference's "
                    "subtle style."
                )

            elif (
                has_eyeshadow
                and makeup_selections.get(
                    "eyeshadow"
                )
            ):
                # Eyeshadow only
                eyeshadow_color = (
                    makeup_selections.get(
                        "eyeshadow"
                    )
                )

                # Add eye state instruction
                eye_state_instruction = ""
                if eye_state == "closed":
                    eye_state_instruction = (
                        "\nEYE STATE: Generate with "
                        "EYES CLOSED - person "
                        "looking down with closed "
                        "eyelids visible"
                    )
                else:
                    eye_state_instruction = (
                        "\nEYE STATE: Generate with "
                        "EYES OPEN - normal "
                        "forward gaze"
                    )

                prompt = (
                    "MODIFY the face in Image 1 "
                    "by adding eyeshadow. DO NOT "
                    "generate a new face - ONLY "
                    "modify the provided face in "
                    "Image 1.\n\n"
                    "IMAGES PROVIDED:\n"
                    "1. THE FACE TO MODIFY - This"
                    " is the ONLY face you should"
                    " use. Add eyeshadow to THIS "
                    "EXACT FACE.\n"
                    "2. Product icon - "
                    f"{eyeshadow_color} exact "
                    "color/texture reference\n"
                    "3. Reference image "
                    "(img1.png) - showing "
                    "application style"
                    f"{eye_state_instruction}\n\n"
                    "CRITICAL INSTRUCTIONS:\n"
                    "- You MUST use the face from"
                    " Image 1 - DO NOT generate a"
                    " different person\n"
                    "- ONLY add eyeshadow to the "
                    "face in Image 1, keeping "
                    "everything else identical\n"
                    f"- {dim_instruction}\n"
                    "- The top of the head, hair,"
                    " and all body parts visible "
                    "in Image 1 MUST remain fully"
                    " visible\n\n"
                    "GENERATION INSTRUCTIONS:\n"
                    "- Apply eyeshadow ONLY on "
                    "UPPER EYELIDS - absolutely "
                    "NO eyeshadow below the eyes "
                    "or on lower lids\n"
                    "- DO NOT apply any color "
                    "under the eyes, on the lower"
                    " lash line, or on the "
                    "brow bone\n"
                    "- Only the area between the "
                    "crease and the upper lash "
                    "line should have "
                    "eyeshadow\n"
                    "- Match the EXACT color from"
                    " product icon\n"
                    "- CRITICAL: Capture any "
                    "SHIMMER, SHINE, or LUMINOSITY"
                    " shown in product\n"
                    "- For metallic/shimmer "
                    "finishes, ADD VISIBLE SHINE "
                    "to the eyelid\n"
                    "- Even for nude/skin-toned "
                    "colors, the eyeshadow MUST "
                    "be VISIBLE through shimmer\n"
                    "- The shimmer/shine creates "
                    "visibility even when color "
                    "matches skin tone\n"
                    "- Subtle to moderate "
                    "intensity (40-50% opacity)\n"
                    "- Professional blending at "
                    "edges\n\n"
                    "PRESERVE:\n"
                    f"- {dim_instruction}\n"
                    "- Background, clothing, "
                    "hair - all identical\n"
                    "- Face structure and features"
                    " unchanged\n"
                    "- Keep ALL clothing, "
                    "accessories, shoes, handbags"
                    " EXACTLY as shown\n"
                    "- Do NOT alter outfit, dress"
                    ", or any accessories"
                )

            elif (
                has_lipstick
                and makeup_selections.get(
                    "lipstick"
                )
            ):
                # Lipstick only
                lipstick_color = (
                    makeup_selections.get(
                        "lipstick"
                    )
                )
                prompt = (
                    "Apply the lipstick to the "
                    "model's lips with "
                    "PROFESSIONAL PRECISION:\n\n"
                    "IMAGES PROVIDED:\n"
                    "1. Model face - apply "
                    "lipstick here\n"
                    "2. Product icon - "
                    f"{lipstick_color} exact color"
                    " reference\n"
                    "3. Reference image "
                    "(img1.png) - showing "
                    "application style\n\n"
                    "CRITICAL COLOR REQUIREMENTS "
                    "(MUST MATCH EXACTLY):\n"
                    "- Extract and match the EXACT"
                    " color from the reference "
                    "image and product icon\n"
                    f"- This is {lipstick_color} "
                    "lipstick - preserve its "
                    "precise hue, saturation, "
                    "and luminance\n"
                    "- Maintain the IDENTICAL "
                    "opacity/intensity level as "
                    "the reference\n"
                    "- Preserve the EXACT finish "
                    "type (matte/glossy/satin/"
                    "cream/metallic/shimmer)\n"
                    "- Zero color deviation - no "
                    "warming, cooling, or tint "
                    "adjustment\n"
                    "- Match the exact undertones "
                    "(warm/cool/neutral)\n\n"
                    "PROFESSIONAL APPLICATION "
                    "STANDARDS:\n"
                    "- Ultra-high quality, "
                    "photorealistic result\n"
                    "- Perfect edge definition "
                    "with no bleeding\n"
                    "- Even, flawless coverage "
                    "distribution\n"
                    "- Natural lip texture and "
                    "dimension preserved\n"
                    "- Professional beauty "
                    "campaign quality\n"
                    "- Maintain natural shadows "
                    "and highlights\n\n"
                    "PRESERVE:\n"
                    f"- {dim_instruction}\n"
                    "- The top of the head, hair,"
                    " and all body parts visible "
                    "in Image 1 MUST remain fully"
                    " visible\n"
                    "- Background, clothing, "
                    "hair - all identical\n"
                    "- Face structure unchanged\n"
                    "- Keep ALL clothing, "
                    "accessories, shoes, handbags"
                    " EXACTLY as shown\n"
                    "- Do NOT alter outfit, dress"
                    ", or any accessories"
                )
            else:
                # Fallback
                print(
                    "[ERROR] No valid makeup "
                    "selections found!"
                )
                return None

            # Call Gemini 3 Pro with retry
            print(
                f"[DEBUG] Thread {thread_id}: "
                "Calling Gemini 3 Pro with "
                f"prompt length: "
                f"{len(prompt)} chars"
            )
            print(
                f"[DEBUG] Thread {thread_id}: "
                "Using model: "
                "gemini-3-pro-image-preview "
                "with location: global"
            )
            print(
                f"[DEBUG] Thread {thread_id}: "
                "Number of product images: "
                f"{len(product_images)}"
            )

            # Build parts list
            parts_list = [
                types.Part.from_bytes(
                    data=model_bytes,
                    mime_type="image/png"
                )
            ]

            # Add all product images
            for prod_type, prod_bytes in (
                product_images
            ):
                parts_list.append(
                    types.Part.from_bytes(
                        data=prod_bytes,
                        mime_type="image/png"
                    )
                )
                print(
                    f"[DEBUG] Added {prod_type}"
                    " product image to request"
                )

            # Add text prompt last
            parts_list.append(
                types.Part.from_text(text=prompt)
            )

            # Retry loop for rate limiting
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    img_cfg = types.ImageConfig(
                        output_mime_type=(
                            "image/png"
                        ),
                        aspect_ratio=input_aspect,
                    )
                    config = (
                        types.GenerateContentConfig(
                            temperature=0.2,
                            top_p=0.9,
                            response_modalities=[
                                "IMAGE"
                            ],
                            candidate_count=1,
                            image_config=img_cfg,
                        )
                    )
                    response = (
                        self.gemini3_client.models
                        .generate_content(
                            model=(
                                "gemini-3-pro"
                                "-image-preview"
                            ),
                            contents=[
                                types.Content(
                                    role="user",
                                    parts=parts_list
                                )
                            ],
                            config=config,
                        )
                    )

                    # Extract result image
                    print(
                        "[DEBUG] Got response "
                        "from Gemini 3 Pro"
                    )
                    if (
                        response
                        and response.candidates
                    ):
                        num_cands = len(
                            response.candidates
                        )
                        print(
                            "[DEBUG] Response has"
                            f" {num_cands} "
                            "candidates"
                        )
                        cand = (
                            response.candidates[0]
                        )
                        if (
                            cand.content
                            and cand.content.parts
                        ):
                            num_parts = len(
                                cand.content.parts
                            )
                            print(
                                "[DEBUG] Response"
                                f" has {num_parts}"
                                " parts"
                            )
                            for part in (
                                cand.content.parts
                            ):
                                if (
                                    part.inline_data
                                    and part
                                    .inline_data
                                    .data
                                ):
                                    result_data = (
                                        part
                                        .inline_data
                                        .data
                                    )
                                    elapsed = (
                                        time.time()
                                        - start_time
                                    )
                                    print(
                                        "[DEBUG] "
                                        "Thread "
                                        f"{thread_id}"
                                        ": Got image"
                                        " result: "
                                        f"{len(result_data)}"
                                        " bytes "
                                        "(took "
                                        f"{elapsed:.2f}"
                                        "s)"
                                    )
                                    return (
                                        result_data
                                    )

                    print(
                        f"[DEBUG] Thread "
                        f"{thread_id}: No image "
                        "data found in response"
                    )
                    return None

                except (
                    ConnectionError,
                    TimeoutError,
                    RuntimeError,
                    ValueError,
                ) as api_e:
                    if (
                        "429" in str(api_e)
                        and attempt
                        < max_retries - 1
                    ):
                        wait_time = (
                            (attempt + 1) * 5
                        )
                        print(
                            "[RETRY] Thread "
                            f"{thread_id}: Rate "
                            "limited. Waiting "
                            f"{wait_time}s "
                            f"(attempt "
                            f"{attempt + 1}/"
                            f"{max_retries})"
                        )
                        time.sleep(wait_time)
                        continue
                    raise api_e

            return None

        except (
            ConnectionError,
            TimeoutError,
            RuntimeError,
            ValueError,
            OSError,
        ) as e:
            elapsed = time.time() - start_time
            print(
                f"[ERROR] Thread {thread_id}: "
                "Makeup application error after"
                f" {elapsed:.2f}s: {str(e)}"
            )
            st.error(
                "Makeup application error: "
                f"{str(e)}"
            )
            return None

    def resize_image_for_display(
        self, image_bytes,
        max_width=400, max_height=600
    ):
        """Resize image for display."""
        try:
            img = Image.open(
                io.BytesIO(image_bytes)
            )

            # Calculate scaling factor
            width_ratio = max_width / img.width
            height_ratio = (
                max_height / img.height
            )
            scale_factor = min(
                width_ratio, height_ratio
            )

            # Calculate new dimensions
            new_width = int(
                img.width * scale_factor
            )
            new_height = int(
                img.height * scale_factor
            )

            # Resize preserving aspect ratio
            img_resized = img.resize(
                (new_width, new_height),
                Image.Resampling.LANCZOS
            )

            # White background, paste centered
            background = Image.new(
                "RGB",
                (max_width, max_height),
                "white"
            )
            paste_x = (
                (max_width - new_width) // 2
            )
            paste_y = (
                (max_height - new_height) // 2
            )
            background.paste(
                img_resized, (paste_x, paste_y)
            )

            # Convert back to bytes
            output = io.BytesIO()
            background.save(
                output, format="PNG"
            )
            return output.getvalue()
        except (OSError, ValueError) as e:
            print(
                f"Error resizing image: {e}"
            )
            return image_bytes

    def display_results_navigation(self):
        """Display results with navigation."""
        all_combos = (
            st.session_state
            .beauty_all_combinations
        )
        if not all_combos:
            st.error("No results to display")
            return

        cur_idx = (
            st.session_state
            .beauty_current_index
        )
        current_combo = all_combos[cur_idx]
        total_combos = len(all_combos)

        # Debug log
        print(
            "[DEBUG] Displaying result "
            f"{cur_idx + 1}/{total_combos}"
        )
        orig_len = len(
            current_combo.get(
                "original_bytes", b""
            )
        )
        print(
            "[DEBUG] Combo has "
            f"original_bytes: {orig_len} bytes"
        )
        result_b = current_combo.get(
            "result_bytes", b""
        )
        if isinstance(result_b, bytes):
            rb_info = len(result_b)
        else:
            rb_info = "dict"
        print(
            "[DEBUG] Combo has "
            f"result_bytes: {rb_info}"
        )

        # Header with navigation
        st.markdown(
            "### Beauty Results - "
            f"{cur_idx + 1} of {total_combos}"
        )

        # Product info
        products_text = []
        if current_combo.get("is_3_product"):
            lip = current_combo.get("lipstick")
            blsh = current_combo.get("blush")
            eysh = current_combo.get("eyeshadow")
            products_text = [
                f"Lipstick: {lip}",
                f"Blush: {blsh}",
                f"Eyeshadow: {eysh}"
            ]
        else:
            if current_combo.get("lipstick"):
                lip_name = current_combo["lipstick"]
                products_text.append(
                    "Lipstick: "
                    f"{lip_name}"
                )
            if current_combo.get("blush"):
                blush_name = current_combo["blush"]
                products_text.append(
                    "Blush: "
                    f"{blush_name}"
                )
            if current_combo.get("eyeshadow"):
                eye_name = current_combo["eyeshadow"]
                eyeshadow_text = (
                    "Eyeshadow: "
                    f"{eye_name}"
                )
                if current_combo.get("eye_state"):
                    eye_st = (
                        current_combo["eye_state"]
                        .capitalize()
                    )
                    eyeshadow_text += (
                        f" (Eyes {eye_st})"
                    )
                products_text.append(
                    eyeshadow_text
                )

        if products_text:
            st.success(
                "**Applied:** "
                + " | ".join(products_text)
            )

        # Navigation
        col_prev, col_counter, col_next = (
            st.columns([1, 3, 1])
        )

        with col_prev:
            if st.button(
                "Previous",
                disabled=cur_idx == 0
            ):
                st.session_state.beauty_current_index -= 1
                st.rerun()

        with col_counter:
            # Quick jump buttons
            if total_combos > 1:
                num_jumps = min(5, total_combos)
                jump_cols = st.columns(num_jumps)
                for idx in range(num_jumps):
                    with jump_cols[idx]:
                        btn_type = (
                            "primary"
                            if idx == cur_idx
                            else "secondary"
                        )
                        if st.button(
                            f"{idx+1}",
                            key=f"jump_{idx}",
                            type=btn_type
                        ):
                            st.session_state.beauty_current_index = idx
                            st.rerun()

        with col_next:
            if st.button(
                "Next",
                disabled=(
                    cur_idx
                    == total_combos - 1
                )
            ):
                st.session_state.beauty_current_index += 1
                st.rerun()

        # Display results
        if current_combo.get("result_bytes"):
            result_data = current_combo.get(
                "result_bytes"
            )
            has_face_crop = (
                isinstance(result_data, dict)
                and "face" in result_data
            )

            if has_face_crop:
                col1, col2, col3 = st.columns(
                    [1, 1, 1]
                )

                with col1:
                    st.markdown("**Original**")
                    orig = current_combo.get(
                        "original_bytes"
                    )
                    if orig:
                        original_img = (
                            Image.open(
                                io.BytesIO(orig)
                            )
                        )
                        dw = min(
                            original_img.width,
                            300
                        )
                        st.image(
                            original_img,
                            width=dw
                        )

                with col2:
                    st.markdown("**With Makeup**")
                    if isinstance(
                        result_data, dict
                    ):
                        rb = result_data["full"]
                    else:
                        rb = result_data
                    result_img = Image.open(
                        io.BytesIO(rb)
                    )
                    orig = current_combo.get(
                        "original_bytes"
                    )
                    original_img = Image.open(
                        io.BytesIO(orig)
                    )
                    dw = min(
                        original_img.width, 300
                    )
                    st.image(
                        result_img, width=dw
                    )

                with col3:
                    st.markdown(
                        "**Face Close-up**"
                    )
                    if (
                        isinstance(
                            result_data, dict
                        )
                        and "face" in result_data
                    ):
                        face_img = Image.open(
                            io.BytesIO(
                                result_data[
                                    "face"
                                ]
                            )
                        )
                        dw = min(
                            original_img.width,
                            300
                        )
                        st.image(
                            face_img, width=dw
                        )
            else:
                # 2 column layout
                col1, col2 = st.columns(
                    [1, 1]
                )

                with col1:
                    st.markdown("**Original**")
                    orig = current_combo.get(
                        "original_bytes"
                    )
                    if orig:
                        original_img = (
                            Image.open(
                                io.BytesIO(orig)
                            )
                        )
                        dw = min(
                            original_img.width,
                            500
                        )
                        st.image(
                            original_img,
                            width=dw
                        )

                with col2:
                    st.markdown(
                        "**With Makeup**"
                    )
                    rb = (
                        current_combo.get(
                            "result_bytes"
                        )
                    )
                    if rb:
                        result_img = (
                            Image.open(
                                io.BytesIO(rb)
                            )
                        )
                        orig = current_combo.get(
                            "original_bytes"
                        )
                        original_img = (
                            Image.open(
                                io.BytesIO(orig)
                            )
                        )
                        dw = min(
                            original_img.width,
                            500
                        )
                        st.image(
                            result_img,
                            width=dw
                        )
        else:
            st.error("No result image available")

        # Video Section
        st.markdown("---")

        # Check if video exists
        video_key = (
            "beauty_video_"
            f"{cur_idx}"
        )

        if (
            video_key in st.session_state
            and st.session_state[video_key]
        ):
            st.markdown("### Beauty Video")

            # pylint: disable=import-outside-toplevel
            import base64
            video_b64 = base64.b64encode(
                st.session_state[video_key]
            ).decode()

            # Display video centered
            _col_v1, col_v2, _col_v3 = (  # pylint: disable=unused-variable
                st.columns([1, 1, 1])
            )
            with col_v2:
                video_html = (
                    "<div style=\"border-radius:"
                    "10px; overflow:hidden; "
                    "box-shadow:0 4px 6px "
                    "rgba(0,0,0,0.1);\">"
                    "<video style=\"width:100%; "
                    "display:block; "
                    "background:white;\" "
                    "controls autoplay loop "
                    "muted>"
                    "<source src=\"data:video/"
                    f"mp4;base64,{video_b64}\" "
                    "type=\"video/mp4\">"
                    "Your browser does not "
                    "support the video tag."
                    "</video></div>"
                )
                st.markdown(
                    video_html,
                    unsafe_allow_html=True
                )

            # Download button
            col1, col2, col3 = st.columns(
                [1, 1, 1]
            )
            with col2:
                vid_fname = (
                    "beauty_video_"
                    f"{cur_idx + 1}.mp4"
                )
                st.download_button(
                    label="Download Video",
                    data=(
                        st.session_state[
                            video_key
                        ]
                    ),
                    file_name=vid_fname,
                    mime="video/mp4",
                    use_container_width=True
                )
        else:
            # Generate video button
            col1, col2, col3 = st.columns(
                [1, 1, 1]
            )
            with col2:
                if st.button(
                    "Bring to Life",
                    type="primary",
                    use_container_width=True
                ):
                    with st.spinner(
                        "Creating beauty video..."
                    ):
                        # Get result image
                        rd = current_combo.get(
                            "result_bytes"
                        )
                        if isinstance(rd, dict):
                            video_source = (
                                rd["full"]
                            )
                        else:
                            video_source = rd

                        if video_source:
                            makeup_items = []
                            if current_combo.get(
                                "lipstick"
                            ):
                                lip = (
                                    current_combo[
                                        "lipstick"
                                    ]
                                )
                                makeup_items.append(
                                    f"{lip} "
                                    "lipstick"
                                )
                            if current_combo.get(
                                "blush"
                            ):
                                blsh = (
                                    current_combo[
                                        "blush"
                                    ]
                                )
                                makeup_items.append(
                                    f"{blsh} blush"
                                )
                            if current_combo.get(
                                "eyeshadow"
                            ):
                                eysh = (
                                    current_combo[
                                        "eyeshadow"
                                    ]
                                )
                                makeup_items.append(
                                    f"{eysh} "
                                    "eyeshadow"
                                )

                            makeup_desc = (
                                ", ".join(
                                    makeup_items
                                )
                                if makeup_items
                                else "makeup"
                            )

                            video_result = (
                                self
                                .generate_beauty_video(
                                    video_source,
                                    makeup_desc
                                )
                            )

                            if (
                                video_result
                                and video_result.get(
                                    "video_bytes"
                                )
                            ):
                                st.session_state[
                                    video_key
                                ] = video_result[
                                    "video_bytes"
                                ]
                                st.success(
                                    "Video "
                                    "generated!"
                                )
                                st.rerun()
                            elif (
                                video_result
                                and video_result
                                .get("error")
                            ):
                                error = (
                                    video_result[
                                        "error"
                                    ]
                                )
                                if (
                                    "usage "
                                    "guidelines"
                                    in str(error)
                                ):
                                    st.warning(
                                        "Video "
                                        "generation"
                                        " blocked "
                                        "by safety"
                                        " filter. "
                                        "Try using"
                                        " a Gallery"
                                        " model."
                                    )
                                else:
                                    st.error(
                                        "Video "
                                        "generation"
                                        " failed: "
                                        f"{error}"
                                    )
                            else:
                                st.error(
                                    "Failed to "
                                    "generate "
                                    "video"
                                )

        # Back button
        st.markdown("---")
        if st.button(
            "Back to Selection",
            use_container_width=True
        ):
            for key in list(
                st.session_state.keys()
            ):
                if key.startswith(
                    "beauty_video_"
                ):
                    del st.session_state[key]
            st.session_state.pop(
                "beauty_uploaded_photo", None
            )
            st.session_state.beauty_showing_results = False
            st.session_state.beauty_current_index = 0
            st.session_state.beauty_all_combinations = []
            st.rerun()

    def _get_face_prompts(self):
        """Return diverse face prompts."""
        return [
            "FRONT-FACING beauty portrait: "
            "Young East Asian woman, "
            "straight black hair, looking "
            "directly at camera, clear skin",
            "FRONT-FACING beauty portrait: "
            "African woman, natural hair, "
            "looking straight ahead at "
            "camera, deep skin tone",
            "FRONT-FACING beauty portrait: "
            "Caucasian woman, wavy blonde "
            "hair, direct eye contact with "
            "camera, fair skin",
            "FRONT-FACING beauty portrait: "
            "South Asian woman, dark hair, "
            "looking directly forward, "
            "medium brown skin",
            "FRONT-FACING beauty portrait: "
            "Latin American woman, brown "
            "hair, facing camera straight "
            "on, olive skin",
            "FRONT-FACING beauty portrait: "
            "Middle Eastern woman, dark "
            "hair, looking directly at "
            "camera, light olive skin",
            "FRONT-FACING beauty portrait: "
            "Mixed-race woman, textured "
            "hair, straight-on view to "
            "camera, caramel skin",
            "FRONT-FACING beauty portrait: "
            "European woman, red hair, "
            "facing directly forward, "
            "pale skin",
            "FRONT-FACING beauty portrait: "
            "Southeast Asian woman, black "
            "hair, looking straight at "
            "camera, tan skin",
            "FRONT-FACING beauty portrait: "
            "Nordic woman, blonde hair, "
            "direct frontal view, fair skin"
        ]

    def _resize_result(self, result, combo):
        """Resize result to match original."""
        original_img = Image.open(
            io.BytesIO(combo["original_bytes"])
        )
        result_img = Image.open(
            io.BytesIO(result)
        )

        orig_w, orig_h = original_img.size

        if result_img.size != (orig_w, orig_h):
            rw, rh = result_img.size
            t_ratio = orig_w / orig_h
            r_ratio = rw / rh

            if r_ratio > t_ratio:
                scale = orig_h / rh
                new_h = orig_h
                new_w = int(rw * scale)
            else:
                scale = orig_w / rw
                new_w = orig_w
                new_h = int(rh * scale)

            result_img = result_img.resize(
                (new_w, new_h),
                Image.Resampling.LANCZOS
            )

            left = (new_w - orig_w) // 2
            top = (new_h - orig_h) // 2
            result_img = result_img.crop(
                (
                    left, top,
                    left + orig_w,
                    top + orig_h
                )
            )

            output = io.BytesIO()
            result_img.save(
                output, format="PNG"
            )
            result = output.getvalue()

        return result

    def render(self):
        """Render the Beauty Demo tab"""

        st.markdown("## Virtual Makeup Try-On")
        st.markdown(
            "Select models and makeup "
            "to see results"
        )

        # Check if we're showing results
        if (
            st.session_state
            .beauty_showing_results
            and st.session_state
            .beauty_all_combinations
        ):
            self.display_results_navigation()
            return

        # Main layout
        col_left, col_right = st.columns(
            [1.5, 0.8]
        )

        # Model Selection
        with col_left:
            st.markdown("### Model Selection")

            options = [
                "Select from Gallery",
                "Generate Faces",
                "Upload Your Photo",
                "Use VTO Result"
            ]
            model_source = st.radio(
                "Choose option:",
                options,
                horizontal=True,
                key="beauty_model_source"
            )

            face_models = []

            if model_source == "Upload Your Photo":
                uploaded_file = st.file_uploader(
                    "Upload your photo",
                    type=[
                        "png", "jpg", "jpeg"
                    ],
                    key="beauty_upload_photo",
                    help=(
                        "Upload front-facing "
                        "portrait photo for "
                        "best results"
                    )
                )

                if uploaded_file:
                    uploaded_bytes = (
                        uploaded_file.read()
                    )

                    # Save uploaded photo
                    try:
                        bucket = (
                            self.storage_client
                            .bucket(
                                self.bucket_name
                            )
                        )
                        hex_id = (
                            uuid.uuid4().hex[:8]
                        )
                        upload_path = (
                            "outputs/beauty_demo"
                            "/uploads/"
                            "uploaded_photo_"
                            f"{hex_id}.png"
                        )
                        blob = bucket.blob(
                            upload_path
                        )
                        blob.upload_from_string(
                            uploaded_bytes,
                            content_type=(
                                "image/png"
                            )
                        )
                        print(
                            "[DEBUG] Saved uploaded"
                            " photo to gs://"
                            f"{self.bucket_name}"
                            f"/{upload_path}"
                        )
                    except (
                        OSError,
                        ValueError,
                    ) as e:
                        print(
                            "[DEBUG] Failed to "
                            "save uploaded photo "
                            f"to GCS: {e}"
                        )

                    face_models = [{
                        "id": "uploaded",
                        "name": "Uploaded Photo",
                        "image_bytes": (
                            uploaded_bytes
                        ),
                        "original_bytes": (
                            uploaded_bytes
                        )
                    }]
                    st.session_state.beauty_uploaded_photo = uploaded_bytes
                    st.session_state.beauty_selected_models = ["uploaded"]

                elif st.session_state.get(
                    "beauty_uploaded_photo"
                ):
                    uploaded_bytes = (
                        st.session_state
                        .beauty_uploaded_photo
                    )
                    face_models = [{
                        "id": "uploaded",
                        "name": "Uploaded Photo",
                        "image_bytes": (
                            uploaded_bytes
                        ),
                        "original_bytes": (
                            uploaded_bytes
                        )
                    }]

            elif (
                model_source == "Generate Faces"
            ):
                st.info(
                    "Generate diverse "
                    "FRONT-FACING face models "
                    "for makeup application"
                )

                gen_col1, gen_col2 = st.columns(
                    [2, 1]
                )
                with gen_col1:
                    num_faces = st.radio(
                        "Number of faces:",
                        [3, 5, 10],
                        index=1,
                        horizontal=True,
                        key=(
                            "num_faces_to_generate"
                        )
                    )

                with gen_col2:
                    if st.button(
                        "Generate Faces",
                        key="generate_faces_btn",
                        type="primary"
                    ):
                        with st.spinner(
                            f"Generating "
                            f"{num_faces} diverse"
                            " face models..."
                        ):
                            face_prompts = self._get_face_prompts()

                            generated_faces = []
                            progress_bar = (
                                st.progress(0)
                            )
                            status_text = (
                                st.empty()
                            )

                            prompts_to_gen = []
                            for i in range(
                                num_faces
                            ):
                                fp = face_prompts[
                                    i % len(
                                        face_prompts
                                    )
                                ]
                                full_prompt = (
                                    f"{fp}\n"
                                    "- CRITICAL: "
                                    "FRONT-FACING "
                                    "VIEW ONLY\n"
                                    "- NO SIDE "
                                    "PROFILES, NO "
                                    "3/4 ANGLES\n"
                                    "- Both eyes "
                                    "fully visible "
                                    "and "
                                    "symmetrical\n"
                                    "- Face fills "
                                    "70% of frame\n"
                                    "- Clear skin "
                                    "texture "
                                    "visible\n"
                                    "- Natural "
                                    "lighting\n"
                                    "- Minimal or "
                                    "no makeup\n"
                                    "- Perfect for "
                                    "virtual makeup"
                                    " try-on\n"
                                    "- Neutral "
                                    "background\n"
                                    "- Direct "
                                    "facing "
                                    "camera\n"
                                    "- Focus on "
                                    "facial "
                                    "features\n"
                                    "- Professional"
                                    " beauty "
                                    "photography "
                                    "style"
                                )
                                desc = (
                                    fp.split(":")[1]
                                    .split(",")[0]
                                    .strip()
                                )
                                prompts_to_gen.append({
                                    "prompt": (
                                        full_prompt
                                    ),
                                    "description": (
                                        desc
                                    )
                                })

                            completed = 0
                            max_w = min(
                                5, num_faces
                            )
                            with (
                                concurrent.futures
                                .ThreadPoolExecutor(
                                    max_workers=(
                                        max_w
                                    )
                                ) as executor
                            ):
                                future_map = {
                                    executor.submit(
                                        self.generate_face_model,
                                        p["prompt"]
                                    ): p
                                    for p in (
                                        prompts_to_gen
                                    )
                                }

                                for future in (
                                    concurrent
                                    .futures
                                    .as_completed(
                                        future_map
                                    )
                                ):
                                    pinfo = (
                                        future_map[
                                            future
                                        ]
                                    )
                                    try:
                                        fb = (
                                            future
                                            .result()
                                        )
                                        if fb:
                                            bg = (
                                                st.session_state
                                                .beauty_generated_faces
                                            )
                                            gf_len = (
                                                len(bg)
                                                + len(
                                                    generated_faces
                                                )
                                            )
                                            gname = (
                                                "Generated "
                                                "Face "
                                                f"{gf_len + 1}"
                                            )
                                            gdesc = (
                                                pinfo[
                                                    "description"
                                                ]
                                            )
                                            generated_faces.append({
                                                "id": f"generated_{gf_len}",
                                                "name": gname,
                                                "image_bytes": fb,
                                                "description": gdesc,
                                            })
                                    except (
                                        ConnectionError,
                                        TimeoutError,
                                        RuntimeError,
                                        ValueError,
                                    ) as e:
                                        st.warning(
                                            "Failed to"
                                            " generate"
                                            " one face"
                                            f": {e}"
                                        )

                                    completed += 1
                                    progress_bar.progress(
                                        completed
                                        / num_faces
                                    )
                                    status_text.text(
                                        "Generated "
                                        f"{completed}"
                                        "/"
                                        f"{num_faces}"
                                        " faces"
                                    )

                            progress_bar.empty()
                            status_text.empty()

                            if generated_faces:
                                saved_count = 0

                                for face in (
                                    generated_faces
                                ):
                                    try:
                                        blob_path = generate_unique_path(
                                            "beauty/vto/models/",
                                            prefix="face",
                                            extension="png"
                                        )

                                        fdesc = (
                                            face[
                                                "description"
                                            ]
                                        )
                                        gcs_uri = save_to_gcs(
                                            self.storage_client,
                                            self.bucket_name,
                                            blob_path,
                                            face["image_bytes"],
                                            metadata={
                                                "description": fdesc
                                            },
                                            content_type="image/png"
                                        )

                                        if gcs_uri:
                                            face["gcs_uri"] = gcs_uri
                                            saved_count += 1
                                    except (
                                        OSError,
                                        ValueError,
                                    ) as e:
                                        st.warning(
                                            "Failed to"
                                            " save one"
                                            " face to"
                                            " GCS: "
                                            f"{e}"
                                        )

                                st.session_state.beauty_generated_faces.extend(
                                    generated_faces
                                )
                                num_gen = len(
                                    generated_faces
                                )
                                st.success(
                                    f"Generated "
                                    f"{num_gen} "
                                    "face models!"
                                )

                # Use generated faces as models
                gen_faces = (
                    st.session_state
                    .beauty_generated_faces
                )
                if gen_faces:
                    face_models = gen_faces[-6:]

            elif (
                model_source
                == "Use VTO Result"
            ):
                with st.spinner(
                    "Loading VTO results..."
                ):
                    try:
                        bucket = (
                            self.storage_client
                            .bucket(
                                self.bucket_name
                            )
                        )
                        vto_results = []

                        prefixes = [
                            "outputs/single_vto"
                            "/final_look/"
                        ]

                        for prefix in prefixes:
                            blobs = (
                                bucket.list_blobs(
                                    prefix=prefix
                                )
                            )
                            for blob in blobs:
                                exts = (
                                    ".png",
                                    ".jpg",
                                    ".jpeg"
                                )
                                if (
                                    blob.name
                                    .endswith(exts)
                                    and not
                                    blob.name
                                    .endswith("/")
                                ):
                                    image_bytes = (
                                        blob
                                        .download_as_bytes()
                                    )

                                    resized_bytes = (
                                        self
                                        .resize_image_for_display(
                                            image_bytes
                                        )
                                    )

                                    fname = (
                                        blob.name
                                        .split("/")
                                        [-1]
                                        .replace(
                                            ".png",
                                            ""
                                        )
                                        .replace(
                                            ".jpg",
                                            ""
                                        )
                                        .replace(
                                            ".jpeg",
                                            ""
                                        )
                                    )

                                    if (
                                        "final_try-on"
                                        in blob.name
                                    ):
                                        fname = (
                                            "Final: "
                                            f"{fname}"
                                        )

                                    vto_num = (
                                        len(
                                            vto_results
                                        ) + 1
                                    )
                                    gcs_p = (
                                        "gs://"
                                        f"{self.bucket_name}"
                                        f"/{blob.name}"
                                    )
                                    vto_results.append({
                                        "id": f"vto_{vto_num}",
                                        "name": fname,
                                        "image_bytes": resized_bytes,
                                        "original_bytes": image_bytes,
                                        "gcs_path": gcs_p
                                    })

                        face_models = (
                            vto_results[-6:]
                        )

                        if not face_models:
                            st.warning(
                                "No VTO results "
                                "found. Process "
                                "a VTO first."
                            )

                    except (
                        OSError,
                        ValueError,
                    ) as e:
                        st.error(
                            "Error loading VTO "
                            f"results: {str(e)}"
                        )

            else:  # Select from Gallery
                with st.spinner(
                    "Loading models..."
                ):
                    face_models = (
                        self
                        .load_face_models_from_gallery()
                    )

            if face_models:
                st.markdown(
                    "<p style=\"color: #FFD700;"
                    " font-size: 0.9rem;\">"
                    "Select ONE model only</p>",
                    unsafe_allow_html=True
                )

                if (
                    st.session_state
                    .beauty_selected_models
                ):
                    st.success(
                        "1 model selected"
                    )

                # Display models
                first_id = (
                    face_models[0]["id"]
                )
                if (
                    face_models
                    and first_id.startswith(
                        "vto_"
                    )
                ):
                    st.markdown(
                        "#### Available "
                        "VTO Results"
                    )
                elif (
                    face_models
                    and first_id.startswith(
                        "generated_"
                    )
                ):
                    st.markdown(
                        "#### Generated "
                        "Face Models"
                    )
                else:
                    st.markdown(
                        "#### Available Models"
                    )

                # Display in rows of 3
                for row_start in range(
                    0, len(face_models), 3
                ):
                    num_in_row = min(
                        3,
                        len(face_models)
                        - row_start
                    )
                    cols = st.columns(
                        num_in_row
                    )
                    for col_idx in range(
                        num_in_row
                    ):
                        model_idx = (
                            row_start + col_idx
                        )
                        model = (
                            face_models[model_idx]
                        )
                        with cols[col_idx]:
                            img = Image.open(
                                io.BytesIO(
                                    model[
                                        "image_bytes"
                                    ]
                                )
                            )
                            dw = min(
                                img.width, 350
                            )
                            st.image(
                                img, width=dw
                            )

                            mid = model["id"]
                            if mid == "uploaded":
                                label = (
                                    "Your Photo"
                                )
                            elif mid.startswith(
                                "vto_"
                            ):
                                label = (
                                    "VTO "
                                    f"{model_idx+1:02d}"
                                )
                            elif mid.startswith(
                                "generated_"
                            ):
                                label = (
                                    "Gen "
                                    f"{model_idx+1:02d}"
                                )
                            else:
                                label = (
                                    "Model "
                                    f"{model_idx+1:02d}"
                                )

                            is_sel = (
                                mid
                                in st.session_state
                                .beauty_selected_models
                            )
                            if is_sel:
                                st.markdown(
                                    f"**{label}"
                                    " (Selected)**"
                                )
                            else:
                                if st.button(
                                    "Select",
                                    key=(
                                        "model_"
                                        "check_"
                                        f"{model_idx}"
                                    )
                                ):
                                    st.session_state.beauty_selected_models = [
                                        mid
                                    ]
                                    st.rerun()

                st.session_state.face_models = (
                    face_models
                )

        # Makeup Selection
        with col_right:
            st.markdown("### Select Makeup")

            all_types_selected = (
                len(
                    st.session_state
                    .beauty_makeup_types
                ) == 3
            )

            if st.checkbox(
                "Select All Makeup Products",
                value=all_types_selected,
                key="select_all_makeup"
            ):
                st.session_state.beauty_makeup_types = [
                    "lipstick",
                    "blush",
                    "eyeshadow"
                ]
                for mt in (
                    st.session_state
                    .beauty_makeup_types
                ):
                    if (
                        mt not in
                        st.session_state
                        .beauty_selections
                    ):
                        st.session_state.beauty_selections[mt] = None
            else:
                if all_types_selected:
                    st.session_state.beauty_makeup_types = []
                    st.session_state.beauty_selections = {
                        "lipstick": None,
                        "blush": None,
                        "eyeshadow": None
                    }

            makeup_types = (
                st.session_state
                .beauty_makeup_types
            )
            if makeup_types:
                makeup_count = len(
                    makeup_types
                )
                if makeup_count == 3:
                    st.success(
                        "All 3 makeup products"
                        " selected - 3-product"
                        " combination mode"
                    )
                    st.info(
                        "Select exactly 1 "
                        "color from each "
                        "category (lipstick, "
                        "blush, eyeshadow)"
                    )
                else:
                    st.info(
                        f"{makeup_count} makeup"
                        " product(s) selected"
                    )

            prod_cols = st.columns(3)
            categories = [
                "eyeshadow",
                "lipstick",
                "blush"
            ]
            bucket = self.storage_client.bucket(
                self.bucket_name
            )

            demo_pfx = "beauty/demo_img/"

            for idx, (col, category) in (
                enumerate(
                    zip(prod_cols, categories)
                )
            ):
                with col:
                    demo_paths = [
                        f"{demo_pfx}"
                        f"{category}_demo.png",
                        f"{demo_pfx}"
                        f"{category}.png",
                        f"{demo_pfx}"
                        f"{category}_icon.png"
                    ]

                    demo_found = False
                    for dp in demo_paths:
                        demo_blob = (
                            bucket.blob(dp)
                        )
                        if demo_blob.exists():
                            demo_bytes = (
                                demo_blob
                                .download_as_bytes()
                            )
                            img = Image.open(
                                io.BytesIO(
                                    demo_bytes
                                )
                            )
                            img.thumbnail(
                                (80, 80),
                                Image.Resampling
                                .LANCZOS
                            )
                            st.image(
                                img, width=80
                            )
                            demo_found = True
                            break

                    if not demo_found:
                        prod_icon_paths = [
                            f"beauty/{category}"
                            "/icon.png",
                            f"beauty/{category}"
                            "/product.png",
                        ]

                        for ip in (
                            prod_icon_paths
                        ):
                            ib = bucket.blob(ip)
                            if ib.exists():
                                icon_bytes = (
                                    ib.download_as_bytes()
                                )
                                img = Image.open(
                                    io.BytesIO(
                                        icon_bytes
                                    )
                                )
                                img.thumbnail(
                                    (80, 80),
                                    Image
                                    .Resampling
                                    .LANCZOS
                                )
                                st.image(
                                    img,
                                    width=80
                                )
                                demo_found = True
                                break

                        if not demo_found:
                            if category == (
                                "lipstick"
                            ):
                                clr = "#ff6b6b"
                            elif category == (
                                "blush"
                            ):
                                clr = "#ff9999"
                            else:
                                clr = "#9b59b6"

                            img = Image.new(
                                "RGB",
                                (80, 80),
                                color=clr
                            )
                            st.image(
                                img, width=80
                            )

                    is_all_sel = (
                        len(makeup_types) == 3
                    )
                    is_selected = st.checkbox(
                        category.title(),
                        value=(
                            category
                            in makeup_types
                        ),
                        key=(
                            f"cat_check_"
                            f"{category}"
                        ),
                        disabled=is_all_sel
                    )

                    if not is_all_sel:
                        sels = (
                            st.session_state
                            .beauty_selections
                        )
                        if is_selected:
                            if (
                                category
                                not in
                                makeup_types
                            ):
                                makeup_types.append(
                                    category
                                )
                                sels[
                                    category
                                ] = None
                        else:
                            if (
                                category
                                in makeup_types
                            ):
                                makeup_types.remove(
                                    category
                                )
                                sels[
                                    category
                                ] = None

            st.markdown("---")

            cats_to_show = makeup_types

            if cats_to_show:
                st.markdown(
                    "#### Select Colors:"
                )

                if len(makeup_types) == 3:
                    st.info(
                        "Select exactly 1 color"
                        " from each category"
                    )

                for category in cats_to_show:
                    cat_title = (
                        category.title()
                    )
                    st.markdown(
                        f"##### {cat_title}"
                        " Colors"
                    )
                    st.markdown(
                        "*Select exactly "
                        "1 color:*"
                    )

                    color_prefix = (
                        f"beauty/{category}/"
                    )
                    color_names = set()

                    for blob in (
                        bucket.list_blobs(
                            prefix=color_prefix
                        )
                    ):
                        if (
                            "/icon.png"
                            in blob.name
                        ):
                            parts = (
                                blob.name
                                .split("/")
                            )
                            if len(parts) >= 3:
                                color_names.add(
                                    parts[2]
                                )

                    color_names = sorted(
                        list(color_names)
                    )[:5]

                    if color_names:
                        num_cols = min(
                            len(color_names), 5
                        )
                        cols = st.columns(
                            num_cols
                        )

                        for idx, color in (
                            enumerate(
                                color_names[
                                    :len(cols)
                                ]
                            )
                        ):
                            with cols[idx]:
                                clr_label = (
                                    color[:8]
                                )
                                st.markdown(
                                    "<center>"
                                    "<small>"
                                    f"{clr_label}"
                                    "</small>"
                                    "</center>",
                                    unsafe_allow_html=True
                                )

                                ip = (
                                    f"{color_prefix}"
                                    f"{color}"
                                    "/icon.png"
                                )
                                ib = bucket.blob(
                                    ip
                                )

                                if ib.exists():
                                    icon_bytes = (
                                        ib
                                        .download_as_bytes()
                                    )
                                    img = (
                                        Image.open(
                                            io.BytesIO(
                                                icon_bytes
                                            )
                                        )
                                    )
                                    img.thumbnail(
                                        (60, 60),
                                        Image
                                        .Resampling
                                        .LANCZOS
                                    )
                                    st.image(
                                        img,
                                        width=60
                                    )
                                else:
                                    if category == "lipstick":
                                        dc = "#ff6b6b"
                                    elif category == "blush":
                                        dc = "#ff9999"
                                    else:
                                        dc = "#9b59b6"
                                    img = (
                                        Image.new(
                                            "RGB",
                                            (60, 60),
                                            color=dc
                                        )
                                    )
                                    st.image(
                                        img,
                                        width=60
                                    )

                        cur_sel = (
                            st.session_state
                            .beauty_selections
                            .get(category)
                        )
                        if (
                            cur_sel
                            in color_names
                        ):
                            radio_idx = (
                                color_names
                                .index(cur_sel)
                            )
                        else:
                            radio_idx = None
                        selected_color = (
                            st.radio(
                                "",
                                options=(
                                    color_names
                                ),
                                index=radio_idx,
                                horizontal=True,
                                key=(
                                    "radio_"
                                    f"{category}"
                                ),
                                label_visibility=(
                                    "collapsed"
                                )
                            )
                        )

                        if selected_color:
                            st.session_state.beauty_selections[
                                category
                            ] = selected_color

                        sel_val = (
                            st.session_state
                            .beauty_selections
                            .get(category)
                        )
                        if sel_val:
                            st.success(
                                "Selected: "
                                f"{sel_val}"
                            )
                    else:
                        st.warning(
                            f"No {category} "
                            "colors found"
                        )

        # Show selected products
        st.markdown("---")
        selected_products = []

        b_sels = (
            st.session_state
            .beauty_selections
        )
        lip_sel = b_sels.get("lipstick")
        if (
            lip_sel
            and isinstance(lip_sel, str)
        ):
            selected_products.append(
                f"Lipstick: {lip_sel}"
            )
        blush_sel = b_sels.get("blush")
        if (
            blush_sel
            and isinstance(blush_sel, str)
        ):
            selected_products.append(
                f"Blush: {blush_sel}"
            )
        eye_sel = b_sels.get("eyeshadow")
        if (
            eye_sel
            and isinstance(eye_sel, str)
        ):
            selected_products.append(
                f"Eyeshadow: {eye_sel}"
            )

        if selected_products:
            st.markdown(
                "**Selected products:** "
                + " | ".join(selected_products)
            )

        # Beauty Try-On Button
        st.markdown("---")

        has_models = (
            len(
                st.session_state
                .beauty_selected_models
            ) > 0
        )
        has_products = any(
            v and isinstance(v, str)
            for v in b_sels.values()
        )

        is_3_product_mode = (
            len(makeup_types) == 3
        )
        if is_3_product_mode:
            missing_colors = []
            if not isinstance(
                b_sels.get("lipstick"), str
            ):
                missing_colors.append(
                    "lipstick"
                )
            if not isinstance(
                b_sels.get("blush"), str
            ):
                missing_colors.append(
                    "blush"
                )
            if not isinstance(
                b_sels.get("eyeshadow"), str
            ):
                missing_colors.append(
                    "eyeshadow"
                )

            if missing_colors:
                missing = ", ".join(missing_colors)
                st.warning(
                    "Please select colors "
                    "for: "
                    f"{missing}"
                )
                has_products = False

        if has_models and has_products:
            total_combos = len(
                st.session_state
                .beauty_selected_models
            )
            st.info(
                "Ready to process "
                f"{total_combos} "
                "combination(s)"
            )

        _col_spacer1, col_try_on, _col_spacer2 = (  # pylint: disable=unused-variable
            st.columns([1.5, 1, 1.5])
        )

        with col_try_on:
            if st.button(
                "Beauty Try-On",
                type="primary",
                disabled=not (
                    has_models and has_products
                ),
                use_container_width=True
            ):
                progress_bar = st.progress(0)
                status_text = st.status(
                    "Processing makeup..."
                )

                with status_text:
                    st.write(
                        "Applying makeup to "
                        "selected models..."
                    )

                    all_combinations = []

                    face_models = (
                        st.session_state.get(
                            "face_models", []
                        )
                    )

                    makeup_tasks = []
                    sel_models = (
                        st.session_state
                        .beauty_selected_models
                    )
                    for idx, model_id in (
                        enumerate(sel_models)
                    ):
                        model = next(
                            (
                                m for m in
                                face_models
                                if m["id"]
                                == model_id
                            ),
                            None
                        )
                        if not model:
                            continue

                        process_bytes = (
                            model.get(
                                "original_bytes",
                                model["image_bytes"]
                            )
                        )

                        src = (
                            "original_bytes"
                            if "original_bytes"
                            in model
                            else "image_bytes"
                        )
                        print(
                            f"[DEBUG] Model "
                            f"{idx+1} "
                            f"({model_id}): "
                            f"Using {src}"
                        )
                        print(
                            f"[DEBUG] Model "
                            f"{idx+1}: Bytes "
                            "length = "
                            f"{len(process_bytes)}"
                        )

                        makeup_tasks.append({
                            "model_id": model_id,
                            "model_num": idx + 1,
                            "model_bytes": (
                                process_bytes
                            ),
                            "makeup_selections": (
                                b_sels.copy()
                            )
                        })

                    completed = 0

                    is_eyeshadow_only = (
                        b_sels.get("eyeshadow")
                        and not
                        b_sels.get("lipstick")
                        and not
                        b_sels.get("blush")
                    )

                    if is_eyeshadow_only:
                        total_tasks = (
                            len(makeup_tasks) * 2
                        )
                    else:
                        total_tasks = len(
                            makeup_tasks
                        )

                    with (
                        concurrent.futures
                        .ThreadPoolExecutor(
                            max_workers=2
                        ) as executor
                    ):
                        print(
                            "[DEBUG] Submitting "
                            f"{total_tasks} tasks"
                            " (2 workers)"
                        )

                        if is_eyeshadow_only:
                            future_to_task = {}
                            for task in (
                                makeup_tasks
                            ):
                                mnum = (
                                    task[
                                        "model_num"
                                    ]
                                )
                                print(
                                    "[DEBUG] "
                                    "Submitting "
                                    f"model "
                                    f"{mnum} "
                                    "- eyes open"
                                )
                                fo = (
                                    executor.submit(
                                        self.apply_makeup_realtime,
                                        task["model_bytes"],
                                        task["makeup_selections"],
                                        eye_state="open"
                                    )
                                )
                                future_to_task[fo] = {
                                    **task,
                                    "eye_state": (
                                        "open"
                                    )
                                }

                                print(
                                    "[DEBUG] "
                                    "Submitting "
                                    f"model "
                                    f"{mnum} "
                                    "- eyes "
                                    "closed"
                                )
                                fc = (
                                    executor.submit(
                                        self.apply_makeup_realtime,
                                        task["model_bytes"],
                                        task["makeup_selections"],
                                        eye_state="closed"
                                    )
                                )
                                future_to_task[fc] = {
                                    **task,
                                    "eye_state": (
                                        "closed"
                                    )
                                }
                        else:
                            future_to_task = {}
                            for task in (
                                makeup_tasks
                            ):
                                mnum = (
                                    task[
                                        "model_num"
                                    ]
                                )
                                print(
                                    "[DEBUG] "
                                    "Submitting "
                                    f"model "
                                    f"{mnum}"
                                )
                                f = (
                                    executor.submit(
                                        self.apply_makeup_realtime,
                                        task["model_bytes"],
                                        task["makeup_selections"]
                                    )
                                )
                                future_to_task[f] = task

                        print(
                            "[DEBUG] All tasks "
                            "submitted. Waiting "
                            "for completion..."
                        )

                        for future in (
                            concurrent.futures
                            .as_completed(
                                future_to_task
                            )
                        ):
                            task = (
                                future_to_task[
                                    future
                                ]
                            )

                            mnum = (
                                task["model_num"]
                            )
                            es = task.get(
                                "eye_state",
                                "n/a"
                            )
                            print(
                                "[DEBUG] Completed"
                                f" model {mnum}"
                                f" (eye_state:"
                                f" {es})"
                            )

                            is_3 = (
                                isinstance(
                                    b_sels.get(
                                        "lipstick"
                                    ),
                                    str
                                )
                                and isinstance(
                                    b_sels.get(
                                        "blush"
                                    ),
                                    str
                                )
                                and isinstance(
                                    b_sels.get(
                                        "eyeshadow"
                                    ),
                                    str
                                )
                            )
                            combo = {
                                "model_id": (
                                    task[
                                        "model_id"
                                    ]
                                ),
                                "model_num": (
                                    mnum
                                ),
                                "original_bytes": (
                                    task[
                                        "model_bytes"
                                    ]
                                ),
                                "is_3_product": (
                                    is_3
                                ),
                                "eye_state": (
                                    task.get(
                                        "eye_state",
                                        "open"
                                    )
                                )
                            }

                            lip_s = b_sels.get(
                                "lipstick"
                            )
                            if (
                                lip_s
                                and isinstance(
                                    lip_s, str
                                )
                            ):
                                combo[
                                    "lipstick"
                                ] = lip_s
                            blush_s = b_sels.get(
                                "blush"
                            )
                            if (
                                blush_s
                                and isinstance(
                                    blush_s, str
                                )
                            ):
                                combo[
                                    "blush"
                                ] = blush_s
                            eye_s = b_sels.get(
                                "eyeshadow"
                            )
                            if (
                                eye_s
                                and isinstance(
                                    eye_s, str
                                )
                            ):
                                combo[
                                    "eyeshadow"
                                ] = eye_s

                            try:
                                result = (
                                    future.result()
                                )
                                r_len = (
                                    len(result)
                                    if result
                                    else 0
                                )
                                print(
                                    "[DEBUG] "
                                    f"Model "
                                    f"{mnum}: "
                                    "Got result "
                                    f"- {r_len}"
                                    " bytes"
                                )

                                if result:
                                    result = (
                                        self
                                        ._resize_result(
                                            result,
                                            combo
                                        )
                                    )
                                    combo[
                                        "result_bytes"
                                    ] = result

                                    orig = combo["original_bytes"]
                                    print(
                                        "[DEBUG] "
                                        f"Model "
                                        f"{mnum}: "
                                        "Original "
                                        "bytes = "
                                        f"{len(orig)}"
                                    )
                                    print(
                                        "[DEBUG] "
                                        f"Model "
                                        f"{mnum}: "
                                        "Result "
                                        "bytes = "
                                        f"{len(result)}"
                                    )
                                    print(
                                        "[DEBUG] "
                                        f"Model "
                                        f"{mnum}: "
                                        "Saving to"
                                        " GCS..."
                                    )

                                    blob_path = (
                                        generate_unique_path(
                                            "outputs/beauty_demo/try-on/",
                                            prefix="beauty",
                                            extension="png"
                                        )
                                    )
                                    print(
                                        "[DEBUG] "
                                        f"Model "
                                        f"{mnum}: "
                                        "Saving to "
                                        f"{blob_path}"
                                    )

                                    meta = {
                                        "model_id": (
                                            task[
                                                "model_id"
                                            ]
                                        ),
                                        "lipstick": (
                                            b_sels.get(
                                                "lipstick"
                                            )
                                        ),
                                        "blush": (
                                            b_sels.get(
                                                "blush"
                                            )
                                        ),
                                        "eyeshadow": (
                                            b_sels.get(
                                                "eyeshadow"
                                            )
                                        ),
                                        "is_3_product": (
                                            combo[
                                                "is_3_product"
                                            ]
                                        )
                                    }
                                    gcs_uri = (
                                        save_to_gcs(
                                            self.storage_client,
                                            self.bucket_name,
                                            blob_path,
                                            result,
                                            metadata=meta,
                                            content_type="image/png"
                                        )
                                    )

                                    if gcs_uri:
                                        combo[
                                            "gcs_uri"
                                        ] = gcs_uri
                                        print(
                                            "[DEBUG]"
                                            f" Model "
                                            f"{mnum}:"
                                            " Saved "
                                            "to "
                                            f"{gcs_uri}"
                                        )
                                    else:
                                        print(
                                            "[DEBUG]"
                                            f" Model "
                                            f"{mnum}:"
                                            " Failed"
                                            " to save"
                                        )
                                else:
                                    print(
                                        "[DEBUG]"
                                        f" Model "
                                        f"{mnum}:"
                                        " No "
                                        "result "
                                        "from API"
                                    )

                            except (
                                ConnectionError,
                                TimeoutError,
                                RuntimeError,
                                ValueError,
                                OSError,
                            ) as e:
                                st.warning(
                                    "Failed to "
                                    "process "
                                    f"model "
                                    f"{mnum}:"
                                    f" {str(e)}"
                                )

                            all_combinations.append(
                                combo
                            )

                            completed += 1
                            progress = min(
                                completed
                                / total_tasks,
                                1.0
                            )
                            progress_bar.progress(
                                progress
                            )

                            if is_eyeshadow_only:
                                md = (
                                    (completed + 1)
                                    // 2
                                )
                                tm = (
                                    total_tasks
                                    // 2
                                )
                                if (
                                    completed % 2
                                    == 0
                                ):
                                    st.write(
                                        "Completed"
                                        f" model "
                                        f"{md}/"
                                        f"{tm}"
                                        " (both "
                                        "eye "
                                        "states)"
                                    )
                                else:
                                    st.write(
                                        "Processing"
                                        f" model "
                                        f"{md + 1}"
                                        f"/{tm}..."
                                    )
                            else:
                                st.write(
                                    "Processed"
                                    f" {completed}"
                                    "/"
                                    f"{total_tasks}"
                                    " models"
                                )

                    progress_bar.empty()
                    status_text.update(
                        label=(
                            "Processing "
                            "complete!"
                        ),
                        state="complete"
                    )

                if all_combinations:
                    for key in list(
                        st.session_state.keys()
                    ):
                        if key.startswith(
                            "beauty_video_"
                        ):
                            del st.session_state[
                                key
                            ]
                    st.session_state.beauty_all_combinations = all_combinations
                    st.session_state.beauty_current_index = 0
                    st.session_state.beauty_showing_results = True
                    n = len(all_combinations)
                    st.success(
                        f"Processed {n} "
                        "combination(s) "
                        "successfully!"
                    )
                    st.rerun()
                else:
                    st.error(
                        "No results generated. "
                        "Please try again."
                    )

