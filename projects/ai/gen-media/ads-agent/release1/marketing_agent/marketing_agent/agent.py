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
# pylint: disable=C0301, C0413, C0415, E0606, W0102, W0104, W0404, W0611, W0612, W0613, W0718, W1203, W1309, W1405, W1510, W1514
"""Personalized Marketing Agent — End-to-end campaign generation with image ads and video ads."""

import asyncio
import json
import os
import random
import time
from typing import Any

from adk_common.dtos.generated_media import GeneratedMedia
from adk_common.utils import utils_agents, utils_gcs, utils_prompts
from adk_common.utils.constants import (
    get_optional_env_var,
    get_required_env_var,
)
from adk_common.utils.env_loader import load_env_cascade
from adk_common.utils.utils_agents import to_dict_recursive
from adk_common.utils.utils_logging import Severity, log_message
from google import genai
from google.genai import types

load_env_cascade(__file__)

from google.adk.agents import Agent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.skills import load_skill_from_dir
from google.adk.tools import AgentTool
from google.adk.tools.skill_toolset import SkillToolset
from google.adk.tools.tool_context import ToolContext

from .campaign_utils import (
    Asset,
    Campaign,
    Segment,
    find_campaign_by_name,
    parse_campaigns_from_xml,
)
from .data.products import get_product_by_sku_from_bq, retrieve_products
from .generate_campaigns import generate_campaigns_xml
from .generate_display_ad import generate_display_ad
from .schema import Brand, Product
from .sub_agents.trend_spotter import TrendSpotter
from .tools.inventory import InventoryTool
from .tools.sales import SalesTool

# ============================================================
# Environment Configuration
# ============================================================
GOOGLE_CLOUD_PROJECT = get_required_env_var("GOOGLE_CLOUD_PROJECT")
GOOGLE_CLOUD_LOCATION = get_required_env_var("GOOGLE_CLOUD_LOCATION")
GOOGLE_CLOUD_BUCKET_ARTIFACTS = get_required_env_var("GOOGLE_CLOUD_BUCKET_ARTIFACTS")
GEMINI_IMAGE_MODEL = get_required_env_var("IMAGE_GENERATION_MODEL")
GEMINI_TTS_MODEL = get_required_env_var("AUDIO_TTS_GENERATION_MODEL")
GEMINI_TTS_VOICE = get_required_env_var("AUDIO_TTS_VOICE_NAME")
VEO_MODEL = get_required_env_var("VIDEO_GENERATION_MODEL")
VEO_CLIP_DURATION = int(get_optional_env_var("VIDEO_DEFAULT_DURATION", "4"))
LLM_GEMINI_MODEL_MARKETING_ANALYST = get_required_env_var("LLM_GEMINI_MODEL_MARKETING_ANALYST")
AGENT_VERSION = get_required_env_var("AGENT_VERSION")
DEMO_COMPANY_NAME = get_optional_env_var("DEMO_COMPANY_NAME", "LayoGenMedia")
MARKETING_ANALYST_DATASTORE_CLOUD_BUCKET = get_required_env_var("MARKETING_ANALYST_DATASTORE_CLOUD_BUCKET")
CAMPAIGNS_CONFIG_URL = get_required_env_var("CAMPAIGNS_CONFIG_URL")
OUTPUT_FOLDER = "generated"


def _set_output_folder(tool_context):
    """Sets global OUTPUT_FOLDER to {product_name}_{persona}/."""
    global OUTPUT_FOLDER
    product_name = tool_context.state.get("PRODUCT_NAME", "")
    persona_desc = tool_context.state.get("CUSTOMER_PERSONA", "")
    if product_name:
        safe_name = product_name.replace(" ", "_").replace("/", "_")[:40]
        if persona_desc:
            persona_map = {
                "family": "Family_with_Kids",
                "vacation": "Travel_Enthusiast",
                "travel": "Travel_Enthusiast",
                "young": "Young_Professional",
                "professional": "Young_Professional",
                "fitness": "Fitness_Wellness",
                "wellness": "Fitness_Wellness",
                "luxury": "Luxury_Premium",
                "premium": "Luxury_Premium",
            }
            matched = None
            for keyword, folder_name in persona_map.items():
                if keyword in persona_desc.lower():
                    matched = folder_name
                    break
            if matched:
                OUTPUT_FOLDER = f"{safe_name}_{matched}"
            else:
                safe_persona = persona_desc.split(".")[0].replace(" ", "_").replace(",", "")[:30]
                OUTPUT_FOLDER = f"{safe_name}_{safe_persona}"
        else:
            OUTPUT_FOLDER = safe_name
    log_message(f"Output folder: {OUTPUT_FOLDER}", Severity.INFO)

SELECTED_CAMPAIGN_FILE_NAME = f"{get_required_env_var('SELECTED_CAMPAIGN_FILE_NAME')}.{AGENT_VERSION}.txt"
SELECTED_ASSET_SHEET_FILE_NAME = f"{get_required_env_var('SELECTED_ASSET_SHEET_FILE_NAME')}.{AGENT_VERSION}.txt"
SESSION_STATE_FILE_NAME = f"{get_required_env_var('SESSION_STATE_FILE_NAME')}.{AGENT_VERSION}.json"

# State keys
CHOSEN_CAMPAIGN_IDEA_STATE_KEY = "CHOSEN_CAMPAIGN_IDEA"
CHOSEN_ASSET_SHEET_ID_STATE_KEY = "CHOSEN_ASSET_SHEET_ID"
PRODUCT_COMPANY_NAME_STATE_KEY = "PRODUCT_COMPANY_NAME"
PRODUCT_IMAGE_URI_STATE_KEY = "PRODUCT_IMAGE_URI"
LOGO_IMAGE_URI_STATE_KEY = "LOGO_IMAGE_URI"
PRODUCT_SETUP_DONE_STATE_KEY = "PRODUCT_SETUP_DONE"
GENERATED_GCS_URIS_STATE_KEY = "GENERATED_GCS_URIS"
SELECTED_ASSET_SHEETS_STATE_KEY = "SELECTED_ASSET_SHEETS"
SELECTED_CAMPAIGN_IDEAS_STATE_KEY = "SELECTED_CAMPAIGN_IDEAS"
SELECTED_IMAGES_STATE_KEY = "SELECTED_IMAGES"
SELECTED_VIDEOS_STATE_KEY = "SELECTED_VIDEOS"
REFERENCE_GUIDELINES_STATE_KEY = "REFERENCE_GUIDELINES"
CUSTOMER_PERSONA_STATE_KEY = "CUSTOMER_PERSONA"

CUSTOMER_PERSONAS = {
    1: {
        "name": "Family with Kids",
        "description": (
            "Parents and families. They value safety, durability, fun, and quality family time. "
            "Show the product in warm family homes, cozy living rooms, backyards, and family spaces. "
            "Focus on the PRODUCT in the family environment — NOT on people's faces. "
            "Show hands interacting with the product, rooms where families live, toys and family items in the background. "
            "Warm, nurturing, joyful tone."
        ),
    },
    2: {
        "name": "Vacation/Travel Enthusiast",
        "description": (
            "Adventure seekers and travel lovers. They value experiences, exploration, and freedom. "
            "Show the product in exotic destinations, travel scenarios, outdoor adventures. "
            "Exciting, aspirational, wanderlust tone."
        ),
    },
    3: {
        "name": "Young Professional",
        "description": (
            "Career-focused urbanites aged 25-35. Tech-savvy, style-conscious, busy lifestyle. "
            "Show the product in modern urban settings — offices, coffee shops, city apartments, commutes. "
            "Sleek, confident, contemporary tone."
        ),
    },
    4: {
        "name": "Fitness/Wellness Seeker",
        "description": (
            "Health-conscious, active lifestyle consumers. They value performance, self-improvement, and wellness. "
            "Show the product in gym, yoga studio, running trail, home workout, or healthy kitchen settings. "
            "Energetic, motivational, empowering tone."
        ),
    },
    5: {
        "name": "Luxury/Premium Lifestyle",
        "description": (
            "Affluent consumers seeking exclusivity and sophistication. They value craftsmanship, premium materials, and status. "
            "Show the product in upscale environments — luxury homes, fine dining, premium events. "
            "Elegant, refined, aspirational tone."
        ),
    },
}

# Global cache
_CACHED_CAMPAIGNS_LIST: list[Campaign] | None = None
_CACHED_IDEAS_STRING: str | None = None

# ============================================================
# Initialize sub-agents and tools (from Andrew)
# ============================================================
inventory_tool = InventoryTool()
sales_tool = SalesTool()
trend_spotter_agent = TrendSpotter()


# ============================================================
# Retail Pipeline Tools (from Andrew)
# ============================================================

def identify_inventory_opportunities(tool_context: ToolContext) -> list[dict]:
    """Identifies high-stock, low-velocity inventory items by cross-referencing inventory and sales data.
    Returns a list of product opportunities sorted by priority: low velocity first, then by highest stock.
    """
    high_stock_products = inventory_tool.find_high_stock()
    low_velocity_products = sales_tool.find_low_velocity()

    # Build set of low-velocity SKUs for quick lookup
    low_velocity_skus = set()
    for p in low_velocity_products:
        if hasattr(p, 'core_identifiers') and p.core_identifiers:
            low_velocity_skus.add(p.core_identifiers.sku)

    # Sort: low velocity first, then by stock quantity descending
    velocity_order = {"low": 0, "average": 1, "high": 2}
    high_stock_products.sort(
        key=lambda p: (
            velocity_order.get(
                p.commercial_status.sales_velocity if p.commercial_status else "average",
                1
            ),
            -(p.commercial_status.stock_quantity if p.commercial_status else 0),
        )
    )

    opportunities_as_dict = []
    for product in high_stock_products:
        opportunities_as_dict.append(to_dict_recursive(product))
    tool_context.state["opportunities"] = opportunities_as_dict
    return opportunities_as_dict



async def display_product_image(
    tool_context: ToolContext,
    image_url: str,
    product_name: str = "product",
):
    """Displays a product image inline.

    Call this in Path B when the user provides their product
    image URL.

    Args:
        image_url: The GCS URI or HTTPS URL of the product image.
        product_name: Name of the product (used for the filename).
    """
    try:
        img_bytes, _ = (
            utils_agents.download_bytes_from_reference(image_url)
        )
        if img_bytes:
            safe_name = product_name.replace(" ", "_")[:30]
            product_media = GeneratedMedia(
                filename=f"product_{safe_name}.png",
                mime_type="image/png",
                media_bytes=img_bytes,
            )
            await utils_agents.save_to_artifact_and_render_asset(
                asset=product_media,
                context=tool_context,
                save_in_gcs=False,
                save_in_artifacts=True,
            )
            tool_context.state["_product_image_displayed"] = True
            return {
                "status": "success",
                "details": (
                    f"Product image displayed for {product_name}"
                ),
            }
    except Exception as e:
        return {"status": "error", "details": str(e)}
    return {
        "status": "error",
        "details": "Could not download image",
    }


async def get_product_by_sku(tool_context: ToolContext, sku: str) -> dict:
    """Retrieves a product and its associated brand information by SKU.
    Also displays the product image inline immediately.

    Args:
        sku: The SKU of the product to retrieve.
    """
    product = get_product_by_sku_from_bq(sku)
    if not product:
        return {}, {}

    tool_context.state['product'] = to_dict_recursive(product)
    brand_name = product.core_identifiers.brand
    brand_info = next(
        (brand for brand in tool_context.state.get("brand_data", [])
         if brand.get("name") == brand_name), None
    )
    if brand_info:
        tool_context.state['brand_info'] = brand_info

    product_image_uri = product.media.main_image_url if product.media else ""
    if product_image_uri:
        try:
            img_bytes, _ = utils_agents.download_bytes_from_reference(product_image_uri)
            if img_bytes:
                product_media = GeneratedMedia(
                    filename=f"product_{sku}.png", mime_type="image/png", media_bytes=img_bytes,
                )
                await utils_agents.save_to_artifact_and_render_asset(
                    asset=product_media, context=tool_context,
                    save_in_gcs=False, save_in_artifacts=True,
                )
                tool_context.state["_product_image_displayed"] = True
        except Exception:
            pass

    return to_dict_recursive(product), brand_info or {}


async def setup_campaign_from_sku(tool_context: ToolContext, sku: str, num_segments: int = 2, reference_guidelines: str = ""):
    """Sets up a full marketing campaign from a product SKU.
    Automatically extracts brand, product name, description, image, and target audience
    from the product database — no manual input needed.

    Args:
        sku: The SKU of the product to create a campaign for (e.g. 'ELEC-001', '292929').
        num_segments: Number of audience segments per campaign (1-4, default 2).
        reference_guidelines: Extracted text content from user-provided reference documents
            (product docs, marketing briefs, brand guidelines). Will be used throughout
            campaign creation to ensure alignment with brand voice, messaging, and visual direction.
    """
    # Try to find product from session state first (already loaded by inventory call)
    product = None
    opportunities = tool_context.state.get("opportunities", [])
    for opp in opportunities:
        if isinstance(opp, dict) and opp.get("core_identifiers", {}).get("sku") == sku:
            # Reconstruct Product from dict
            product = Product(**opp)
            break

    # Fallback to BQ if not in state
    if not product:
        product = get_product_by_sku_from_bq(sku)

    if not product:
        return {"status": "error", "details": f"Product with SKU '{sku}' not found."}

    company_name = product.core_identifiers.brand or DEMO_COMPANY_NAME
    product_name = product.core_identifiers.product_name
    product_description = (
        product.description.long if product.description and product.description.long
        else product.description.short if product.description and product.description.short
        else product_name
    )

    # Auto-generate target audience from product category and price
    dept = product.categorization.department if product.categorization else ""
    cat = product.categorization.category if product.categorization else ""
    price = product.commercial_status.current_price if product.commercial_status else 0
    price_tier = "premium" if price > 200 else "mid-range" if price > 50 else "value"
    target_audience = f"{dept} {cat} consumers interested in {price_tier} {product_name.lower()} products, ages 25-50"

    product_image_uri = product.media.main_image_url if product.media else ""
    logo_uri = get_optional_env_var("BACKUP_LOGO_IMAGE_URL", "")

    # Store product in state for sub-agents
    tool_context.state['product'] = to_dict_recursive(product)

    num_segments = max(1, min(num_segments, 4))  # clamp 1-4

    result = await setup_product_campaign(
        tool_context=tool_context,
        company_name=company_name,
        product_name=product_name,
        product_description=product_description,
        target_audience=target_audience,
        logo_uri=logo_uri,
        product_image_uri=product_image_uri,
        num_segments=num_segments,
        reference_guidelines=reference_guidelines,
    )

    # Enrich result with product details for display
    if isinstance(result, dict) and result.get("status") == "success":
        result["product_summary"] = {
            "brand": company_name,
            "product_name": product_name,
            "description": product.description.short if product.description else "",
            "category": f"{dept} / {cat}",
            "price": f"${price:.2f}",
            "target_audience": target_audience,
            "product_image_url": product_image_uri,
            "logo_url": logo_uri,
        }

    return result


# ============================================================
# On-Demand Image Generation (ported from fast_video_marketing_demo)
# ============================================================

_VARIATION_STYLES = [
    "PREMIUM STUDIO — Clean white/grey studio with precise product lighting, geometric shadows, ultra-minimal Apple-style composition. The product floats in perfect light.",
    "LIFESTYLE IN ACTION — The product being used in its natural environment by a real person. Warm, candid, aspirational. Think 'a day in the life' with the product as the hero.",
    "URBAN NIGHT — Dramatic cityscape at night with neon reflections, rain-slicked streets, moody teal-and-orange color grade. The product glows against the dark city.",
    "GOLDEN HOUR EPIC — Sweeping outdoor landscape at golden hour with warm amber backlighting, lens flares, and dramatic long shadows. Cinematic wide-angle grandeur.",
    "TECH NOIR — Dark, sophisticated, high-contrast. Brushed metal surfaces, precision engineering close-ups, holographic UI elements. The product as cutting-edge technology.",
    "COZY HOME — Warm, inviting home environment. Soft textures, natural wood, ambient lighting. The product fits seamlessly into a beautiful living space.",
    "AERIAL ADVENTURE — Bird's-eye or drone perspective showing the product in a vast, breathtaking outdoor environment. Scale and drama.",
    "INDUSTRIAL LUXE — Raw concrete, exposed steel, and architectural brutalism contrasted with the product's refined design. Moody volumetric lighting.",
    "NATURE MACRO — Extreme close-up details of the product surrounded by organic textures (water droplets, leaves, sand). Hyper-detailed macro photography.",
    "NEON FUTURISM — Cyberpunk-inspired with holographic accents, electric blue and magenta lighting, reflective surfaces. The product from 2035.",
    "CULINARY ARTISTRY — Rich textures, steam, condensation, warm tones. Food/beverage products presented like Michelin-star plating. For non-food: the product in an upscale dining context.",
    "SPORT PERFORMANCE — Dynamic motion blur, sweat, intensity. The product captured mid-action. Speed ramps, dramatic angles, peak performance moment.",
]

