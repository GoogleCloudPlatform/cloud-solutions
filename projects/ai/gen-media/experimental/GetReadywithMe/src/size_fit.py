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

# Virtual Try-On for Better Fit with Size Recommendation
"""Virtual Try-On size and fit recommendation module."""

import base64
import io
import json
import math
import os
import re
import time
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from typing import Dict, List, Optional, Tuple

import streamlit as st
from google.genai.types import (
    GenerateContentConfig,
    Modality,
    Part,
)
from PIL import Image

# pylint: disable=line-too-long
_MODEL_REF_EXTRACTION_PROMPT = """
You are a product-data extractor. You will be given PRODUCT_INFO_TEXT.
Return ONLY a single JSON object (no commentary, no surrounding text). If no model/sample
height or size is present, return the literal JSON value null.

**REQUIRED EXACT JSON SHAPE** (use null for missing values):
{{
  "reference_model_height_in": <integer_or_null>,
  "reference_model_height_string": "<human_readable_or_null>",
  "reference_model_size_raw": "<raw_size_phrase_or_null>",
  "reference_model_size_label": "<normalized_label_or_null>",
  "raw_source_excerpt": "<up to 300 chars of the product text where this came from>"
}}

Now extract from this PRODUCT_INFO_TEXT (do NOT append any other text):
\"\"\"{product_info_text}\"\"\"
""".strip()

_BODY_ANALYSIS_PROMPT = """
You are a fashion fit and body measurement assistant.
Analyze the person in the image and return ONLY a JSON object with:
{
  "estimated_height_in": number,
  "bust_or_chest_in": number,
  "waist_in": number,
  "hip_in": number,
  "build": "slim|medium|curvy|broad|athletic",
  "posture_notes": "string",
  "skin_tone": "Fair|Light|Medium|Olive|Tan|Brown|Dark|Deep"
}

For skin_tone, choose the closest match from: Fair (very pale), Light (light beige), Medium (medium beige), Olive (olive/mediterranean), Tan (golden brown), Brown (medium brown), Dark (dark brown), Deep (very dark).
""".strip()

_OUTFIT_ANALYSIS_PROMPT = """
You are a fashion product expert.
Given OUTFIT_IMAGE and optional PRODUCT_INFO_TEXT, return ONE short sentence/phrase
describing the SINGLE MAIN PRODUCT being sold (e.g., "women's black tailored blazer").
Return only that phrase, nothing else.

PRODUCT_INFO_TEXT:
\"\"\"{product_info_text}\"\"\"
""".strip()

_BEST_SIZE_VISUAL_PROMPT = """
You are an expert fashion fit stylist.

You are given:
- ORIGINAL PRODUCT OUTFIT IMAGE (the reference for how the garment or full outfit
  is supposed to look on a model).
- Multiple TRY-ON images of the SAME PERSON wearing the SAME OUTFIT
  in DIFFERENT SIZES. Each try-on image is paired with a text label like "TRY_ON size M".

You also receive:
- ESTIMATED_BODY_MEASUREMENTS_JSON for the person:
{body_measurements_json}

- PRODUCT_INFO_TEXT about fabric, stretch, silhouette, and intended fit:
\"\"\"{product_info_text}\"\"\"

- MODEL_REFERENCE_JSON about the sample model on the product page (if available):
{model_reference_json}

- AVAILABLE_SIZES in order from smallest to largest: [{available_sizes}]

Your main guidance:
- Compare each TRY-ON image to the ORIGINAL PRODUCT OUTFIT IMAGE. Do not compare their poses.
- The BEST SIZE should preserve the garment's intended style:
  similar silhouette, drape, proportions, and natural fit ease as seen in the product image,
  while still looking realistic on this specific person's body and posture.

Your tasks, using VISUAL appearance as the main signal:

1) Choose EXACTLY ONE size as the BEST overall fit for everyday wear.
2) Also choose:
   - ONE smaller size (if available) that you would recommend for a more fitted / sharp / bodycon look.
   - ONE larger size (if available) that you would recommend for a more relaxed / oversized / roomy look.
   If there is no smaller or larger size than the best, use null for that field.

3) Return a SINGLE JSON object with this shape (no extra commentary):

{{
  "best_size": "size_label_here",
  "best_reason": "short 1-2 sentence explanation of why this looks like the best fit",
  "alt_smaller_size": "size_label_or_null",
  "alt_smaller_reason": "very short reason, or empty string if null",
  "alt_larger_size": "size_label_or_null",
  "alt_larger_reason": "very short reason, or empty string if null"
}}

Rules:
- Use ONLY size labels from AVAILABLE_SIZES.
- Do NOT wrap JSON in backticks or markdown fences.
- Use null (not the string "null") when there is no smaller or larger size.
""".strip()

_VTO_PROMPT_TEMPLATE = """
VTO engine. TARGET_SIZE: {target_size}
OUTFIT_TYPE: {outfit_type}
ESTIMATED_BODY_MEASUREMENTS_JSON:
{body_measurements_json}
PRODUCT_INFO_TEXT:
\"\"\"{product_info_text}\"\"\"
MODEL_REFERENCE_JSON:
{model_reference_json}

FIRST: CAREFULLY ANALYZE THE OUTFIT REFERENCE IMAGE
Look for and note ALL design details including:
- Slits (side, front, back) - their position and length
- Belt or waist details
- Pleats, gathers, or draping
- Color blocking or patterns
- Neckline and sleeve style
- Any unique design elements

THEN APPLY THESE ABSOLUTE CRITICAL REQUIREMENTS - VIOLATIONS WILL FAIL:

1. EXACT ZOOM AND FRAMING - DO NOT VARY:
   - The person's HEIGHT in the image must be EXACTLY the same pixels as input
   - Head must be at EXACT same position from top edge
   - Feet must be at EXACT same position from bottom edge
   - Person must occupy EXACT same percentage of frame
   - NO ZOOM IN or ZOOM OUT allowed - maintain pixel-perfect scale

2. PRESERVE ORIGINAL MODEL COMPLETELY:
   - Keep the EXACT same person/model from input image
   - Face, hair, skin tone must be identical
   - ORIGINAL SHOES/FOOTWEAR MUST BE UNCHANGED (white sneakers stay white sneakers)
   - Same pose and body positioning

3. GARMENT DETAILS & DESIGN ELEMENTS - CRITICAL:
   - MAINTAIN ALL DESIGN DETAILS from outfit reference image:
     * Side slits, front slits, back slits (if present)
     * Pleats, gathers, ruching, draping
     * Buttons, zippers, belts, ties
     * Pockets, seams, stitching details
     * Patterns, prints, color blocks
     * Collars, necklines, sleeve details
     * Any asymmetrical elements
   - MAINTAIN EXACT HEMLINE POSITION from outfit reference image
   - If outfit shows knee-length dress, ALL sizes must be knee-length
   - If outfit shows midi dress, ALL sizes must be midi length
   - Dress/skirt length must END at the SAME BODY POSITION across all sizes
   - The hem should fall at the same relative position on the body regardless of size

4. SIZE PROGRESSION LOGIC - EXTREMELY IMPORTANT:
   - Sizes MUST show realistic progression: XS < S < M < L < XL
   - Each size up should appear visibly LOOSER/WIDER than the previous
   - XS should be the MOST FITTED (tightest)
   - XL should be the MOST RELAXED (loosest)
   - NEVER show a smaller size (like S) looking looser than a larger size (like M)
   - The difference between sizes should be proportional (about 2-4 inches in circumference)
   - Common sense check: Would someone looking at all sizes side-by-side see clear progression?

5. REALISTIC FIT FOR TARGET_SIZE:
   - XS: Very fitted, close to body, minimal ease
   - S: Fitted but comfortable, slight ease
   - M: Moderate fit, natural drape, comfortable ease
   - L: Relaxed fit, more room, generous ease
   - XL: Most relaxed, ample room, maximum ease
   - Apply these fit characteristics consistently

6. ONLY MODIFY THE DRESS/CLOTHING FIT:
   - Replace ONLY the dress/main outfit with target outfit
   - Apply TARGET_SIZE fit variations (tightness/looseness) but NOT length
   - Shoes, accessories, background remain IDENTICAL
   - Dress LENGTH remains IDENTICAL to outfit reference

7. CONSISTENCY CHECK:
   - If you lined up all size images, you would see:
     * Heads, shoulders, and feet align perfectly
     * Dress hemlines at same height
     * Clear progression from tightest (XS) to loosest (XL)
     * No size anomalies or reversals
   - Background, lighting, shadows must be identical

OUTPUT: One try-on image with dress changed to TARGET_SIZE that:
- Shows proper size progression (XS tightest -> XL loosest)
- Maintains EXACT length from outfit reference
- Preserves ALL design details (slits, pleats, belts, patterns, etc.)
- Keeps everything else pixel-identical to input (pose, zoom, shoes, background)
""".strip()
# pylint: enable=line-too-long


