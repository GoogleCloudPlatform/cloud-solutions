# Copyright 2025 Google LLC
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
"""Handles the generation of final display ads."""

import datetime
import json
import random
import re
import string
from typing import Any, Dict, List, Optional, cast

from ..adk_common.utils import ad_generation_constants
from ..adk_common.utils.eval_result import EvalResult
from ..adk_common.utils.gemini_utils import generate_and_select_best_image
from ..adk_common.dtos.generated_media import GeneratedMedia
from ..adk_common.utils import utils_agents
from ..adk_common.utils.constants import get_required_env_var
from ..adk_common.utils.utils_logging import Severity, log_message
from google.adk.tools.tool_context import ToolContext
from google.genai import types

IMAGE_DEFAULT_ASPECT_RATIO = get_required_env_var("IMAGE_DEFAULT_ASPECT_RATIO")


async def _load_asset_sheet(
    asset_sheet_uri: str, tool_context: ToolContext
) -> tuple[Optional[types.Part], Optional[str]]:
    """Loads the asset sheet image."""
    try:
        if not asset_sheet_uri:
            return (
                None,
                "Asset sheet URL is empty, please pass a correct URL of the asset sheet to use.",
            )

        generated_media: GeneratedMedia | None = None
        if asset_sheet_uri:
            generated_media = await utils_agents.load_resource(
                source_path=asset_sheet_uri,
                tool_context=tool_context,
            )

        if not generated_media or not generated_media.media_bytes:
            return (
                None,
                "Asset sheet could not be retrieved. The URL sent is invalid or the file is corrupted.",
            )

        asset_sheet_image = types.Part.from_bytes(
            data=generated_media.media_bytes, mime_type=generated_media.mime_type
        )
    except Exception as e:
        log_message(f"Failed to load asset sheet: {e}", Severity.ERROR)
        return None, f"Failed to load asset sheet: {e}"

    return asset_sheet_image, None