async def _retry_generate_content(client, model, contents, config, label="LLM", max_attempts=4):
    """Shared retry wrapper for all Gemini generate_content calls with 429 backoff."""
    for attempt in range(max_attempts):
        try:
            kwargs = {"model": model, "contents": contents}
            if config is not None:
                kwargs["config"] = config
            response = client.models.generate_content(**kwargs)
            return response
        except Exception as e:
            is_429 = "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)
            if is_429 and attempt < max_attempts - 1:
                backoff = (2 ** attempt) * 3 + random.uniform(0, 2)
                log_message(f"{label}: 429 retry {attempt+1}/{max_attempts}, backoff {backoff:.1f}s", Severity.WARNING)
                await asyncio.sleep(backoff)
            elif attempt < max_attempts - 1:
                await asyncio.sleep(2)
                log_message(f"{label}: error retry {attempt+1}/{max_attempts}: {e}", Severity.WARNING)
            else:
                log_message(f"{label}: failed after {max_attempts} attempts: {e}", Severity.ERROR)
                raise


def _find_asset_rationale(asset_url: str) -> str | None:
    if not _CACHED_CAMPAIGNS_LIST:
        return None
    for campaign in _CACHED_CAMPAIGNS_LIST:
        for sheet in campaign.asset_sheets:
            if sheet.uri == asset_url:
                return sheet.rationale
        for segment in campaign.segments:
            for ad in segment.image_ads:
                if ad.uri == asset_url:
                    return ad.rationale
            for vid in segment.video_ads:
                if vid.uri == asset_url:
                    return vid.rationale
    return None


async def _generate_gemini_image(prompt: str, reference_images: list[bytes], label: str = "image") -> bytes | None:
    parts = [types.Part.from_bytes(data=img, mime_type="image/png") for img in reference_images]
    parts.append(types.Part.from_text(text=prompt))

    for attempt in range(5):
        try:
            client = genai.Client(vertexai=True, project=GOOGLE_CLOUD_PROJECT, location="global")
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=GEMINI_IMAGE_MODEL,
                    contents=[types.Content(role="user", parts=parts)],
                    config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
                ),
                timeout=120,
            )
            if response.candidates and response.candidates[0].content:
                for part in response.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.data:
                        log_message(f"{label} generated ({len(part.inline_data.data)} bytes)", Severity.INFO)
                        return part.inline_data.data
            log_message(f"{label}: no image in response (attempt {attempt + 1}/5)", Severity.WARNING)
        except Exception as e:
            error_str = str(e)
            is_429 = "429" in error_str or "RESOURCE_EXHAUSTED" in error_str
            log_message(f"{label} failed (attempt {attempt + 1}/5, 429={is_429}): {e}", Severity.WARNING)
            if is_429 and attempt < 4:
                backoff = (2 ** attempt) * 2 + random.uniform(0, 3)
                log_message(f"{label}: 429 backoff {backoff:.1f}s", Severity.INFO)
                await asyncio.sleep(backoff)
                continue
        if attempt < 4:
            await asyncio.sleep((attempt + 1) * 3 + random.uniform(0, 2))
    return None


async def _generate_image_on_demand(
    asset_url: str, rationale: str, product_image_bytes: bytes,
    company_name: str, product_name: str,
    logo_image_bytes: bytes | None = None, variation_index: int = 0,
    reference_guidelines: str = "",
    customer_persona: str = "",
) -> bytes | None:
    is_asset_sheet = "asset_sheet" in asset_url

    # Build reference guidelines instruction if available
    guidelines_instruction = ""
    if reference_guidelines and reference_guidelines.strip():
        guidelines_instruction = (
            f"\n\nBRAND & REFERENCE GUIDELINES (MUST FOLLOW):\n"
            f"The following guidelines were provided from the brand's reference documents. "
            f"All visual style, tone, messaging, color choices, and creative direction MUST align with these:\n"
            f"{reference_guidelines.strip()}\n"
        )

    scale_instruction = (
        f"\n\nCRITICAL — REAL-WORLD SCALE (ZERO TOLERANCE):\n"
        f"The product '{product_name}' MUST be at its EXACT real-world physical size. "
        f"If a person is in the image, the product must be CORRECTLY proportioned relative to their body:\n"
        f"- A bottle of whisky is ~30cm tall — reaches a person's FOREARM, NOT their chest or head\n"
        f"- A coffee bottle is ~20cm tall — fits in ONE hand\n"
        f"- Earbuds fit in a palm, ~2-3cm each\n"
        f"- A phone/tablet is hand-held, ~15-30cm\n"
        f"- A drone is ~30-50cm wingspan\n"
        f"- A serum bottle is ~12cm tall\n"
        f"- A smart ring fits on a finger, ~2cm\n"
        f"- A pet tracker collar attachment is ~4cm\n"
        f"- Hiking boots are foot-sized, ~30cm\n"
        f"ABSOLUTE RULE: If a person is standing next to the product, the product MUST look like "
        f"it would in a REAL photograph — a whisky bottle next to a person is about knee-to-shin height, "
        f"NOT waist height, NOT chest height, NOT human-sized. "
        f"NEVER enlarge or shrink the product. NEVER make it a centerpiece that dominates the frame unrealistically.\n\n"
        f"ANATOMY — NO PHANTOM BODY PARTS:\n"
        f"- Every hand in the image must be connected to a visible arm and body\n"
        f"- NO disembodied hands, NO extra arms, NO floating fingers\n"
        f"- If a person is cropped, their hands must still be anatomically connected to their visible body\n"
        f"- Count the hands: each person has EXACTLY 2 hands, no more\n"
    )

    if is_asset_sheet:
        prompt = (
            f"Create a premium COMMERCIAL ASSET SHEET / CREATIVE STYLE GUIDE for '{company_name}' — '{product_name}'. "
            f"Visual concept and mood: {rationale}.\n\n"
            f"This should look like a pitch deck from a world-class creative agency — polished, cohesive, stunning.\n\n"
            f"REFERENCE IMAGES — MUST USE (attached below):\n"
            f"- IMAGE 1 (first attached) = the ACTUAL product photo. Copy this EXACTLY in every product shot.\n"
            f"- IMAGE 2 (second attached) = the ACTUAL brand logo. Copy this EXACTLY for brand identity.\n"
            f"- Do NOT invent a different logo. Do NOT imagine a different product. USE THE ATTACHED IMAGES.\n"
            f"- The product in every shot must match the attached photo — same shape, same color, same details.\n"
            f"- The logo must be a pixel-perfect copy of the attached logo — not your interpretation of it.\n\n"
            f"GRID LAYOUT RULES:\n"
            f"- Clean, perfectly aligned grid with consistent gutters and padding\n"
            f"- Every cell MUST fit its content — no overflow, no cropping, no elements bleeding outside their cell\n"
            f"- Section labels must be consistent size, same font, same style — never duplicated\n"
            f"- The overall layout must look NEAT and ORGANIZED — like a Figma or InDesign presentation\n\n"
            f"MANDATORY SECTIONS (each appears EXACTLY ONCE):\n"
            f"1. HEADER: '{company_name.upper()}: {product_name.upper()}' in bold uppercase typography on a premium textured header.\n"
            f"2. BRAND IDENTITY: The SECOND reference image is the logo — place it prominently. Reproduce EXACTLY as provided.\n"
            f"3. COLOR PALETTE: 4-5 color swatches with premium creative names. Swatches must be neat rectangles with "
            f"labels below, all fitting cleanly within their cell.\n"
            f"4. LIFESTYLE SHOTS: 2 photorealistic shots showing the ideal customer using the product. "
            f"Shot 1: intimate close-up interaction. Shot 2: wide environmental context. "
            f"Both must be VISUALLY DISTINCT and show the product being used REALISTICALLY.\n"
            f"5. ENVIRONMENT/MOOD: 2 aspirational environment shots — DIFFERENT locations, DIFFERENT lighting. "
            f"These set the brand atmosphere.\n"
            f"6. PRODUCT HERO: Study the FIRST reference image carefully — reproduce the product with EXACT fidelity. "
            f"Show it UPRIGHT, resting on a solid surface — NEVER tilted, floating, or at an angle. "
            f"The product label, shape, color, and all details must match the reference precisely. "
            f"One dramatic hero shot in an environment, one artistic macro close-up of product details.\n"
            f"7. TYPOGRAPHY: Campaign tagline shown ONCE in one elegant font treatment.\n\n"
            f"PRODUCT FIDELITY — CRITICAL (ZERO TOLERANCE):\n"
            f"- Study the first reference image and reproduce the product EXACTLY in every shot\n"
            f"- Same label design, same shape, same colors, same proportions — pixel-perfect match\n"
            f"- The product must be RECOGNIZABLE as the exact same item in every image\n"
            f"- Product at REAL-WORLD scale — proportional to hands, surfaces, environments\n"
            f"- Do NOT add, invent, or imagine ANY features not visible in the reference image\n"
            f"- Do NOT add shutters, mechanical parts, gears, ports, buttons, or details that are NOT in the reference\n"
            f"- Do NOT show the product opened, disassembled, exploded, or in any state other than how it appears in the reference\n"
            f"- The product is a RETAIL item — show it EXACTLY as a customer would see it in a store\n\n"
            f"QUALITY:\n"
            f"- Ultra-premium presentation — $100M creative agency standard\n"
            f"- Sophisticated dark or textured background, immaculate alignment\n"
            f"- Every image photorealistic, cinematic lighting, luxury color grading\n"
            f"- NO duplicate images — every shot is UNIQUE in angle, lighting, and composition\n"
            f"- 16:9 landscape\n"
            f"IMPORTANT: Do NOT invent product features. Only visualize what's described.\n"
            f"{scale_instruction}"
            f"{guidelines_instruction}"
        )
        if customer_persona and customer_persona.strip():
            prompt += (
                f"\nCUSTOMER PERSONA — MUST DRIVE ALL VISUALS:\n{customer_persona.strip()}\n"
                f"Every lifestyle shot, environment, person, and mood MUST reflect this persona's world.\n"
                f"The people shown must LOOK like this customer type — their age, style, setting, and aspirations.\n"
                f"Environments must be places this customer frequents — their home, their hangout, their lifestyle.\n"
            )
        prompt += (
            f"Return only the image."
        )
    else:
        prompt = (
            f"Create a stunning, ready-to-publish digital marketing display ad for "
            f"{company_name} {product_name}.\n"
            f"Creative direction: {rationale}.\n\n"
            f"RULE 1 — PRODUCT IN CONTEXT: The FIRST reference image is the product. "
            f"Show the product being USED in a real-world scenario — worn, held, poured, placed on a surface. "
            f"The product MUST be at its REAL PHYSICAL SIZE relative to people and environment. "
            f"A bottle of whisky should be on a table next to a glass — NOT as tall as a fireplace. "
            f"Hiking boots should be on someone's feet — NOT floating giant in the scene. "
            f"A drone should be held in hands or flying — NOT the size of a car. "
            f"Reproduce product with EXACT fidelity — same shape, color, proportions, textures, "
            f"design details. The product must be IDENTIFIABLE but at REALISTIC scale. "
            f"Do NOT add, invent, or imagine ANY features not visible in the reference image. "
            f"No extra buttons, ports, shutters, mechanical parts, or internal components. "
            f"Show the product EXACTLY as a customer would see it in a store — sealed, complete, retail-ready.\n\n"
            f"RULE 2 — BRAND LOGO: The SECOND reference image is the logo. Place it prominently. "
            f"Reproduce EXACTLY as provided.\n\n"
            f"RULE 3 — COMPOSITION & PHYSICS: Professional layout with dramatic background or scene. "
            f"Bold headline with brand name, short punchy tagline, clean modern typography. "
            f"Premium color grading, dramatic lighting, depth of field. "
            f"ALL objects MUST obey PHYSICS: gravity applies, liquids flow downward, objects rest on surfaces. "
            f"NOTHING floats, hovers, or is suspended in mid-air unless the product actually flies. "
            f"NO floating ingredients, NO suspended splashes, NO magical hovering elements. "
            f"LIQUIDS: when pouring, liquid flows in ONE clean stream into the glass — NO droplets, "
            f"NO bubbles outside the glass, NO splashes suspended in air, NO mist or spray. "
            f"Liquid lands INSIDE the glass only. This is a real pour, not a special effect. "
            f"Drinks do NOT emit smoke, steam, or vapor from the glass — whisky, wine, beer, cocktails are NOT hot beverages. "
            f"Only hot drinks (coffee, tea) can have steam. NO smoke effects on any drink.\n\n"
            f"RULE 4 — VISUAL STYLE (MANDATORY):\n"
            f"{_VARIATION_STYLES[variation_index % len(_VARIATION_STYLES)]}\n"
            f"This style MUST make the ad look distinctly different from other ads in the same campaign.\n\n"
            f"RULE 5 — NO HALLUCINATION: Do NOT add text claims, features, or specs that aren't in the creative direction. "
            f"Keep text to brand name + tagline only.\n\n"
            f"{scale_instruction}"
            f"{guidelines_instruction}"
        )
        if customer_persona and customer_persona.strip():
            prompt += (
                f"\nCUSTOMER PERSONA (tailor the ad to this audience):\n{customer_persona.strip()}\n"
                f"Show people, environments, and scenarios that resonate with this customer type.\n"
            )
        prompt += (
            "16:9 landscape. Shot on Phase One IQ4 150MP. "
            "Luxury editorial quality — Vogue, Architectural Digest, or Apple-level production value. "
            "Cinematic color grading, masterful lighting, photorealistic rendering. "
            "This ad must look like it cost $50,000 to produce. Return only the image."
        )

    refs = [product_image_bytes]
    if logo_image_bytes:
        refs.append(logo_image_bytes)
    label = "asset sheet" if is_asset_sheet else "display ad"
    return await _generate_gemini_image(prompt, refs, label=label)


_cached_product_bytes: bytes | None = None
_cached_logo_bytes: bytes | None = None