class SizeFitTab:
    """Virtual try-on size and fit tab."""

    def __init__(
        self,
        storage_client,
        genai_client,
        gemini3_client,
        project_id,
    ):
        self.storage_client = storage_client
        # client_flash (us-central1, for flash analysis)
        self.genai_client = genai_client
        # client_vto (global, for image-preview VTO)
        self.gemini3_client = gemini3_client
        self.project_id = project_id

        self.ANALYSIS_MODEL = "gemini-3-flash-preview"
        self.VTO_MODEL = (
            "gemini-3-pro-image-preview"
        )
        self.bucket_name = os.getenv(
            "GCS_BUCKET_NAME", "lj-vto-demo"
        )
        self.gcs_input_prefix = "inputs/size_fit"

    # -------------------------
    # PROMPTS (module-level)
    # -------------------------
    MODEL_REF_EXTRACTION_PROMPT = (
        _MODEL_REF_EXTRACTION_PROMPT
    )
    BODY_ANALYSIS_PROMPT = _BODY_ANALYSIS_PROMPT
    OUTFIT_ANALYSIS_PROMPT = _OUTFIT_ANALYSIS_PROMPT
    BEST_SIZE_VISUAL_PROMPT = (
        _BEST_SIZE_VISUAL_PROMPT
    )
    VTO_PROMPT_TEMPLATE = _VTO_PROMPT_TEMPLATE

    # -------------------------
    # HELPERS
    # -------------------------
    def load_gcs_image(self, gcs_path: str) -> bytes:
        """Load image bytes from GCS."""
        bucket = self.storage_client.bucket(
            self.bucket_name
        )
        blob = bucket.blob(gcs_path)
        return blob.download_as_bytes()

    def load_gcs_text(self, gcs_path: str) -> str:
        """Load text content from GCS."""
        bucket = self.storage_client.bucket(
            self.bucket_name
        )
        blob = bucket.blob(gcs_path)
        if not blob.exists():
            return ""
        return blob.download_as_text(encoding="utf-8")

    def _image_part(
        self,
        image_bytes: bytes,
        mime_type: str = "image/png",
    ) -> Part:
        return Part.from_bytes(
            data=image_bytes, mime_type=mime_type
        )

    def _extract_image_bytes(self, response) -> bytes:
        for cand in getattr(
            response, "candidates", []
        ):
            content = getattr(cand, "content", None)
            if not content:
                continue
            for part in getattr(
                content, "parts", []
            ):
                inline = getattr(
                    part, "inline_data", None
                )
                if (
                    inline is not None
                    and getattr(
                        inline, "data", None
                    )
                    is not None
                ):
                    return inline.data
        raise RuntimeError(
            "No image inline_data found in "
            "Gemini response"
        )

    def _extract_text(self, response) -> str:
        texts = []
        for cand in getattr(
            response, "candidates", []
        ):
            content = getattr(cand, "content", None)
            if not content:
                continue
            for part in getattr(
                content, "parts", []
            ):
                if getattr(part, "text", None):
                    texts.append(part.text)
        if (
            not texts
            and hasattr(response, "text")
            and response.text
        ):
            return response.text
        if not texts:
            raise RuntimeError(
                "No text found in Gemini response"
            )
        return "\n".join(texts).strip()

    def _strip_md_fence(self, text: str) -> str:
        t = text.strip()
        if t.startswith("```"):
            lines = t.splitlines()
            lines = lines[1:]
            if lines and lines[-1].strip().startswith(
                "```"
            ):
                lines = lines[:-1]
            return "\n".join(lines).strip()
        return t

    def is_image_bytes(self, b: bytes) -> bool:
        if not b:
            return False
        return (
            b.startswith(b"\x89PNG")
            or b.startswith(b"\xff\xd8\xff")
        )

    # -------------------------
    # GEMINI CALLS
    # -------------------------
    def extract_model_reference_with_flash(
        self, product_info_text: str
    ) -> str:
        """Extract model reference info via flash."""
        if not product_info_text:
            return ""
        prompt = (
            self.MODEL_REF_EXTRACTION_PROMPT.format(
                product_info_text=product_info_text
            )
        )

        # Add retry logic for network issues
        max_retries = 3
        for attempt in range(max_retries):
            try:
                resp = (
                    self.genai_client
                    .models.generate_content(
                        model=self.ANALYSIS_MODEL,
                        contents=[prompt],
                        config=GenerateContentConfig(
                            temperature=0.0,
                            response_modalities=[
                                Modality.TEXT
                            ],
                        ),
                    )
                )
                raw = self._strip_md_fence(
                    self._extract_text(resp)
                ).strip()
                break  # Success, exit retry loop
            except (
                RuntimeError, ConnectionError,
                TimeoutError, OSError, ValueError
            ) as e:
                if (
                    "timeout" in str(e).lower()
                    and attempt < max_retries - 1
                ):
                    st.warning(
                        "Request timed out, "
                        "retrying... "
                        f"(attempt {attempt + 2}"
                        f"/{max_retries})"
                    )
                    time.sleep(2 * (attempt + 1))
                    continue
                else:
                    raise e
        if raw.lower() in ("null", ""):
            return ""
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as e:
            raise RuntimeError(
                "Gemini returned non-JSON or "
                "malformed JSON. "
                f"Raw: {raw}\n\nError: {e}"
            ) from e
        if not isinstance(obj, dict):
            raise RuntimeError(
                "Expected JSON object but got "
                f"{type(obj)}. Raw:\n{raw}"
            )
        return json.dumps(obj, indent=2)

    def analyze_body_with_flash(
        self, person_bytes: bytes
    ) -> str:
        """Analyze body measurements via flash."""
        person_part = self._image_part(person_bytes)
        resp = (
            self.genai_client
            .models.generate_content(
                model=self.ANALYSIS_MODEL,
                contents=[
                    person_part,
                    self.BODY_ANALYSIS_PROMPT,
                ],
                config=GenerateContentConfig(
                    temperature=0.0,
                    response_modalities=[
                        Modality.TEXT
                    ],
                ),
            )
        )
        body_json = self._strip_md_fence(
            self._extract_text(resp)
        )
        try:
            json.loads(body_json)
        except (json.JSONDecodeError, ValueError) as e:
            raise RuntimeError(
                "Body analysis returned invalid "
                f"JSON. Raw:\n{body_json}"
                f"\n\nError: {e}"
            ) from e
        return body_json

    def analyze_measurements(
        self,
        height: float,
        bust: float,
        waist: float,
        hip: float,
        build: str = "medium",
    ) -> str:
        """Convert user measurements to JSON."""
        body_json = {
            "estimated_height_in": height,
            "bust_or_chest_in": bust,
            "waist_in": waist,
            "hip_in": hip,
            "build": build,
            "posture_notes": "normal posture",
            "confidence_0_to_1": 0.95,
        }
        return json.dumps(body_json)

    def infer_outfit_type_with_flash(
        self,
        outfit_bytes: bytes,
        product_info_text: str,
    ) -> str:
        """Infer outfit type via flash."""
        outfit_part = self._image_part(outfit_bytes)
        prompt = (
            self.OUTFIT_ANALYSIS_PROMPT.format(
                product_info_text=(
                    product_info_text
                    or "No extra product info "
                    "provided."
                )
            )
        )
        resp = (
            self.genai_client
            .models.generate_content(
                model=self.ANALYSIS_MODEL,
                contents=[outfit_part, prompt],
                config=GenerateContentConfig(
                    temperature=0.0,
                    response_modalities=[
                        Modality.TEXT
                    ],
                ),
            )
        )
        return self._strip_md_fence(
            self._extract_text(resp)
        ).strip()

    def generate_tryon_for_size(  # noqa: C901
        self,
        person_bytes: bytes,
        outfit_bytes: bytes,
        sizeguide_bytes: Optional[bytes],
        *,
        body_measurements_json: str,
        target_size: str,
        outfit_type: str,
        product_info_text: str,
        model_reference_json: str,
    ) -> bytes:
        """Generate a try-on image for a size."""
        size_guide_text = None
        contents = [
            self._image_part(person_bytes),
            self._image_part(outfit_bytes),
        ]

        if sizeguide_bytes:
            if self.is_image_bytes(sizeguide_bytes):
                contents.append(
                    self._image_part(sizeguide_bytes)
                )
            else:
                try:
                    size_guide_text = (
                        sizeguide_bytes.decode(
                            "utf-8", errors="replace"
                        )
                    )
                except (
                    UnicodeDecodeError,
                    AttributeError,
                ):
                    size_guide_text = None

        # Extract dress length from product info
        dress_length = ""
        if product_info_text:
            lower_info = product_info_text.lower()
            if "midi" in lower_info:
                dress_length = (
                    "MIDI (knee to mid-calf)"
                )
            elif (
                "mini" in lower_info
                and "mini dress" in lower_info
            ):
                dress_length = "MINI (above knee)"
            elif "maxi" in lower_info:
                dress_length = (
                    "MAXI (ankle length)"
                )
            elif "knee" in lower_info:
                dress_length = "KNEE-LENGTH"

            length_match = re.search(
                r"(?:Dress & Skirt Length:"
                r"|Length:)\s*(\w+)",
                product_info_text,
                re.IGNORECASE,
            )
            if length_match:
                length_val = (
                    length_match.group(1).upper()
                )
                dress_length = (
                    f"{length_val} length"
                )

        no_info = "No extra product info provided."
        prompt = self.VTO_PROMPT_TEMPLATE.format(
            target_size=target_size,
            outfit_type=outfit_type,
            body_measurements_json=(
                body_measurements_json
            ),
            product_info_text=(
                product_info_text or no_info
            ),
            model_reference_json=(
                model_reference_json or "null"
            ),
        )

        # Add dress length instruction if found
        if dress_length:
            prompt = (
                "CRITICAL: This dress is "
                f"{dress_length}. ALL sizes MUST "
                "maintain this exact length."
                "\n\n" + prompt
            )

        # Parse size chart and compute recommended
        size_chart = {}
        if sizeguide_bytes:
            try:
                if isinstance(
                    sizeguide_bytes, bytes
                ):
                    size_chart = (
                        self
                        .parse_size_chart_from_text_bytes(
                            sizeguide_bytes
                        )
                    )
            except (
                ValueError, KeyError,
                IndexError, UnicodeDecodeError,
            ):
                pass

        # Determine recommended size
        person_meas = {}
        try:
            person_meas = json.loads(
                body_measurements_json
            )
        except (json.JSONDecodeError, ValueError):
            pass

        recommended_size = target_size
        if size_chart and person_meas:
            best_score = float("inf")
            for sz, sz_meas in size_chart.items():
                score = self.compute_fit_score(
                    person_meas, sz_meas
                )
                if score < best_score:
                    best_score = score
                    recommended_size = sz

        # Build size context
        size_order_list = [
            "XXS", "XS", "S", "M",
            "L", "XL", "XXL",
        ]
        size_lines = []
        for sz in size_order_list:
            if sz in size_chart:
                sc = size_chart[sz]
                marker = ""
                if sz == recommended_size:
                    marker = (
                        " <-- RECOMMENDED "
                        "(best fit for this person)"
                    )
                chest_v = sc["chest"]
                waist_v = sc["waist"]
                hip_v = sc["hip"]
                size_lines.append(
                    f"- {sz}: "
                    f"Chest {chest_v:.1f}\", "
                    f"Waist {waist_v:.1f}\", "
                    f"Hip {hip_v:.1f}\""
                    f"{marker}"
                )

        # Calculate adjacent size differences
        diff_lines = []
        prev_sz = None
        for sz in size_order_list:
            if sz in size_chart:
                if prev_sz and prev_sz in size_chart:
                    sc_cur = size_chart[sz]
                    sc_prev = size_chart[prev_sz]
                    chest_diff = (
                        sc_cur["chest"]
                        - sc_prev["chest"]
                    )
                    waist_diff = (
                        sc_cur["waist"]
                        - sc_prev["waist"]
                    )
                    hip_diff = (
                        sc_cur["hip"]
                        - sc_prev["hip"]
                    )
                    diff_lines.append(
                        f"- {prev_sz} -> {sz}: "
                        f"Chest +{chest_diff:.1f}\""
                        f", Waist "
                        f"+{waist_diff:.1f}\""
                        f", Hip "
                        f"+{hip_diff:.1f}\""
                    )
                prev_sz = sz

        # Find where target sits vs recommended
        fit_instruction = ""
        if target_size.upper() == recommended_size:
            fit_instruction = (
                f"Size {target_size} IS the "
                "recommended/best fit. Show the "
                "garment fitting naturally and "
                "comfortably on this person's "
                "body - not too tight, "
                "not too loose."
            )
        else:
            tgt_upper = target_size.upper()
            target_idx = (
                size_order_list.index(tgt_upper)
                if tgt_upper in size_order_list
                else -1
            )
            rec_idx = (
                size_order_list.index(
                    recommended_size
                )
                if recommended_size
                in size_order_list
                else -1
            )
            if target_idx >= 0 and rec_idx >= 0:
                diff = target_idx - rec_idx
                ad = abs(diff)
                ts = target_size
                rs = recommended_size
                if diff < 0:
                    fit_instruction = (
                        f"Size {ts} is {ad} "
                        "size(s) SMALLER than "
                        f"the recommended "
                        f"size {rs}. It MUST "
                        "appear visibly TIGHTER "
                        "and more fitted than "
                        f"{rs}. Show fabric "
                        "pulling slightly, "
                        "closer to the body, "
                        "with less ease."
                    )
                else:
                    fit_instruction = (
                        f"Size {ts} is {ad} "
                        "size(s) LARGER than "
                        f"the recommended "
                        f"size {rs}. It MUST "
                        "appear visibly LOOSER "
                        "and more relaxed than "
                        f"{rs}. Show more "
                        "fabric drape, extra "
                        "room, and visible ease "
                        "around the body."
                    )

        bust_val = person_meas.get(
            "bust_or_chest_in", "N/A"
        )
        waist_val = person_meas.get(
            "waist_in", "N/A"
        )
        hip_val = person_meas.get(
            "hip_in", "N/A"
        )

        # pylint: disable=line-too-long
        size_context = f"""
SIZE CHART MEASUREMENTS (from actual product size chart):
{chr(10).join(size_lines)}

MEASUREMENT DIFFERENCES BETWEEN ADJACENT SIZES:
{chr(10).join(diff_lines)}

PERSON'S BODY MEASUREMENTS:
- Bust/Chest: {bust_val}"
- Waist: {waist_val}"
- Hip: {hip_val}"

RECOMMENDED SIZE FOR THIS PERSON: {recommended_size}

YOU ARE GENERATING: Size {target_size}
{fit_instruction}

CRITICAL FIT REALISM:
- Use the ACTUAL measurement differences above to determine how much tighter or looser each size should appear.
- If the difference between S and M is 2" in chest, that difference must be visually apparent.
- The garment fit must match what a real person would experience wearing that exact size based on the size chart.
- Never make a smaller size look looser than a larger size.
"""
        # pylint: enable=line-too-long
        prompt = size_context + prompt

        if size_guide_text:
            prompt = (
                prompt
                + "\n\nSIZE_GUIDE_TEXT:\n\"\"\""
                + size_guide_text
                + "\"\"\""
            )

        contents.append(prompt)

        max_retries = 3
        for attempt in range(max_retries):
            try:
                resp = (
                    self.gemini3_client
                    .models.generate_content(
                        model=self.VTO_MODEL,
                        contents=contents,
                        config=GenerateContentConfig(
                            temperature=0.0,
                            response_modalities=[
                                Modality.IMAGE
                            ],
                        ),
                    )
                )
                return self._extract_image_bytes(
                    resp
                )
            except (
                RuntimeError, ConnectionError,
                TimeoutError, OSError, ValueError
            ) as e:
                if (
                    "429" in str(e)
                    and attempt < max_retries - 1
                ):
                    wait_time = (attempt + 1) * 5
                    print(
                        "[RETRY] Rate limited for"
                        f" size {target_size}. "
                        f"Waiting {wait_time}s "
                        f"(attempt {attempt + 1}"
                        f"/{max_retries})"
                    )
                    time.sleep(wait_time)
                    continue
                raise

    def evaluate_best_size_visually(
        self,
        body_measurements_json: str,
        product_info_text: str,
        sizes: List[str],
        tryon_results: Dict[str, bytes],
        outfit_bytes: bytes,
        model_reference_json: str,
    ) -> Tuple[
        str, str, Optional[str],
        str, Optional[str], str,
    ]:
        """Evaluate best size visually."""
        ordered_sizes = [
            s for s in sizes
            if s in tryon_results
        ]
        if not ordered_sizes:
            raise RuntimeError(
                "No try-on images available "
                "for requested sizes."
            )

        no_info = "No extra product info provided."
        prompt = (
            self.BEST_SIZE_VISUAL_PROMPT.format(
                body_measurements_json=(
                    body_measurements_json
                ),
                product_info_text=(
                    product_info_text or no_info
                ),
                model_reference_json=(
                    model_reference_json or "null"
                ),
                available_sizes=", ".join(
                    ordered_sizes
                ),
            )
        )

        contents = []
        contents.append(
            "ORIGINAL PRODUCT OUTFIT IMAGE "
            "(reference)"
        )
        contents.append(
            self._image_part(outfit_bytes)
        )
        for sz in ordered_sizes:
            contents.append(
                f"TRY_ON_IMAGE size {sz}"
            )
            contents.append(
                self._image_part(
                    tryon_results[sz]
                )
            )
        contents.append(prompt)

        resp = (
            self.genai_client
            .models.generate_content(
                model=self.ANALYSIS_MODEL,
                contents=contents,
                config=GenerateContentConfig(
                    temperature=0.0,
                    response_modalities=[
                        Modality.TEXT
                    ],
                ),
            )
        )

        raw = self._strip_md_fence(
            self._extract_text(resp)
        ).strip()
        if not raw:
            raise RuntimeError(
                "Visual evaluator returned empty "
                "response (expected JSON)."
            )

        # Clean up common JSON issues
        raw_cleaned = re.sub(
            r",\s*}", "}", raw
        )
        raw_cleaned = re.sub(
            r",\s*]", "]", raw_cleaned
        )

        try:
            parsed = json.loads(raw_cleaned)
        except (
            json.JSONDecodeError, ValueError
        ) as e:
            # Try to extract just the JSON object
            json_match = re.search(
                r"\{.*\}",
                raw_cleaned,
                re.DOTALL,
            )
            if json_match:
                try:
                    parsed = json.loads(
                        json_match.group()
                    )
                except (
                    json.JSONDecodeError,
                    ValueError,
                ):
                    raise RuntimeError(
                        "Visual evaluator returned"
                        " invalid JSON. "
                        f"Raw: {raw}"
                        f"\n\nError: {e}"
                    ) from e
            else:
                raise RuntimeError(
                    "Visual evaluator returned"
                    " invalid JSON. "
                    f"Raw: {raw}"
                    f"\n\nError: {e}"
                ) from e

        required = {
            "best_size",
            "best_reason",
            "alt_smaller_size",
            "alt_larger_size",
        }
        if (
            not isinstance(parsed, dict)
            or not required.issubset(
                set(parsed.keys())
            )
        ):
            raise RuntimeError(
                "Visual evaluator JSON missing "
                "required keys. Raw JSON:\n"
                f"{json.dumps(parsed, indent=2)}"
            )

        return (
            parsed["best_size"],
            parsed.get("best_reason", ""),
            parsed.get("alt_smaller_size"),
            parsed.get(
                "alt_smaller_reason", ""
            ),
            parsed.get("alt_larger_size"),
            parsed.get(
                "alt_larger_reason", ""
            ),
        )

    # -------------------------
    # Parse size chart
    # -------------------------
    def parse_size_chart_from_text_bytes(
        self, txt_bytes: bytes
    ) -> Dict[str, Dict[str, float]]:
        """Parse size chart from text bytes."""
        text = txt_bytes.decode(
            "utf-8", errors="replace"
        )
        lines = [
            ln.strip()
            for ln in text.splitlines()
            if ln.strip()
        ]
        size_chart: Dict[
            str, Dict[str, float]
        ] = {}

        header_idx = None
        for i, ln in enumerate(lines[:6]):
            has_size = re.search(
                r"\bSize\b",
                ln,
                flags=re.IGNORECASE,
            )
            has_chest = re.search(
                r"\bChest\b|\bBust\b",
                ln,
                flags=re.IGNORECASE,
            )
            if has_size and has_chest:
                header_idx = i
                break
        start_idx = (
            header_idx + 1
            if header_idx is not None
            else 0
        )

        for ln in lines[start_idx:]:
            if re.match(r"^[A-Za-z \-]+:$", ln):
                continue
            tokens = re.split(
                r"[\t,]| {2,}|\s{2,}", ln
            )
            tokens = [
                t.strip()
                for t in tokens
                if t.strip()
            ]
            if not tokens:
                continue
            label = tokens[0].upper()
            nums = []
            # Store (min, max) tuples
            ranges = []
            for t in tokens[1:]:
                if "\u2013" in t or "-" in t:
                    parts = re.split(
                        r"[\u2013\-]", t
                    )
                    if len(parts) == 2:
                        try:
                            val1 = float(
                                re.sub(
                                    r"[^\d\.]",
                                    "",
                                    parts[0],
                                )
                            )
                            val2 = float(
                                re.sub(
                                    r"[^\d\.]",
                                    "",
                                    parts[1],
                                )
                            )
                            nums.append(
                                (val1 + val2) / 2
                            )
                            ranges.append(
                                (val1, val2)
                            )
                        except (
                            ValueError, TypeError
                        ):
                            continue
                else:
                    t_clean = re.sub(
                        r"[^\d\.]", "", t
                    )
                    if t_clean:
                        try:
                            val = float(t_clean)
                            nums.append(val)
                            ranges.append(
                                (val, val)
                            )
                        except (
                            ValueError, TypeError
                        ):
                            continue
                if len(nums) >= 3:
                    break
            if len(nums) >= 3:
                chest = nums[0]
                waist = nums[1]
                hip = nums[2]
                c_rng = (
                    ranges[0]
                    if len(ranges) > 0
                    else (chest, chest)
                )
                w_rng = (
                    ranges[1]
                    if len(ranges) > 1
                    else (waist, waist)
                )
                h_rng = (
                    ranges[2]
                    if len(ranges) > 2
                    else (hip, hip)
                )
                size_chart[label] = {
                    "chest": chest,
                    "waist": waist,
                    "hip": hip,
                    "chest_range": c_rng,
                    "waist_range": w_rng,
                    "hip_range": h_rng,
                }
        return size_chart

    def compute_fit_score(
        self,
        person_meas: Dict[str, float],
        size_meas: Dict[str, float],
    ) -> float:
        """Calculate fit score.

        Better handling for measurements at
        range boundaries. Lower score = better fit.
        """
        score = 0.0
        mapping = [
            ("bust_or_chest_in", "chest"),
            ("waist_in", "waist"),
            ("hip_in", "hip"),
        ]
        count = 0

        for p_key, s_key in mapping:
            if (
                p_key in person_meas
                and s_key in size_meas
            ):
                person_val = person_meas[p_key]
                size_val = size_meas[s_key]

                range_key = s_key + "_range"
                if isinstance(
                    size_meas.get(range_key),
                    tuple,
                ):
                    s_min, s_max = (
                        size_meas[range_key]
                    )
                    if s_min <= person_val <= s_max:
                        diff = 0
                    elif person_val < s_min:
                        diff = s_min - person_val
                    else:
                        diff = person_val - s_max
                else:
                    diff = person_val - size_val

                score += diff * diff
                count += 1

        if count == 0:
            return float("inf")
        return math.sqrt(score)

    def evaluate_best_size(
        self,
        body_measurements_json: str,
        sizeguide_bytes: bytes,
        sizes: List[str],
        tryon_results: Dict[str, bytes],
        outfit_bytes: bytes,
        product_info_text: str,
        model_reference_json: str,
    ) -> Tuple[
        str, str, Optional[str],
        str, Optional[str], str,
    ]:
        """Evaluate best size."""
        person_meas = json.loads(
            body_measurements_json
        )
        size_chart = (
            self.parse_size_chart_from_text_bytes(
                sizeguide_bytes
            )
        )

        meas_scores: Dict[str, float] = {}
        for sz in sizes:
            key = sz.upper()
            if key in size_chart:
                meas_scores[sz] = (
                    self.compute_fit_score(
                        person_meas,
                        size_chart[key],
                    )
                )

        if not meas_scores:
            raise ValueError(
                "None of the requested sizes "
                "were found in the parsed "
                "size chart."
            )

        best_meas_size = min(
            meas_scores, key=meas_scores.get
        )

        best_vis_size = None
        best_reason = ""
        _alt_smaller = None  # pylint: disable=unused-variable
        _alt_larger = None  # pylint: disable=unused-variable
        _alt_smaller_reason = ""  # pylint: disable=unused-variable
        _alt_larger_reason = ""  # pylint: disable=unused-variable

        try:
            if tryon_results:
                (
                    best_vis_size,
                    best_reason,
                    _alt_smaller,
                    _alt_smaller_reason,
                    _alt_larger,
                    _alt_larger_reason,
                ) = (
                    self
                    .evaluate_best_size_visually(
                        body_measurements_json=(
                            body_measurements_json
                        ),
                        product_info_text=(
                            product_info_text
                        ),
                        sizes=sizes,
                        tryon_results=tryon_results,
                        outfit_bytes=outfit_bytes,
                        model_reference_json=(
                            model_reference_json
                        ),
                    )
                )
        except (
            RuntimeError, ValueError, KeyError,
            json.JSONDecodeError,
        ) as e:
            st.warning(
                f"Visual evaluator failed: {e}"
            )

        final_best = best_meas_size
        if (
            best_vis_size
            and best_vis_size == best_meas_size
        ):
            final_best = best_meas_size
            if not best_reason:
                best_reason = (
                    "Measurement and visual "
                    "evaluator agree."
                )
        elif (
            best_vis_size
            and best_vis_size != best_meas_size
        ):
            best_reason = (
                (best_reason or "")
                + f" Visual suggested "
                f"{best_vis_size}, measurement "
                f"suggests {best_meas_size}."
            )

        ordered = [
            s for s in sizes
            if s in meas_scores
        ]
        if final_best in ordered:
            idx = ordered.index(final_best)
            smaller = (
                ordered[idx - 1]
                if idx > 0
                else None
            )
            larger = (
                ordered[idx + 1]
                if idx < len(ordered) - 1
                else None
            )
        else:
            smaller, larger = None, None

        return (
            final_best,
            best_reason or (
                "Selected via measurement match"
                f" ({best_meas_size})."
            ),
            smaller,
            (
                "More fitted option based on "
                "measurements"
                if smaller
                else ""
            ),
            larger,
            (
                "More relaxed option based on "
                "measurements"
                if larger
                else ""
            ),
        )

    # -------------------------
    # STREAMLIT UI HELPERS
    # -------------------------
    def parse_size_chart_for_display(
        self, size_chart_text
    ):
        """Parse size chart text for display."""
        lines = size_chart_text.strip().split("\n")
        data = []
        for line in lines[2:]:
            parts = line.split("\t")
            if len(parts) >= 4:
                size = parts[0]
                chest = parts[1].replace(
                    "\u2013", "-"
                )
                waist = parts[2].replace(
                    "\u2013", "-"
                )
                hip = parts[3].replace(
                    "\u2013", "-"
                )
                data.append(
                    [size, chest, waist, hip]
                )
        return data

    def format_product_info_markdown(
        self, product_info
    ):
        """Format product info as markdown."""
        lines = product_info.strip().split("\n")
        formatted = []
        current_section = None
        section_names = [
            "Product details",
            "Features",
            "Size & Fit",
            "Materials & Care",
        ]

        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line in section_names:
                formatted.append(f"\n### {line}")
                current_section = line
            elif (
                line.startswith("MODEL IS")
                or line.startswith("Approx. model")
            ):
                formatted.append(f"**{line}**")
            elif (
                ":" in line
                and current_section == "Features"
            ):
                parts = line.split(":", 1)
                formatted.append(
                    f"- **{parts[0]}**: "
                    f"{parts[1].strip()}"
                )
            else:
                formatted.append(line)

        return "\n".join(formatted)

    def process_virtual_tryon(
        self,
        person_bytes,
        outfit_bytes,
        product_info,
        size_chart_text,
        sizes,
        tryon_cache=None,
    ):
        """Process virtual try-on."""
        if tryon_cache is None:
            tryon_cache = {}

        sizeguide_bytes = (
            size_chart_text.encode("utf-8")
        )

        # Analyze body
        body_json = (
            self.analyze_body_with_flash(
                person_bytes
            )
            if isinstance(person_bytes, bytes)
            else person_bytes
        )

        # Analyze outfit type
        outfit_type = (
            self.infer_outfit_type_with_flash(
                outfit_bytes, product_info
            )
        )

        # Extract model reference
        model_reference_json = (
            self
            .extract_model_reference_with_flash(
                product_info
            )
        )

        # For measurement method
        if isinstance(person_bytes, str):
            sf_gen = (
                "sf_generated_model_image"
            )
            if (
                sf_gen in st.session_state
                and st.session_state[sf_gen]
            ):
                actual_person_bytes = (
                    st.session_state[sf_gen]
                )
            else:
                actual_person_bytes = (
                    self.load_gcs_image(
                        f"{self.gcs_input_prefix}"
                        "/women.png"
                    )
                )
            actual_body_json = person_bytes
        else:
            actual_person_bytes = person_bytes
            actual_body_json = body_json

        # Generate try-ons in parallel
        results = {}
        progress_bar = st.progress(0)
        st.text("Generating...")

        def generate_single_tryon(size_label):
            cache_key = (
                f"{outfit_type}_{size_label}_"
                f"{actual_body_json[:50]}"
            )

            if cache_key in tryon_cache:
                return (
                    size_label,
                    tryon_cache[cache_key],
                )

            img_bytes = (
                self.generate_tryon_for_size(
                    person_bytes=(
                        actual_person_bytes
                    ),
                    outfit_bytes=outfit_bytes,
                    sizeguide_bytes=(
                        sizeguide_bytes
                    ),
                    body_measurements_json=(
                        actual_body_json
                    ),
                    target_size=size_label,
                    outfit_type=outfit_type,
                    product_info_text=(
                        product_info
                    ),
                    model_reference_json=(
                        model_reference_json
                        or "null"
                    ),
                )
            )

            tryon_cache[cache_key] = img_bytes
            return size_label, img_bytes

        # Check how many need generating
        sizes_to_generate = []
        for size in sizes:
            cache_key = (
                f"{outfit_type}_{size}_"
                f"{actual_body_json[:50]}"
            )
            if cache_key not in tryon_cache:
                sizes_to_generate.append(size)

        if not sizes_to_generate:
            st.text("Retrieving from cache...")

        with ThreadPoolExecutor(
            max_workers=2
        ) as executor:
            futures = [
                executor.submit(
                    generate_single_tryon, size
                )
                for size in sizes
            ]
            completed = 0
            for future in as_completed(futures):
                size_label, img_bytes = (
                    future.result()
                )
                results[size_label] = img_bytes
                completed += 1
                progress_bar.progress(
                    completed / len(sizes)
                )

        # Evaluate best size
        bj = (
            body_json
            if isinstance(person_bytes, bytes)
            else person_bytes
        )
        person_meas = json.loads(bj)
        size_chart = (
            self.parse_size_chart_from_text_bytes(
                sizeguide_bytes
            )
        )

        # Get measurement-based recommendation
        meas_scores = {}
        for sz in sizes:
            key = sz.upper()
            if key in size_chart:
                meas_scores[sz] = (
                    self.compute_fit_score(
                        person_meas,
                        size_chart[key],
                    )
                )

        measurement_best = (
            min(meas_scores, key=meas_scores.get)
            if meas_scores
            else sizes[0]
        )

        # Get visual-based recommendation
        visual_best = None
        visual_reason = ""
        try:
            if results:
                (
                    visual_best,
                    visual_reason,
                    _, _, _, _,
                ) = (
                    self
                    .evaluate_best_size_visually(
                        body_measurements_json=bj,
                        product_info_text=(
                            product_info
                        ),
                        sizes=sizes,
                        tryon_results=results,
                        outfit_bytes=outfit_bytes,
                        model_reference_json=(
                            model_reference_json
                        ),
                    )
                )
        except (
            RuntimeError, ValueError, KeyError,
            json.JSONDecodeError,
        ) as e:
            st.warning(
                f"Visual evaluator failed: {e}"
            )
            visual_best = measurement_best
            visual_reason = (
                "Visual evaluation unavailable,"
                " using measurement-based"
                " recommendation."
            )

        # If visual evaluation failed
        if not visual_best:
            visual_best = measurement_best
            visual_reason = (
                "Using measurement-based "
                "recommendation."
            )

        # Determine final best and alternatives
        ordered = [
            s for s in sizes
            if s in meas_scores
        ]
        if measurement_best in ordered:
            idx = ordered.index(measurement_best)
            alt_smaller = (
                ordered[idx - 1]
                if idx > 0
                else None
            )
            alt_larger = (
                ordered[idx + 1]
                if idx < len(ordered) - 1
                else None
            )
        else:
            alt_smaller, alt_larger = None, None

        return (
            results,
            visual_best,
            visual_reason,
            measurement_best,
            alt_smaller,
            alt_larger,
        )

    # -------------------------
    # RENDER (main UI)
    # -------------------------
    def render(self):  # noqa: C901
        """Render the size fit tab."""
        # Apply Google Blue theme
        st.markdown(
            """
            <style>
                .stButton > button[kind="primary"],
                .stButton > button {
                    background-color: #4285F4
                        !important;
                    color: white !important;
                    border: none !important;
                    border-radius: 4px !important;
                    font-weight: 500 !important;
                }
                .stButton > button:hover {
                    background-color: #357AE8
                        !important;
                }
                .stCheckbox > label >
                div[role="checkbox"]
                [aria-checked="true"] {
                    background-color: #4285F4
                        !important;
                    border-color: #4285F4
                        !important;
                }
                [data-testid="stCheckbox"] >
                label >
                div[data-checked="true"] {
                    background-color: #4285F4
                        !important;
                }
                .stSuccess {
                    color: #1976D2 !important;
                }
            </style>
            """,
            unsafe_allow_html=True,
        )

        # Initialize session state
        defaults = {
            "sf_tryon_results": None,
            "sf_recommendations": None,
            "sf_selected_product": None,
            "sf_try_on_method": None,
            "sf_generated_model_image": None,
            "sf_generated_model_measurements": (
                None
            ),
            "sf_tryon_cache": {},
        }
        for key, val in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = val

        # Load dress images and product info
        pfx = self.gcs_input_prefix
        dress1_img = self.load_gcs_image(
            f"{pfx}/dress1.png"
        )
        dress2_img = self.load_gcs_image(
            f"{pfx}/dress2.png"
        )
        dress1_info = self.load_gcs_text(
            f"{pfx}/dress1-product-info"
        )
        dress2_info = self.load_gcs_text(
            f"{pfx}/dress2-product-info"
        )
        size_chart_text = self.load_gcs_text(
            f"{pfx}/size-chart.txt"
        )

        # Step 1: Choose Try-On Method
        st.markdown(
            "## Step 1: Choose Your Try-On Method"
        )

        col_method1, col_method2 = st.columns(2)

        with col_method1:
            if st.button(
                "Image for Virtual Try-On",
                key="sf_method_upload",
                use_container_width=True,
            ):
                self._switch_to_upload_method()

        with col_method2:
            if st.button(
                "Enter Measurements for Size Fit",
                key="sf_method_measure",
                use_container_width=True,
            ):
                self._switch_to_measure_method()

        if st.session_state.sf_try_on_method:
            method = (
                st.session_state.sf_try_on_method
            )
            if method == "upload":
                self._render_upload_method(
                    size_chart_text
                )
            elif method == "measurements":
                self._render_measurements_method(
                    size_chart_text
                )

            # Show dress selection
            self._render_dress_selection(
                dress1_img,
                dress2_img,
                dress1_info,
                dress2_info,
                size_chart_text,
            )

        # Display results
        self._render_results(
            dress1_img, dress2_img
        )

    def _switch_to_upload_method(self):
        """Switch to upload method."""
        ss = st.session_state
        if ss.sf_try_on_method != "upload":
            ss.sf_tryon_results = None
            ss.sf_recommendations = None
            ss.sf_selected_product = None
            for k in [
                "sf_generated_model_image",
                "sf_generated_model_measurements",
                "sf_measurements",
                "sf_original_extracted_"
                "measurements",
            ]:
                if k in ss:
                    ss[k] = None
            ss.sf_tryon_cache = {}
        ss.sf_try_on_method = "upload"

    def _switch_to_measure_method(self):
        """Switch to measurements method."""
        ss = st.session_state
        if ss.sf_try_on_method != "measurements":
            ss.sf_tryon_results = None
            ss.sf_recommendations = None
            ss.sf_selected_product = None
            for k in [
                "sf_uploaded_person_photo",
                "sf_original_extracted_"
                "measurements",
            ]:
                if k in ss:
                    ss[k] = None
            ss.sf_tryon_cache = {}
        ss.sf_try_on_method = "measurements"

    def _render_upload_method(  # pylint: disable=unused-argument
        self, size_chart_text
    ):
        """Render upload photo method."""
        st.markdown("---")
        st.markdown(
            "## Step 2: Select or Upload "
            "Your Photo"
        )

        if (
            "sf_selected_model_bytes"
            not in st.session_state
        ):
            st.session_state[
                "sf_selected_model_bytes"
            ] = None

        photo_source = st.radio(
            "Choose photo source:",
            ["Select from Gallery", "Upload Photo"],
            horizontal=True,
            key="sf_photo_source",
        )

        uploaded_file = None

        if photo_source == "Select from Gallery":
            uploaded_file = (
                self._render_gallery_selection()
            )
        else:
            uploaded_file = (
                self._render_photo_upload()
            )

        if uploaded_file is not None:
            ss = st.session_state
            ss.sf_uploaded_person_photo = (
                uploaded_file
            )
            self._render_extracted_measurements(
                uploaded_file
            )

        if uploaded_file:
            st.markdown("---")
            st.markdown(
                "## Step 3: Select a Dress"
            )

    def _render_gallery_selection(self):
        """Render gallery model selection."""
        uploaded_file = None
        with st.spinner("Loading models..."):
            try:
                bucket = (
                    self.storage_client.bucket(
                        self.bucket_name
                    )
                )
                model_blobs = list(
                    bucket.list_blobs(
                        prefix=(
                            "beauty/vto/"
                            "models/model_"
                        )
                    )
                )
                model_images = []
                for blob in sorted(
                    model_blobs,
                    key=lambda b: b.name,
                ):
                    exts = (
                        ".png", ".jpg", ".jpeg"
                    )
                    if blob.name.endswith(exts):
                        img_bytes = (
                            blob.download_as_bytes()
                        )
                        name = (
                            blob.name.split("/")
                            [-1]
                            .replace(".png", "")
                            .replace(".jpg", "")
                        )
                        model_images.append({
                            "name": name,
                            "bytes": img_bytes,
                        })
            except (
                OSError, ValueError, RuntimeError
            ) as e:
                st.error(
                    "Error loading "
                    f"models: {e}"
                )
                model_images = []

        if model_images:
            cols = st.columns(
                min(5, len(model_images))
            )
            for idx, model in enumerate(
                model_images
            ):
                col_idx = idx % len(cols)
                with cols[col_idx]:
                    img = Image.open(
                        io.BytesIO(model["bytes"])
                    )
                    st.image(img, width=250)
                    is_selected = (
                        st.session_state.get(
                            "sf_gallery_selected"
                        )
                        == idx
                    )
                    if is_selected:
                        st.markdown(
                            "**Selected**"
                        )
                    else:
                        btn_key = (
                            "sf_gallery_"
                            f"model_{idx}"
                        )
                        if st.button(
                            "Select",
                            key=btn_key,
                        ):
                            ss = st.session_state
                            ss[
                                "sf_gallery_"
                                "selected"
                            ] = idx
                            ss[
                                "sf_selected_"
                                "model_bytes"
                            ] = model["bytes"]
                            ss[
                                "sf_uploaded_"
                                "person_photo"
                            ] = None
                            st.rerun()

            smb = st.session_state.get(
                "sf_selected_model_bytes"
            )
            if smb:

                class BytesFile:
                    """File-like bytes wrapper."""

                    def __init__(self, data):
                        self._data = data

                    def getvalue(self):
                        """Return bytes."""
                        return self._data

                    def read(self):
                        """Read bytes."""
                        return self._data

                uploaded_file = BytesFile(smb)
                st.session_state[
                    "sf_uploaded_person_photo"
                ] = uploaded_file
        else:
            st.warning(
                "No models found in gallery."
            )

        return uploaded_file

    def _render_photo_upload(self):
        """Render photo upload widget."""
        uploaded_file = None
        upload_widget = st.file_uploader(
            "Choose a photo for virtual try-on...",
            type=["jpg", "jpeg", "png"],
            key="sf_person_photo_upload",
        )
        if upload_widget is not None:
            uploaded_file = upload_widget
            ss = st.session_state
            ss.sf_uploaded_person_photo = (
                uploaded_file
            )
            ss.sf_selected_model_bytes = None
            ss.sf_gallery_selected = None

            _col1, col2, _col3 = st.columns(  # pylint: disable=unused-variable
                [1, 2, 1]
            )
            with col2:
                st.image(
                    uploaded_file,
                    caption="Your uploaded photo",
                    width=350,
                )

        return uploaded_file

    def _render_extracted_measurements(
        self, uploaded_file
    ):
        """Render extracted measurements."""
        st.markdown(
            "#### Extracted Virtual Measurements"
        )
        with st.spinner(
            "Analyzing body measurements "
            "from your photo..."
        ):
            try:
                person_bytes = (
                    uploaded_file.getvalue()
                )
                body_json = (
                    self.analyze_body_with_flash(
                        person_bytes
                    )
                )
                measurements = json.loads(
                    body_json
                )

                orig_key = (
                    "sf_original_extracted_"
                    "measurements"
                )
                if (
                    orig_key
                    not in st.session_state
                ):
                    st.session_state[
                        orig_key
                    ] = measurements.copy()

                st.markdown(
                    "##### Review and Edit "
                    "Measurements"
                )
                st.info(
                    "The measurements below were "
                    "extracted from your photo. "
                    "You can edit them if needed "
                    "for better fit "
                    "recommendations."
                )

                col1_edit, col2_edit = (
                    st.columns(2)
                )

                with col1_edit:
                    measurements = (
                        self
                        ._render_measurement_inputs(
                            measurements
                        )
                    )

                with col2_edit:
                    self._render_body_details(
                        measurements
                    )

                updated_body_json = json.dumps(
                    measurements
                )
                st.session_state[
                    "sf_uploaded_photo_measurements"
                ] = updated_body_json

                self._check_measurements_edited(
                    measurements
                )

                st.markdown("---")
                st.markdown(
                    "##### Final Measurements "
                    "for Virtual Try-On:"
                )
                self._render_measurement_summary(
                    measurements
                )

                st.info(
                    "**Note:** These measurements "
                    "will be used to determine the "
                    "best fit for virtual try-on. "
                    "You can edit them above "
                    "if needed."
                )

            except (
                RuntimeError, ValueError,
                KeyError, json.JSONDecodeError,
            ) as e:
                st.warning(
                    "Could not extract "
                    "measurements from "
                    f"photo: {e}"
                )

    def _render_measurement_inputs(
        self, measurements
    ):
        """Render measurement input fields."""
        st.markdown("**Physical Measurements:**")

        height_inches = measurements.get(
            "estimated_height_in", 0
        )
        feet_default = int(height_inches // 12)
        inches_default = int(height_inches % 12)

        st.markdown("Height:")
        col_ft, col_in = st.columns(2)
        with col_ft:
            feet_edited = st.number_input(
                "Feet",
                min_value=4,
                max_value=7,
                value=feet_default,
                key="sf_upload_height_feet",
                label_visibility="collapsed",
            )
        with col_in:
            inches_edited = st.number_input(
                "Inches",
                min_value=0,
                max_value=11,
                value=inches_default,
                key="sf_upload_height_inches",
                label_visibility="collapsed",
            )

        edited_height = (
            feet_edited * 12 + inches_edited
        )
        st.caption(
            f"Total: {edited_height} inches"
        )

        bust_val = float(
            measurements.get(
                "bust_or_chest_in", 35
            )
        )
        bust_edited = st.number_input(
            "Bust/Chest (inches)",
            min_value=20.0,
            max_value=60.0,
            value=bust_val,
            step=0.5,
            key="sf_upload_bust",
        )

        waist_val = float(
            measurements.get("waist_in", 28)
        )
        waist_edited = st.number_input(
            "Waist (inches)",
            min_value=20.0,
            max_value=50.0,
            value=waist_val,
            step=0.5,
            key="sf_upload_waist",
        )

        hip_val = float(
            measurements.get("hip_in", 37)
        )
        hip_edited = st.number_input(
            "Hip (inches)",
            min_value=25.0,
            max_value=60.0,
            value=hip_val,
            step=0.5,
            key="sf_upload_hip",
        )

        measurements[
            "estimated_height_in"
        ] = edited_height
        measurements[
            "bust_or_chest_in"
        ] = bust_edited
        measurements["waist_in"] = waist_edited
        measurements["hip_in"] = hip_edited

        return measurements

    def _render_body_details(self, measurements):
        """Render body detail attributes."""
        st.markdown("**Additional Details:**")

        detected_tone = measurements.get(
            "skin_tone", "Medium"
        )

        skin_tone_colors = {
            "Fair": "#FDDCB2",
            "Light": "#F3CEAF",
            "Medium": "#D5A987",
            "Olive": "#C4915C",
            "Tan": "#A67C52",
            "Brown": "#8B6947",
            "Dark": "#654936",
            "Deep": "#4A3426",
        }

        color_code = skin_tone_colors.get(
            detected_tone, "#D5A987"
        )

        build_val = measurements.get(
            "build", "N/A"
        ).title()
        posture_val = measurements.get(
            "posture_notes", "Normal"
        )
        details_data = {
            "Attribute": [
                "Body Build",
                "Posture",
                "Skin Tone",
            ],
            "Value": [
                build_val,
                posture_val,
                detected_tone,
            ],
        }
        st.table(details_data)

        # pylint: disable=line-too-long
        st.markdown(
            f"""
            <div style="display: flex; align-items: center; margin-top: -10px;">
                <span style="margin-right: 10px;">Skin Tone Color:</span>
                <div style="width: 80px; height: 30px; background-color: {color_code};
                     border: 2px solid #ccc; border-radius: 5px;"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        # pylint: enable=line-too-long

    def _check_measurements_edited(
        self, measurements
    ):
        """Check if measurements were edited."""
        orig_key = (
            "sf_original_extracted_measurements"
        )
        if orig_key in st.session_state:
            orig = st.session_state[orig_key]
            fields = [
                "estimated_height_in",
                "bust_or_chest_in",
                "waist_in",
                "hip_in",
            ]
            changed = any(
                orig.get(f) != measurements.get(f)
                for f in fields
            )
            if changed:
                st.success(
                    "Measurements updated! "
                    "These edited values will "
                    "be used for size "
                    "recommendations."
                )

    def _render_measurement_summary(
        self, measurements
    ):
        """Render measurement summary."""
        height = measurements[
            "estimated_height_in"
        ]
        feet_final = int(height // 12)
        inches_final = int(height % 12)

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric(
                "Height",
                f"{feet_final}' "
                f"{inches_final}\"",
            )
        with c2:
            bust = measurements[
                "bust_or_chest_in"
            ]
            st.metric(
                "Bust", f"{bust:.1f}\""
            )
        with c3:
            waist = measurements["waist_in"]
            st.metric(
                "Waist", f"{waist:.1f}\""
            )
        with c4:
            hip = measurements["hip_in"]
            st.metric(
                "Hip", f"{hip:.1f}\""
            )

    def _render_measurements_method(  # pylint: disable=unused-argument
        self, size_chart_text
    ):
        """Render measurements input method."""
        st.markdown("---")
        st.markdown(
            "## Step 2: Enter Your Measurements"
        )

        st.info(
            "Using standard model measurements "
            "(5'8\" tall). You can adjust them "
            "below if needed:"
        )

        col1, col2 = st.columns(2)
        with col1:
            height_total = st.number_input(
                "Height (inches)",
                min_value=48,
                max_value=84,
                value=68,
                key="sf_height_total_step2",
                help=(
                    "Enter your height in inches"
                ),
            )
            feet = height_total // 12
            inches = height_total % 12
            st.caption(
                f"Height: {height_total} inches "
                f"({feet}'{inches}\")"
            )

            bust = st.number_input(
                "Bust/Chest (inches)",
                min_value=20.0,
                max_value=60.0,
                value=35.0,
                step=0.5,
                key="sf_bust_step2",
            )
            waist = st.number_input(
                "Waist (inches)",
                min_value=20.0,
                max_value=50.0,
                value=28.0,
                step=0.5,
                key="sf_waist_step2",
            )

        with col2:
            hip = st.number_input(
                "Hip (inches)",
                min_value=25.0,
                max_value=60.0,
                value=37.5,
                step=0.5,
                key="sf_hip_step2",
            )

            build_options = {
                "slim": (
                    "Slim - Narrow frame, "
                    "smaller bone structure"
                ),
                "medium": (
                    "Medium - Average build, "
                    "balanced proportions"
                ),
                "curvy": (
                    "Curvy - Fuller hips and "
                    "bust, defined waist"
                ),
                "broad": (
                    "Broad - Wider shoulders "
                    "and frame"
                ),
                "athletic": (
                    "Athletic - Muscular, "
                    "toned build"
                ),
            }

            build = st.selectbox(
                "Body Build",
                options=list(
                    build_options.keys()
                ),
                format_func=(
                    lambda x: build_options[x]
                ),
                index=1,
                key="sf_build_step2",
                help=(
                    "Select the body type that "
                    "best describes your build"
                ),
            )

            skin_tones = {
                "Fair": "#FDDCB2",
                "Light": "#F3CEAF",
                "Medium": "#D5A987",
                "Olive": "#C4915C",
                "Tan": "#A67C52",
                "Brown": "#8B6947",
                "Dark": "#654936",
                "Deep": "#4A3426",
            }

            skin_tone = st.selectbox(
                "Skin Tone",
                options=list(skin_tones.keys()),
                index=2,
                key="sf_skin_tone_step2",
                help=(
                    "Select your skin tone "
                    "for the model"
                ),
            )

            # pylint: disable=line-too-long
            st.markdown(
                f"<div style=\"width: 100%; height: 30px; background-color: {skin_tones[skin_tone]}; "
                f"border: 2px solid #ccc; border-radius: 5px; margin-top: -10px;\"></div>",
                unsafe_allow_html=True,
            )
            # pylint: enable=line-too-long

        # Save measurements to session state
        st.session_state.sf_measurements = {
            "height_total": height_total,
            "bust": bust,
            "waist": waist,
            "hip": hip,
            "build": build,
            "skin_tone": skin_tone,
        }

        st.markdown("---")

        current_measurements = {
            "height": height_total,
            "bust": bust,
            "waist": waist,
            "hip": hip,
            "build": build,
            "skin_tone": skin_tone,
        }

        ss = st.session_state
        model_exists = (
            ss.sf_generated_model_image is not None
            and ss.sf_generated_model_measurements
            == current_measurements
        )

        button_text = (
            "Model Already Generated "
            "(Click to Regenerate)"
            if model_exists
            else "Generate Virtual Model"
        )

        if st.button(
            button_text,
            type="primary",
            key="sf_generate_model_btn",
            use_container_width=True,
        ):
            if model_exists:
                ss.sf_tryon_cache = {}

            self._generate_virtual_model(
                height_total,
                bust,
                waist,
                hip,
                build,
                skin_tone,
                current_measurements,
            )

        # Display generated model if available
        if (
            ss.sf_generated_model_image
            is not None
        ):
            self._display_generated_model(
                height_total,
                bust,
                waist,
                hip,
                build,
                skin_tone,
                feet,
                inches,
            )

        st.markdown("---")
        st.markdown(
            "## Step 3: Select a Dress"
        )

    def _generate_virtual_model(
        self,
        height_total,
        bust,
        waist,
        hip,
        build,
        skin_tone,
        current_measurements,
    ):
        """Generate a virtual model image."""
        with st.spinner(
            "Generating your virtual model "
            "based on measurements..."
        ):
            try:
                feet = height_total // 12
                inches = height_total % 12

                # pylint: disable=line-too-long
                model_prompt = f"""Generate a COMPLETE full-body studio photograph of a female model with EXACT specifications:

CRITICAL FRAMING REQUIREMENTS:
- FULL HEIGHT image showing ENTIRE body from top of head to bottom of shoes
- Vertical portrait orientation
- Model takes up 80% of frame height
- Equal spacing above head and below feet
- NO CROPPING anywhere - full figure must be completely visible

Physical Specifications:
- Height: {feet}'{inches}" ({height_total} inches)
- Bust: {bust} inches
- Waist: {waist} inches
- Hip: {hip} inches
- Body type: {build}
- Skin tone: {skin_tone}

Exact Outfit (all must be fully visible):
- Plain white fitted t-shirt (tucked into jeans)
- Black straight-leg jeans (full length)
- White canvas sneakers (Converse/Vans style)

Pose Requirements:
- Standing perfectly straight
- Facing directly forward
- Arms naturally at sides
- Feet shoulder-width apart
- Neutral expression
- Looking at camera

Background & Style:
- Pure white seamless background
- Professional studio lighting
- Fashion catalog style
- High resolution, sharp focus
- No shadows at feet

VERIFY: Entire person from hair to shoes is visible in frame"""
                # pylint: enable=line-too-long

                response = (
                    self.gemini3_client
                    .models.generate_content(
                        model=self.VTO_MODEL,
                        contents=[model_prompt],
                        config=(
                            GenerateContentConfig(
                                temperature=0.0,
                                response_modalities=[
                                    Modality.IMAGE
                                ],
                            )
                        ),
                    )
                )

                generated_image_bytes = (
                    self._extract_image_bytes(
                        response
                    )
                )

                ss = st.session_state
                ss.sf_generated_model_image = (
                    generated_image_bytes
                )
                ss.sf_generated_model_measurements = (
                    current_measurements
                )
                try:
                    bucket = (
                        self.storage_client.bucket(
                            self.bucket_name
                        )
                    )
                    # pylint: disable=import-outside-toplevel
                    from datetime import datetime

                    # pylint: enable=import-outside-toplevel
                    ts = datetime.now().strftime(
                        "%Y%m%d_%H%M%S"
                    )
                    gcs_path = (
                        "outputs/size_fit/"
                        f"generated_model_{ts}.png"
                    )
                    blob = bucket.blob(gcs_path)
                    blob.upload_from_string(
                        generated_image_bytes,
                        content_type="image/png",
                    )
                except (
                    OSError, RuntimeError
                ):
                    pass
                st.success(
                    "Virtual model generated "
                    "successfully!"
                )

            except (
                RuntimeError, ValueError, OSError
            ) as e:
                st.error(
                    "Failed to generate "
                    f"model: {e}"
                )

    def _display_generated_model(
        self,
        height_total,
        bust,
        waist,
        hip,
        build,
        skin_tone,
        feet,
        inches,
    ):
        """Display generated model."""
        st.markdown(
            "### Your Generated Virtual Model"
        )
        st.markdown(
            "*Full-body model wearing white "
            "shirt, black jeans, and white "
            "canvas shoes*"
        )

        st.markdown(
            "#### Virtual Model Measurements:"
        )
        mc1, mc2, mc3 = st.columns(3)
        with mc1:
            st.metric(
                "Height",
                f"{feet}' {inches}\" "
                f"({height_total} in)",
            )
            st.metric(
                "Bust/Chest",
                f"{bust} inches",
            )
        with mc2:
            st.metric(
                "Waist", f"{waist} inches"
            )
            st.metric(
                "Hip", f"{hip} inches"
            )
        with mc3:
            st.metric("Build", build.title())
            st.metric("Skin Tone", skin_tone)

        st.markdown(
            "#### Generated Model Image:"
        )
        try:
            ss = st.session_state
            img_gen = Image.open(
                io.BytesIO(
                    ss.sf_generated_model_image
                )
            )
            if img_gen.mode == "RGBA":
                bg = Image.new(
                    "RGB",
                    img_gen.size,
                    (255, 255, 255),
                )
                bg.paste(
                    img_gen,
                    mask=img_gen.split()[3],
                )
                img_gen = bg
            buf = io.BytesIO()
            img_gen.save(
                buf, format="JPEG", quality=90
            )
            b64_gen = base64.b64encode(
                buf.getvalue()
            ).decode()
            # pylint: disable=line-too-long
            st.markdown(
                f"""
                <div style="display:flex; justify-content:center; margin:10px auto;">
                    <img src="data:image/jpeg;base64,{b64_gen}" style="max-height:550px; width:auto; border-radius:8px; border:1px solid #e0e0e0; box-shadow:0 2px 8px rgba(0,0,0,0.1);" />
                </div>
                <p style="text-align:center; color:#666; font-size:13px; margin-top:6px;">Virtual Model Ready for Try-On</p>
                """,
                unsafe_allow_html=True,
            )
            # pylint: enable=line-too-long
        except (OSError, ValueError) as e:
            st.error(
                "Error displaying "
                f"model image: {e}"
            )

    def _render_dress_selection(
        self,
        dress1_img,
        dress2_img,
        dress1_info,
        dress2_info,
        size_chart_text,
    ):
        """Render dress selection UI."""
        method = st.session_state.sf_try_on_method
        has_photo = (
            "sf_uploaded_person_photo"
            in st.session_state
        )
        if not (
            method == "measurements"
            or (
                method == "upload" and has_photo
            )
        ):
            return

        col1, col2 = st.columns(2)

        with col1:
            self._render_dress_centered(
                dress1_img,
                "Dress 1 - Donna Karan "
                "Colorblocked Fit & Flare",
            )
            if st.button(
                "Select Dress 1",
                key="sf_select_dress1",
                use_container_width=True,
            ):
                st.session_state[
                    "sf_selected_product"
                ] = "Dress 1"

        with col2:
            self._render_dress_centered(
                dress2_img,
                "Dress 2 - DKNY Ombre "
                "Sunburst Pleat-Skirt",
            )
            if st.button(
                "Select Dress 2",
                key="sf_select_dress2",
                use_container_width=True,
            ):
                st.session_state[
                    "sf_selected_product"
                ] = "Dress 2"

        # Show selected product info
        if st.session_state.sf_selected_product:
            self._render_selected_product_info(
                dress1_img,
                dress2_img,
                dress1_info,
                dress2_info,
                size_chart_text,
            )

    def _render_dress_centered(
        self, img_bytes, caption
    ):
        """Render dress image centered."""
        img = Image.open(
            io.BytesIO(img_bytes)
        )
        if img.mode == "RGBA":
            bg = Image.new(
                "RGB",
                img.size,
                (255, 255, 255),
            )
            bg.paste(
                img, mask=img.split()[3]
            )
            img = bg
        buf = io.BytesIO()
        img.save(
            buf, format="JPEG", quality=90
        )
        b64 = base64.b64encode(
            buf.getvalue()
        ).decode()
        # pylint: disable=line-too-long
        st.markdown(
            f"""
            <div style="display:flex; flex-direction:column; align-items:center; padding:10px;">
                <img src="data:image/jpeg;base64,{b64}" style="max-height:450px; width:auto; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.1);" />
                <p style="text-align:center; margin-top:8px; font-size:14px; color:#555;">{caption}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        # pylint: enable=line-too-long

    def _render_selected_product_info(
        self,
        dress1_img,
        dress2_img,
        dress1_info,
        dress2_info,
        size_chart_text,
    ):
        """Render selected product info."""
        selected = (
            st.session_state.sf_selected_product
        )
        st.success(f"Selected: {selected}")

        st.markdown("---")
        info_col1, info_col2 = st.columns(2)

        with info_col1:
            with st.expander(
                "Product Information",
                expanded=False,
            ):
                info = (
                    dress1_info
                    if selected == "Dress 1"
                    else dress2_info
                )
                st.markdown(
                    self
                    .format_product_info_markdown(
                        info
                    )
                )

        with info_col2:
            with st.expander(
                "Size Chart", expanded=False
            ):
                size_data = (
                    self
                    .parse_size_chart_for_display(
                        size_chart_text
                    )
                )
                if size_data:
                    st.markdown(
                        "**Donna Karan New York "
                        "Dress Size Chart**"
                    )
                    st.table({
                        "Size": [
                            row[0]
                            for row in size_data
                        ],
                        "Chest (in.)": [
                            row[1]
                            for row in size_data
                        ],
                        "Waist (in.)": [
                            row[2]
                            for row in size_data
                        ],
                        "Hip (in.)": [
                            row[3]
                            for row in size_data
                        ],
                    })

        st.markdown("---")
        method = st.session_state.sf_try_on_method
        if method == "measurements":
            st.markdown(
                "## Step 4: Proceed with Try-On"
            )
        else:
            st.markdown(
                "## Step 3: Proceed with Try-On"
            )

        # Get outfit bytes and info
        if selected == "Dress 1":
            outfit_bytes = dress1_img
            product_info = dress1_info
        else:
            outfit_bytes = dress2_img
            product_info = dress2_info

        if method == "upload":
            self._render_upload_tryon(
                outfit_bytes,
                product_info,
                size_chart_text,
            )
        elif method == "measurements":
            self._render_measurement_tryon(
                outfit_bytes,
                product_info,
                size_chart_text,
            )

    def _render_upload_tryon(
        self,
        outfit_bytes,
        product_info,
        size_chart_text,
    ):
        """Render upload-based try-on."""
        ss = st.session_state
        if "sf_uploaded_person_photo" not in ss:
            return

        uploaded_file = ss.sf_uploaded_person_photo
        st.markdown(
            "### Using Your Uploaded Photo"
        )
        st.markdown(
            "### Smart Size Selection Based on "
            "Your Extracted Measurements"
        )

        all_sizes = ["XS", "S", "M", "L", "XL"]

        photo_meas_key = (
            "sf_uploaded_photo_measurements"
        )
        if photo_meas_key in ss:
            body_json = ss[photo_meas_key]
            person_meas = json.loads(body_json)

            sizeguide_bytes = (
                size_chart_text.encode("utf-8")
            )
            size_chart = (
                self
                .parse_size_chart_from_text_bytes(
                    sizeguide_bytes
                )
            )

            meas_scores = {}
            for sz in all_sizes:
                key = sz.upper()
                if key in size_chart:
                    meas_scores[sz] = (
                        self.compute_fit_score(
                            person_meas,
                            size_chart[key],
                        )
                    )

            if meas_scores:
                best_size = min(
                    meas_scores,
                    key=meas_scores.get,
                )
                ordered_sizes = [
                    s for s in all_sizes
                    if s in meas_scores
                ]
                recommended_sizes = [best_size]

                if best_size in ordered_sizes:
                    idx = ordered_sizes.index(
                        best_size
                    )
                    if idx > 0:
                        recommended_sizes.insert(
                            0,
                            ordered_sizes[idx - 1],
                        )
                    if idx < (
                        len(ordered_sizes) - 1
                    ):
                        recommended_sizes.append(
                            ordered_sizes[idx + 1]
                        )
            else:
                recommended_sizes = [
                    "S", "M", "L"
                ]

            rec_str = ", ".join(
                recommended_sizes
            )
            st.info(
                "Based on your extracted "
                "measurements, we recommend "
                f"trying: **{rec_str}**"
            )
            st.write(
                "These sizes are automatically "
                "selected for virtual try-on:"
            )
        else:
            recommended_sizes = ["S", "M", "L"]
            st.write(
                "Choose which sizes to generate "
                "virtual try-ons for:"
            )

        selected_sizes = (
            self._render_size_checkboxes(
                all_sizes,
                recommended_sizes,
                "sf_upload_size_",
            )
        )

        if st.button(
            "Start Virtual Try-On",
            type="primary",
            key="sf_start_upload_tryon",
            disabled=len(selected_sizes) == 0,
        ):
            if len(selected_sizes) == 0:
                st.error(
                    "Please select at least "
                    "one size"
                )
            else:
                with st.spinner("Generating..."):
                    try:
                        person_bytes = (
                            uploaded_file.getvalue()
                        )
                        (
                            results,
                            visual_best,
                            visual_reason,
                            measurement_best,
                            alt_smaller,
                            alt_larger,
                        ) = self.process_virtual_tryon(
                            person_bytes,
                            outfit_bytes,
                            product_info,
                            size_chart_text,
                            selected_sizes,
                            ss.sf_tryon_cache,
                        )

                        ss.sf_tryon_results = (
                            results
                        )
                        self._save_recommendations(
                            visual_best,
                            visual_reason,
                            measurement_best,
                            alt_smaller,
                            alt_larger,
                        )
                        self._save_output_to_gcs(
                            results
                        )

                    except (
                        RuntimeError,
                        ValueError,
                        OSError,
                    ) as e:
                        st.error(
                            "An error occurred: "
                            f"{e}"
                        )

    def _render_measurement_tryon(
        self,
        outfit_bytes,
        product_info,
        size_chart_text,
    ):
        """Render measurement-based try-on."""
        ss = st.session_state
        st.markdown("### Your Measurements")

        if "sf_measurements" in ss:
            meas = ss.sf_measurements
            ht = meas["height_total"]
            ft = ht // 12
            inc = ht % 12
            bust = meas["bust"]
            waist = meas["waist"]
            hip = meas["hip"]
            build = meas["build"]
            st.info(
                f"**Height:** {ft}' {inc}\" "
                f"({ht} inches) | "
                f"**Bust:** {bust}\" | "
                f"**Waist:** {waist}\" | "
                f"**Hip:** {hip}\" | "
                f"**Build:** "
                f"{build.title()}"
            )

        st.markdown(
            "### Smart Size Selection Based on "
            "Your Measurements"
        )

        meas = ss.sf_measurements
        body_json = self.analyze_measurements(
            meas["height_total"],
            meas["bust"],
            meas["waist"],
            meas["hip"],
            meas["build"],
        )

        sizeguide_bytes = (
            size_chart_text.encode("utf-8")
        )
        person_meas = json.loads(body_json)
        size_chart = (
            self.parse_size_chart_from_text_bytes(
                sizeguide_bytes
            )
        )

        all_sizes = ["XS", "S", "M", "L", "XL"]
        meas_scores = {}
        for sz in all_sizes:
            key = sz.upper()
            if key in size_chart:
                meas_scores[sz] = (
                    self.compute_fit_score(
                        person_meas,
                        size_chart[key],
                    )
                )

        if meas_scores:
            best_size = min(
                meas_scores,
                key=meas_scores.get,
            )
            ordered_sizes = [
                s for s in all_sizes
                if s in meas_scores
            ]
            recommended_sizes = [best_size]

            if best_size in ordered_sizes:
                idx = ordered_sizes.index(
                    best_size
                )
                if idx > 0:
                    recommended_sizes.insert(
                        0, ordered_sizes[idx - 1]
                    )
                if idx < len(ordered_sizes) - 1:
                    recommended_sizes.append(
                        ordered_sizes[idx + 1]
                    )
        else:
            recommended_sizes = ["S", "M", "L"]

        rec_str = ", ".join(recommended_sizes)
        st.info(
            "Based on your measurements, we "
            "recommend trying: "
            f"**{rec_str}**"
        )
        st.write(
            "These sizes are automatically "
            "selected for virtual try-on:"
        )

        selected_sizes = (
            self._render_size_checkboxes(
                all_sizes,
                recommended_sizes,
                "sf_size_",
            )
        )

        if st.button(
            "Generate Virtual Try-On "
            "with Measurements",
            type="primary",
            key="sf_start_measure_tryon",
            disabled=len(selected_sizes) == 0,
        ):
            if len(selected_sizes) == 0:
                st.error(
                    "Please select at least "
                    "one size"
                )
            else:
                with st.spinner("Generating..."):
                    try:
                        meas = ss.sf_measurements
                        body_json = (
                            self
                            .analyze_measurements(
                                meas[
                                    "height_total"
                                ],
                                meas["bust"],
                                meas["waist"],
                                meas["hip"],
                                meas["build"],
                            )
                        )

                        (
                            results,
                            visual_best,
                            visual_reason,
                            measurement_best,
                            alt_smaller,
                            alt_larger,
                        ) = self.process_virtual_tryon(
                            body_json,
                            outfit_bytes,
                            product_info,
                            size_chart_text,
                            selected_sizes,
                            ss.sf_tryon_cache,
                        )

                        ss.sf_tryon_results = (
                            results
                        )
                        self._save_recommendations(
                            visual_best,
                            visual_reason,
                            measurement_best,
                            alt_smaller,
                            alt_larger,
                        )
                        self._save_output_to_gcs(
                            results
                        )

                    except (
                        RuntimeError,
                        ValueError,
                        OSError,
                    ) as e:
                        st.error(
                            "An error occurred: "
                            f"{e}"
                        )

    def _render_size_checkboxes(
        self,
        all_sizes,
        recommended_sizes,
        key_prefix,
    ):
        """Render size checkbox selection."""
        cols = st.columns(5)
        selected_sizes = []
        size_to_col = {
            "XS": 0, "S": 1, "M": 2,
            "L": 3, "XL": 4,
        }

        for size in all_sizes:
            col_idx = size_to_col[size]
            with cols[col_idx]:
                is_rec = (
                    size in recommended_sizes
                )
                label = (
                    f"{size}*"
                    if is_rec
                    else size
                )
                help_text = (
                    "Recommended based on "
                    "measurements"
                    if is_rec
                    else "Not recommended for "
                    "your measurements"
                )
                if st.checkbox(
                    label,
                    value=is_rec,
                    key=(
                        f"{key_prefix}"
                        f"{size.lower()}"
                    ),
                    help=help_text,
                ):
                    selected_sizes.append(size)

        return selected_sizes

    def _save_recommendations(
        self,
        visual_best,
        visual_reason,
        measurement_best,
        alt_smaller,
        alt_larger,
    ):
        """Save recommendations to session."""
        fit_sm = (
            "More fitted option based on "
            "measurements"
            if alt_smaller
            else ""
        )
        fit_lg = (
            "More relaxed option based on "
            "measurements"
            if alt_larger
            else ""
        )
        st.session_state.sf_recommendations = {
            "visual_best": visual_best,
            "visual_reason": visual_reason,
            "measurement_best": measurement_best,
            "alt_smaller": alt_smaller,
            "alt_smaller_reason": fit_sm,
            "alt_larger": alt_larger,
            "alt_larger_reason": fit_lg,
        }

    def _save_output_to_gcs(self, results):
        """Save output images to GCS."""
        ss = st.session_state
        dress_name = (
            ss.sf_selected_product.replace(
                " ", ""
            )
        )
        bucket = self.storage_client.bucket(
            self.bucket_name
        )

        saved_files = []
        for size, img_bytes in results.items():
            filename = (
                f"{size}_{dress_name}.png"
            )
            gcs_path = (
                f"outputs/size_fit/{filename}"
            )
            blob = bucket.blob(gcs_path)
            blob.upload_from_string(
                img_bytes,
                content_type="image/png",
            )
            saved_files.append(filename)

        st.success(
            "Virtual try-on complete! "
            "Images saved to "
            f"gs://{self.bucket_name}"
            "/outputs/size_fit/"
        )
        files_str = ", ".join(saved_files)
        st.info(f"Saved files: {files_str}")

    def _render_results(
        self, dress1_img, dress2_img
    ):
        """Render try-on results."""
        ss = st.session_state
        if not ss.sf_recommendations:
            return

        st.markdown("---")
        st.markdown("## Size Recommendations")

        rec = ss.sf_recommendations

        visual_best = rec.get("visual_best")
        measurement_best = rec.get(
            "measurement_best"
        )
        visual_reason = rec.get(
            "visual_reason", ""
        )

        if visual_best and measurement_best:
            if visual_best != measurement_best:
                best_size = measurement_best
            else:
                best_size = measurement_best
        else:
            best_size = (
                measurement_best
                if measurement_best
                else visual_best
            )

        if best_size:
            self._render_main_recommendation(
                best_size,
                visual_best,
                measurement_best,
                visual_reason,
            )

        has_alternatives = (
            rec.get("alt_smaller")
            or rec.get("alt_larger")
        )
        if has_alternatives:
            self._render_alternatives(rec)

        if ss.sf_tryon_results:
            self._render_tryon_images(
                rec, dress1_img, dress2_img
            )

        # Final summary
        st.markdown("---")
        st.markdown("### Final Summary")

        if visual_best and measurement_best:
            if visual_best == measurement_best:
                st.success(
                    "**Perfect Match!**\n\n"
                    "Both visual and measurement "
                    "analysis agree that "
                    f"**Size {visual_best}** is "
                    "your ideal fit.\n\n"
                    "This size will give you:\n"
                    "- Proper length and "
                    "coverage\n"
                    "- Comfortable fit through "
                    "bust, waist, and hips\n"
                    "- Natural drape as intended "
                    "by the designer"
                )
            else:
                st.info(
                    "**Two Options to "
                    "Consider:**\n\n"
                    "**Measurement-based:** Size "
                    f"{measurement_best} matches "
                    "your body measurements\n\n"
                    "**Visual analysis:** Size "
                    f"{visual_best} looks best "
                    "in the virtual try-on\n\n"
                    "We recommend trying "
                    f"**Size {measurement_best}**"
                    " first, as body measurements "
                    "provide the most reliable "
                    "fit prediction."
                )

        # Disclaimer
        st.markdown("---")
        # pylint: disable=line-too-long
        st.markdown("""
        <div style="background-color: #FFF3CD; padding: 15px; border-radius: 5px; border: 1px solid #FFC107;">
            <p style="margin: 0; font-size: 12px; color: #856404;">
                <b>Disclaimer:</b> This virtual try-on system uses AI-generated imagery and analysis.
                While we strive for accuracy, there may be variations from actual fit due to:
            </p>
            <ul style="margin: 5px 0; padding-left: 20px; font-size: 12px; color: #856404;">
                <li>Individual body proportions, posture, and personal fit preferences</li>
                <li>Fabric characteristics (stretch, drape, weight, texture)</li>
                <li>Manufacturing tolerances and sizing variations between batches</li>
                <li>Differences between virtual representation and physical garments</li>
            </ul>
            <p style="margin: 0; font-size: 12px; color: #856404;">
                <b>Please use these recommendations as a reference guide only.</b>
            </p>
        </div>
        """, unsafe_allow_html=True)
        # pylint: enable=line-too-long

    def _render_main_recommendation(
        self,
        best_size,
        visual_best,
        measurement_best,
        visual_reason,
    ):
        """Render main recommendation."""
        analysis_summary = ""
        if visual_best and measurement_best:
            if visual_best == measurement_best:
                # pylint: disable=line-too-long
                analysis_summary = (
                    "<p style='color: #1976D2; font-size: 15px; margin: 10px 0;'>"
                    f"<b>Visual Analysis:</b> Size {visual_best}<br>"
                    f"<b>Measurement Analysis:</b> Size {measurement_best}<br>"
                    "<b>Perfect Agreement!</b> Both methods recommend the same size.</p>"
                )
                # pylint: enable=line-too-long
            else:
                # pylint: disable=line-too-long
                analysis_summary = (
                    "<p style='color: #1976D2; font-size: 15px; margin: 10px 0;'>"
                    f"<b>Visual Analysis:</b> Size {visual_best}<br>"
                    f"<b>Measurement Analysis:</b> Size {measurement_best}<br>"
                    f"<b>Final Recommendation:</b> Size {best_size} (based on body measurements)</p>"
                )
                # pylint: enable=line-too-long

        if visual_best == measurement_best:
            final_reason = (
                visual_reason
                if visual_reason
                else "Both visual and measurement "
                "analysis agree on this size."
            )
        else:
            final_reason = (
                "Based on your body measurements"
                f", Size {measurement_best} "
                "provides the optimal fit. "
                "While visual analysis suggests "
                f"Size {visual_best}, "
                "measurements are typically more "
                "reliable for determining "
                "actual fit."
            )

        # pylint: disable=line-too-long
        st.markdown(
            f"""
            <div style="background-color: #E3F2FD; padding: 25px; border-radius: 10px; border: 2px solid #4285F4; margin-bottom: 20px;">
                <h2 style="color: #1565C0; margin-top: 0; text-align: center;">RECOMMENDED SIZE: {best_size}</h2>
                <hr style="border: 1px solid #4285F4; margin: 15px 0;">
                {analysis_summary}
                <hr style="border: 1px solid #90CAF9; margin: 15px 0;">
                <h4 style="color: #1565C0;">Why Size {best_size} is Best:</h4>
                <p style="color: #333; font-size: 16px; margin-bottom: 0;">{final_reason}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        # pylint: enable=line-too-long

    def _render_alternatives(self, rec):
        """Render alternative sizing options."""
        st.markdown(
            "### Alternative Sizing Options"
        )

        has_smaller = rec.get("alt_smaller")
        has_larger = rec.get("alt_larger")

        if has_smaller and has_larger:
            col1, col2 = st.columns(2)
            with col1:
                self._render_tighter_option(rec)
            with col2:
                self._render_looser_option(rec)
        elif has_smaller:
            _c1, c2, _c3 = st.columns([1, 2, 1])  # pylint: disable=unused-variable
            with c2:
                self._render_tighter_option(rec)
        elif has_larger:
            _c1, c2, _c3 = st.columns([1, 2, 1])  # pylint: disable=unused-variable
            with c2:
                self._render_looser_option(rec)

    def _render_tighter_option(self, rec):
        """Render tighter fit option."""
        reason = rec.get(
            "alt_smaller_reason",
            "Choose this size if you prefer "
            "a more fitted, body-hugging "
            "silhouette",
        )
        sz = rec["alt_smaller"]
        # pylint: disable=line-too-long
        st.markdown(
            f"""
            <div style="background-color: #FFF3E0; padding: 20px; border-radius: 10px; border: 2px solid #FF9800;">
                <h4 style="color: #E65100; margin-top: 0;">For a TIGHTER Fit</h4>
                <h3 style="color: #E65100; margin: 10px 0;">Try Size {sz}</h3>
                <p style="color: #333; margin-bottom: 0;">{reason}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        # pylint: enable=line-too-long

    def _render_looser_option(self, rec):
        """Render looser fit option."""
        reason = rec.get(
            "alt_larger_reason",
            "Choose this size if you prefer "
            "a more relaxed, comfortable fit "
            "with extra room",
        )
        sz = rec["alt_larger"]
        # pylint: disable=line-too-long
        st.markdown(
            f"""
            <div style="background-color: #E8F5E9; padding: 20px; border-radius: 10px; border: 2px solid #4CAF50;">
                <h4 style="color: #2E7D32; margin-top: 0;">For a LOOSER Fit</h4>
                <h3 style="color: #2E7D32; margin: 10px 0;">Try Size {sz}</h3>
                <p style="color: #333; margin-bottom: 0;">{reason}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        # pylint: enable=line-too-long

    def _render_tryon_images(
        self, rec, dress1_img, dress2_img
    ):
        """Render try-on result images."""
        ss = st.session_state

        # Show original model + product image
        st.markdown("### Input Images")
        ref_col1, ref_col2 = st.columns(2)

        with ref_col1:
            st.markdown("**Your Model**")
            person_bytes = (
                self._get_person_bytes()
            )
            if person_bytes:
                self._show_image_html(
                    person_bytes, 500
                )

        with ref_col2:
            st.markdown("**Product**")
            selected = ss.sf_selected_product
            prod_bytes = (
                dress1_img
                if selected == "Dress 1"
                else dress2_img
            )
            self._show_image_html(
                prod_bytes, 500
            )

        st.markdown("---")
        st.markdown(
            "### Virtual Try-On Results"
        )
        st.markdown(
            "*Sizes ordered from smallest to "
            "largest (XS -> XL)*"
        )

        # Sort sizes in order
        size_order = [
            "XS", "S", "M", "L", "XL"
        ]
        sorted_results = {
            size: ss.sf_tryon_results[size]
            for size in size_order
            if size in ss.sf_tryon_results
        }

        cols = st.columns(len(sorted_results))
        for i, (size, img_bytes) in enumerate(
            sorted_results.items()
        ):
            with cols[i]:
                visual_best = rec.get(
                    "visual_best"
                )
                measurement_best = rec.get(
                    "measurement_best"
                )
                best_to_highlight = (
                    measurement_best
                    if measurement_best
                    else visual_best
                )

                self._render_size_card(
                    size,
                    img_bytes,
                    best_to_highlight,
                    visual_best,
                    measurement_best,
                )

    def _get_person_bytes(self):
        """Get person image bytes."""
        ss = st.session_state
        smb = ss.get("sf_selected_model_bytes")
        if smb:
            return smb
        gen = ss.get("sf_generated_model_image")
        if gen:
            return gen
        photo = ss.get(
            "sf_uploaded_person_photo"
        )
        if photo:
            if hasattr(photo, "getvalue"):
                return photo.getvalue()
            if isinstance(photo, bytes):
                return photo
        return None

    def _show_image_html(
        self, img_bytes, max_height
    ):
        """Show image via HTML."""
        img = Image.open(
            io.BytesIO(img_bytes)
        )
        if img.mode == "RGBA":
            bg = Image.new(
                "RGB",
                img.size,
                (255, 255, 255),
            )
            bg.paste(
                img, mask=img.split()[3]
            )
            img = bg
        buf = io.BytesIO()
        img.save(
            buf, format="JPEG", quality=90
        )
        b64 = base64.b64encode(
            buf.getvalue()
        ).decode()
        # pylint: disable=line-too-long
        st.markdown(
            f"<div style=\"text-align:center;\"><img src=\"data:image/jpeg;base64,{b64}\" style=\"max-height:{max_height}px; width:auto; border-radius:8px; border:1px solid #e0e0e0;\" /></div>",
            unsafe_allow_html=True,
        )
        # pylint: enable=line-too-long

    def _render_size_card(
        self,
        size,
        img_bytes,
        best_to_highlight,
        visual_best,
        measurement_best,
    ):
        """Render a single size card."""
        img = Image.open(
            io.BytesIO(img_bytes)
        )
        if img.mode == "RGBA":
            bg = Image.new(
                "RGB",
                img.size,
                (255, 255, 255),
            )
            bg.paste(
                img, mask=img.split()[3]
            )
            img = bg
        buf = io.BytesIO()
        img.save(
            buf, format="JPEG", quality=85
        )
        b64 = base64.b64encode(
            buf.getvalue()
        ).decode()

        # pylint: disable=line-too-long
        if size == best_to_highlight:
            label_text = "BEST FIT"
            if (
                visual_best != measurement_best
                and measurement_best
            ):
                label_text = (
                    "BEST FIT (Measurements)"
                )
            st.markdown(
                f"""
                <div style="text-align:center;">
                    <div style="background-color:#4285F4; color:white; padding:6px; border-radius:8px 8px 0 0; font-weight:bold; font-size:13px;">
                        Size {size} {label_text}
                    </div>
                    <div style="border:3px solid #4285F4; border-top:none; border-radius:0 0 8px 8px; padding:6px; box-shadow:0 0 8px rgba(66,133,244,0.3);">
                        <img src="data:image/jpeg;base64,{b64}" style="width:100%; max-height:550px; object-fit:contain; display:block;" />
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div style="text-align:center;">
                    <div style="background-color:#f0f0f0; padding:6px; border-radius:8px 8px 0 0; font-weight:bold; font-size:13px;">
                        Size {size}
                    </div>
                    <div style="border:1px solid #ddd; border-top:none; border-radius:0 0 8px 8px; padding:6px;">
                        <img src="data:image/jpeg;base64,{b64}" style="width:100%; max-height:550px; object-fit:contain; display:block;" />
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        # pylint: enable=line-too-long