async def _create_display_ad_task(
    prompt_description: str,
    asset_sheet_image: types.Part,
    reference_images_uris: List[str],
    product_image_uri: str,
    logo_image_uri: str,
    tool_context: ToolContext,
    concept_keywords: str,
) -> Dict[str, Any]:
    """Creates a task for generating a single display ad.

    Args:
        prompt_description (str): The visual description/concept for the ad.
        asset_sheet_image (types.Part): The asset sheet image part.
        reference_images_uris (List[str]): URIs of reference images.
        product_image_uri (str): URI of the product image.
        logo_image_uri (str): URI of the logo image.
        tool_context (ToolContext): The tool context for saving artifacts.
        concept_keywords (str): Short descriptive keywords for the filename.

    Returns:
        Dict[str, Any]: A dictionary containing the result of the image generation.
    """
    log_message(
        f"Generating display ad for prompt: {prompt_description}", Severity.INFO
    )

    # Sanitize Concept Keywords
    # Allow alphanumeric and replace spaces/others with underscores
    sanitized_keywords = re.sub(r"[^a-zA-Z0-9]", "_", concept_keywords).strip("_")
    if not sanitized_keywords:
        sanitized_keywords = "generic"

    # Collapse multiple underscores
    sanitized_keywords = re.sub(r"_+", "_", sanitized_keywords)

    # 1. Microsecond Timestamp
    now = datetime.datetime.now()
    timestamp_str = now.strftime("%Y%m%d_%H%M%S_%f")

    # 2. Random 3 Characters
    random_chars = "".join(random.choices(string.ascii_lowercase + string.digits, k=3))

    # Construct Filename
    filename_prefix = f"display_ad_{sanitized_keywords}_{timestamp_str}_{random_chars}"
    # Remove trailing dot if extension was empty in helper, or just use helper for full name if we could,
    # but here we need `filename_without_extension` for `generate_and_select_best_image`.
    # Let's check `generate_and_select_best_image` signature.
    # It takes `filename_without_extension`.
    # So we should probably just use the helper to generate the ID part or modify helper.
    # actually, the helper adds extension.
    # Let's just generate the ID part manually here or adapt.
    # Re-reading user request: "Mimic the logic... User timestamp_str..."
    # If I use `generate_unique_filename` with empty extension, it returns `prefix_timestamp_random`.
    # That works for `filename_prefix`.

    reference_image_parts = []

    # Always include asset sheet as context
    reference_image_parts.append(asset_sheet_image)
    image_descriptions = [
        "ASSET SHEET: Follow the visual style and character look defined here."
    ]

    # Load Product Image
    if product_image_uri:
        try:
            product_media = await utils_agents.load_resource(
                source_path=product_image_uri, tool_context=tool_context
            )
            if product_media and product_media.media_bytes:
                part = types.Part.from_bytes(
                    data=product_media.media_bytes, mime_type=product_media.mime_type
                )
                reference_image_parts.append(part)
                image_descriptions.append(
                    f"PRODUCT IMAGE: This is the exact product ({product_media.filename}). It MUST be the central focus."
                )
        except Exception as e:
            log_message(
                f"Failed to load product image from {product_image_uri}: {e}",
                Severity.WARNING,
            )

    # Load Logo Image
    if logo_image_uri:
        try:
            logo_media = await utils_agents.load_resource(
                source_path=logo_image_uri, tool_context=tool_context
            )
            if logo_media and logo_media.media_bytes:
                part = types.Part.from_bytes(
                    data=logo_media.media_bytes, mime_type=logo_media.mime_type
                )
                reference_image_parts.append(part)
                image_descriptions.append(
                    f"BRAND LOGO: This is the official logo ({logo_media.filename}). It MUST be clearly visible and undistorted."
                )
        except Exception as e:
            log_message(
                f"Failed to load logo image from {logo_image_uri}: {e}",
                Severity.WARNING,
            )

    # Load other reference images (products, logos, etc.)
    if reference_images_uris:
        for uri in reference_images_uris:
            generated_media: GeneratedMedia | None = await utils_agents.load_resource(
                source_path=uri, tool_context=tool_context
            )

            if generated_media and generated_media.media_bytes:
                part = types.Part.from_bytes(
                    data=generated_media.media_bytes,
                    mime_type=generated_media.mime_type,
                )
                reference_image_parts.append((part))
                image_descriptions.append(f"REFERENCE: {generated_media.filename}")

    # Construct the specialized Display Ad Prompt
    final_prompt = f"CONCEPT: \n\n ```text"
    final_prompt += f"\n\n{prompt_description}"
    final_prompt += "\n\n```\n\n"

    final_prompt += "\n\n**ROLE**: You are an expert Digital Ad Designer. Create a high-converting Display Ad."

    final_prompt += f"\n\n**FORMAT**: Aspect Ratio {IMAGE_DEFAULT_ASPECT_RATIO}."

    final_prompt += "\n\n**COPY REQUIREMENTS**:"
    final_prompt += "\n* Start with a SHORT, PUNCHY headline or copy directly embedded in the image."
    final_prompt += "\n* Maximum 5-7 words. Keep text legible, bold, and high-contrast."
    final_prompt += "\n* Text must be perfectly spelled."

    final_prompt += "\n\n**BRANDING**:"
    final_prompt += "\n* The company LOGO must be clearly visible, undistorted, and placed in a standard ad position (e.g., corner or visual center)."
    final_prompt += (
        "\n* Use the reference images to match the exact Product and Logo look."
    )

    final_prompt += "\n\n**AESTHETIC**:"
    final_prompt += "\n* Ultra-premium luxury commercial photography — Porsche campaign deck meets Hasselblad editorial."
    final_prompt += "\n* Lighting must be cinematic studio-quality with volumetric depth and ray-traced reflections."
    final_prompt += "\n* This is a FINAL ASSET, not a sketch or storyboard."
    final_prompt += "\n\n**LUXURY INNOVATION**:"
    final_prompt += "\n* The ad must feel futuristic, technologically sophisticated, and aspirational"
    final_prompt += "\n* Think precision engineering, premium materials (carbon fiber, brushed titanium, glass), volumetric lighting"
    final_prompt += "\n* Art direction: Porsche campaign deck meets Apple product launch meets Hasselblad editorial"
    final_prompt += "\n* This is a Cannes Lions Grand Prix contender — every pixel must justify its existence"

    final_prompt += "\n\nAttached references include the Asset Sheet (style guide) and specific product/logo shots; adhere to them strictly."

    if image_descriptions:
        final_prompt += "\n\n**IMAGE CONTEXT**:"
        for desc in image_descriptions:
            final_prompt += f"\n* {desc}"

    return await generate_and_select_best_image(
        filename_without_extension=filename_prefix,
        input_images=reference_image_parts,
        prompt=final_prompt,
    )