async def _render_asset(asset_url: str, tool_context: ToolContext):
    """Generates an image on-demand, uploads to GCS, saves as artifact, returns public URL."""
    global _cached_product_bytes, _cached_logo_bytes
    try:
        base_filename = os.path.basename(asset_url.split("?")[0])
        name, ext = os.path.splitext(base_filename)
        filename = f"{name}.png"

        rationale = _find_asset_rationale(asset_url)
        if not rationale:
            return {"status": "error", "details": f"No rationale for {asset_url}"}

        product_image_uri = tool_context.state.get(PRODUCT_IMAGE_URI_STATE_KEY)
        if not product_image_uri:
            return {"status": "error", "details": "No product image URI"}

        # Cache product + logo bytes — download once, reuse across parallel calls
        if _cached_product_bytes is None:
            try:
                _cached_product_bytes, _ = utils_agents.download_bytes_from_reference(product_image_uri)
            except Exception:
                return {"status": "error", "details": "Failed to download product image"}

        if _cached_logo_bytes is None:
            logo_uri = tool_context.state.get(LOGO_IMAGE_URI_STATE_KEY)
            if logo_uri:
                try:
                    _cached_logo_bytes, _ = utils_agents.download_bytes_from_reference(logo_uri)
                except Exception:
                    pass

        company_name = tool_context.state.get(PRODUCT_COMPANY_NAME_STATE_KEY, "")
        product_name = tool_context.state.get("PRODUCT_NAME", "product")
        var_idx = hash(asset_url) % len(_VARIATION_STYLES)
        ref_guidelines = tool_context.state.get(REFERENCE_GUIDELINES_STATE_KEY, "")
        persona = tool_context.state.get(CUSTOMER_PERSONA_STATE_KEY, "")

        asset_bytes = await _generate_image_on_demand(
            asset_url=asset_url, rationale=rationale,
            product_image_bytes=_cached_product_bytes, company_name=company_name,
            product_name=product_name, logo_image_bytes=_cached_logo_bytes,
            variation_index=var_idx,
            reference_guidelines=ref_guidelines,
            customer_persona=persona,
        )

        if not asset_bytes:
            return {"status": "error", "details": f"Failed to generate image for {asset_url}"}

        generated_media = GeneratedMedia(
            filename=filename, mime_type="image/png", media_bytes=asset_bytes,
        )
        generated_media = await utils_agents.save_to_artifact_and_render_asset(
            asset=generated_media, context=tool_context,
            save_in_gcs=True, save_in_artifacts=True,
            gcs_folder=OUTPUT_FOLDER,
        )

        public_url = f"https://storage.googleapis.com/{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{OUTPUT_FOLDER}/{base_filename}"
        return {"status": "success", "gcs_url": public_url}

    except Exception as e:
        log_message(f"Failed to render asset: {e}", Severity.ERROR)
        return {"status": "error", "details": str(e)}


async def _pre_generate_images(asset_uris: list[str], tool_context: ToolContext):
    """Pre-generates multiple images in parallel using Gemini."""
    uris_needing_generation = []
    for uri in asset_uris:
        rationale = _find_asset_rationale(uri)
        if rationale:
            base = os.path.basename(uri.split("?")[0])
            try:
                prefixed_uri = f"gs://{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{OUTPUT_FOLDER}/{base}"
                utils_agents.download_bytes_from_reference(prefixed_uri)
            except Exception:
                uris_needing_generation.append((uri, rationale))

    if not uris_needing_generation:
        return

    product_image_uri = tool_context.state.get(PRODUCT_IMAGE_URI_STATE_KEY)
    if not product_image_uri:
        return
    try:
        product_bytes, _ = utils_agents.download_bytes_from_reference(product_image_uri)
    except Exception:
        return

    logo_bytes = None
    logo_uri = tool_context.state.get(LOGO_IMAGE_URI_STATE_KEY)
    if logo_uri:
        try:
            logo_bytes, _ = utils_agents.download_bytes_from_reference(logo_uri)
        except Exception:
            pass

    company_name = tool_context.state.get(PRODUCT_COMPANY_NAME_STATE_KEY, "")
    product_name = tool_context.state.get("PRODUCT_NAME", "product")
    ref_guidelines = tool_context.state.get(REFERENCE_GUIDELINES_STATE_KEY, "")
    persona = tool_context.state.get(CUSTOMER_PERSONA_STATE_KEY, "")

    async def _gen_one(uri, rationale, var_idx):
        img_bytes = await _generate_image_on_demand(
            asset_url=uri, rationale=rationale,
            product_image_bytes=product_bytes, company_name=company_name,
            product_name=product_name, logo_image_bytes=logo_bytes,
            variation_index=var_idx,
            reference_guidelines=ref_guidelines,
            customer_persona=persona,
        )
        return uri, img_bytes

    results = await asyncio.gather(
        *[_gen_one(uri, rat, i) for i, (uri, rat) in enumerate(uris_needing_generation)],
        return_exceptions=True,
    )

    # Images are uploaded by _render_asset via save_to_artifact_and_render_asset — no pre-upload needed


# ============================================================
# Campaign Generation Pipeline (from your parallel agent)
# ============================================================

def _folder_has_content(folder: str, prefix_filter: str = "") -> bool:
    """Checks if a GCS folder already has files matching a specific prefix."""
    try:
        from google.cloud import storage as gcs_storage
        storage_client = gcs_storage.Client(project=GOOGLE_CLOUD_PROJECT)
        bucket = storage_client.bucket(GOOGLE_CLOUD_BUCKET_ARTIFACTS)
        search = f"{folder}/{prefix_filter}" if prefix_filter else f"{folder}/"
        blobs = list(bucket.list_blobs(prefix=search, max_results=1))
        return len(blobs) > 0
    except Exception:
        return False


def delete_asset_from_gcs(tool_context: ToolContext, filename: str):
    """Deletes a specific asset file from GCS. Call this BEFORE regenerating an asset
    to remove the old version the user rejected.

    Args:
        filename: The filename to delete (e.g. 'img_c1_s1_urban_1.png', 'asset_sheet_c1_1.png', 'video_ad_123_456.mp4').
    """
    _set_output_folder(tool_context)
    try:
        from google.cloud import storage as gcs_storage
        storage_client = gcs_storage.Client(project=GOOGLE_CLOUD_PROJECT)
        bucket = storage_client.bucket(GOOGLE_CLOUD_BUCKET_ARTIFACTS)
        blob_path = f"{OUTPUT_FOLDER}/{filename}"
        blob = bucket.blob(blob_path)
        if blob.exists():
            blob.delete()
            log_message(f"Deleted old asset from GCS: {blob_path}", Severity.INFO)
            return {"status": "success", "details": f"Deleted {filename} from GCS"}
        return {"status": "not_found", "details": f"{filename} not found in GCS"}
    except Exception as e:
        log_message(f"Failed to delete {filename}: {e}", Severity.WARNING)
        return {"status": "error", "details": str(e)}


def _prefixed_blob(blob_path: str) -> str:
    return f"{OUTPUT_FOLDER}/{blob_path}"


def _get_state():
    path = f"gs://{MARKETING_ANALYST_DATASTORE_CLOUD_BUCKET}/{_prefixed_blob(SESSION_STATE_FILE_NAME)}"
    try:
        state = utils_gcs.download_text_from_gcs(path)
        return json.loads(state)
    except Exception:
        return {}


def _add_selected_asset(state_key: str, asset: str) -> list[str]:
    state_json = _get_state()
    selected_assets = state_json.get(state_key, [])
    if asset not in selected_assets:
        selected_assets.append(asset)
    state_json[state_key] = selected_assets
    utils_gcs.upload_to_gcs(
        bucket_path=MARKETING_ANALYST_DATASTORE_CLOUD_BUCKET,
        file_bytes=json.dumps(state_json).encode('utf-8'),
        destination_blob_name=_prefixed_blob(SESSION_STATE_FILE_NAME)
    )
    return selected_assets


def check_existing_assets(tool_context: ToolContext):
    """Checks if marketing assets already exist for the current product + persona combination.
    Call this after personalization is set to see if assets can be reused.
    """
    _set_output_folder(tool_context)
    if _folder_has_content(OUTPUT_FOLDER):
        from google.cloud import storage as gcs_storage
        try:
            storage_client = gcs_storage.Client(project=GOOGLE_CLOUD_PROJECT)
            bucket = storage_client.bucket(GOOGLE_CLOUD_BUCKET_ARTIFACTS)
            blobs = list(bucket.list_blobs(prefix=f"{OUTPUT_FOLDER}/", max_results=50))
            files = {"images": [], "videos": [], "text_ads": [], "asset_sheets": []}
            for b in blobs:
                name = b.name.split("/")[-1]
                if name.startswith("asset_sheet"):
                    files["asset_sheets"].append(name)
                elif name.startswith("img_"):
                    files["images"].append(name)
                elif name.endswith(".mp4"):
                    files["videos"].append(name)
                elif name.endswith(".json") and "text_ad" in name:
                    files["text_ads"].append(name)
            return {
                "status": "exists",
                "folder": OUTPUT_FOLDER,
                "asset_sheets": len(files["asset_sheets"]),
                "image_ads": len(files["images"]),
                "video_ads": len(files["videos"]),
                "text_ads": len(files["text_ads"]),
                "details": f"Found {len(blobs)} files in gs://{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{OUTPUT_FOLDER}/",
            }
        except Exception:
            pass
    return {"status": "empty", "folder": OUTPUT_FOLDER}


def _get_nonselected_assets(state_key: str, alternatives: list[str]) -> list[str]:
    state_json = _get_state()
    selected_assets = state_json.get(state_key, [])
    return [a for a in alternatives if a not in selected_assets]


def _clear_selected_assets_of_type(state_key: str) -> None:
    state_json = _get_state()
    state_json[state_key] = []
    utils_gcs.upload_to_gcs(
        bucket_path=MARKETING_ANALYST_DATASTORE_CLOUD_BUCKET,
        file_bytes=json.dumps(state_json).encode('utf-8'),
        destination_blob_name=_prefixed_blob(SESSION_STATE_FILE_NAME)
    )


def _get_ideas_and_briefs_string(context: ReadonlyContext) -> tuple[str, bool]:
    global _CACHED_IDEAS_STRING
    if _CACHED_IDEAS_STRING:
        return _CACHED_IDEAS_STRING, True
    try:
        ideas_content = utils_gcs.download_text_from_gcs(CAMPAIGNS_CONFIG_URL)
        if ideas_content:
            _CACHED_IDEAS_STRING = ideas_content
            return ideas_content, False
    except Exception as e:
        log_message(f"Error reading campaigns config: {e}", Severity.ERROR)

    raise RuntimeError("Could not retrieve campaigns config. Run setup_product_campaign first.")


def _get_and_cache_campaigns(tool_context) -> list[Campaign]:
    global _CACHED_CAMPAIGNS_LIST
    if _CACHED_CAMPAIGNS_LIST:
        return _CACHED_CAMPAIGNS_LIST
    xml_string, _ = _get_ideas_and_briefs_string(tool_context)
    campaigns = parse_campaigns_from_xml(xml_string)
    if campaigns:
        _CACHED_CAMPAIGNS_LIST = campaigns
    return campaigns


async def setup_product_campaign(
    tool_context: ToolContext,
    company_name: str,
    product_name: str,
    product_description: str,
    target_audience: str,
    logo_uri: str,
    product_image_uri: str,
    num_segments: int = 2,
    reference_guidelines: str = "",
):
    """Sets up the marketing campaign system for a new product. This MUST be called first.
    It generates campaign ideas, audience segments, and ad configurations.

    Args:
        company_name: The brand/company name.
        product_name: The product name.
        product_description: Description of the product.
        target_audience: Description of the target audience.
        logo_uri: GCS URI or URL of the brand logo image.
        product_image_uri: GCS URI or URL of the product image.
        num_segments: Number of audience segments per campaign (1-4, default 2).
        reference_guidelines: Extracted text content from user-provided reference documents
            (product docs, marketing briefs, brand guidelines, style guides). These guidelines
            will be used throughout the entire campaign creation pipeline to ensure all generated
            content aligns with the brand voice, messaging, visual direction, and constraints.
    """
    global _CACHED_CAMPAIGNS_LIST, _CACHED_IDEAS_STRING, _cached_product_bytes, _cached_logo_bytes
    _CACHED_CAMPAIGNS_LIST = None
    _CACHED_IDEAS_STRING = None
    _cached_product_bytes = None
    _cached_logo_bytes = None

    # Assets are preserved across sessions — no cleanup

    tool_context.state[PRODUCT_COMPANY_NAME_STATE_KEY] = company_name
    tool_context.state["PRODUCT_NAME"] = product_name
    tool_context.state[PRODUCT_IMAGE_URI_STATE_KEY] = product_image_uri
    tool_context.state[LOGO_IMAGE_URI_STATE_KEY] = logo_uri

    # Display product image inline for Path B (Path A already shows via get_product_by_sku)
    if product_image_uri and not tool_context.state.get("_product_image_displayed"):
        try:
            img_bytes, _ = utils_agents.download_bytes_from_reference(product_image_uri)
            if img_bytes:
                safe_name = product_name.replace(" ", "_")[:30]
                product_media = GeneratedMedia(
                    filename=f"product_{safe_name}.png", mime_type="image/png", media_bytes=img_bytes,
                )
                await utils_agents.save_to_artifact_and_render_asset(
                    asset=product_media, context=tool_context,
                    save_in_gcs=False, save_in_artifacts=True,
                )
                tool_context.state["_product_image_displayed"] = True
        except Exception:
            pass
    tool_context.state[GENERATED_GCS_URIS_STATE_KEY] = []

    # Store reference guidelines in session state for use by downstream generation steps
    if reference_guidelines and reference_guidelines.strip():
        tool_context.state[REFERENCE_GUIDELINES_STATE_KEY] = reference_guidelines.strip()

    try:
        xml_content = generate_campaigns_xml(
            company_name=company_name,
            product_name=product_name,
            product_description=product_description,
            target_audience=target_audience,
            logo_uri=logo_uri,
            product_image_uri=product_image_uri,
            num_segments=num_segments,
            reference_guidelines=reference_guidelines,
        )
    except Exception as e:
        return {"status": "error", "details": f"Failed to generate campaigns: {e}"}

    try:
        campaigns = parse_campaigns_from_xml(xml_content)
        if not campaigns:
            return {"status": "error", "details": "No valid campaigns generated."}
        _CACHED_CAMPAIGNS_LIST = campaigns
        _CACHED_IDEAS_STRING = xml_content

        try:
            utils_gcs.upload_to_gcs(
                bucket_path=MARKETING_ANALYST_DATASTORE_CLOUD_BUCKET,
                file_bytes=xml_content.encode("utf-8"),
                destination_blob_name=_prefixed_blob(f"generated_campaigns.{AGENT_VERSION}.xml"),
            )
        except Exception:
            pass

        tool_context.state[PRODUCT_SETUP_DONE_STATE_KEY] = True
        campaign_names = [c.name for c in campaigns]
        all_segments = set()
        for c in campaigns:
            for s in c.segments:
                all_segments.add(s.name)

        return {
            "status": "success",
            "details": f"Configured {len(campaigns)} campaigns for {company_name} {product_name}.",
            "campaign_names": campaign_names,
            "audience_segments": list(all_segments),
        }
    except Exception as e:
        return {"status": "error", "details": f"XML validation error: {e}"}


def get_campaign_idea(tool_context: ToolContext, quantity: int):
    """Generates alternative marketing campaign ideas.

    Args:
        quantity: Number of campaign ideas to generate.
    """
    campaigns = _get_and_cache_campaigns(tool_context)
    campaign_names = [c.name for c in campaigns]
    selected_campaigns = []
    picked = []
    for _ in range(max(quantity, 1)):
        valid = [a for a in _get_nonselected_assets(SELECTED_CAMPAIGN_IDEAS_STATE_KEY, campaign_names) if a not in picked]
        if not valid:
            valid = [a for a in campaign_names if a not in picked]
            if not valid:
                break
        name = random.choice(valid)
        picked.append(name)
        _add_selected_asset(SELECTED_CAMPAIGN_IDEAS_STATE_KEY, name)
        campaign = find_campaign_by_name(campaigns, name)
        if campaign:
            selected_campaigns.append({
                "name": campaign.name, "hook": campaign.hook,
                "insight": campaign.insight, "visual_key": campaign.visual_key,
                "tagline": campaign.tagline, "why_it_works": campaign.why_it_works,
                "segments": [s.name for s in campaign.segments],
            })
    _clear_selected_assets_of_type(SELECTED_ASSET_SHEETS_STATE_KEY)
    _clear_selected_assets_of_type(SELECTED_IMAGES_STATE_KEY)
    _clear_selected_assets_of_type(SELECTED_VIDEOS_STATE_KEY)
    return {"campaign_ideas": selected_campaigns}


def save_selected_campaign(chosen_idea: str, tool_context: ToolContext):
    """Saves the user's chosen campaign idea."""
    campaigns = _get_and_cache_campaigns(tool_context)
    chosen = find_campaign_by_name(campaigns, chosen_idea)
    if not chosen:
        names = [c.name for c in campaigns]
        return {"status": "error", "details": f"No campaign named '{chosen_idea}'. Options: {names}"}
    tool_context.state[CHOSEN_CAMPAIGN_IDEA_STATE_KEY] = chosen.name
    return {"status": "success", "details": f"Saved: {chosen.name}"}


def get_selected_brief(tool_context: ToolContext, selected_campaign_name: str):
    """Retrieves the brief for the selected campaign.

    Args:
        selected_campaign_name: Name of the selected campaign.
    """
    campaigns = _get_and_cache_campaigns(tool_context)
    campaign = find_campaign_by_name(campaigns, selected_campaign_name)
    if not campaign:
        return {"status": "error", "details": f"No campaign named '{selected_campaign_name}'"}
    save_selected_campaign(selected_campaign_name, tool_context)
    return campaign.relevant_brief


async def get_asset_sheet(tool_context: ToolContext, selected_campaign_name: str, quantity: int = 2):
    """Generates asset sheet configurations for the selected campaign.

    Args:
        selected_campaign_name: Name of the selected campaign.
        quantity: Number of asset sheets to retrieve.
    """
    _set_output_folder(tool_context)
    campaigns = _get_and_cache_campaigns(tool_context)
    campaign = find_campaign_by_name(campaigns, selected_campaign_name)
    if not campaign or not campaign.asset_sheets:
        return {"status": "error", "details": "No asset sheets available."}
    save_selected_campaign(selected_campaign_name, tool_context)

    all_alts = [s.id or s.uri for s in campaign.asset_sheets]
    selected_sheets = []
    picked = []
    for _ in range(max(quantity, 1)):
        valid = [a for a in _get_nonselected_assets(SELECTED_ASSET_SHEETS_STATE_KEY, all_alts) if a not in picked]
        if not valid:
            valid = [a for a in all_alts if a not in picked]
            if not valid:
                break
        key = random.choice(valid)
        picked.append(key)
        _add_selected_asset(SELECTED_ASSET_SHEETS_STATE_KEY, key)
        sheet = next((s for s in campaign.asset_sheets if (s.id or s.uri) == key), None)
        if sheet:
            selected_sheets.append(sheet)

    # Generate images on-demand and render as artifacts — ALL IN PARALLEL
    if selected_sheets:
        render_results = await asyncio.gather(
            *[_render_asset(sheet.uri, tool_context) for sheet in selected_sheets],
            return_exceptions=True,
        )

        sheets_out = []
        for sheet, result in zip(selected_sheets, render_results):
            d = sheet.model_dump()
            if isinstance(result, dict):
                d["gcs_url"] = result.get("gcs_url", sheet.uri)
            else:
                d["gcs_url"] = sheet.uri
            sheets_out.append(d)
        return {"status": "success", "asset_sheets": sheets_out}

    return {"status": "success", "asset_sheets": [s.model_dump() for s in selected_sheets]}


async def get_image_ads_for_audience(
    tool_context: ToolContext, quantity: int, segment_name: str,
    asset_sheet_uri: str, selected_campaign_name: str,
):
    """Retrieves image ad concepts for a specific audience segment.

    Args:
        quantity: Number of image ads.
        segment_name: Target audience segment name.
        asset_sheet_uri: URI of the selected asset sheet.
        selected_campaign_name: Name of the selected campaign.
    """
    _set_output_folder(tool_context)
    campaigns = _get_and_cache_campaigns(tool_context)
    campaign = find_campaign_by_name(campaigns, selected_campaign_name)
    if not campaign:
        return {"status": "error", "details": f"No campaign named '{selected_campaign_name}'"}

    segment = campaign.get_segment_by_name(segment_name)
    if not segment:
        return {"status": "error", "details": f"No segment named '{segment_name}'"}

    all_alts = [a.uri for a in segment.image_ads]
    selected_ads = []
    picked = []
    for _ in range(max(quantity, 1)):
        valid = [a for a in _get_nonselected_assets(SELECTED_IMAGES_STATE_KEY, all_alts) if a not in picked]
        if not valid:
            valid = [a for a in all_alts if a not in picked]
            if not valid:
                break
        uri = random.choice(valid)
        picked.append(uri)
        _add_selected_asset(SELECTED_IMAGES_STATE_KEY, uri)
        ad = next((a for a in segment.image_ads if a.uri == uri), None)
        if ad:
            selected_ads.append(ad)

    # Generate images on-demand and render as artifacts — ALL IN PARALLEL
    if selected_ads:
        render_results = await asyncio.gather(
            *[_render_asset(ad.uri, tool_context) for ad in selected_ads],
            return_exceptions=True,
        )

        ads_out = []
        for ad, result in zip(selected_ads, render_results):
            d = ad.model_dump()
            if isinstance(result, dict):
                d["gcs_url"] = result.get("gcs_url", ad.uri)
            else:
                d["gcs_url"] = ad.uri
            ads_out.append(d)
        return {"status": "success", "image_ads": ads_out}

    return {"status": "success", "image_ads": [a.model_dump() for a in selected_ads]}


async def get_video_ads_for_audience(
    tool_context: ToolContext, quantity: int, segment_name: str,
    asset_sheet_uri: str, selected_campaign_name: str,
):
    """Retrieves video ad concepts for a specific audience segment.

    Args:
        quantity: Number of video ads.
        segment_name: Target audience segment name.
        asset_sheet_uri: URI of the selected asset sheet.
        selected_campaign_name: Name of the selected campaign.
    """
    _set_output_folder(tool_context)
    campaigns = _get_and_cache_campaigns(tool_context)
    campaign = find_campaign_by_name(campaigns, selected_campaign_name)
    if not campaign:
        return {"status": "error", "details": f"No campaign named '{selected_campaign_name}'"}

    segment = campaign.get_segment_by_name(segment_name)
    if not segment:
        return {"status": "error", "details": f"No segment named '{segment_name}'"}

    all_alts = [a.uri for a in segment.video_ads]
    selected_ads = []
    picked = []
    for _ in range(max(quantity, 1)):
        valid = [a for a in _get_nonselected_assets(SELECTED_VIDEOS_STATE_KEY, all_alts) if a not in picked]
        if not valid:
            valid = [a for a in all_alts if a not in picked]
            if not valid:
                break
        uri = random.choice(valid)
        picked.append(uri)
        _add_selected_asset(SELECTED_VIDEOS_STATE_KEY, uri)
        ad = next((a for a in segment.video_ads if a.uri == uri), None)
        if ad:
            selected_ads.append(ad)

    # Generate actual video ads on-demand — ALL IN PARALLEL
    if selected_ads:
        product_image_uri = tool_context.state.get(PRODUCT_IMAGE_URI_STATE_KEY, "")
        company_name = tool_context.state.get(PRODUCT_COMPANY_NAME_STATE_KEY, "")
        product_name = tool_context.state.get("PRODUCT_NAME", "product")

        async def _gen_video_ad(ad, idx):
            log_message(f"Generating video ad {idx + 1}/{len(selected_ads)}: {ad.rationale}", Severity.INFO)
            return await _generate_full_video_ad(
                rationale=ad.rationale,
                product_image_uri=product_image_uri,
                company_name=company_name,
                product_name=product_name,
                tool_context=tool_context,
            )

        log_message(f"Launching {len(selected_ads)} video ads in parallel...", Severity.INFO)
        parallel_results = await asyncio.gather(
            *[_gen_video_ad(ad, i) for i, ad in enumerate(selected_ads)],
            return_exceptions=True,
        )

        video_results = []
        for ad, result in zip(selected_ads, parallel_results):
            d = ad.model_dump()
            if isinstance(result, Exception):
                log_message(f"Video ad failed: {result}", Severity.ERROR)
                d["status"] = "failed"
            elif result:
                video_bytes, processing_time, video_length = result
                ts = int(time.time())
                filename = f"video_ad_{id(ad)}_{ts}.mp4"

                video_media = GeneratedMedia(
                    filename=filename,
                    mime_type="video/mp4",
                    media_bytes=video_bytes,
                )
                video_media = await utils_agents.save_to_artifact_and_render_asset(
                    asset=video_media,
                    context=tool_context,
                    save_in_gcs=True,
                    save_in_artifacts=True,
                    gcs_folder=OUTPUT_FOLDER,
                )

                public_url = f"https://storage.googleapis.com/{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{OUTPUT_FOLDER}/{filename}"
                d["gcs_url"] = public_url
                d["status"] = "generated"
                mins = int(processing_time // 60)
                secs = int(processing_time % 60)
                d["processing_time"] = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
                d["video_length"] = f"{video_length} seconds"
            else:
                d["status"] = "failed"
            video_results.append(d)

        return {"status": "success", "video_ads": video_results}

    return {"status": "success", "video_ads": [a.model_dump() for a in selected_ads]}


# ============================================================
# Full Video Ad Pipeline
# ============================================================

STORYLINE_MODEL = "gemini-3.1-pro-preview"
LYRIA_MODEL = "lyria-3-pro-preview"

_VEO_SENSITIVE_WORDS = [
    "surveillance", "spy", "spying", "weapon", "gun", "knife", "blood",
    "violent", "violence", "attack", "kill", "murder", "death", "dead",
    "bomb", "explosive", "terror", "child", "children", "minor", "nude",
    "naked", "drugs", "injection", "syringe", "intruder", "burglar",
    "break-in", "breaking in", "trespasser", "stalker", "stalking",
]


def _sanitize_veo_prompt(prompt: str) -> str:
    """Removes words that VEO's content policy may flag."""
    sanitized = prompt
    for word in _VEO_SENSITIVE_WORDS:
        sanitized = sanitized.replace(word, "").replace(word.capitalize(), "").replace(word.upper(), "")
    return " ".join(sanitized.split())


async def _generate_storyline(company_name: str, product_name: str, rationale: str, reference_guidelines: str = "", customer_persona: str = "") -> dict:
    """Gemini generates a 3-act storyline with per-act voiceover and motion prompts.

    Each act is 8 seconds. Voiceover is split per act (~20 words each = 8s at 2.5 words/sec).
    No overlap between acts — each voiceover chunk is self-contained.
    """
    ACTS = 3
    CLIP_SEC = 8
    words_per_act = 15  # ~2 words/sec x 8s (energetic pace with speaking_rate=0.95)

    try:
        client = genai.Client(vertexai=True, project=GOOGLE_CLOUD_PROJECT, location="global")
        guidelines_context = ""
        if reference_guidelines and reference_guidelines.strip():
            guidelines_context = (
                f"\n\nReference Guidelines (MUST follow for tone, messaging, visual style):\n"
                f"{reference_guidelines.strip()}\n"
            )
        persona_context = ""
        if customer_persona and customer_persona.strip():
            persona_context = (
                f"\n\nTARGET CUSTOMER PERSONA (MUST tailor the entire ad to this persona):\n"
                f"{customer_persona.strip()}\n"
                f"All scenes, voiceover tone, environments, and emotional appeal MUST resonate with this persona.\n"
            )
        prompt = (
            f"You are an AWARD-WINNING commercial film director. Your ads win Cannes Lions and make people stop scrolling.\n\n"
            f"Create a BOLD, CAPTIVATING 3-act video ad that tells ONE unforgettable story:\n"
            f"- Act 1 must HOOK the viewer in the first 2 seconds — intrigue, surprise, or beauty that demands attention\n"
            f"- Act 2 must BUILD with rising energy — unexpected twist, emotional shift, or jaw-dropping visual\n"
            f"- Act 3 must deliver a PAYOFF that gives goosebumps — iconic product moment, then graceful close\n"
            f"- The 3 acts must flow like ONE continuous story, not 3 separate scenes\n"
            f"- Be WILDLY CREATIVE — surprise the viewer, break expectations, tell a story no one has seen before\n"
            f"- Think Nike 'Dream Crazy', Apple '1984', Old Spice 'The Man Your Man Could Smell Like'\n"
            f"- NO generic product-on-table shots. Every frame must have PURPOSE, EMOTION, and VISUAL IMPACT\n"
            f"- Show the product in REAL-LIFE USAGE — people living their lives WITH the product naturally present\n"
            f"- The product is a background hero — it's THERE, it's VISIBLE, but the STORY is about the people using it\n"
            f"- Example: a security camera sits on a shelf while kids play below, a whisky bottle on a dinner table while friends laugh\n"
            f"- The product NEVER activates, moves, transforms, or does anything — it just EXISTS in the scene\n\n"
            f"Product details:\n"
            f"Brand: {company_name}\nProduct: {product_name}\nAd concept: {rationale}\n"
            f"{guidelines_context}{persona_context}\n"
            f"The video is {ACTS * CLIP_SEC} seconds total — 3 acts of {CLIP_SEC} seconds each.\n\n"
            f"STORY FLOW MANDATE:\n"
            f"The 3 acts MUST tell ONE connected story — each scene flows naturally into the next.\n"
            f"Think of it as one continuous narrative with 3 distinct chapters:\n"
            f"  Act 1: SETUP — introduce the product in a real-world moment (morning or daytime)\n"
            f"  Act 2: BUILD — the product being enjoyed/used, wow cinematic moment (afternoon or golden hour)\n"
            f"  Act 3: RESOLVE — the payoff, brand spotlight moment (evening or night)\n"
            f"The time progression (morning→afternoon→evening) creates natural scene variety.\n\n"
            f"WOW MOMENTS (real-world magic, NOT fantasy):\n"
            f"- Use LIGHTING as the wow: lights turning on to reveal product, sunlight breaking through clouds,\n"
            f"  spotlight illuminating the product, candles being lit, neon signs flickering on\n"
            f"- Use ENVIRONMENT: rain starting/stopping, steam rising from a drink, ice forming on glass,\n"
            f"  fireplace crackling to life, city coming alive at dusk, reflections in polished surfaces\n"
            f"- Use MOTION: slow-motion pour, product emerging from shadow into light, smooth dolly reveal\n"
            f"- Think Johnnie Walker 'Keep Walking', Apple 'Shot on iPhone', Mercedes 'The Best or Nothing'\n"
            f"- These are REAL moments that feel magical — not CGI or fantasy\n\n"
            f"REALISM MANDATE — ABSOLUTE (ZERO HALLUCINATION):\n"
            f"- REAL locations, REAL lighting, REAL people — as if filmed with a REAL camera on a REAL set\n"
            f"- ALL objects must obey PHYSICS: gravity, proper liquid behavior, realistic surfaces\n"
            f"- NO: floating objects, suspended ingredients, digital art, painting, CGI, cartoon, fantasy glow\n"
            f"- NO: surreal compositions, dreamlike scenes, AI-generated aesthetic\n"
            f"- Products sit on surfaces, liquids flow down, people stand on ground\n"
            f"- Objects do NOT move by themselves — only a human hand can move an object\n"
            f"- Objects do NOT teleport, change location, fall over, roll away, or disappear\n"
            f"- The product does NOT open, close, fold, unfold, transform, or animate on its own\n"
            f"- The product has NO moving parts in the video — no lens opening, no shutter, no lights turning on\n"
            f"- The product sits MOTIONLESS like a prop — only people and environment move around it\n"
            f"- The motion_prompt must NEVER describe the product activating, powering on, or doing anything mechanical\n"
            f"- People walk naturally, sit naturally, hold things naturally — no supernatural movements\n"
            f"- Every scene must look like something that ACTUALLY HAPPENS in real life\n"
            f"- If you wouldn't see it in a real TV commercial filmed with real cameras, DON'T include it\n\n"
            f"MOTION MANDATE — CRITICAL:\n"
            f"- EVERY motion_prompt MUST describe CONTINUOUS camera and/or subject movement for the FULL {CLIP_SEC} seconds\n"
            f"- The camera MUST ALWAYS be moving: dolly, steadicam track, crane, orbit, handheld walk, push-in, pull-out\n"
            f"- NO static shots. NO still frames. The video must have constant cinematic motion throughout\n"
            f"- Also describe subject movement: person walking, wind blowing, product rotating, hands interacting\n\n"
            f"PRODUCT FIDELITY — CRITICAL:\n"
            f"- The product MUST appear EXACTLY as in the reference image — EVERY part, component, wing, arm, "
            f"button, detail MUST be present. Do NOT remove, add, or alter ANY part of the product.\n"
            f"- Describe the product by referencing the reference image, not from imagination.\n\n"
            f"Output EXACTLY this JSON (no markdown, no code fences):\n"
            f'{{"acts": ['
            f'{{"act_number": 1, '
            f'"scene_description": "SETUP — real location, real lighting. Product introduced in context. Describe specific location and lighting.", '
            f'"end_scene_description": "Act 1 closing frame — transitions toward Act 2 scene.", '
            f'"motion_prompt": "CONTINUOUS motion for {CLIP_SEC}s. Camera MUST be moving the entire time. Describe specific camera movement AND subject movement.", '
            f'"voiceover": "Exactly {words_per_act} words. Bold, energetic, commanding tone."}},'
            f'{{"act_number": 2, '
            f'"scene_description": "BUILD — different real location from Act 1, different time of day. Product in action. Describe specific setting.", '
            f'"end_scene_description": "Act 2 closing frame — leads naturally into Act 3.", '
            f'"motion_prompt": "CONTINUOUS motion for {CLIP_SEC}s. Different camera technique from Act 1. Camera NEVER stops moving.", '
            f'"voiceover": "Exactly {words_per_act} words. Builds intensity, powerful delivery."}},'
            f'{{"act_number": 3, '
            f'"scene_description": "RESOLVE — different setting, evening/night. The product takes center stage — hero shot, beautifully lit.", '
            f'"end_scene_description": "Final frame — product ALONE in frame, perfectly composed, brand name visible. Elegant, still, iconic. Like a magazine cover.", '
            f'"motion_prompt": "CONTINUOUS motion for {CLIP_SEC}s. Slow, elegant push-in toward the product. Camera settles on a CLEAN hero shot. Last 2 seconds: product fills the frame, beautifully lit, no distractions.", '
            f'"voiceover": "Exactly {words_per_act} words. Final brand statement — then silence for the product to breathe."}}'
            f'],\n'
            f'"storyline": "Combined voiceover script for all 3 acts (~{words_per_act * ACTS} words total)",\n'
            f'"lyria_prompt": "A concise prompt (under 80 words) for instrumental background music that PERFECTLY matches the storyline mood and energy. '
            f'The music must make viewers feel the SAME emotion as the video — if the ad is luxurious, the music is sophisticated; '
            f'if the ad is adventurous, the music is thrilling; if the ad is heartwarming, the music is tender then uplifting. '
            f'Must build progressively with the storyline arc — start engaging, build momentum, finish with an unforgettable crescendo. '
            f'STRICTLY INSTRUMENTAL — NO vocals, NO lyrics, NO singing. '
            f'Describe specific instruments, tempo (BPM), mood shifts per act, and dynamic range."\n'
            f"}}\n\n"
            f"CRITICAL RULES:\n"
            f"- Each voiceover is ~{words_per_act} words for its own {CLIP_SEC}-second act\n"
            f"- The 3 acts tell ONE connected story with natural progression\n"
            f"- EVERY motion_prompt MUST have CONTINUOUS movement — NO static frames\n"
            f"- Product MUST match reference image EXACTLY — all parts, wings, arms, components present\n"
            f"- Different real-world location and time of day for each act\n"
            f"- lyria_prompt MUST be instrumental only — NO vocals, NO lyrics\n"
            f"- lyria_prompt MUST match the storyline mood EXACTLY — same emotion, same energy, same arc\n"
            f"- The music should make the viewer feel what the video shows — it's the emotional backbone of the ad"
        )
        response = await _retry_generate_content(
            client, STORYLINE_MODEL, prompt,
            config=types.GenerateContentConfig(temperature=1.0, top_p=0.95, max_output_tokens=8192),
            label="storyline",
        )
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            raw = raw.rsplit("```", 1)[0]
        import json as _json
        result = _json.loads(raw)

        # Build combined storyline from per-act voiceovers
        acts = result.get("acts", [])
        combined_vo = " ".join(act.get("voiceover", "") for act in acts)
        result["storyline"] = combined_vo
        return result

    except Exception as e:
        log_message(f"Storyline failed, using fallback: {e}", Severity.WARNING)
        return {
            "storyline": (
                f"Some things you just know the moment you see them. "
                f"The {product_name} fits into your world like it was always there. "
                f"{company_name}. Made for moments like these."
            ),
            "acts": [
                {
                    "act_number": 1,
                    "scene_description": f"Bright morning. {product_name} revealed on a sunlit surface. Clean, fresh, vibrant daylight",
                    "end_scene_description": f"Close-up of {product_name} with all details visible in bright natural light",
                    "motion_prompt": f"Slow orbit around {product_name} in bright daylight. Camera continuously circles. Light shifts as camera moves. Bright to dramatic shadow transition.",
                    "voiceover": f"Some things you just know the moment you see them. The {product_name} needs no introduction.",
                },
                {
                    "act_number": 2,
                    "scene_description": f"Golden hour outdoors. {product_name} in action, being used in a stunning landscape. Warm amber tones, wind visible",
                    "end_scene_description": f"Wide sweeping view with {product_name} against a dramatic golden sky",
                    "motion_prompt": f"Sweeping drone-style tracking shot following {product_name} in golden hour landscape. Continuous movement, dramatic light shifts. Wind in environment.",
                    "voiceover": f"The {product_name} fits into your world like it was always there. Effortlessly extraordinary.",
                },
                {
                    "act_number": 3,
                    "scene_description": f"Dramatic evening or night. {product_name} hero shot with moody lighting. Neon or city lights reflecting off product",
                    "end_scene_description": f"Final frame: {product_name} centered, {company_name} brand name visible. Cinematic closing",
                    "motion_prompt": f"Slow cinematic push-in toward {product_name} in dramatic evening light. Camera glides continuously. Lights shift from warm to cool. Brand name appears.",
                    "voiceover": f"{company_name}. Made for moments like these. The pursuit of extraordinary.",
                },
            ],
        }


async def _generate_single_veo_clip(prompt: str, start_frame_gcs_uri: str,
                                     clip_duration: int = 6, end_frame_gcs_uri: str | None = None,
                                     label: str = "clip") -> bytes | None:
    """Generates a single VEO video clip from a keyframe image."""
    mode = "interpolation" if end_frame_gcs_uri else "i2v"
    try:
        client = genai.Client(vertexai=True, project=GOOGLE_CLOUD_PROJECT, location="global")
        img_mime = "image/png"

        last_frame = None
        if end_frame_gcs_uri:
            last_frame = types.Image(gcs_uri=end_frame_gcs_uri, mime_type=img_mime)

        veo_config = types.GenerateVideosConfig(
            number_of_videos=1, duration_seconds=clip_duration, aspect_ratio="16:9",
            last_frame=last_frame,
            generate_audio=False,
            person_generation="allow_all",
        )

        log_message(f"VEO {label} ({mode}): submitting {clip_duration}s clip...", Severity.INFO)

        operation = None
        for veo_attempt in range(3):
            try:
                operation = client.models.generate_videos(
                    model=VEO_MODEL,
                    prompt=prompt,
                    image=types.Image(gcs_uri=start_frame_gcs_uri, mime_type=img_mime),
                    config=veo_config,
                )
                break
            except Exception as submit_err:
                if "429" in str(submit_err) or "RESOURCE_EXHAUSTED" in str(submit_err):
                    backoff = (2 ** veo_attempt) * 5 + random.uniform(0, 3)
                    log_message(f"VEO {label}: 429 on submit, backoff {backoff:.1f}s (attempt {veo_attempt+1}/3)", Severity.WARNING)
                    await asyncio.sleep(backoff)
                else:
                    raise
        if not operation:
            log_message(f"VEO {label} ({mode}): failed to submit after 3 retries", Severity.ERROR)
            return None

        for poll in range(80):
            if operation.done:
                break
            await asyncio.sleep(10)
            operation = client.operations.get(operation)

        if not operation.done:
            log_message(f"VEO {label} ({mode}): timed out after {80 * 10}s polling", Severity.ERROR)
            return None
        if operation.error:
            log_message(f"VEO {label} ({mode}): operation error: {operation.error}", Severity.ERROR)
            return None
        if not operation.response or not operation.response.generated_videos:
            log_message(f"VEO {label} ({mode}): no videos in response", Severity.ERROR)
            return None

        generated = operation.response.generated_videos[0]
        if not generated.video or not generated.video.video_bytes:
            log_message(f"VEO {label} ({mode}): generated video has no bytes", Severity.ERROR)
            return None

        log_message(f"VEO {label} ({mode}): success, {len(generated.video.video_bytes):,} bytes", Severity.INFO)
        return generated.video.video_bytes
    except Exception as e:
        log_message(f"VEO {label} ({mode}) exception: {e}", Severity.ERROR)
        return None




async def _generate_lyria_music(lyria_prompt: str, product_name: str) -> bytes | None:
    """Generates instrumental background music using Lyria from the storyline's lyria_prompt."""
    try:
        client = genai.Client(vertexai=True, project=GOOGLE_CLOUD_PROJECT, location="global")

        if not lyria_prompt or len(lyria_prompt) < 20:
            lyria_prompt = (
                f"Cinematic instrumental that builds with the story — starts with intrigue and sophistication, "
                f"builds momentum with layered instruments, and finishes with a powerful, unforgettable crescendo. "
                f"Match the vibe of a premium {product_name} commercial — captivating from the first note, "
                f"impossible to skip. Rich textures, dynamic builds, emotional depth. "
                f"STRICTLY INSTRUMENTAL — no vocals, no singing, no humming."
            )

        log_message(f"Lyria prompt: {lyria_prompt[:100]}...", Severity.INFO)

        # Generate music with Lyria via generate_content API
        response = await _retry_generate_content(
            client, LYRIA_MODEL, lyria_prompt,
            config=types.GenerateContentConfig(response_modalities=["AUDIO", "TEXT"]),
            label="lyria-music",
        )
        for part in response.parts:
            if part.inline_data and part.inline_data.data:
                log_message(f"Lyria music generated: {len(part.inline_data.data) // 1024} KB", Severity.INFO)
                return part.inline_data.data

        log_message("Lyria returned no audio", Severity.WARNING)
        return None
    except Exception as e:
        log_message(f"Lyria music generation failed: {e}", Severity.ERROR)
        return None



async def _generate_voiceover_audio(script: str) -> bytes | None:
    """Generates voiceover audio using Cloud TTS Chirp3-HD with a deep luxury male voice."""
    from google.cloud import texttospeech

    for attempt in range(3):
        try:
            client = texttospeech.TextToSpeechClient()
            response = client.synthesize_speech(
                input=texttospeech.SynthesisInput(text=script),
                voice=texttospeech.VoiceSelectionParams(
                    language_code="en-US",
                    name=f"en-US-Chirp3-HD-{GEMINI_TTS_VOICE}",
                ),
                audio_config=texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.MP3,
                    speaking_rate=1.0,
                ),
            )
            if response.audio_content:
                log_message(f"Voiceover generated: {len(response.audio_content)} bytes", Severity.INFO)
                return response.audio_content
        except Exception as e:
            log_message(f"TTS attempt {attempt + 1}/3 failed: {e}", Severity.WARNING)
        if attempt < 2:
            await asyncio.sleep(2)
    return None