async def generate_display_ad(
    prompt: str,
    asset_sheet_uri: str,
    tool_context: ToolContext,
    reference_images: List[str] = [],
    concept_keywords: str = "ad",
) -> Dict[str, Any]:
    f"""Generates a final, high-quality Display Ad (image) with short copy and branding.
    
    Use this tool ONLY when the user specifically requests to "Change", "Modify", or "Alter" a specific Display Ad.
    Do NOT use this for "New" or "Another" requests (use the standard asset retrieval for those).

    Args:
        prompt (str): A detailed description of the ad concept, mood, and any specific copy text requested.
        asset_sheet_uri (str): The GCS URL of the asset sheet image (required for consistency).
        tool_context (ToolContext): The context for artifact management.
        reference_images (List[str], optional): List of URIs. MUST include the URI of the ad being modified if applicable. Defaults to [].
        concept_keywords (str, optional): Short descriptive keywords (1-3 words) to identify the ad concept in the filename. Defaults to "ad".

    Returns:
        Dict[str, Any]: A dictionary containing the status and details of the generated ad.
    """
    try:
        # Load asset sheet (Critical for style/context)
        asset_sheet_image, error_msg = await _load_asset_sheet(
            asset_sheet_uri, tool_context
        )
        if not asset_sheet_image or error_msg:
            log_message(
                f"[generate_display_ad] Error loading asset sheet. Error: {error_msg}.",
                Severity.ERROR,
            )
            return {"status": "failed", "detail": error_msg}

        utils_agents.agentspace_print(tool_context, "Generating Display Ad...")

        # Use dynamic URIs from session state if available, otherwise fall back to env vars
        final_product_uri = tool_context.state.get(
            "PRODUCT_IMAGE_URI"
        ) or get_required_env_var("BACKUP_CATALOG_IMAGE_URL")
        final_logo_uri = tool_context.state.get(
            "LOGO_IMAGE_URI"
        ) or get_required_env_var("BACKUP_LOGO_IMAGE_URL")

        log_message(f"Using Product URI: {final_product_uri}", Severity.INFO)
        log_message(f"Using Logo URI: {final_logo_uri}", Severity.INFO)

        result: Dict[str, Any] = await _create_display_ad_task(
            prompt_description=prompt,
            asset_sheet_image=asset_sheet_image,
            reference_images_uris=reference_images,
            product_image_uri=final_product_uri,
            logo_image_uri=final_logo_uri,
            tool_context=tool_context,
            concept_keywords=concept_keywords,
        )

        if result and result.get("status") == "success" and result.get("image_bytes"):
            generated_media = GeneratedMedia(
                filename=result["file_name"],
                mime_type=ad_generation_constants.IMAGE_MIMETYPE,
                media_bytes=result["image_bytes"],
            )

            generated_media = await utils_agents.save_to_artifact_and_render_asset(
                asset=generated_media,
                context=tool_context,
                save_in_gcs=True,
                save_in_artifacts=True,
                gcs_folder=utils_agents.get_or_create_unique_session_id(tool_context),
            )

            # We reuse the existing EvalResult structure, which is now Unified.
            best_eval = result.get("best_eval")
            best_attempt_evaluation = cast(EvalResult, best_eval) if best_eval else None

            # Log success
            log_message(
                f"[generate_display_ad] Success. New image URI: {generated_media.gcs_uri}",
                Severity.INFO,
            )

            return {
                "status": "success",
                "detail": "Display Ad generated successfully.",
                "generated_image_uri": generated_media.gcs_uri,
                "evaluation": (
                    best_attempt_evaluation.model_dump()
                    if best_attempt_evaluation
                    else None
                ),
            }

        else:
            result_string = json.dumps(result) if result else "None"
            log_message(
                f"[generate_display_ad] Failed to save image. Result: {result_string}",
                Severity.ERROR,
            )
            return {"status": "failed", "detail": "Display Ad generation failed."}

    except Exception as e:
        log_message(f"Error in generate_display_ad: {e}", Severity.ERROR)
        raise e