def _stitch_videos(clip_bytes_list: list[bytes]) -> bytes | None:
    """Stitches video clips with crossfade transitions using ffmpeg."""
    import subprocess

    if len(clip_bytes_list) == 1:
        return clip_bytes_list[0]

    clip_paths = []
    out_path = "/tmp/_stitched_output.mp4"
    try:
        for i, clip in enumerate(clip_bytes_list):
            path = f"/tmp/_stitch_clip_{i}.mp4"
            with open(path, "wb") as f:
                f.write(clip)
            clip_paths.append(path)

        # Simple concat with ffmpeg
        list_file = "/tmp/_concat_list.txt"
        with open(list_file, "w") as f:
            for p in clip_paths:
                f.write(f"file '{p}'\n")

        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", out_path]
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        if result.returncode == 0:
            with open(out_path, "rb") as f:
                return f.read()
    except Exception as e:
        log_message(f"Stitch failed: {e}", Severity.WARNING)
    finally:
        for p in clip_paths + [out_path, "/tmp/_concat_list.txt"]:
            try:
                os.unlink(p)
            except Exception:
                pass
    return clip_bytes_list[0] if clip_bytes_list else None


def _mix_audio_onto_video(video_bytes: bytes, voiceover_bytes: bytes | None,
                           music_bytes: bytes | None) -> bytes:
    """Mixes voiceover (100% volume) and Lyria music (15% volume) onto video using ffmpeg.
    Voiceover and music are trimmed to match video duration exactly."""
    import subprocess

    vid_path = "/tmp/_mix_video.mp4"
    vo_path = "/tmp/_mix_vo.mp3"
    music_path = "/tmp/_mix_music.wav"
    out_path = "/tmp/_mix_output.mp4"

    try:
        with open(vid_path, "wb") as f:
            f.write(video_bytes)

        # Get video duration for precise trimming
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", vid_path],
            capture_output=True, text=True, timeout=10,
        )
        video_duration = float(probe.stdout.strip()) if probe.returncode == 0 else 24.0
        log_message(f"Video duration for audio mix: {video_duration}s", Severity.INFO)

        inputs = ["-i", vid_path]

        if voiceover_bytes:
            with open(vo_path, "wb") as f:
                f.write(voiceover_bytes)
            inputs.extend(["-i", vo_path])

        if music_bytes:
            with open(music_path, "wb") as f:
                f.write(music_bytes)
            inputs.extend(["-i", music_path])

        if not voiceover_bytes and not music_bytes:
            return video_bytes

        # Build filter complex — trim all audio to video duration
        # Voiceover at 100%, Lyria music at 15%
        filter_complex = ""
        mix_inputs = []
        audio_idx = 1

        if voiceover_bytes:
            filter_complex += f"[{audio_idx}:a]atrim=0:{video_duration},asetpts=PTS-STARTPTS,aresample=48000,volume=1.5,afade=t=out:st={video_duration - 1.5}:d=1.5[vo];"
            mix_inputs.append("[vo]")
            audio_idx += 1

        if music_bytes:
            filter_complex += f"[{audio_idx}:a]atrim=0:{video_duration},asetpts=PTS-STARTPTS,aresample=48000,volume=0.30,afade=t=in:st=0:d=1.5,afade=t=out:st={video_duration - 0.5}:d=0.5[music];"
            mix_inputs.append("[music]")
            audio_idx += 1

        if len(mix_inputs) == 1:
            filter_complex = filter_complex.rstrip(";")
            label = mix_inputs[0].strip("[]")
            filter_complex = filter_complex.replace(f"[{label}]", "[aout]")
        else:
            filter_complex += f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:duration=longest:dropout_transition=0[aout]"

        cmd = [
            "ffmpeg", "-y", *inputs,
            "-filter_complex", filter_complex,
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", out_path,
        ]

        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode == 0:
            with open(out_path, "rb") as f:
                return f.read()
        else:
            log_message(f"Audio mix failed: {result.stderr.decode()[:300]}", Severity.WARNING)
            return video_bytes
    except Exception as e:
        log_message(f"Audio mix error: {e}", Severity.WARNING)
        return video_bytes
    finally:
        for p in [vid_path, vo_path, music_path, out_path]:
            try:
                os.unlink(p)
            except Exception:
                pass


def _overlay_logo_on_video(video_bytes: bytes, logo_bytes: bytes, opacity: float = 0.4) -> bytes:
    """Overlays logo on video top-right corner using ffmpeg."""
    import subprocess

    try:
        vid_path = "/tmp/_logo_video.mp4"
        logo_path = "/tmp/_logo.png"
        out_path = "/tmp/_logo_output.mp4"

        with open(vid_path, "wb") as f:
            f.write(video_bytes)
        with open(logo_path, "wb") as f:
            f.write(logo_bytes)

        cmd = [
            "ffmpeg", "-y", "-i", vid_path, "-i", logo_path,
            "-filter_complex",
            f"[1:v]scale=iw*0.12:-1,format=rgba,colorchannelmixer=aa={opacity}[logo];"
            f"[0:v][logo]overlay=W-w-20:20[out]",
            "-map", "[out]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "fast", "-c:a", "copy", out_path,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        if result.returncode == 0:
            with open(out_path, "rb") as f:
                return f.read()
        return video_bytes
    except Exception:
        return video_bytes
    finally:
        for p in [vid_path, logo_path, out_path]:
            try:
                os.unlink(p)
            except Exception:
                pass


def _add_text_overlays(video_bytes: bytes, company_name: str, tagline: str, video_duration: float,
                        product_name: str = "", price: str = "") -> bytes:
    """Adds cinematic text overlays: brand + product at start, tagline mid-video, price near end."""
    import subprocess

    vid_path = "/tmp/_text_video.mp4"
    out_path = "/tmp/_text_output.mp4"

    try:
        with open(vid_path, "wb") as f:
            f.write(video_bytes)

        def _sanitize(text):
            return text.replace("'", "").replace(":", "").replace("\\", "").replace('"', '')

        safe_company = _sanitize(company_name)
        safe_product = _sanitize(product_name)[:40] if product_name else ""
        safe_tagline = _sanitize(tagline)[:50] if tagline else ""
        safe_price = _sanitize(price) if price else ""

        filters = []
        # Brand name — bottom-left, fades in at 0.5s, stays for 4s
        filters.append(
            f"drawtext=text='{safe_company}':fontsize=36:fontcolor=white:borderw=2:bordercolor=black@0.6"
            f":x=40:y=h-80:enable='between(t,0.5,5)':alpha='if(lt(t,1.5),min(1,(t-0.5)),if(gt(t,4),max(0,1-(t-4)),1))'"
        )
        # Product name — below brand, fades in slightly after
        if safe_product:
            filters.append(
                f"drawtext=text='{safe_product}':fontsize=24:fontcolor=white@0.9:borderw=1:bordercolor=black@0.4"
                f":x=40:y=h-50:enable='between(t,1,5.5)':alpha='if(lt(t,2),min(1,(t-1)),if(gt(t,4.5),max(0,1-(t-4.5)),1))'"
            )
        # Tagline — bottom center, appears mid-video for 5s
        if safe_tagline:
            mid = video_duration / 2 - 1
            end = mid + 5
            filters.append(
                f"drawtext=text='{safe_tagline}':fontsize=28:fontcolor=white:borderw=2:bordercolor=black@0.6"
                f":x=(w-text_w)/2:y=h-50:enable='between(t,{mid},{end})':alpha='if(lt(t,{mid+1}),min(1,(t-{mid})),if(gt(t,{end-1}),max(0,1-(t-{end-1})),1))'"
            )
        # Price — bottom-right, appears in last 6 seconds
        if safe_price:
            price_start = video_duration - 6
            filters.append(
                f"drawtext=text='{safe_price}':fontsize=32:fontcolor=white:borderw=2:bordercolor=black@0.6"
                f":x=w-text_w-40:y=h-50:enable='between(t,{price_start},{video_duration})'"
                f":alpha='min(1,(t-{price_start})*2)'"
            )

        filter_str = ",".join(filters)
        cmd = [
            "ffmpeg", "-y", "-i", vid_path,
            "-vf", filter_str,
            "-c:a", "copy", "-c:v", "libx264", "-preset", "fast",
            "-movflags", "+faststart", out_path,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        if result.returncode == 0:
            with open(out_path, "rb") as f:
                return f.read()
        log_message(f"Text overlay failed: {result.stderr.decode()[:200]}", Severity.WARNING)
        return video_bytes
    except Exception as e:
        log_message(f"Text overlay error: {e}", Severity.WARNING)
        return video_bytes
    finally:
        for p in [vid_path, out_path]:
            try:
                os.unlink(p)
            except Exception:
                pass


def _add_end_card(video_bytes: bytes, logo_bytes: bytes | None, company_name: str, tagline: str,
                   duration: float = 3.0, product_bytes: bytes | None = None) -> bytes:
    """Appends a branded end card: dark background, product image, logo, company name, tagline."""
    import subprocess

    vid_path = "/tmp/_endcard_video.mp4"
    logo_path = "/tmp/_endcard_logo.png"
    product_path = "/tmp/_endcard_product.png"
    card_path = "/tmp/_endcard.mp4"
    out_path = "/tmp/_endcard_output.mp4"

    try:
        with open(vid_path, "wb") as f:
            f.write(video_bytes)

        # Get video dimensions
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height,r_frame_rate",
             "-of", "csv=p=0", vid_path],
            capture_output=True, text=True, timeout=10,
        )
        parts = probe.stdout.strip().split(",")
        w, h = int(parts[0]), int(parts[1])

        safe_company = company_name.replace("'", "").replace(":", "")
        safe_tagline = (tagline.replace("'", "").replace(":", "")[:50]) if tagline else ""

        inputs = ["-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:d={duration}:r=24"]
        overlay_idx = 1

        # Add product image input
        has_product = False
        if product_bytes:
            with open(product_path, "wb") as f:
                f.write(product_bytes)
            inputs.extend(["-i", product_path])
            has_product = True
            product_input_idx = overlay_idx
            overlay_idx += 1

        # Add logo input
        has_logo = False
        if logo_bytes:
            with open(logo_path, "wb") as f:
                f.write(logo_bytes)
            inputs.extend(["-i", logo_path])
            has_logo = True
            logo_input_idx = overlay_idx
            overlay_idx += 1

        # Silent audio
        inputs.extend(["-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={duration}"])
        audio_idx = overlay_idx

        # Build filter: product on left, logo+text on right
        filter_complex = ""
        current_label = "0:v"

        if has_product:
            filter_complex += f"[{product_input_idx}:v]scale=-1:{int(h*0.6)}[prod];"
            filter_complex += f"[{current_label}][prod]overlay=W*0.08:(H-h)/2[withprod];"
            current_label = "withprod"

        if has_logo:
            filter_complex += f"[{logo_input_idx}:v]scale=-1:{h//6}[logo];"
            logo_x = "W*0.65" if has_product else "(W-w)/2"
            logo_y = "H*0.25" if has_product else "H*0.3"
            filter_complex += f"[{current_label}][logo]overlay={logo_x}:{logo_y}[withlogo];"
            current_label = "withlogo"

        # Text: company name + tagline
        text_x = "w*0.65" if has_product else "(w-text_w)/2"
        filter_complex += (
            f"[{current_label}]drawtext=text='{safe_company}':fontsize=40:fontcolor=white"
            f":x={text_x}:y=h*0.55:enable='between(t,0.3,{duration})'"
            f":alpha='min(1,(t-0.3)*2)'"
        )
        if safe_tagline:
            filter_complex += (
                f",drawtext=text='{safe_tagline}':fontsize=24:fontcolor=white@0.8"
                f":x={text_x}:y=h*0.65:enable='between(t,0.8,{duration})'"
                f":alpha='min(1,(t-0.8)*2)'"
            )
        filter_complex += "[out]"

        cmd = [
            "ffmpeg", "-y", *inputs,
            "-filter_complex", filter_complex,
            "-map", "[out]", "-map", f"{audio_idx}:a",
            "-c:v", "libx264", "-preset", "fast", "-c:a", "aac",
            "-shortest", card_path,
        ]

        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode != 0:
            log_message(f"End card generation failed: {result.stderr.decode()[:200]}", Severity.WARNING)
            return video_bytes

        # Concat video + end card
        list_file = "/tmp/_endcard_list.txt"
        with open(list_file, "w") as f:
            f.write(f"file '{vid_path}'\nfile '{card_path}'\n")

        concat_cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
            "-c:v", "libx264", "-preset", "fast", "-c:a", "aac",
            "-movflags", "+faststart", out_path,
        ]
        result = subprocess.run(concat_cmd, capture_output=True, timeout=60)
        if result.returncode == 0:
            with open(out_path, "rb") as f:
                return f.read()
        log_message(f"End card concat failed: {result.stderr.decode()[:200]}", Severity.WARNING)
        return video_bytes
    except Exception as e:
        log_message(f"End card error: {e}", Severity.WARNING)
        return video_bytes
    finally:
        for p in [vid_path, logo_path, product_path, card_path, out_path, "/tmp/_endcard_list.txt"]:
            try:
                os.unlink(p)
            except Exception:
                pass


def _add_end_card_overlay(video_bytes: bytes, company_name: str, tagline: str, product_price: str = "") -> bytes:
    """Overlays brand name, tagline, and price on the last 3 seconds of the video — no separate end card."""
    import subprocess

    vid_path = "/tmp/_endoverlay_video.mp4"
    out_path = "/tmp/_endoverlay_output.mp4"

    try:
        with open(vid_path, "wb") as f:
            f.write(video_bytes)

        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", vid_path],
            capture_output=True, text=True, timeout=10,
        )
        duration = float(probe.stdout.strip()) if probe.returncode == 0 else 24.0
        start = max(0, duration - 3)

        def _s(text):
            return text.replace("'", "").replace(":", "").replace("\\", "").replace('"', '')

        safe_company = _s(company_name)
        safe_tagline = _s(tagline)[:50] if tagline else ""
        safe_price = _s(product_price) if product_price else ""

        filters = []
        # Semi-transparent dark bar at bottom for readability
        filters.append(
            f"drawbox=x=0:y=ih*0.75:w=iw:h=ih*0.25:color=black@0.5:t=fill"
            f":enable='between(t,{start},{duration})'"
        )
        # Brand name — large, center
        filters.append(
            f"drawtext=text='{safe_company}':fontsize=44:fontcolor=white"
            f":x=(w-text_w)/2:y=h*0.78:enable='between(t,{start},{duration})'"
            f":alpha='min(1,(t-{start})*3)'"
        )
        # Tagline — below brand
        if safe_tagline:
            filters.append(
                f"drawtext=text='{safe_tagline}':fontsize=26:fontcolor=white@0.9"
                f":x=(w-text_w)/2:y=h*0.87:enable='between(t,{start+0.5},{duration})'"
                f":alpha='min(1,(t-{start+0.5})*3)'"
            )
        # Price — bottom right
        if safe_price:
            filters.append(
                f"drawtext=text='{safe_price}':fontsize=32:fontcolor=white"
                f":x=w-text_w-30:y=h*0.92:enable='between(t,{start+0.5},{duration})'"
                f":alpha='min(1,(t-{start+0.5})*3)'"
            )

        cmd = [
            "ffmpeg", "-y", "-i", vid_path,
            "-vf", ",".join(filters),
            "-c:a", "copy", "-c:v", "libx264", "-preset", "fast",
            "-movflags", "+faststart", out_path,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        if result.returncode == 0:
            with open(out_path, "rb") as f:
                return f.read()
        log_message(f"End card overlay failed: {result.stderr.decode()[:200]}", Severity.WARNING)
        return video_bytes
    except Exception as e:
        log_message(f"End card overlay error: {e}", Severity.WARNING)
        return video_bytes
    finally:
        for p in [vid_path, out_path]:
            try:
                os.unlink(p)
            except Exception:
                pass


async def _generate_full_video_ad(
    rationale: str, product_image_uri: str,
    company_name: str, product_name: str,
    tool_context: ToolContext,
) -> bytes | None:
    """Full video ad pipeline — 3 acts, 24 seconds + 3s end card.

    Keyframe strategy: 4 keyframes (KF1, KF2, KF3, KF4)
      Act 1: KF1 → KF2 (8s) — SETUP (bright/daylight)
      Act 2: KF2 → KF3 (8s) — BUILD (golden hour/dramatic)
      Act 3: KF3 → KF4 (8s) — RESOLVE (evening/night)
      End card: 3s — logo + brand name + tagline on black

    Pipeline (optimized — Lyria/TTS overlap with keyframes + VEO):
      1. Gemini → 3-act storyline
      2. IN PARALLEL (fire-and-forget):
         ├── Lyria 3 → background music
         └── Cloud TTS Chirp3-HD → voiceover audio
      3. Gemini Image → 4 keyframe images (parallel)
      4. Upload keyframes to GCS
      5. VEO 3.1 → 3 clips (parallel), poll every 10s
      6. Collect Lyria + TTS results (already done by now)
      7. ffmpeg → stitch + audio mix + logo overlay
    """
    import time as _time
    _pipeline_start = _time.time()

    ACTS = 3
    CLIP_SEC = 8
    NUM_KEYFRAMES = ACTS + 1  # 4 keyframes for 3 acts

    # Step 0: Download product image + logo
    try:
        product_bytes, _ = utils_agents.download_bytes_from_reference(product_image_uri)
    except Exception as e:
        log_message(f"Could not download product image: {e}", Severity.ERROR)
        return None

    logo_bytes = None
    logo_uri = tool_context.state.get(LOGO_IMAGE_URI_STATE_KEY)
    if logo_uri:
        try:
            logo_bytes, _ = utils_agents.download_bytes_from_reference(logo_uri)
        except Exception:
            pass

    # Retrieve reference guidelines and customer persona from session state
    ref_guidelines = tool_context.state.get(REFERENCE_GUIDELINES_STATE_KEY, "")
    customer_persona = tool_context.state.get(CUSTOMER_PERSONA_STATE_KEY, "")

    # ================================================================
    # PHASE 1: Storyline (needed before keyframes)
    # Lyria + Voiceover start later alongside VEO to overlap
    # ================================================================
    log_message("Phase 1: Storyline...", Severity.INFO)

    storyline_data = {}
    try:
        storyline_data = await _generate_storyline(
            company_name, product_name, rationale,
            reference_guidelines=ref_guidelines, customer_persona=customer_persona,
        )
        if not isinstance(storyline_data, dict):
            storyline_data = {}
    except Exception as e:
        log_message(f"Storyline failed: {e}", Severity.WARNING)

    voiceover_script = storyline_data.get("storyline", "")
    lyria_prompt_from_storyline = storyline_data.get("lyria_prompt", "")
    acts = storyline_data.get("acts", [])
    while len(acts) < ACTS:
        acts.append(acts[-1] if acts else {"scene_description": "Hero shot", "motion_prompt": "Slow push-in"})
    acts = acts[:ACTS]

    # Start voiceover + Lyria immediately — they run alongside keyframes + VEO
    vo_task = asyncio.create_task(_generate_voiceover_audio(voiceover_script))
    lyria_task = asyncio.create_task(_generate_lyria_music(lyria_prompt_from_storyline, product_name))

    # ================================================================
    # PHASE 2: Generate 5 keyframe images in parallel
    # Each keyframe MUST be a COMPLETELY DIFFERENT scene/environment
    # ================================================================
    log_message(f"Phase 2: Generating {NUM_KEYFRAMES} distinct keyframes...", Severity.INFO)
    refs = [product_bytes] + ([logo_bytes] if logo_bytes else [])

    # 4 keyframes with DRAMATIC bright-to-dark progression — wow visual transitions
    kf_environments = [
        "BRIGHT DAYLIGHT — vivid sunlight, clean blue sky, sharp shadows. Fresh, energetic, vibrant. High-key lighting.",
        "GOLDEN HOUR — warm amber backlighting, lens flares, dramatic long shadows. Wind visible in environment. Magical warmth.",
        "DRAMATIC DUSK — deep orange and purple sky, silhouette edges, moody atmosphere. Cinematic transition moment. Wow factor.",
        "NIGHT / NEON — dark environment with dramatic artificial lighting. City lights, neon reflections, glowing edges on product. High contrast, bold.",
    ]

    kf_descriptions = [
        acts[0].get("scene_description", f"Bright reveal of {product_name} in daylight"),
        acts[0].get("end_scene_description", acts[1].get("scene_description", f"{product_name} in golden hour")),
        acts[1].get("end_scene_description", acts[2].get("scene_description", f"{product_name} at dramatic dusk")),
        acts[2].get("end_scene_description", f"Hero shot of {product_name} in dramatic night lighting with {company_name}"),
    ]

    # Build guidelines and persona context for keyframes
    kf_guidelines = ""
    if ref_guidelines:
        kf_guidelines = (
            f"\nBRAND GUIDELINES (follow for visual style and tone): {ref_guidelines[:500]}\n"
        )
    kf_persona = ""
    if customer_persona:
        kf_persona = (
            f"\nCUSTOMER PERSONA (tailor scene to this audience): {customer_persona}\n"
            f"Show people, environments, and scenarios that resonate with this specific customer type.\n"
        )

    async def _gen_kf(idx):
        is_final = idx == NUM_KEYFRAMES - 1
        prompt = (
            f"Photorealistic commercial photograph for a {product_name} ad by {company_name}.\n"
            f"Keyframe #{idx + 1} of {NUM_KEYFRAMES} — these keyframes form a connected visual story.\n\n"
            f"SCENE: {kf_descriptions[idx]}\n\n"
            f"LIGHTING & ATMOSPHERE: {kf_environments[idx]}\n\n"
            f"PRODUCT IN REAL LIFE — ABSOLUTELY CRITICAL:\n"
            f"- Study the reference image (first attached image) to understand what the product looks like\n"
            f"- Show the product in a REAL, GROUNDED scenario — as if photographed on set:\n"
            f"  * Bottles/drinks → standing on a solid surface (bar, table, shelf), being poured, held in hand\n"
            f"  * Boots/shoes → being WORN on feet, on the ground, on a shelf\n"
            f"  * Electronics → on a desk, held by a person, in a bag, plugged in\n"
            f"  * Jewelry/accessories → being worn, in a case, on a display\n"
            f"- PHYSICS MUST BE REAL: gravity applies, liquids flow downward, objects rest on surfaces\n"
            f"- NOTHING floats, hovers, or defies gravity unless it's an actual flying product (drone)\n"
            f"- NO magical suspended ingredients, NO floating particles, NO surreal compositions\n"
            f"- Product MUST be at REAL-WORLD physical size — proportional to surroundings\n"
            f"- Reproduce the product with exact fidelity — same shape, color, design as reference\n"
            f"- Do NOT add features not in the reference — no extra buttons, shutters, ports, or internal parts\n"
            f"- Show the product as a RETAIL item exactly as it appears in the reference photo\n\n"
            f"CINEMATIC WOW FACTOR (real-world magic, not fantasy):\n"
            f"- Use dramatic LIGHTING as the wow element: shafts of sunlight, spotlight illumination,\n"
            f"  neon reflections, candlelight glow, window light patterns, golden hour backlight\n"
            f"- Use ENVIRONMENT storytelling: rain on window, steam rising, ice condensation on glass,\n"
            f"  fireplace glow, city lights bokeh, morning mist, reflections in polished surfaces\n"
            f"- Use COMPOSITION: rule of thirds, leading lines, reflections, shallow depth of field\n"
            f"- Think luxury commercial (Johnnie Walker, Rolex, Mercedes) — premium but REAL\n"
            f"- Each keyframe MUST look dramatically different from others (bright→golden→dusk→night)\n\n"
            f"SUBJECT CONSISTENCY FOR SMOOTH VIDEO TRANSITIONS:\n"
            f"- Any person or animal MUST face the SAME general direction across all keyframes\n"
            f"- The subject should be in a SIMILAR position and pose — only the environment/lighting changes\n"
            f"- Do NOT flip, rotate, or dramatically reposition the subject between keyframes\n"
            f"- The product must stay in the SAME relative position in the frame across keyframes\n"
            f"- This prevents morphing/distortion artifacts when the video transitions between scenes\n\n"
            f"VIDEO SAFETY — CRITICAL FOR ALL KEYFRAMES:\n"
            f"- The PRODUCT must be the hero of every keyframe — center of attention, clearly visible\n"
            f"- If people appear, show them from behind, side angle, or at a distance — NOT close-up faces\n"
            f"- NEVER show close-up faces of children, minors, or babies\n"
            f"- Focus on the product in its environment, with people as supporting context (blurred background, silhouettes, hands only)\n"
            f"- This ensures the keyframes pass video generation safety checks\n\n"
            f"ANTI-HALLUCINATION — CRITICAL:\n"
            f"- Every keyframe must depict a scene that ACTUALLY EXISTS in real life\n"
            f"- NO supernatural events, NO impossible physics, NO fantasy elements\n"
            f"- The product must look EXACTLY like the reference — no added features, no transformations\n"
            f"- Scenes must be mundane and realistic — a real room, a real street, a real table\n"
            f"- Nothing should surprise a viewer as 'that could never happen in real life'\n\n"
            f"{'Include brand name ' + company_name + ' as elegant text in the scene.' if is_final else ''}"
            f"{kf_guidelines}{kf_persona}"
            f"Product at CORRECT real-world scale. 16:9 landscape. Single image. Return only the image."
        )
        return await _generate_gemini_image(prompt, refs, label=f"keyframe {idx + 1}/{NUM_KEYFRAMES}")

    # Generate all keyframes in parallel
    kf_results = await asyncio.gather(
        *[_gen_kf(i) for i in range(NUM_KEYFRAMES)],
        return_exceptions=True,
    )
    keyframes = [r if isinstance(r, bytes) else product_bytes for r in kf_results]
    log_message(f"Keyframes: {sum(1 for r in kf_results if isinstance(r, bytes))}/{NUM_KEYFRAMES} generated", Severity.INFO)

    # Upload keyframes to GCS — parallel
    kf_blobs = [f"{OUTPUT_FOLDER}/_keyframe_{i + 1}.png" for i in range(NUM_KEYFRAMES)]
    await asyncio.gather(*[
        asyncio.to_thread(utils_gcs.upload_to_gcs, GOOGLE_CLOUD_BUCKET_ARTIFACTS, img, blob)
        for img, blob in zip(keyframes, kf_blobs)
    ])
    kf_uris = [f"gs://{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{blob}" for blob in kf_blobs]

    # ================================================================
    # PHASE 3: VEO clips — all parallel (voiceover + Lyria already in flight)
    # ================================================================
    log_message("Phase 3: VEO clips (parallel, voiceover + Lyria already in flight)...", Severity.INFO)

    transition_effects = [
        "SEAMLESS FLOW: Camera glides forward through the scene in one unbroken move — passing through doorways, around corners, or across surfaces. The environment evolves naturally as the camera moves. Think 1917-style continuous shot. No cuts, no jumps.",
        "REVEAL MOMENT: Something in the scene triggers a dramatic shift — a match lights, a curtain parts, rain begins, golden light floods in. The camera follows this moment smoothly, revealing the product in its new context. Build anticipation then payoff.",
        "CONVERGENCE: Multiple elements in the scene gravitate toward the product — light narrows, focus sharpens, environment simplifies. The camera pulls in with purpose, like the whole world is pointing to this one moment. Triumphant, inevitable.",
    ]

    def _build_motion_prompt(act_idx):
        act = acts[act_idx]
        base_motion = act.get("motion_prompt", f"Cinematic shot of {product_name}")
        transition = transition_effects[min(act_idx, len(transition_effects) - 1)]
        return (
            f"{base_motion}. "
            f"TRANSITION EFFECT: {transition} "
            f"CRITICAL: The camera MUST be in CONTINUOUS SMOOTH MOTION for the entire {CLIP_SEC} seconds — "
            f"no static frames, no pauses, no freeze frames. Constant cinematic movement throughout. "
            f"Use smooth dolly, steadicam, or crane moves — like a high-end commercial. "
            f"REAL-LIFE PHYSICS — ABSOLUTE REQUIREMENT: "
            f"This video must look like it was filmed in REAL LIFE with a real camera. "
            f"OBJECTS DO NOT MOVE BY THEMSELVES: bottles stay where placed, mats stay on the floor, "
            f"food stays on the counter, glasses stay on tables. NOTHING slides, rolls, falls, or teleports on its own. "
            f"Only a human hand physically touching an object can move it. "
            f"OBJECTS DO NOT CHANGE LOCATION: if vegetables are on the countertop, they stay on the countertop — "
            f"they do NOT suddenly appear on the island or a different surface. Everything stays where it was placed. "
            f"PRODUCT {product_name} — ABSOLUTE RULES: "
            f"The product must NEVER change size, open, close, fold, unfold, transform, or animate. "
            f"NO lens opening, NO shutter closing, NO parts moving, NO lights blinking on/off, NO mechanical motion. "
            f"The product is a SEALED, STATIC, MOTIONLESS object — like a prop on a shelf. "
            f"It does NOT do anything. It just SITS THERE. Only the ENVIRONMENT and PEOPLE move around it. "
            f"The product looks EXACTLY like the reference photo at ALL times — no added parts, no removed parts. "
            f"If it is a camera, it does NOT zoom, pan, tilt, open a lens, or activate. It is OFF and STILL. "
            f"PEOPLE MOVE NATURALLY: walking is smooth, arms move realistically, no sudden jumps or teleporting. "
            f"Think of this as a REAL video shot with a REAL camera — nothing magical, nothing impossible."
        )

    async def _gen_clip(act_idx):
        label = f"act{act_idx + 1}/{ACTS}"
        motion = _sanitize_veo_prompt(_build_motion_prompt(act_idx))
        start_uri = kf_uris[act_idx]
        end_uri = kf_uris[act_idx + 1]

        result = await _generate_single_veo_clip(motion, start_uri, CLIP_SEC, end_uri, label=label)
        if result is None:
            log_message(f"Clip {label} interpolation failed, retrying as i2v (no end frame)", Severity.WARNING)
            result = await _generate_single_veo_clip(motion, start_uri, CLIP_SEC, None, label=f"{label}-retry")
        return act_idx, result

    veo_results = await asyncio.gather(
        *[_gen_clip(i) for i in range(ACTS)],
        return_exceptions=True,
    )

    # Collect results, track which acts failed
    clip_map: dict[int, bytes] = {}
    failed_acts: list[int] = []
    for r in veo_results:
        if isinstance(r, Exception):
            log_message(f"VEO clip raised exception: {r}", Severity.ERROR)
            continue
        act_idx, clip_bytes = r
        if isinstance(clip_bytes, bytes):
            clip_map[act_idx] = clip_bytes
        else:
            failed_acts.append(act_idx)

    # Retry failed clips one more time (sequential to avoid quota collision)
    for act_idx in failed_acts:
        label = f"act{act_idx + 1}/{ACTS}-retry-final"
        motion = _build_motion_prompt(act_idx)
        log_message(f"Final retry for failed clip {label}", Severity.WARNING)
        result = await _generate_single_veo_clip(motion, kf_uris[act_idx], CLIP_SEC, None, label=label)
        if isinstance(result, bytes):
            clip_map[act_idx] = result
        else:
            log_message(f"Clip {label} failed after all retries", Severity.ERROR)

    # Save individual clips to GCS
    for act_idx, clip_bytes in clip_map.items():
        clip_blob = f"{OUTPUT_FOLDER}/clip_act{act_idx + 1}.mp4"
        try:
            await asyncio.to_thread(
                utils_gcs.upload_to_gcs,
                GOOGLE_CLOUD_BUCKET_ARTIFACTS, clip_bytes, clip_blob,
            )
            log_message(f"Saved clip act{act_idx + 1} to GCS: {clip_blob}", Severity.INFO)
        except Exception as e:
            log_message(f"Failed to save clip act{act_idx + 1} to GCS: {e}", Severity.WARNING)

    # Assemble clips in act order
    clips = [clip_map[i] for i in sorted(clip_map.keys())]

    # Collect voiceover + Lyria (should be done by now — started before keyframes)
    vo_bytes = None
    try:
        vo_bytes = await vo_task
    except Exception as e:
        log_message(f"Voiceover failed: {e}", Severity.WARNING)

    music_bytes = None
    try:
        lyria_result = await lyria_task
        if isinstance(lyria_result, bytes):
            music_bytes = lyria_result
            music_filename = f"background_music_{int(time.time())}.mp3"
            utils_gcs.upload_to_gcs(
                bucket_path=GOOGLE_CLOUD_BUCKET_ARTIFACTS,
                file_bytes=music_bytes,
                destination_blob_name=f"{OUTPUT_FOLDER}/{music_filename}",
            )
            log_message(f"Lyria music saved to GCS: {OUTPUT_FOLDER}/{music_filename}", Severity.INFO)
    except Exception as e:
        log_message(f"Lyria music failed: {e}", Severity.WARNING)

    log_message(
        f"Results: {len(clips)}/{ACTS} clips, "
        f"music={'yes' if music_bytes else 'no'}, "
        f"voiceover={'yes' if vo_bytes else 'no'}",
        Severity.INFO,
    )

    if not clips:
        log_message("No clips generated — video failed", Severity.ERROR)
        return None

    # ================================================================
    # PHASE 4: Post-production — stitch + audio + text overlays + end card
    # ================================================================
    log_message("Phase 4: Stitch + audio + text overlays + end card...", Severity.INFO)
    stitched = _stitch_videos(clips) if len(clips) > 1 else clips[0]
    if not stitched:
        stitched = clips[0]

    final = _mix_audio_onto_video(stitched, vo_bytes, music_bytes)

    if logo_bytes:
        final = _overlay_logo_on_video(final, logo_bytes, opacity=0.4)

    # Get tagline from campaign data
    campaign_tagline = ""
    if _CACHED_CAMPAIGNS_LIST:
        chosen = tool_context.state.get(CHOSEN_CAMPAIGN_IDEA_STATE_KEY, "")
        for c in _CACHED_CAMPAIGNS_LIST:
            if c.name == chosen:
                campaign_tagline = c.tagline or ""
                break

    # Text overlays — brand name + product name + tagline + price
    video_dur = len(clips) * CLIP_SEC
    product_price = ""
    product_data = tool_context.state.get("product", {})
    if isinstance(product_data, dict):
        cs = product_data.get("commercial_status", {})
        if cs and cs.get("current_price"):
            product_price = f"Price ${cs['current_price']:.2f}"
    final = _add_text_overlays(final, company_name, campaign_tagline, video_dur,
                                product_name=product_name, price=product_price)

    # End card overlay — brand + tagline + price on the last 3 seconds of the video (no separate card)
    final = _add_end_card_overlay(final, company_name, campaign_tagline, product_price=product_price)

    # Rename keyframes from temp prefix to permanent names
    for i in range(NUM_KEYFRAMES):
        try:
            old_blob = f"{OUTPUT_FOLDER}/_keyframe_{i + 1}.png"
            new_blob = f"{OUTPUT_FOLDER}/keyframe_{i + 1}.png"
            from google.cloud import storage as gcs_storage
            bucket = gcs_storage.Client(project=GOOGLE_CLOUD_PROJECT).bucket(GOOGLE_CLOUD_BUCKET_ARTIFACTS)
            src = bucket.blob(old_blob)
            if src.exists():
                bucket.rename_blob(src, new_blob)
                log_message(f"Kept keyframe {i + 1} in GCS: {new_blob}", Severity.INFO)
        except Exception:
            pass

    processing_time = _time.time() - _pipeline_start
    video_length = len(clips) * CLIP_SEC
    log_message(
        f"Video ad complete: processing_time={processing_time:.0f}s, "
        f"video_length={video_length}s, size={len(final):,} bytes, clips={len(clips)}",
        Severity.INFO,
    )
    return final, processing_time, video_length


def save_selected_asset_sheet(asset_sheet_uri: str, tool_context: ToolContext, selected_campaign_name: str):
    """Saves the user's chosen asset sheet.

    Args:
        asset_sheet_uri: URL of the selected asset sheet.
        selected_campaign_name: Name of the selected campaign.
    """
    tool_context.state[CHOSEN_ASSET_SHEET_ID_STATE_KEY] = asset_sheet_uri
    return {"status": "success", "details": f"Saved asset sheet: {asset_sheet_uri}"}


def recommend_campaign_settings(tool_context: ToolContext, segment_name: str, selected_campaign_name: str):
    """Recommends campaign launch settings for a segment.

    Args:
        segment_name: Target audience segment.
        selected_campaign_name: Name of the selected campaign.
    """
    campaigns = _get_and_cache_campaigns(tool_context)
    campaign = find_campaign_by_name(campaigns, selected_campaign_name)
    if not campaign:
        return {"status": "error", "details": "Campaign not found."}
    segment = campaign.get_segment_by_name(segment_name)
    if not segment:
        return {"status": "error", "details": "Segment not found."}
    return {
        "campaign_settings": segment.campaign_settings,
        "optimization_note": segment.optimization_note,
    }


def get_stocking_projection(tool_context: ToolContext, selected_campaign_name: str):
    """Returns stocking projection and optimization suggestions.

    Args:
        selected_campaign_name: Name of the selected campaign.
    """
    campaigns = _get_and_cache_campaigns(tool_context)
    campaign = find_campaign_by_name(campaigns, selected_campaign_name)
    if not campaign:
        return {"status": "error", "details": "Campaign not found."}
    return {"suggested_optimization": campaign.suggested_optimization}


# ============================================================
# Customer Personalization
# ============================================================

def set_customer_persona(tool_context: ToolContext, persona_number: int):
    """Sets the customer persona for personalized ad generation.
    Call this AFTER the user selects a persona number (1-5).
    When set, all subsequent text ads, image ads, and video ads will be
    tailored to this customer type.

    Args:
        persona_number: The persona number (1-5):
            1 = Family with Kids
            2 = Vacation/Travel Enthusiast
            3 = Young Professional
            4 = Fitness/Wellness Seeker
            5 = Luxury/Premium Lifestyle
    """
    if persona_number not in CUSTOMER_PERSONAS:
        return {
            "status": "error",
            "details": f"Invalid persona number {persona_number}. Choose 1-5.",
            "options": {k: v["name"] for k, v in CUSTOMER_PERSONAS.items()},
        }

    persona = CUSTOMER_PERSONAS[persona_number]
    tool_context.state[CUSTOMER_PERSONA_STATE_KEY] = persona["description"]
    _set_output_folder(tool_context)

    return {
        "status": "success",
        "persona_name": persona["name"],
        "persona_description": persona["description"],
        "details": f"Personalization set: {persona['name']}. All ads will be tailored to this customer type.",
    }


def clear_customer_persona(tool_context: ToolContext):
    """Clears the customer persona, reverting to generic (non-personalized) ad generation."""
    tool_context.state[CUSTOMER_PERSONA_STATE_KEY] = ""
    return {"status": "success", "details": "Personalization cleared. Ads will use default targeting."}


# ============================================================
# Text Ad Generation
# ============================================================

async def generate_text_ad(
    tool_context: ToolContext, segment_name: str,
    selected_campaign_name: str,
):
    """Generates a text ad for a specific audience segment and saves it to a file in GCS.
    This should be called BEFORE generating image ads to establish the messaging foundation.

    Args:
        segment_name: Target audience segment name.
        selected_campaign_name: Name of the selected campaign.
    """
    _set_output_folder(tool_context)
    campaigns = _get_and_cache_campaigns(tool_context)
    campaign = find_campaign_by_name(campaigns, selected_campaign_name)
    if not campaign:
        return {"status": "error", "details": f"No campaign named '{selected_campaign_name}'"}

    segment = campaign.get_segment_by_name(segment_name)
    if not segment:
        return {"status": "error", "details": f"No segment named '{segment_name}'"}

    company_name = tool_context.state.get(PRODUCT_COMPANY_NAME_STATE_KEY, "")
    product_name = tool_context.state.get("PRODUCT_NAME", "product")
    ref_guidelines = tool_context.state.get(REFERENCE_GUIDELINES_STATE_KEY, "")
    customer_persona = tool_context.state.get(CUSTOMER_PERSONA_STATE_KEY, "")

    client = genai.Client(vertexai=True, project=GOOGLE_CLOUD_PROJECT, location="global")

    guidelines_context = ""
    if ref_guidelines:
        guidelines_context = f"\nBrand Guidelines (MUST follow): {ref_guidelines[:500]}\n"

    persona_context = ""
    if customer_persona:
        persona_context = (
            f"\nCUSTOMER PERSONA (MUST tailor all copy to this persona):\n{customer_persona}\n"
            f"All messaging, tone, and CTAs must resonate with this specific customer type.\n"
        )

    prompt = (
        f"You are a world-class advertising copywriter for Google Ads.\n\n"
        f"Generate a Responsive Search Ad for:\n"
        f"Brand: {company_name}\nProduct: {product_name}\n"
        f"Campaign: {campaign.name}\nTagline: {campaign.tagline}\n"
        f"Campaign Hook: {campaign.hook}\n"
        f"Target Audience Segment: {segment.name}\n"
        f"{guidelines_context}{persona_context}\n\n"
        f"Output ONLY valid JSON in this EXACT format (no markdown, no code fences):\n\n"
        f'{{"headlines": ["Headline 1", "Headline 2", "Headline 3"], '
        f'"descriptions": ["Description 1", "Description 2", "Description 3"]}}\n\n'
        f"Rules:\n"
        f"- headlines: EXACTLY 3 headlines, each max 30 characters\n"
        f"- descriptions: EXACTLY 3 descriptions, each max 90 characters\n"
        f"- Headlines must be punchy, attention-grabbing, and distinct from each other\n"
        f"- Descriptions must expand on the value proposition with clear benefits\n"
        f"- Include brand name in at least one headline\n"
        f"- Include a call-to-action in at least one description\n"
        f"- Be concise, persuasive, and on-brand\n"
        f"- NEVER invent product features not in the campaign brief\n"
        f"- Match the tone to the target audience segment\n"
    )

    try:
        response = await _retry_generate_content(
            client, "gemini-3.1-pro-preview", prompt,
            config=types.GenerateContentConfig(
                temperature=0.8, max_output_tokens=1024,
                response_mime_type="application/json",
            ),
            label="text-ad",
        )
        text_ad_data = json.loads(response.text)
    except Exception as e:
        log_message(f"Text ad generation failed, using fallback: {e}", Severity.WARNING)
        text_ad_data = {
            "headlines": [
                campaign.tagline[:30],
                f"{product_name} by {company_name}"[:30],
                f"Discover {product_name}"[:30],
            ],
            "descriptions": [
                f"{campaign.hook}"[:90],
                f"Experience what makes {product_name} extraordinary. Shop now."[:90],
                f"Premium {product_name} designed for {segment.name}. Learn more."[:90],
            ],
        }

    # Save to GCS as JSON
    ts = int(time.time())
    safe_segment = segment.name.replace(" ", "_").replace("/", "_")[:30]
    filename = f"text_ad_{safe_segment}_{ts}.json"
    blob_path = f"{OUTPUT_FOLDER}/{filename}"

    ad_with_metadata = {
        "campaign": campaign.name,
        "segment": segment.name,
        "brand": company_name,
        "product": product_name,
        **text_ad_data,
    }

    utils_gcs.upload_to_gcs(
        bucket_path=GOOGLE_CLOUD_BUCKET_ARTIFACTS,
        file_bytes=json.dumps(ad_with_metadata, indent=2).encode("utf-8"),
        destination_blob_name=blob_path,
    )
    gcs_url = f"https://storage.googleapis.com/{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{blob_path}"

    log_message(f"Text ad saved to GCS: {gcs_url}", Severity.INFO)

    headlines = text_ad_data.get("headlines", [])
    descriptions = text_ad_data.get("descriptions", [])
    tool_context.state["_last_text_ad_headlines"] = headlines
    tool_context.state["_last_text_ad_descriptions"] = descriptions

    return {
        "status": "success",
        "headlines": headlines,
        "descriptions": descriptions,
        "gcs_url": gcs_url,
        "filename": filename,
    }


# ============================================================
# Dynamic Instruction Provider
# ============================================================

def _dynamic_instruction_provider(context: ReadonlyContext) -> str:
    prompt_path = os.path.join(os.path.dirname(__file__), "prompt.md")
    with open(prompt_path, "r") as f:
        prompt_template = f.read()

    company_name = context.state.get(PRODUCT_COMPANY_NAME_STATE_KEY, DEMO_COMPANY_NAME)
    selected_campaign = context.state.get(CHOSEN_CAMPAIGN_IDEA_STATE_KEY, "Not selected yet")
    selected_asset_sheet = context.state.get(CHOSEN_ASSET_SHEET_ID_STATE_KEY, "Not selected yet")
    product_setup_done = context.state.get(PRODUCT_SETUP_DONE_STATE_KEY, False)

    reference_guidelines = context.state.get(REFERENCE_GUIDELINES_STATE_KEY, "")
    has_guidelines = "Yes — guidelines loaded and active" if reference_guidelines else "No reference documents provided"

    prompt = prompt_template.replace("{{AGENT_NAME}}", "LayoAgent")
    prompt = prompt_template.replace("{{DEMO_COMPANY_NAME}}", str(company_name))
    prompt = prompt.replace("{{SELECTED_CAMPAIGN_NAME}}", str(selected_campaign))
    prompt = prompt.replace("{{SELECTED_ASSET_SHEET_URI}}", str(selected_asset_sheet))
    prompt = prompt.replace("{{PRODUCT_SETUP_DONE}}", str(product_setup_done))
    prompt = prompt.replace("{{REFERENCE_GUIDELINES_STATUS}}", has_guidelines)
    return prompt


# ============================================================
# ADK Skills (progressive disclosure — loaded on demand)
# ============================================================

_SKILLS_DIR = os.path.join(os.path.dirname(__file__), "skills")

_marketing_skills = SkillToolset(
    skills=[
        load_skill_from_dir(os.path.join(_SKILLS_DIR, "ad-copywriting")),
        load_skill_from_dir(os.path.join(_SKILLS_DIR, "video-storytelling")),
        load_skill_from_dir(os.path.join(_SKILLS_DIR, "visual-direction")),
        load_skill_from_dir(os.path.join(_SKILLS_DIR, "brand-strategy")),
        load_skill_from_dir(os.path.join(_SKILLS_DIR, "trend-analysis")),
        load_skill_from_dir(os.path.join(_SKILLS_DIR, "platform-specs")),
    ],
)

# ============================================================
# A2A — Google Ads Publisher (via A2A Python SDK)
# ============================================================

async def publish_to_google_ads(
    tool_context: ToolContext,
    account_id: str,
    customer_id: str,
    is_mcc: bool,
    budget: float,
    final_urls: list[str],
    location_id_targeting: str,
    language_id_targeting: str,
):
    """Publishes the generated campaign to Google Ads as a Performance Max (PMAX) campaign via A2A.

    Auto-populates headlines, descriptions, image URIs, video URIs, logo, and business name
    from session state. The user only needs to provide Google Ads account details.

    Args:
        account_id: The Google Ads login customer ID (e.g. "<your-account-id>").
        customer_id: The target customer ID (e.g. "<your-customer-id>").
        is_mcc: Whether account_id is a Manager (MCC) account.
        budget: Daily budget in the account's currency.
        final_urls: Landing page URLs (e.g. ["http://www.example.com"]).
        location_id_targeting: Comma-separated location IDs (e.g. "1023191").
        language_id_targeting: Language ID (e.g. "1000" for English).
    """
    # Auto-populate from session state
    business_name = tool_context.state.get(PRODUCT_COMPANY_NAME_STATE_KEY, "")
    product_name = tool_context.state.get("PRODUCT_NAME", "")
    logo_uri = tool_context.state.get(LOGO_IMAGE_URI_STATE_KEY, "")

    # Collect generated asset URIs — first try session, then scan GCS folder
    _set_output_folder(tool_context)
    session_artifacts = tool_context.state.get("SESSION_ARTIFACTS_STATE", {})
    image_uris = []
    video_uris = []
    for entry in session_artifacts.values():
        asset = entry.get("asset", {})
        gcs_uri = asset.get("gcs_uri", "")
        mime = asset.get("mime_type", "")
        if "image" in mime and gcs_uri:
            image_uris.append(gcs_uri)
        elif "video" in mime and gcs_uri:
            video_uris.append(gcs_uri)

    # If session is empty, scan GCS folder for existing assets
    if not image_uris and not video_uris:
        try:
            from google.cloud import storage as gcs_storage
            storage_client = gcs_storage.Client(project=GOOGLE_CLOUD_PROJECT)
            bucket = storage_client.bucket(GOOGLE_CLOUD_BUCKET_ARTIFACTS)
            for blob in bucket.list_blobs(prefix=f"{OUTPUT_FOLDER}/", max_results=50):
                uri = f"gs://{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{blob.name}"
                name = blob.name.split("/")[-1]
                if name.endswith(".png") and not name.endswith("_resized.png"):
                    image_uris.append(uri)
                elif name.endswith(".mp4"):
                    video_uris.append(uri)
        except Exception as e:
            log_message(f"GCS scan for existing assets failed: {e}", Severity.WARNING)

    # Get headlines/descriptions — first try session, then try GCS text ad JSON
    headlines = tool_context.state.get("_last_text_ad_headlines", [])
    descriptions = tool_context.state.get("_last_text_ad_descriptions", [])
    if not headlines:
        try:
            from google.cloud import storage as gcs_storage
            storage_client = gcs_storage.Client(project=GOOGLE_CLOUD_PROJECT)
            bucket = storage_client.bucket(GOOGLE_CLOUD_BUCKET_ARTIFACTS)
            for blob in bucket.list_blobs(prefix=f"{OUTPUT_FOLDER}/text_ad_", max_results=1):
                text_ad_json = json.loads(blob.download_as_text())
                headlines = text_ad_json.get("headlines", [])
                descriptions = text_ad_json.get("descriptions", [])
                break
        except Exception:
            pass
    if not headlines:
        headlines = [product_name[:30], business_name[:30], f"Discover {product_name}"[:30]]
    if not descriptions:
        descriptions = [f"Discover {product_name} by {business_name}."[:90], f"Premium {product_name}. Shop now."[:90]]

    # Build payload matching create_pmax_campaign signature exactly
    publish_payload = {
        "account_id": account_id,
        "is_mcc": is_mcc,
        "customer_id": customer_id,
        "business_name": business_name,
        "logo_uri": logo_uri,
        "brand_guidelines_enabled": True,
        "final_urls": final_urls,
        "final_mobile_urls": final_urls,
        "budget": budget,
        "location_id_targeting": location_id_targeting,
        "negative_location_id_targeting": "1022762",
        "language_id_targeting": language_id_targeting,
        "headlines": headlines,
        "descriptions": descriptions,
        "long_headlines": headlines[:3],
        "marketing_image_asset_gcs_uris": image_uris[:20],
        "square_marketing_image_asset_gcs_uris": [logo_uri] if logo_uri else image_uris[:3],
        "search_theme": product_name,
        "audience_id": None,
        "portrait_marketing_image_asset_gcs_uris": None,
        "video_asset_gcs_uris": video_uris[:20],
    }

    try:
        import sys
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        from ads_agent.agent import create_pmax_campaign

        result = create_pmax_campaign(**publish_payload)
        log_message(f"Google Ads publish result: {result}", Severity.INFO)
        return {
            "status": result.get("status", "UNKNOWN"),
            "published_payload": publish_payload,
            "google_ads_response": result.get("response", ""),
        }
    except ImportError:
        log_message("ads_agent not available, returning payload for manual publish", Severity.WARNING)
        return {
            "status": "manual_review",
            "published_payload": publish_payload,
            "details": "Google Ads agent not available. Use the payload above to create the campaign manually.",
        }
    except Exception as e:
        log_message(f"Google Ads publish failed: {e}", Severity.ERROR)
        return {"status": "error", "details": str(e), "published_payload": publish_payload}

# ============================================================
# Root Agent Definition
# ============================================================

root_agent = Agent(
    name="marketing_agent",
    model="gemini-3.1-pro-preview",
    instruction=_dynamic_instruction_provider,
    description="Combined Marketing Campaign Agent for generating image ads and video ads. "
                "Combines retail analytics, trend analysis, brand-aware creative direction, "
                "and on-demand media generation.",
    tools=[
        # --- ADK Skills (on-demand expertise) ---
        _marketing_skills,

        # --- Product & Campaign Pipeline ---
        setup_product_campaign,
        setup_campaign_from_sku,
        get_campaign_idea,
        save_selected_campaign,
        get_selected_brief,
        get_asset_sheet,
        save_selected_asset_sheet,
        set_customer_persona,
        clear_customer_persona,
        generate_text_ad,
        get_image_ads_for_audience,
        get_video_ads_for_audience,
        generate_display_ad,
        recommend_campaign_settings,
        get_stocking_projection,
        check_existing_assets,
        delete_asset_from_gcs,

        # --- Retail Pipeline ---
        identify_inventory_opportunities,
        get_product_by_sku,
        display_product_image,

        # --- Sub-agents ---
        AgentTool(agent=trend_spotter_agent.agent),

        # --- A2A — Google Ads Publisher ---
        publish_to_google_ads,

    ],
)
