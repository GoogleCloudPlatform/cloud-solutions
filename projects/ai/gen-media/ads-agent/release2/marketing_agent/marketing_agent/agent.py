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
# pylint: disable=C0114, C0115, C0301, C0303, C0412, C0413, C0415, E0606, E1136, W0102, W0104, W0311, W0404, W0611, W0612, W0613, W0718, W1203, W1309, W1405, W1510, W1514
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
GOOGLE_CLOUD_BUCKET_ARTIFACTS = get_required_env_var(
    "GOOGLE_CLOUD_BUCKET_ARTIFACTS"
)
GEMINI_IMAGE_MODEL = get_required_env_var("IMAGE_GENERATION_MODEL")
GEMINI_TTS_MODEL = get_required_env_var("AUDIO_TTS_GENERATION_MODEL")
GEMINI_TTS_VOICE = get_required_env_var("AUDIO_TTS_VOICE_NAME")
VEO_MODEL = get_required_env_var("VIDEO_GENERATION_MODEL")
VEO_CLIP_DURATION = int(get_optional_env_var("VIDEO_DEFAULT_DURATION", "4"))
LLM_GEMINI_MODEL_MARKETING_ANALYST = get_required_env_var(
    "LLM_GEMINI_MODEL_MARKETING_ANALYST"
)
AGENT_VERSION = get_required_env_var("AGENT_VERSION")
DEMO_COMPANY_NAME = get_optional_env_var("DEMO_COMPANY_NAME", "LayoGenMedia")
MARKETING_ANALYST_DATASTORE_CLOUD_BUCKET = get_required_env_var(
    "MARKETING_ANALYST_DATASTORE_CLOUD_BUCKET"
)
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
                safe_persona = (
                    persona_desc.split(".")[0]
                    .replace(" ", "_")
                    .replace(",", "")[:30]
                )
                OUTPUT_FOLDER = f"{safe_name}_{safe_persona}"
        else:
            OUTPUT_FOLDER = safe_name
    log_message(f"Output folder: {OUTPUT_FOLDER}", Severity.INFO)


SELECTED_CAMPAIGN_FILE_NAME = (
    f"{get_required_env_var('SELECTED_CAMPAIGN_FILE_NAME')}.{AGENT_VERSION}.txt"
)
SELECTED_ASSET_SHEET_FILE_NAME = f"{get_required_env_var('SELECTED_ASSET_SHEET_FILE_NAME')}.{AGENT_VERSION}.txt"
SESSION_STATE_FILE_NAME = (
    f"{get_required_env_var('SESSION_STATE_FILE_NAME')}.{AGENT_VERSION}.json"
)

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
        if hasattr(p, "core_identifiers") and p.core_identifiers:
            low_velocity_skus.add(p.core_identifiers.sku)

    # Sort: low velocity first, then by stock quantity descending
    velocity_order = {"low": 0, "average": 1, "high": 2}
    high_stock_products.sort(
        key=lambda p: (
            velocity_order.get(
                (
                    p.commercial_status.sales_velocity
                    if p.commercial_status
                    else "average"
                ),
                1,
            ),
            -(p.commercial_status.stock_quantity if p.commercial_status else 0),
        )
    )

    opportunities_as_dict = []
    for product in high_stock_products:
        opportunities_as_dict.append(to_dict_recursive(product))
    tool_context.state["opportunities"] = opportunities_as_dict
    return opportunities_as_dict


def _extract_structured_data(html: str) -> dict:
    """Extract JSON-LD, Open Graph, and meta tag data from raw HTML."""
    import re as _re

    structured = {"json_ld": [], "og": {}, "meta": {}}

    for m in _re.finditer(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        _re.DOTALL,
    ):
        try:
            data = json.loads(m.group(1).strip())
            if isinstance(data, list):
                structured["json_ld"].extend(data)
            else:
                structured["json_ld"].append(data)
        except json.JSONDecodeError:
            pass

    for m in _re.finditer(
        r'<meta\s+(?:property|name)=["\']og:(\w+)["\']\s+content=["\']([^"\']*)["\']',
        html,
        _re.IGNORECASE,
    ):
        structured["og"][m.group(1)] = m.group(2)

    for m in _re.finditer(
        r'<meta\s+(?:name|property)=["\']([^"\']+)["\']\s+content=["\']([^"\']*)["\']',
        html,
        _re.IGNORECASE,
    ):
        structured["meta"][m.group(1)] = m.group(2)

    return structured


def _extract_embedded_app_state(html: str) -> dict | None:
    """Extract window.APP_STATE, __NEXT_DATA__, or similar embedded JSON state from HTML.
    Most modern e-commerce sites (Verizon, Best Buy, etc.) embed full product data in JS variables.
    """
    import re as _re

    state_markers = [
        "window.APP_STATE",
        "window.__INITIAL_STATE__",
        "window.__NEXT_DATA__",
        "window.__data",
    ]

    for marker in state_markers:
        idx = html.find(marker)
        if idx < 0:
            continue
        eq_idx = html.find("=", idx)
        if eq_idx < 0 or eq_idx > idx + len(marker) + 5:
            continue
        json_start = eq_idx + 1
        while json_start < len(html) and html[json_start] in " \t\n\r":
            json_start += 1
        try:
            decoder = json.JSONDecoder()
            obj, _ = decoder.raw_decode(html, json_start)
            if isinstance(obj, dict):
                log_message(
                    f"Found embedded state via {marker} ({len(json.dumps(obj))} chars)",
                    Severity.INFO,
                )
                return obj
        except (json.JSONDecodeError, Exception):
            pass

    for m in _re.finditer(
        r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, _re.DOTALL
    ):
        try:
            return json.loads(m.group(1).strip())
        except (json.JSONDecodeError, Exception):
            pass

    return None


def _flatten_app_state_product(app_state: dict) -> dict:
    """Extract product-relevant data from an embedded app state object, regardless of site structure."""
    result = {}

    pdp = app_state.get("pdp", {})
    if pdp:
        pd = pdp.get("productDetails", {})
        if pd:
            result["displayName"] = pd.get("displayName", "")
            result["productName"] = pd.get("productName", "")
            result["brandName"] = pd.get("brandName", "")
            result["category"] = pd.get("category", "")
            result["productId"] = pd.get("productId", "")
            result["defaultSkuId"] = pd.get("defaultSkuId", "")
            result["accessorySpecification"] = pd.get(
                "accessorySpecification", ""
            )
            result["includedAccessories"] = pd.get("includedAccessories", "")
            result["rating"] = pd.get("rating", {})

        sku_obj = pdp.get("defaultSKUObj", {})
        if sku_obj:
            result["skuId"] = sku_obj.get("skuId", "")
            result["skuDescription"] = sku_obj.get("skuDescription", "")
            result["color"] = sku_obj.get("color", {}).get("displayName", "")

            price_data = sku_obj.get("price", {})
            frp = price_data.get("fullRetailPrice", {})
            if frp:
                orig = frp.get("originalPrice", "")
                monthly = frp.get("monthlyPrice", "")
                term = frp.get("afoTerm", "")
                if orig:
                    price_str = f"${orig}"
                    if monthly and term:
                        price_str += f" (or ${monthly}/mo for {term} months)"
                    result["price"] = price_str
                result["originalPrice"] = orig
                result["monthlyPrice"] = monthly
                result["afoTerm"] = term

            img_map = sku_obj.get("imageUrlMap", {})
            if img_map:
                result["imageUrl"] = img_map.get(
                    "largeImage", img_map.get("defaultImage", "")
                )

            inv = sku_obj.get("inventoryDetails", {})
            dfill = inv.get("dFillInventory", {})
            if dfill:
                result["inStock"] = dfill.get("isInStock", False)
                result["qtyAvailable"] = dfill.get("qtyAvailable", 0)

        faq = pdp.get("faq", {})
        qa_list = faq.get("QAInfo", [])
        if qa_list:
            result["faq"] = [
                {
                    "q": q.get("question", ""),
                    "a": (
                        q.get("answers", [{}])[0].get("answer", "")
                        if q.get("answers")
                        else ""
                    ),
                }
                for q in qa_list[:5]
            ]

    props = app_state.get("props", {}).get("pageProps", {})
    if props:
        product = props.get("product", props.get("productData", {}))
        if product:
            result["displayName"] = result.get("displayName") or product.get(
                "name", product.get("title", "")
            )
            result["brandName"] = result.get("brandName") or product.get(
                "brand", ""
            )
            result["description"] = product.get("description", "")
            result["originalPrice"] = result.get(
                "originalPrice"
            ) or product.get("price", "")

    import re as _re

    for k, v in result.items():
        if isinstance(v, str) and "<" in v:
            result[k] = _re.sub(r"<[^>]+>", " ", v).strip()
            result[k] = _re.sub(r"\s+", " ", result[k])

    return {k: v for k, v in result.items() if v}


async def extract_product_from_url(tool_context: ToolContext, url: str) -> dict:
    """Extracts product details from a product page URL. Works with any e-commerce product page
    (Verizon, Amazon, Best Buy, etc.). Fetches the page, extracts JSON-LD structured data,
    Open Graph meta tags, hidden content sections, and dynamic API data. Uses AI to build
    a comprehensive product profile from all sources.

    The user only needs to provide the URL — everything else is auto-extracted including
    Overview, Specs, Features, and FAQ content even when loaded dynamically.

    Args:
        url: The full product page URL (e.g. https://www.verizon.com/products/...).
    """
    import httpx

    log_message(f"Extracting product from URL: {url}", Severity.INFO)

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
    }

    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=30.0, headers=headers
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html_content = resp.text
    except Exception as e:
        log_message(f"Failed to fetch URL: {e}", Severity.ERROR)
        return {"status": "error", "details": f"Could not fetch the URL: {e}"}

    structured = _extract_structured_data(html_content)
    app_state = _extract_embedded_app_state(html_content)
    app_state_product = (
        _flatten_app_state_product(app_state) if app_state else {}
    )

    content_parts = []

    if app_state_product:
        content_parts.append(
            "=== EMBEDDED APP STATE (highest priority — structured product data from the site) ===\n"
            + json.dumps(app_state_product, indent=2)[:25000]
        )

    if structured["json_ld"]:
        content_parts.append(
            "=== STRUCTURED DATA (JSON-LD) ===\n"
            + json.dumps(structured["json_ld"], indent=2)[:20000]
        )

    if structured["og"]:
        content_parts.append(
            "=== OPEN GRAPH META TAGS ===\n"
            + json.dumps(structured["og"], indent=2)
        )

    if structured["meta"]:
        relevant_meta = {
            k: v
            for k, v in structured["meta"].items()
            if any(
                kw in k.lower()
                for kw in [
                    "description",
                    "price",
                    "product",
                    "title",
                    "brand",
                    "image",
                    "keyword",
                ]
            )
        }
        if relevant_meta:
            content_parts.append(
                "=== META TAGS ===\n" + json.dumps(relevant_meta, indent=2)
            )

    import re as _price_re

    price_section = ""
    all_dollar_amounts = _price_re.findall(
        r"(.{0,100}\$[\d,]+\.?\d*.{0,100})", html_content
    )
    if all_dollar_amounts:
        price_section = (
            "=== PRICE DATA FOUND IN PAGE ===\n"
            + "\n".join(all_dollar_amounts[:20])
            + "\n\n"
        )

    content_parts.append(price_section)
    content_parts.append(
        "=== RAW HTML (page source) ===\n" + html_content[:50000]
    )

    all_content = "\n\n".join(content_parts)
    all_content = all_content[:120000]

    extraction_prompt = (
        "You are a product data extraction specialist. You have MULTIPLE data sources from a product page.\n"
        "Cross-reference ALL sources to build the most COMPLETE and ACCURATE product profile possible.\n\n"
        "PRIORITY ORDER for data sources:\n"
        "1. Embedded App State (highest priority — structured data extracted from the site's JavaScript)\n"
        "2. JSON-LD structured data\n"
        "3. Open Graph / Meta tags (good for name, image, description)\n"
        "4. Raw HTML (fallback for anything not in structured sources)\n\n"
        "Return ONLY valid JSON with these exact keys (use empty string if not found):\n"
        "{\n"
        '  "brand": "the brand/company name (e.g. Verizon, Samsung, Apple)",\n'
        '  "product_name": "full product name as shown on the page",\n'
        '  "price": "price as shown (e.g. $99.99, $149.99/mo) — include any price variants",\n'
        '  "description": "comprehensive product description — combine the marketing overview AND technical summary into 4-6 rich sentences",\n'
        '  "features": ["feature 1 — with detail", "feature 2 — with detail", ...],\n'
        '  "specs": {"Wi-Fi Standard": "Wi-Fi 6E", "Speed": "3.6 Gbps", "Coverage": "2,500 sq ft", ...},\n'
        '  "overview": "the full Overview/About section content if available",\n'
        '  "target_audience": "who this product is for — infer from features, price, and category",\n'
        '  "category": "product category (e.g. Wi-Fi Extenders, Smartphones, Audio, Networking)",\n'
        '  "image_url": "the BEST product image URL — prefer high-res, prefer og:image, must be absolute URL",\n'
        '  "sku": "product SKU/model number if visible",\n'
        '  "compatibility": "what devices/systems this works with if applicable",\n'
        '  "whats_in_box": "contents of the box/package if listed",\n'
        '  "faq_highlights": ["key Q&A 1", "key Q&A 2", ...],\n'
        '  "video_urls": ["product video or demo mp4 URLs — look for storage.googleapis.com or CDN video URLs"],\n'
        '  "gallery_images": ["ONLY images of THIS EXACT product showing different angles/views/colors/usage — NOT related products, banners, icons, or promotional images. Max 8 URLs. Include images showing the product in use, different angles, packaging, and lifestyle context. These help the AI understand how the product looks and functions for ad generation."],\n'
        '  "product_usage": "HOW is this product physically used? Describe installation, interaction, and visual behavior. '
        "Examples: a thermostat is wall-mounted, users turn the outer ring gently, the display color changes with temperature "
        "(blue=cool, orange=warm, green=eco). A phone is held in hand, users tap and swipe the screen. "
        "A speaker sits on a surface, users speak to it. Be specific about how users PHYSICALLY INTERACT with the product "
        'and how the product VISUALLY RESPONDS (screen changes, LED colors, sounds, etc.)"\n'
        "}\n\n"
        "IMPORTANT:\n"
        "- PRICE IS CRITICAL — search ALL data sources for price. Look for keys like: price, originalPrice, salePrice, "
        "fullRetailPrice, monthlyPrice, retailPrice, offerPrice, listPrice, or any dollar amount ($XX.XX). "
        "PREFER the current/sale/offer price over the original/list price if both exist. "
        "If there's a promotional price, use that as the main price and show the original as 'Was $XXX'. "
        "Include ALL pricing variants: full price, sale price, monthly financing, trade-in price. "
        "Format as '$XXX.XX'. NEVER say 'Not specified' if any price data exists anywhere.\n"
        "- Be EXHAUSTIVE with features — extract EVERY feature mentioned anywhere on the page\n"
        "- Be EXHAUSTIVE with specs — extract EVERY spec (dimensions, weight, standards, speeds, etc.)\n"
        "- The description should read like premium marketing copy — what makes this product special and why should someone buy it\n"
        "- For image_url: prefer og:image, then the largest/primary product photo. Must be absolute URL (https://...)\n"
        "- For target_audience: be specific — e.g. 'Homeowners with large homes needing extended Wi-Fi coverage'\n"
        "- Return ONLY the JSON object, no markdown, no code fences\n\n"
        f"PAGE URL: {url}\n\n"
        f"ALL EXTRACTED CONTENT:\n{all_content}"
    )

    try:
        ai_client = genai.Client(
            vertexai=True,
            project=GOOGLE_CLOUD_PROJECT,
            location=GOOGLE_CLOUD_LOCATION,
        )
        response = await asyncio.to_thread(
            ai_client.models.generate_content,
            model=LLM_GEMINI_MODEL_MARKETING_ANALYST,
            contents=extraction_prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
            ),
        )
        extracted_text = response.text.strip()
        product_data = json.loads(extracted_text)
    except Exception as e:
        log_message(f"AI extraction failed: {e}", Severity.ERROR)
        return {
            "status": "error",
            "details": f"Could not extract product details: {e}",
        }

    brand = product_data.get("brand", "")
    product_name = product_data.get("product_name", "")
    price = product_data.get("price", "")
    description = product_data.get("description", "")
    features = product_data.get("features", [])
    specs = product_data.get("specs", {})
    overview = product_data.get("overview", "")
    target_audience = product_data.get("target_audience", "")
    category = product_data.get("category", "")
    image_url = product_data.get("image_url", "")
    sku = product_data.get("sku", "")
    compatibility = product_data.get("compatibility", "")
    product_usage = product_data.get("product_usage", "")
    whats_in_box = product_data.get("whats_in_box", "")
    faq_highlights = product_data.get("faq_highlights", [])

    def _is_empty(val):
        if not val:
            return True
        if isinstance(val, str):
            low = val.strip().lower()
            return low in (
                "",
                "not specified",
                "not listed",
                "not listed/varies",
                "not available",
                "n/a",
                "na",
                "none",
                "varies",
                "unknown",
                "not found",
                "price not available",
                "contact for price",
            )
        return False

    if app_state_product:
        if _is_empty(price) and app_state_product.get("price"):
            price = app_state_product["price"]
        if _is_empty(price) and app_state_product.get("originalPrice"):
            orig = app_state_product["originalPrice"]
            price = f"${orig}" if isinstance(orig, (int, float)) else str(orig)
            monthly = app_state_product.get("monthlyPrice")
            term = app_state_product.get("afoTerm")
            if monthly and term:
                price += f" (or ${monthly}/mo for {term} months)"
        if _is_empty(brand) and app_state_product.get("brandName"):
            brand = app_state_product["brandName"]
        if _is_empty(product_name) and app_state_product.get("displayName"):
            product_name = app_state_product["displayName"]
        if _is_empty(category) and app_state_product.get("category"):
            category = app_state_product["category"]
        if _is_empty(sku) and app_state_product.get("skuId"):
            sku = app_state_product["skuId"]
        if _is_empty(image_url) and app_state_product.get("imageUrl"):
            image_url = app_state_product["imageUrl"]

    if _is_empty(price):
        import re as _re

        price_match = _re.search(
            r'\\?"originalPrice\\?"\s*:\s*([\d.]+)', html_content
        )
        if price_match:
            orig_val = price_match.group(1)
            price = f"${orig_val}"
            monthly_match = _re.search(
                r'\\?"monthlyPrice\\?"\s*:\s*([\d.]+)', html_content
            )
            term_match = _re.search(
                r'\\?"afoTerm\\?"\s*:\s*(\d+)', html_content
            )
            if monthly_match and term_match:
                price += f" (or ${monthly_match.group(1)}/mo for {term_match.group(1)} months)"
            log_message(
                f"Price extracted from embedded JSON: {price}", Severity.INFO
            )
    if _is_empty(price):
        import re as _re

        html_price = _re.search(r">\s*\$([\d,]+\.?\d*)\s*<", html_content)
        if html_price:
            price = f"${html_price.group(1)}"
            log_message(
                f"Price extracted from visible HTML: {price}", Severity.INFO
            )

    full_description = description
    if overview and overview not in description:
        full_description = f"{overview}\n\n{description}"
    if features:
        features_text = "\n".join(f"- {f}" for f in features)
        full_description = (
            f"{full_description}\n\nKey Features:\n{features_text}"
        )
    if specs:
        specs_text = "\n".join(f"- {k}: {v}" for k, v in specs.items())
        full_description = (
            f"{full_description}\n\nSpecifications:\n{specs_text}"
        )
    if product_usage:
        full_description = f"{full_description}\n\nProduct Usage & Interaction: {product_usage}"
    if compatibility:
        full_description = (
            f"{full_description}\n\nCompatibility: {compatibility}"
        )
    if whats_in_box:
        full_description = f"{full_description}\n\nIn the Box: {whats_in_box}"
    if price:
        full_description = f"{full_description}\n\nPrice: {price}"

    additional_images = product_data.get(
        "gallery_images", []
    ) or product_data.get("additional_images", [])

    import re as _html_re

    guest_ids = _html_re.findall(r'"(GUEST_[a-f0-9\-]+)"', html_content)
    guest_ids = list(dict.fromkeys(guest_ids))
    for gid in guest_ids:
        gu = f"https://target.scene7.com/is/image/Target/{gid}"
        additional_images.append(gu)

    def _base_url(u):
        return u.split("?")[0].split("#")[0]

    seen_bases = set()
    if image_url:
        seen_bases.add(_base_url(image_url))
    unique_images = []
    for u in additional_images:
        if not u:
            continue
        base = _base_url(u)
        if base not in seen_bases:
            seen_bases.add(base)
            unique_images.append(u)
    additional_images = unique_images[:8]
    log_message(
        f"Product gallery images from Gemini + HTML: {len(additional_images)}",
        Severity.INFO,
    )

    product_videos_from_html = _html_re.findall(
        r'(https://storage\.googleapis\.com/[^\s"\'<>]+\.mp4)', html_content
    )
    product_videos_from_html += _html_re.findall(
        r'(https://[^\s"\'<>]+\.mp4)', html_content
    )
    scene7_videos = _html_re.findall(
        r"(https://target\.scene7\.com/is/content/Target/GUEST_[a-f0-9\-]+)",
        html_content,
    )
    product_videos_from_html += list(dict.fromkeys(scene7_videos))
    product_videos_from_html = list(dict.fromkeys(product_videos_from_html))[:3]
    log_message(
        f"Product videos from HTML: {len(product_videos_from_html)}",
        Severity.INFO,
    )

    tool_context.state[PRODUCT_COMPANY_NAME_STATE_KEY] = brand
    tool_context.state["PRODUCT_NAME"] = product_name
    tool_context.state["PRODUCT_PRICE"] = price
    tool_context.state["PRODUCT_DESCRIPTION"] = full_description
    tool_context.state["PRODUCT_TARGET_AUDIENCE"] = target_audience
    tool_context.state["PRODUCT_CATEGORY"] = category
    tool_context.state["PRODUCT_SOURCE_URL"] = url

    try:
        safe_name = product_name.replace(" ", "_")[:40]
        product_data_for_gcs = {
            "brand": brand,
            "product_name": product_name,
            "price": price,
            "description": full_description,
            "features": features,
            "specs": specs,
            "target_audience": target_audience,
            "category": category,
            "image_url": image_url,
            "additional_images": additional_images[:5],
            "video_urls": product_videos_from_html,
            "sku": sku,
            "compatibility": compatibility,
            "whats_in_box": whats_in_box,
            "product_usage": product_usage,
            "source_url": url,
        }
        utils_gcs.upload_to_gcs(
            GOOGLE_CLOUD_BUCKET_ARTIFACTS,
            json.dumps(product_data_for_gcs, indent=2).encode("utf-8"),
            f"{safe_name}/product_data.json",
        )
        log_message(
            f"Full product data saved to GCS: {safe_name}/product_data.json",
            Severity.INFO,
        )
    except Exception:
        pass
    if additional_images:
        tool_context.state["PRODUCT_ADDITIONAL_IMAGES"] = additional_images[:10]

    if image_url:
        tool_context.state[PRODUCT_IMAGE_URI_STATE_KEY] = image_url
        try:
            img_bytes = None
            if image_url.startswith("gs://"):
                img_bytes, _ = utils_agents.download_bytes_from_reference(
                    image_url
                )
            else:
                async with httpx.AsyncClient(
                    follow_redirects=True, timeout=20.0
                ) as img_client:
                    img_resp = await img_client.get(
                        image_url, headers={"User-Agent": headers["User-Agent"]}
                    )
                    if img_resp.status_code == 200:
                        img_bytes = img_resp.content
            if img_bytes:
                try:
                    import io

                    from PIL import Image

                    img = Image.open(io.BytesIO(img_bytes))
                    canvas_size = 600
                    max_product = int(canvas_size * 0.7)
                    img.thumbnail((max_product, max_product), Image.LANCZOS)
                    canvas = Image.new(
                        "RGB", (canvas_size, canvas_size), (0, 0, 0)
                    )
                    paste_x = (canvas_size - img.width) // 2
                    paste_y = (canvas_size - img.height) // 2
                    if img.mode == "RGBA":
                        canvas.paste(img, (paste_x, paste_y), img)
                    else:
                        canvas.paste(img, (paste_x, paste_y))
                    buf = io.BytesIO()
                    canvas.save(buf, format="PNG", quality=95)
                    img_bytes = buf.getvalue()
                except Exception:
                    pass
                safe_name = product_name.replace(" ", "_")[:30]
                gcs_blob = f"{safe_name}/product_{safe_name}.png"
                try:
                    utils_gcs.upload_to_gcs(
                        GOOGLE_CLOUD_BUCKET_ARTIFACTS, img_bytes, gcs_blob
                    )
                    gcs_uri = f"gs://{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{gcs_blob}"
                    tool_context.state[PRODUCT_IMAGE_URI_STATE_KEY] = gcs_uri
                    log_message(
                        f"Product image uploaded to GCS: {gcs_uri}",
                        Severity.INFO,
                    )
                except Exception:
                    pass
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
        except Exception:
            pass

    gallery_gcs_uris = []
    if additional_images:

        async def _download_gallery_img(img_u, idx):
            try:
                async with httpx.AsyncClient(
                    follow_redirects=True, timeout=15.0
                ) as gc:
                    gr = await gc.get(
                        img_u, headers={"User-Agent": headers["User-Agent"]}
                    )
                    if gr.status_code == 200 and len(gr.content) > 5000:
                        safe_name = product_name.replace(" ", "_")[:30]
                        gcs_blob = f"{safe_name}/gallery_{idx}.png"
                        try:
                            await asyncio.to_thread(
                                utils_gcs.upload_to_gcs,
                                GOOGLE_CLOUD_BUCKET_ARTIFACTS,
                                gr.content,
                                gcs_blob,
                            )
                            return f"gs://{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{gcs_blob}"
                        except Exception:
                            pass
            except Exception:
                pass
            return None

        gallery_to_show = additional_images[:4]
        gallery_results = await asyncio.gather(
            *[
                _download_gallery_img(u, i)
                for i, u in enumerate(gallery_to_show)
            ],
            return_exceptions=True,
        )
        gallery_gcs_uris = [r for r in gallery_results if isinstance(r, str)]
        log_message(
            f"Gallery images uploaded to GCS: {len(gallery_gcs_uris)}/{len(gallery_to_show)}",
            Severity.INFO,
        )

    video_urls = product_data.get("video_urls", [])
    if not video_urls:
        video_urls = product_videos_from_html
    if video_urls:
        tool_context.state["PRODUCT_VIDEO_URLS"] = video_urls[:3]
        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=20.0
            ) as vc:
                vr = await vc.get(
                    video_urls[0], headers={"User-Agent": headers["User-Agent"]}
                )
                if vr.status_code == 200 and len(vr.content) > 10000:
                    vm = GeneratedMedia(
                        filename="product_video.mp4",
                        mime_type="video/mp4",
                        media_bytes=vr.content,
                    )
                    await utils_agents.save_to_artifact_and_render_asset(
                        asset=vm,
                        context=tool_context,
                        save_in_gcs=False,
                        save_in_artifacts=True,
                    )
        except Exception:
            pass
    if gallery_gcs_uris:
        tool_context.state["PRODUCT_GALLERY_GCS_URIS"] = gallery_gcs_uris
        for i, guri in enumerate(gallery_gcs_uris[:2]):
            try:
                gb, _ = utils_agents.download_bytes_from_reference(guri)
                if gb:
                    gm = GeneratedMedia(
                        filename=f"gallery_{i}.png",
                        mime_type="image/png",
                        media_bytes=gb,
                    )
                    await utils_agents.save_to_artifact_and_render_asset(
                        asset=gm,
                        context=tool_context,
                        save_in_gcs=False,
                        save_in_artifacts=True,
                    )
            except Exception:
                pass
    if additional_images:
        tool_context.state["PRODUCT_ADDITIONAL_IMAGES"] = additional_images[:8]

    log_message(
        f"Extracted product: {brand} — {product_name} ({price})", Severity.INFO
    )
    log_message(
        f"  Features: {len(features)}, Specs: {len(specs)}, Image: {'YES' if image_url else 'NO'}, Gallery: {len(additional_images)}, Videos: {len(video_urls)}",
        Severity.INFO,
    )

    return {
        "status": "success",
        "product_summary": {
            "brand": brand,
            "product_name": product_name,
            "price": price,
            "description": full_description,
            "features": features,
            "specs": specs,
            "target_audience": target_audience,
            "category": category,
            "image_url": image_url,
            "additional_images": additional_images[:5],
            "video_urls": video_urls,
            "sku": sku,
            "compatibility": compatibility,
            "whats_in_box": whats_in_box,
            "faq_highlights": faq_highlights,
            "source_url": url,
        },
        "details": (
            f"Product details extracted from {url}. "
            f"Found {len(features)} features, {len(specs)} specs, {len(additional_images)} gallery images, {len(video_urls)} videos. "
            f"All fields are pre-populated in session state. "
            f"You can now proceed with trend research and campaign setup — "
            f"call setup_product_campaign with the extracted details."
        ),
    }


async def display_product_image(
    tool_context: ToolContext, image_url: str, product_name: str = "product"
):
    """Displays a product image inline. Call this in Path B when the user provides their product image URL.

    Args:
        image_url: The GCS URI or HTTPS URL of the product image.
        product_name: Name of the product (used for the filename).
    """
    try:
        img_bytes, _ = utils_agents.download_bytes_from_reference(image_url)
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
            tool_context.state["PRODUCT_IMAGE_URI"] = image_url
            return {
                "status": "success",
                "details": f"Product image displayed for {product_name}",
            }
    except Exception as e:
        return {"status": "error", "details": str(e)}
    return {"status": "error", "details": "Could not download image"}


async def get_product_by_sku(tool_context: ToolContext, sku: str) -> dict:
    """Retrieves a product and its associated brand information by SKU.
    Also displays the product image inline immediately.

    Args:
        sku: The SKU of the product to retrieve.
    """
    product = get_product_by_sku_from_bq(sku)
    if not product:
        return {}, {}

    tool_context.state["product"] = to_dict_recursive(product)
    brand_name = product.core_identifiers.brand
    brand_info = next(
        (
            brand
            for brand in tool_context.state.get("brand_data", [])
            if brand.get("name") == brand_name
        ),
        None,
    )
    if brand_info:
        tool_context.state["brand_info"] = brand_info

    product_image_uri = product.media.main_image_url if product.media else ""
    if product_image_uri:
        tool_context.state[PRODUCT_IMAGE_URI_STATE_KEY] = product_image_uri

    return to_dict_recursive(product), brand_info or {}


async def setup_campaign_from_sku(
    tool_context: ToolContext,
    sku: str,
    num_segments: int = 2,
    reference_guidelines: str = "",
):
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
        if (
            isinstance(opp, dict)
            and opp.get("core_identifiers", {}).get("sku") == sku
        ):
            # Reconstruct Product from dict
            product = Product(**opp)
            break

    # Fallback to BQ if not in state
    if not product:
        product = get_product_by_sku_from_bq(sku)

    if not product:
        return {
            "status": "error",
            "details": f"Product with SKU '{sku}' not found.",
        }

    company_name = product.core_identifiers.brand or DEMO_COMPANY_NAME
    product_name = product.core_identifiers.product_name
    product_description = (
        product.description.long
        if product.description and product.description.long
        else (
            product.description.short
            if product.description and product.description.short
            else product_name
        )
    )

    # Auto-generate target audience from product category and price
    dept = product.categorization.department if product.categorization else ""
    cat = product.categorization.category if product.categorization else ""
    price = (
        product.commercial_status.current_price
        if product.commercial_status
        else 0
    )
    price_tier = (
        "premium" if price > 200 else "mid-range" if price > 50 else "value"
    )
    target_audience = f"{dept} {cat} consumers interested in {price_tier} {product_name.lower()} products, ages 25-50"

    product_image_uri = product.media.main_image_url if product.media else ""
    logo_uri = get_optional_env_var("BACKUP_LOGO_IMAGE_URL", "")

    # Store product in state for sub-agents
    tool_context.state["product"] = to_dict_recursive(product)

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
            "description": (
                product.description.short if product.description else ""
            ),
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


async def _retry_generate_content(
    client, model, contents, config, label="LLM", max_attempts=4
):
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
                backoff = (2**attempt) * 3 + random.uniform(0, 2)
                log_message(
                    f"{label}: 429 retry {attempt+1}/{max_attempts}, backoff {backoff:.1f}s",
                    Severity.WARNING,
                )
                await asyncio.sleep(backoff)
            elif attempt < max_attempts - 1:
                await asyncio.sleep(2)
                log_message(
                    f"{label}: error retry {attempt+1}/{max_attempts}: {e}",
                    Severity.WARNING,
                )
            else:
                log_message(
                    f"{label}: failed after {max_attempts} attempts: {e}",
                    Severity.ERROR,
                )
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


async def _generate_gemini_image(
    prompt: str, reference_images: list[bytes], label: str = "image"
) -> bytes | None:
    parts = [
        types.Part.from_bytes(data=img, mime_type="image/png")
        for img in reference_images
    ]
    parts.append(types.Part.from_text(text=prompt))

    for attempt in range(5):
        try:
            client = genai.Client(
                vertexai=True, project=GOOGLE_CLOUD_PROJECT, location="global"
            )
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=GEMINI_IMAGE_MODEL,
                    contents=[types.Content(role="user", parts=parts)],
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE", "TEXT"]
                    ),
                ),
                timeout=120,
            )
            if response.candidates and response.candidates[0].content:
                for part in response.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.data:
                        log_message(
                            f"{label} generated ({len(part.inline_data.data)} bytes)",
                            Severity.INFO,
                        )
                        return part.inline_data.data
            log_message(
                f"{label}: no image in response (attempt {attempt + 1}/5)",
                Severity.WARNING,
            )
        except Exception as e:
            error_str = str(e)
            is_429 = "429" in error_str or "RESOURCE_EXHAUSTED" in error_str
            log_message(
                f"{label} failed (attempt {attempt + 1}/5, 429={is_429}): {e}",
                Severity.WARNING,
            )
            if is_429 and attempt < 4:
                backoff = (2**attempt) * 2 + random.uniform(0, 3)
                log_message(
                    f"{label}: 429 backoff {backoff:.1f}s", Severity.INFO
                )
                await asyncio.sleep(backoff)
                continue
        if attempt < 4:
            await asyncio.sleep((attempt + 1) * 3 + random.uniform(0, 2))
    return None


async def _generate_image_on_demand(
    asset_url: str,
    rationale: str,
    product_image_bytes: bytes,
    company_name: str,
    product_name: str,
    logo_image_bytes: bytes | None = None,
    variation_index: int = 0,
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
            f"Both must be VISUALLY DISTINCT and show the product being used REALISTICALLY. "
            f"People MUST face/look at the product they're using — gaze direction, body orientation, and hand position "
            f"must all make common sense. A family watching a screen must ALL face the screen. "
            f"A person holding a device must look at it. Product placement must be logical for the product type.\n"
            f"5. ENVIRONMENT/MOOD: 2 aspirational environment shots — DIFFERENT locations, DIFFERENT lighting. "
            f"These set the brand atmosphere.\n"
            f"6. PRODUCT HERO: Study ALL reference images carefully — reproduce the product with EXACT fidelity. "
            f"Show it in its CORRECT INSTALLATION/USAGE CONTEXT (wall-mounted products on wall, handheld products in hand, etc). "
            f"The product shape, color, screen content, and all details must match the reference precisely. "
            f"One dramatic hero shot in its real environment, one artistic macro close-up of product details.\n"
            f"7. TYPOGRAPHY: Campaign tagline shown ONCE in one elegant font treatment.\n\n"
            f"PRODUCT FIDELITY — CRITICAL (ZERO TOLERANCE):\n"
            f"- Study ALL reference images and reproduce the product EXACTLY in every shot\n"
            f"- Same shape, same colors, same proportions, same screen content — pixel-perfect match\n"
            f"- The product must be RECOGNIZABLE as the exact same item in every image\n"
            f"- Product at CORRECT REAL-WORLD scale — a thermostat is ~4 inches, a phone is ~6 inches, a TV is ~55 inches\n"
            f"- ONLY show angles/sides of the product visible in reference images — do NOT fabricate the back, bottom, or internals\n"
            f"- Do NOT add, invent, or imagine ANY features not visible in the reference image\n"
            f"- Do NOT show the product opened, disassembled, exploded, or in any state other than how it appears in the reference\n"
            f"- CORRECT PLACEMENT: wall-mounted products (thermostats, cameras, switches) MUST be on a wall. "
            f"Tabletop products on tables. Wearables being worn. Handheld products being held.\n"
            f"- If the product has a DISPLAY/SCREEN, show realistic dynamic content — not frozen/static\n"
            f"- PRODUCT BEHAVIOR: study reference images to understand how the product works. "
            f"If it has color-coded displays (e.g. thermostat: blue=cool, orange/red=warm), the display color "
            f"MUST match the value shown. Show DIFFERENT values in different shots — not the same number everywhere.\n"
            f"- The product is a RETAIL item — show it EXACTLY as a customer would see it installed/in use\n\n"
            f"QUALITY:\n"
            f"- Ultra-premium presentation — $100M creative agency standard\n"
            f"- Sophisticated dark or textured background, immaculate alignment\n"
            f"- Every image photorealistic, cinematic lighting, luxury color grading\n"
            f"- NO duplicate images — every shot MUST be UNIQUE in angle, lighting, composition, and scene\n"
            f"- Each lifestyle shot must show a DIFFERENT scenario — never repeat the same setup\n"
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
        prompt += f"Return only the image."
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
            f"RULE 2 — BRAND LOGO: Do NOT draw or generate any logo in the image. "
            f"Leave the top-right corner clear — the logo will be added in post-production.\n\n"
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
            f"RULE 6 — SPATIAL LOGIC & INTERACTION COHERENCE (CRITICAL):\n"
            f"Every person in the scene MUST physically interact with or orient toward the product in a way that makes common sense:\n"
            f"- GAZE DIRECTION: People must LOOK AT what they're using. A family watching a TV/screen must ALL face the screen. "
            f"A person using a phone must look DOWN at it. A person on a laptop must face the laptop. "
            f"NO ONE should stare at the camera, look away from the product, or gaze into empty space while supposedly using it.\n"
            f"- BODY ORIENTATION: People's bodies must face the product they're interacting with. "
            f"If a family is watching TV, they sit FACING the TV — not with backs to it. "
            f"If someone is cooking, they face the stove/counter. If gaming, they face the screen and hold controllers.\n"
            f"- HANDS & PRODUCT CONTACT: If a person is holding/using the product, their hands must be in the correct position. "
            f"Holding a phone = hand wrapped around phone, eyes on screen. Pouring a drink = hand on bottle, liquid going into glass. "
            f"Using a laptop = hands on keyboard or trackpad, eyes on screen.\n"
            f"- PRODUCT PLACEMENT LOGIC (show product in its CORRECT installation/usage context):\n"
            f"  * WALL-MOUNTED (thermostat, camera, light switch, doorbell, TV) → MUST be MOUNTED ON A WALL, never on a table. "
            f"Sits FLUSH against wall — NO thick base plate, NO mounting bracket, NO oversized shadow. Seamlessly integrated.\n"
            f"  * ROUTER/MODEM → on a shelf, desk, or entertainment center NEAR the TV/computer it serves\n"
            f"  * PHONE/TABLET → in someone's hands, screen facing the user, user looking at it\n"
            f"  * HEADPHONES/EARBUDS → being worn on/in ears, person relaxed or moving to music\n"
            f"  * SMART HOME DEVICE (speaker, hub) → on counter/shelf, person speaking toward it\n"
            f"  * WEARABLE (watch/ring/tracker) → on wrist/finger/collar, visible in natural pose\n"
            f"  * DRINK/FOOD → on table, being held, being consumed\n"
            f"  * APPLIANCE (oven, fridge, washer) → in its correct built-in/installed position\n"
            f"- ONLY show product angles visible in reference images — do NOT fabricate back/bottom/internals\n"
            f"- Product MUST be at CORRECT real-world size — check proportions against hands, walls, furniture\n"
            f"- If product has a SCREEN/DISPLAY, show realistic dynamic content (not frozen/static)\n"
            f"- SCENE COHERENCE: Every element in the scene must tell ONE consistent story. "
            f"If it's a 'family movie night' scene, everyone faces the same TV, sits on the same couch, shares the same space. "
            f"No person should be doing something unrelated to the scene's narrative.\n"
            f"- COMMON SENSE TEST: Before finalizing, ask — 'If I walked into this room, would this scene look normal?' "
            f"If any person's position, gaze, or body language looks awkward or disconnected, FIX IT.\n\n"
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
            return {
                "status": "error",
                "details": f"No rationale for {asset_url}",
            }

        product_image_uri = tool_context.state.get(PRODUCT_IMAGE_URI_STATE_KEY)
        if not product_image_uri:
            return {"status": "error", "details": "No product image URI"}

        # Cache product + logo bytes — download once, reuse across parallel calls
        if _cached_product_bytes is None:
            try:
                _cached_product_bytes, _ = (
                    utils_agents.download_bytes_from_reference(
                        product_image_uri
                    )
                )
            except Exception:
                return {
                    "status": "error",
                    "details": "Failed to download product image",
                }

        if _cached_logo_bytes is None:
            logo_uri = tool_context.state.get(LOGO_IMAGE_URI_STATE_KEY)
            if logo_uri:
                try:
                    _cached_logo_bytes, _ = (
                        utils_agents.download_bytes_from_reference(logo_uri)
                    )
                except Exception:
                    pass

        company_name = tool_context.state.get(
            PRODUCT_COMPANY_NAME_STATE_KEY, ""
        )
        product_name = tool_context.state.get("PRODUCT_NAME", "product")
        var_idx = hash(asset_url) % len(_VARIATION_STYLES)
        ref_guidelines = tool_context.state.get(
            REFERENCE_GUIDELINES_STATE_KEY, ""
        )
        fidelity_prompt = tool_context.state.get("PRODUCT_FIDELITY_PROMPT", "")
        if fidelity_prompt:
            ref_guidelines = (
                f"{ref_guidelines}\n\nPRODUCT FIDELITY GUIDE:\n{fidelity_prompt}"
                if ref_guidelines
                else f"PRODUCT FIDELITY GUIDE:\n{fidelity_prompt}"
            )
        persona = tool_context.state.get(CUSTOMER_PERSONA_STATE_KEY, "")

        asset_bytes = await _generate_image_on_demand(
            asset_url=asset_url,
            rationale=rationale,
            product_image_bytes=_cached_product_bytes,
            company_name=company_name,
            product_name=product_name,
            logo_image_bytes=_cached_logo_bytes,
            variation_index=var_idx,
            reference_guidelines=ref_guidelines,
            customer_persona=persona,
        )

        if not asset_bytes:
            return {
                "status": "error",
                "details": f"Failed to generate image for {asset_url}",
            }

        if _cached_logo_bytes:
            try:
                import io as _pio

                from PIL import Image as _PILImg

                bg = _PILImg.open(_pio.BytesIO(asset_bytes)).convert("RGBA")
                logo = _PILImg.open(_pio.BytesIO(_cached_logo_bytes)).convert(
                    "RGBA"
                )
                logo_size = int(bg.width * 0.12)
                logo.thumbnail((logo_size, logo_size), _PILImg.LANCZOS)
                x = bg.width - logo.width - 30
                y = 30
                bg.paste(logo, (x, y), logo)
                buf = _pio.BytesIO()
                bg.convert("RGB").save(buf, format="PNG")
                asset_bytes = buf.getvalue()
            except Exception:
                pass

        generated_media = GeneratedMedia(
            filename=filename,
            mime_type="image/png",
            media_bytes=asset_bytes,
        )
        generated_media = await utils_agents.save_to_artifact_and_render_asset(
            asset=generated_media,
            context=tool_context,
            save_in_gcs=True,
            save_in_artifacts=True,
            gcs_folder=OUTPUT_FOLDER,
        )

        public_url = f"https://storage.googleapis.com/{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{OUTPUT_FOLDER}/{base_filename}"
        return {"status": "success", "gcs_url": public_url}

    except Exception as e:
        log_message(f"Failed to render asset: {e}", Severity.ERROR)
        return {"status": "error", "details": str(e)}


async def _pre_generate_images(
    asset_uris: list[str], tool_context: ToolContext
):
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
        product_bytes, _ = utils_agents.download_bytes_from_reference(
            product_image_uri
        )
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
    fidelity_prompt = tool_context.state.get("PRODUCT_FIDELITY_PROMPT", "")
    if fidelity_prompt:
        ref_guidelines = (
            f"{ref_guidelines}\n\nPRODUCT FIDELITY GUIDE:\n{fidelity_prompt}"
            if ref_guidelines
            else f"PRODUCT FIDELITY GUIDE:\n{fidelity_prompt}"
        )
    persona = tool_context.state.get(CUSTOMER_PERSONA_STATE_KEY, "")

    async def _gen_one(uri, rationale, var_idx):
        img_bytes = await _generate_image_on_demand(
            asset_url=uri,
            rationale=rationale,
            product_image_bytes=product_bytes,
            company_name=company_name,
            product_name=product_name,
            logo_image_bytes=logo_bytes,
            variation_index=var_idx,
            reference_guidelines=ref_guidelines,
            customer_persona=persona,
        )
        return uri, img_bytes

    results = await asyncio.gather(
        *[
            _gen_one(uri, rat, i)
            for i, (uri, rat) in enumerate(uris_needing_generation)
        ],
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


async def generate_product_fidelity_prompt(tool_context: ToolContext) -> dict:
    """Generates a detailed product-specific prompt based on all extracted product information.
    This prompt describes exactly how the product looks, works, is installed, its real-world size,
    and what NOT to hallucinate. It is shown to the user for approval and saved to GCS.
    Used by all subsequent image and video ad generation to maintain product fidelity.

    Call this AFTER product extraction and campaign setup, BEFORE generating any ads.
    """
    _set_output_folder(tool_context)
    product_name = tool_context.state.get("PRODUCT_NAME", "")
    company_name = tool_context.state.get(PRODUCT_COMPANY_NAME_STATE_KEY, "")
    description = tool_context.state.get("PRODUCT_DESCRIPTION", "")
    category = tool_context.state.get("PRODUCT_CATEGORY", "")
    product_image_uri = tool_context.state.get(PRODUCT_IMAGE_URI_STATE_KEY, "")
    additional_images = tool_context.state.get("PRODUCT_ADDITIONAL_IMAGES", [])
    video_urls = tool_context.state.get("PRODUCT_VIDEO_URLS", [])
    source_url = tool_context.state.get("PRODUCT_SOURCE_URL", "")

    # Step 1: Google Search to understand real-world product usage
    search_context = ""
    try:
        search_client = genai.Client(
            vertexai=True, project=GOOGLE_CLOUD_PROJECT, location="global"
        )
        search_prompt = (
            f"Research how the {product_name} by {company_name} is used in real life. "
            f"I need to know:\n"
            f"1. How is it physically installed? (wall-mounted, placed on table, worn, held, etc.)\n"
            f"2. What does it look like installed in a real home/office?\n"
            f"3. How do people interact with it? (touch, voice, app, buttons, dial?)\n"
            f"4. What are its exact physical dimensions?\n"
            f"5. What colors/finishes is it available in?\n"
            f"6. How does its display/screen/interface change during use?\n"
            f"7. What room is it typically installed in?\n"
            f"Be specific and factual."
        )
        search_response = await asyncio.to_thread(
            search_client.models.generate_content,
            model="gemini-3.1-pro-preview",
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=search_prompt)],
                )
            ],
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=2048,
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )
        if search_response.candidates and search_response.candidates[0].content:
            for part in search_response.candidates[0].content.parts:
                if part.text:
                    search_context += part.text
        log_message(
            f"Google Search product research: {len(search_context)} chars",
            Severity.INFO,
        )
    except Exception as e:
        log_message(
            f"Google Search for product research failed: {e}", Severity.WARNING
        )

    # Step 2: Generate fidelity guide using all available info
    prompt_for_gemini = (
        f"You are a product fidelity specialist for advertising. You have product information AND "
        f"real-world research about how this product is actually used. Create a DETAILED PRODUCT FIDELITY GUIDE "
        f"that will be used by IMAGE and VIDEO generation AI to create realistic, accurate ads.\n\n"
        f"PRODUCT INFO:\n"
        f"- Brand: {company_name}\n"
        f"- Product: {product_name}\n"
        f"- Category: {category}\n"
        f"- Description: {description}\n"
        f"- Source URL: {source_url}\n"
        f"- Has {len(additional_images)} gallery images and {len(video_urls)} product videos\n\n"
    )
    if search_context:
        prompt_for_gemini += f"REAL-WORLD RESEARCH (from Google Search):\n{search_context[:3000]}\n\n"
    prompt_for_gemini += (
        f"Generate a JSON with these EXACT keys:\n"
        f"{{\n"
        f'  "physical_description": "Describe the product EXACT physical appearance: shape, color, materials, '
        f'finish, dimensions in inches. Be very specific — this will be used to generate images.",\n'
        f'  "installation_context": "CRITICAL: How is this product PHYSICALLY installed? '
        f"Be EXPLICIT: is it SCREWED TO A WALL? PLACED ON A TABLE? WORN ON WRIST? HELD IN HAND? "
        f"If wall-mounted, specify: which wall, which room, at what height, with what mount/base plate. "
        f'This is the MOST IMPORTANT field — getting this wrong means the entire ad is wrong.",\n'
        f'  "user_interaction": "How do users PHYSICALLY interact with it? Be specific about gestures: '
        f"turn the outer ring, tap the screen, swipe, press a button, speak to it, use an app. "
        f'What happens visually when they interact?",\n'
        f'  "visual_behavior": "Does the product have dynamic visual elements? Describe EXACTLY: '
        f"what colors appear on the display and when, what triggers color changes, what information is shown. "
        f'Example: thermostat shows blue at cool temps, orange at warm temps, green leaf for eco mode.",\n'
        f'  "real_world_size": "EXACT dimensions from research. Compare to common objects. '
        f'Example: 3.3 inches diameter, about the size of a hockey puck, or 6.1 inches tall like a smartphone.",\n'
        f'  "what_NOT_to_show": "CRITICAL — list things that should NEVER appear in generated ads: '
        f"1. Product on a TABLE if it is WALL-MOUNTED. "
        f"2. Product floating or lying on surfaces if it has a specific mount. "
        f"3. Fabricated back/internal views. "
        f"4. Features not confirmed in the product description. "
        f"5. Wrong size/proportions. "
        f'6. People interacting with it in ways it cannot be used.",\n'
        f'  "ad_scene_suggestions": "Write 3 scenes like an AD DIRECTOR shot list. Each scene MUST include: '
        f"SHOT TYPE (wide/medium/close-up), CAMERA MOVEMENT (steadicam walk, dolly push-in, static, slow orbit), "
        f"CAMERA HEIGHT (eye level, low angle, high angle), FRAMING (product position in frame), "
        f"LIGHTING (natural window light, warm evening glow, dramatic side-light), "
        f"ENVIRONMENT (weather outside, room details, time of day — use environment as storytelling), "
        f"PRODUCT STATE (what the display shows, what mode it is in). "
        f"IMPORTANT: Do NOT show anyone physically touching/operating the product — this causes visual artifacts in AI generation. "
        f"Instead, show the product in its installed position with the ENVIRONMENT telling the story "
        f"(rain outside = product shows weather data, evening = warm lighting, morning = fresh start). "
        f"People can be IN the scene but NOT touching the product. "
        f'Each scene should feel like a frame from a premium Apple or Google commercial.",\n'
        f'  "video_ad_guidance": "Write a 3-act DIRECTOR BRIEF for a 24-second video ad (8 seconds per act). '
        f"IMPORTANT: Do NOT show anyone physically operating/touching the product — this causes visual artifacts. "
        f"Instead, let the ENVIRONMENT tell the story while the product sits beautifully in its installed position. "
        f"For EACH act specify: "
        f"ACT 1 (0-8s): ESTABLISHING — steadicam walks into the space. Wide shot showing the environment and mood. "
        f"Use WEATHER and ENVIRONMENT as storytelling (rain on windows, snow outside, golden sunset, morning mist). "
        f"Product is visible in its correct position but not the focus yet. "
        f"ACT 2 (8-16s): HERO — Camera gently pushes toward the product. Medium/close-up shot. "
        f"The product display is clearly visible showing relevant information. "
        f"NO ONE touches the product. The environment around it tells the story (warm light, cozy room, kids playing in background). "
        f"ACT 3 (16-24s): PAYOFF — Pull back to lifestyle wide shot. The result is visible "
        f"(comfortable family, perfect home, peaceful evening). Product in background, part of the beautiful scene. "
        f'CRITICAL: Product stays FIXED in place in ALL 3 acts. Nobody touches it. Camera and environment do all the storytelling.",\n'
        f'  "keyframe_instruction": "ONE sentence that MUST appear in EVERY keyframe generation prompt. '
        f"Example for a thermostat: The Nest thermostat is MOUNTED FLAT ON A WHITE WALL at eye level, showing its round display. "
        f"Example for sneakers: The sneakers are WORN ON FEET, shown at ground level on pavement. "
        f'This sentence forces the image generator to place the product correctly."\n'
        f"}}\n\n"
        f"CRITICAL: Only include information you can CONFIRM from the product description and category. "
        f"Do NOT invent features or behaviors. If unsure, say 'not confirmed from available info'.\n"
        f"Return ONLY the JSON, no markdown."
    )

    try:
        client = genai.Client(
            vertexai=True,
            project=GOOGLE_CLOUD_PROJECT,
            location=GOOGLE_CLOUD_LOCATION,
        )
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=LLM_GEMINI_MODEL_MARKETING_ANALYST,
            contents=prompt_for_gemini,
            config=types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",
            ),
        )
        fidelity_data = json.loads(response.text.strip())
    except Exception as e:
        log_message(
            f"Failed to generate product fidelity prompt: {e}", Severity.ERROR
        )
        return {"status": "error", "details": str(e)}

    keyframe_instruction = fidelity_data.get("keyframe_instruction", "")

    fidelity_text = (
        f"# Product Fidelity Guide: {product_name} by {company_name}\n\n"
        f"## KEYFRAME INSTRUCTION (MUST appear in EVERY image/keyframe prompt)\n{keyframe_instruction}\n\n"
        f"## Physical Description\n{fidelity_data.get('physical_description', '')}\n\n"
        f"## Installation/Usage Context\n{fidelity_data.get('installation_context', '')}\n\n"
        f"## User Interaction\n{fidelity_data.get('user_interaction', '')}\n\n"
        f"## Visual Behavior\n{fidelity_data.get('visual_behavior', '')}\n\n"
        f"## Real-World Size\n{fidelity_data.get('real_world_size', '')}\n\n"
        f"## What NOT to Show in Ads\n{fidelity_data.get('what_NOT_to_show', '')}\n\n"
        f"## Ad Scene Suggestions\n{fidelity_data.get('ad_scene_suggestions', '')}\n\n"
        f"## Video Ad Guidance\n{fidelity_data.get('video_ad_guidance', '')}\n"
    )

    tool_context.state["PRODUCT_FIDELITY_PROMPT"] = fidelity_text
    tool_context.state["PRODUCT_KEYFRAME_INSTRUCTION"] = keyframe_instruction

    try:
        safe_name = product_name.replace(" ", "_")[:40]
        gcs_blob = f"{safe_name}/product_fidelity_prompt.md"
        utils_gcs.upload_to_gcs(
            GOOGLE_CLOUD_BUCKET_ARTIFACTS,
            fidelity_text.encode("utf-8"),
            gcs_blob,
        )
        log_message(
            f"Product fidelity prompt saved to GCS: {gcs_blob}", Severity.INFO
        )
    except Exception:
        pass

    return {
        "status": "success",
        "fidelity_prompt": fidelity_text,
        "details": "Product fidelity guide generated. Show it to the user for review. They can request changes before proceeding to ad generation.",
    }


def delete_asset_from_gcs(tool_context: ToolContext, filename: str):
    """Deletes a specific asset file from GCS. Call this BEFORE regenerating an asset
    to remove the old version the user rejected. Also removes the asset from session state
    so it won't be included in Google Ads publish.

    Args:
        filename: The filename to delete (e.g. 'img_c1_s1_urban_1.png', 'asset_sheet_c1_1.png', 'video_ad_123_456.mp4').
    """
    _set_output_folder(tool_context)
    deleted_uri = (
        f"gs://{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{OUTPUT_FOLDER}/{filename}"
    )
    try:
        from google.cloud import storage as gcs_storage

        storage_client = gcs_storage.Client(project=GOOGLE_CLOUD_PROJECT)
        bucket = storage_client.bucket(GOOGLE_CLOUD_BUCKET_ARTIFACTS)
        blob_path = f"{OUTPUT_FOLDER}/{filename}"
        blob = bucket.blob(blob_path)
        if blob.exists():
            blob.delete()
            log_message(
                f"Deleted old asset from GCS: {blob_path}", Severity.INFO
            )
        else:
            log_message(
                f"Asset not found in GCS (may already be deleted): {blob_path}",
                Severity.INFO,
            )
    except Exception as e:
        log_message(
            f"Failed to delete {filename} from GCS: {e}", Severity.WARNING
        )

    removed_count = 0
    session_artifacts = tool_context.state.get("SESSION_ARTIFACTS_STATE", {})
    if session_artifacts:
        keys_to_remove = [
            k
            for k, v in session_artifacts.items()
            if isinstance(v, dict)
            and (
                filename in (v.get("asset", {}).get("gcs_uri", "") or "")
                or filename in (v.get("asset", {}).get("filename", "") or "")
                or deleted_uri == (v.get("asset", {}).get("gcs_uri", "") or "")
            )
        ]
        for k in keys_to_remove:
            del session_artifacts[k]
            removed_count += 1
        if keys_to_remove:
            tool_context.state["SESSION_ARTIFACTS_STATE"] = session_artifacts

    for state_key in [
        SELECTED_IMAGES_STATE_KEY,
        SELECTED_VIDEOS_STATE_KEY,
        SELECTED_ASSET_SHEETS_STATE_KEY,
        GENERATED_GCS_URIS_STATE_KEY,
    ]:
        uri_list = tool_context.state.get(state_key, [])
        if isinstance(uri_list, list):
            cleaned = [
                u for u in uri_list if filename not in u and deleted_uri != u
            ]
            if len(cleaned) != len(uri_list):
                tool_context.state[state_key] = cleaned
                removed_count += len(uri_list) - len(cleaned)

    log_message(
        f"Removed {removed_count} references to {filename} from session state",
        Severity.INFO,
    )
    return {
        "status": "success",
        "details": f"Deleted {filename} and removed {removed_count} stale references from session state",
    }


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
        file_bytes=json.dumps(state_json).encode("utf-8"),
        destination_blob_name=_prefixed_blob(SESSION_STATE_FILE_NAME),
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
            blobs = list(
                bucket.list_blobs(prefix=f"{OUTPUT_FOLDER}/", max_results=50)
            )
            files = {
                "images": [],
                "videos": [],
                "text_ads": [],
                "asset_sheets": [],
            }
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


def _get_nonselected_assets(
    state_key: str, alternatives: list[str]
) -> list[str]:
    state_json = _get_state()
    selected_assets = state_json.get(state_key, [])
    return [a for a in alternatives if a not in selected_assets]


def _clear_selected_assets_of_type(state_key: str) -> None:
    state_json = _get_state()
    state_json[state_key] = []
    utils_gcs.upload_to_gcs(
        bucket_path=MARKETING_ANALYST_DATASTORE_CLOUD_BUCKET,
        file_bytes=json.dumps(state_json).encode("utf-8"),
        destination_blob_name=_prefixed_blob(SESSION_STATE_FILE_NAME),
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

    raise RuntimeError(
        "Could not retrieve campaigns config. Run setup_product_campaign first."
    )


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
    if product_image_uri and not tool_context.state.get(
        "_product_image_displayed"
    ):
        try:
            img_bytes, _ = utils_agents.download_bytes_from_reference(
                product_image_uri
            )
            if img_bytes:
                tool_context.state["_product_image_displayed"] = True
        except Exception:
            pass
    tool_context.state[GENERATED_GCS_URIS_STATE_KEY] = []

    # Store reference guidelines in session state for use by downstream generation steps
    if reference_guidelines and reference_guidelines.strip():
        tool_context.state[REFERENCE_GUIDELINES_STATE_KEY] = (
            reference_guidelines.strip()
        )

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
        return {
            "status": "error",
            "details": f"Failed to generate campaigns: {e}",
        }

    try:
        campaigns = parse_campaigns_from_xml(xml_content)
        if not campaigns:
            return {
                "status": "error",
                "details": "No valid campaigns generated.",
            }
        _CACHED_CAMPAIGNS_LIST = campaigns
        _CACHED_IDEAS_STRING = xml_content

        try:
            utils_gcs.upload_to_gcs(
                bucket_path=MARKETING_ANALYST_DATASTORE_CLOUD_BUCKET,
                file_bytes=xml_content.encode("utf-8"),
                destination_blob_name=_prefixed_blob(
                    f"generated_campaigns.{AGENT_VERSION}.xml"
                ),
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
        valid = [
            a
            for a in _get_nonselected_assets(
                SELECTED_CAMPAIGN_IDEAS_STATE_KEY, campaign_names
            )
            if a not in picked
        ]
        if not valid:
            valid = [a for a in campaign_names if a not in picked]
            if not valid:
                break
        name = random.choice(valid)
        picked.append(name)
        _add_selected_asset(SELECTED_CAMPAIGN_IDEAS_STATE_KEY, name)
        campaign = find_campaign_by_name(campaigns, name)
        if campaign:
            selected_campaigns.append(
                {
                    "name": campaign.name,
                    "hook": campaign.hook,
                    "insight": campaign.insight,
                    "visual_key": campaign.visual_key,
                    "tagline": campaign.tagline,
                    "why_it_works": campaign.why_it_works,
                    "segments": [s.name for s in campaign.segments],
                }
            )
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
        return {
            "status": "error",
            "details": f"No campaign named '{chosen_idea}'. Options: {names}",
        }
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
        return {
            "status": "error",
            "details": f"No campaign named '{selected_campaign_name}'",
        }
    save_selected_campaign(selected_campaign_name, tool_context)
    return campaign.relevant_brief


async def get_asset_sheet(
    tool_context: ToolContext, selected_campaign_name: str, quantity: int = 2
):
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
        valid = [
            a
            for a in _get_nonselected_assets(
                SELECTED_ASSET_SHEETS_STATE_KEY, all_alts
            )
            if a not in picked
        ]
        if not valid:
            valid = [a for a in all_alts if a not in picked]
            if not valid:
                break
        key = random.choice(valid)
        picked.append(key)
        _add_selected_asset(SELECTED_ASSET_SHEETS_STATE_KEY, key)
        sheet = next(
            (s for s in campaign.asset_sheets if (s.id or s.uri) == key), None
        )
        if sheet:
            selected_sheets.append(sheet)

    # Generate images on-demand and render as artifacts — ALL IN PARALLEL
    if selected_sheets:
        render_results = await asyncio.gather(
            *[
                _render_asset(sheet.uri, tool_context)
                for sheet in selected_sheets
            ],
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

    return {
        "status": "success",
        "asset_sheets": [s.model_dump() for s in selected_sheets],
    }


async def get_image_ads_for_audience(
    tool_context: ToolContext,
    quantity: int,
    segment_name: str,
    asset_sheet_uri: str,
    selected_campaign_name: str,
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
        return {
            "status": "error",
            "details": f"No campaign named '{selected_campaign_name}'",
        }

    segment = campaign.get_segment_by_name(segment_name)
    if not segment:
        return {
            "status": "error",
            "details": f"No segment named '{segment_name}'",
        }

    all_alts = [a.uri for a in segment.image_ads]
    selected_ads = []
    picked = []
    for _ in range(max(quantity, 1)):
        valid = [
            a
            for a in _get_nonselected_assets(
                SELECTED_IMAGES_STATE_KEY, all_alts
            )
            if a not in picked
        ]
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

    return {
        "status": "success",
        "image_ads": [a.model_dump() for a in selected_ads],
    }


async def get_video_ads_for_audience(
    tool_context: ToolContext,
    quantity: int,
    segment_name: str,
    asset_sheet_uri: str,
    selected_campaign_name: str,
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
        return {
            "status": "error",
            "details": f"No campaign named '{selected_campaign_name}'",
        }

    segment = campaign.get_segment_by_name(segment_name)
    if not segment:
        return {
            "status": "error",
            "details": f"No segment named '{segment_name}'",
        }

    all_alts = [a.uri for a in segment.video_ads]
    selected_ads = []
    picked = []
    for _ in range(max(quantity, 1)):
        valid = [
            a
            for a in _get_nonselected_assets(
                SELECTED_VIDEOS_STATE_KEY, all_alts
            )
            if a not in picked
        ]
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
        product_image_uri = tool_context.state.get(
            PRODUCT_IMAGE_URI_STATE_KEY, ""
        )
        company_name = tool_context.state.get(
            PRODUCT_COMPANY_NAME_STATE_KEY, ""
        )
        product_name = tool_context.state.get("PRODUCT_NAME", "product")

        async def _gen_video_ad(ad, idx):
            log_message(
                f"Generating video ad {idx + 1}/{len(selected_ads)}: {ad.rationale}",
                Severity.INFO,
            )
            return await _generate_full_video_ad(
                rationale=ad.rationale,
                product_image_uri=product_image_uri,
                company_name=company_name,
                product_name=product_name,
                tool_context=tool_context,
            )

        log_message(
            f"Launching {len(selected_ads)} video ads in parallel...",
            Severity.INFO,
        )
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
                (
                    video_bytes,
                    processing_time,
                    video_length,
                    storyline_summary,
                ) = result
                ts = int(time.time())
                filename = f"video_ad_{id(ad)}_{ts}.mp4"

                video_media = GeneratedMedia(
                    filename=filename,
                    mime_type="video/mp4",
                    media_bytes=video_bytes,
                )
                video_media = (
                    await utils_agents.save_to_artifact_and_render_asset(
                        asset=video_media,
                        context=tool_context,
                        save_in_gcs=True,
                        save_in_artifacts=True,
                        gcs_folder=OUTPUT_FOLDER,
                    )
                )

                public_url = f"https://storage.googleapis.com/{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{OUTPUT_FOLDER}/{filename}"
                d["gcs_url"] = public_url
                d["status"] = "generated"
                d["video_length"] = f"{video_length} seconds"
                if storyline_summary:
                    d["storyline"] = storyline_summary
            else:
                d["status"] = "failed"
            video_results.append(d)

        return {"status": "success", "video_ads": video_results}

    return {
        "status": "success",
        "video_ads": [a.model_dump() for a in selected_ads],
    }


# ============================================================
# Full Video Ad Pipeline
# ============================================================

STORYLINE_MODEL = "gemini-3.1-pro-preview"
LYRIA_MODEL = "lyria-3-pro-preview"

_VEO_SENSITIVE_WORDS = [
    "surveillance",
    "spy",
    "spying",
    "weapon",
    "gun",
    "knife",
    "blood",
    "violent",
    "violence",
    "attack",
    "kill",
    "murder",
    "death",
    "dead",
    "bomb",
    "explosive",
    "terror",
    "child",
    "children",
    "minor",
    "nude",
    "naked",
    "drugs",
    "injection",
    "syringe",
    "intruder",
    "burglar",
    "break-in",
    "breaking in",
    "trespasser",
    "stalker",
    "stalking",
]


def _sanitize_veo_prompt(prompt: str) -> str:
    """Removes words that VEO's content policy may flag."""
    sanitized = prompt
    for word in _VEO_SENSITIVE_WORDS:
        sanitized = (
            sanitized.replace(word, "")
            .replace(word.capitalize(), "")
            .replace(word.upper(), "")
        )
    return " ".join(sanitized.split())


async def _generate_storyline(
    company_name: str,
    product_name: str,
    rationale: str,
    reference_guidelines: str = "",
    customer_persona: str = "",
) -> dict:
    """Gemini generates a 3-act storyline with per-act voiceover and motion prompts.

    Each act is 8 seconds. Voiceover is split per act (~20 words each = 8s at 2.5 words/sec).
    No overlap between acts — each voiceover chunk is self-contained.
    """
    ACTS = 3
    CLIP_SEC = 8
    words_per_act = (
        15  # ~2 words/sec x 8s (energetic pace with speaking_rate=0.95)
    )

    try:
        client = genai.Client(
            vertexai=True, project=GOOGLE_CLOUD_PROJECT, location="global"
        )
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
            f"- STORY IS ABOUT PEOPLE, NOT THE PRODUCT. Show how the product makes people's lives better.\n"
            f"- People laughing, playing, relaxing, cooking, celebrating — the product is simply THERE in the background.\n"
            f"- DO NOT show close-ups of the product. DO NOT zoom into the product. Keep it small and natural in scene.\n"
            f"- Example: kids chasing bubbles in a garden (bubble maker on table), family watching movie (thermostat on wall)\n"
            f"- The product NEVER activates, moves, transforms, or does anything — it just EXISTS in the scene\n"
            f"- BELIEVABILITY TEST: Before writing each scene, ask yourself 'Could I film this with a real camera in a real location?'\n"
            f"  If the answer is NO — rewrite the scene. Every single moment must be something that happens in real life.\n"
            f"  NO: objects appearing/disappearing, things flying, gravity-defying moments, morphing, glowing effects\n"
            f"  YES: people walking, pouring drinks, picking up products, looking at screens, cooking, traveling\n\n"
            f"Product details:\n"
            f"Brand: {company_name}\nProduct: {product_name}\nAd concept: {rationale}\n"
            f"{guidelines_context}{persona_context}\n"
            f"The video is {ACTS * CLIP_SEC} seconds total — 3 acts of {CLIP_SEC} seconds each.\n\n"
            f"YOU ARE A PREMIUM AD DIRECTOR shooting a real commercial with a real film crew.\n"
            f"Write each act as a DETAILED SHOT LIST — so specific that a cinematographer could film it WITHOUT asking questions.\n\n"
            f"For EACH act you MUST specify ALL of these:\n"
            f"- SHOT TYPE: wide establishing / medium / close-up / over-the-shoulder\n"
            f"- CAMERA: exact movement (steadicam walk forward 10 feet, dolly push-in 3 feet, static tripod, slow 15-degree orbit left)\n"
            f"- FRAMING: exactly where the product is in frame (center, right third, background left, visible but not dominant)\n"
            f"- LIGHTING: specific source and quality (warm tungsten from table lamp camera-left, natural overcast daylight through window, golden hour backlight)\n"
            f"- ENVIRONMENT: specific details about the room, furniture, weather, time of day, season cues\n"
            f"- PEOPLE: what specific people are doing, their position, body language, gaze direction (or 'no people in frame')\n"
            f"- PRODUCT STATE: exactly what the product display shows, what color/mode, how it looks from this angle\n"
            f"- PRODUCT PLACEMENT: the product's EXACT position (e.g. 'mounted on the white wall between the hallway and living room, 5 feet from the floor')\n"
            f"- MOOD: one-word mood descriptor (serene, warm, energetic, cozy, dramatic)\n\n"
            f"STORY FLOW MANDATE:\n"
            f"The 3 acts MUST tell ONE connected story — each scene flows naturally into the next.\n"
            f"Think of it as one continuous narrative shot in one location:\n"
            f"  Act 1 (0-{CLIP_SEC}s): ESTABLISHING — Wide shot. Camera enters the space like a person walking in. "
            f"We see the environment, the mood, the weather/time of day. Product is visible in its installed position "
            f"but the camera is NOT focused on it — it's part of the background. KEEP IT SIMPLE.\n"
            f"  Act 2 ({CLIP_SEC}-{CLIP_SEC*2}s): HERO — Camera moves closer to the product. Medium or close-up. "
            f"The product display is clearly visible. NOBODY touches it. The environment around it tells the story. "
            f"KEEP THE PRODUCT EXACTLY AS IT LOOKS IN THE REFERENCE — no added parts, no thick shadow, no base plate.\n"
            f"  Act 3 ({CLIP_SEC*2}-{CLIP_SEC*3}s): PAYOFF — Camera pulls back to show the lifestyle result. "
            f"Comfortable scene with people. Product in background in its installed position. KEEP IT SIMPLE AND REAL.\n\n"
            f"SIMPLICITY MANDATE — CRITICAL:\n"
            f"- SIMPLE scenes are BETTER than complex ones. A family on a couch > an elaborate party scene.\n"
            f"- FEWER elements per scene = LESS hallucination. Don't overcrowd the scene with details.\n"
            f"- The product should be SMALL in frame and NATURAL — not the giant centerpiece.\n"
            f"- Describe ONLY what a real camera would capture in a real home. No cinematic effects, no CGI.\n"
            f"- Every word in your scene description will be interpreted literally by the AI — choose words carefully.\n"
            f"- AVOID words that cause hallucination: 'glowing', 'radiating', 'pulsing', 'transforming', 'revealing', 'emerging'\n"
            f"- USE words that keep it grounded: 'sitting', 'mounted', 'resting', 'visible', 'showing', 'displaying'\n\n"
            f"VALIDATION — before outputting, check each act:\n"
            f"1. Is the product in its CORRECT installed position? (not on a table if wall-mounted)\n"
            f"2. Does the description avoid words that could make AI hallucinate? (no 'glowing', 'transforming', etc.)\n"
            f"3. Could a real film crew shoot this EXACTLY as described? If not, simplify.\n"
            f"4. Is the product described the SAME WAY in all 3 acts? (same size, same position, same look)\n"
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
            f"- NO: product opening up, revealing internals, disassembling, morphing, or transforming\n"
            f"- NO: adding parts, features, screens, buttons, or components that are NOT in the reference image\n"
            f"- The product looks IDENTICAL in every frame — same shape, same size, same details as the reference\n"
            f"- Products sit on surfaces, liquids flow down, people stand on ground\n"
            f"- Objects do NOT move by themselves — only a human hand can move an object\n"
            f"- Objects do NOT teleport, change location, fall over, roll away, or disappear\n"
            f"- The product does NOT open, close, fold, unfold, transform, or animate on its own\n"
            f"- The product stays IN PLACE — it does NOT move, spin, rotate, fly, or animate on its own\n"
            f"- People interact with the product EXACTLY as they would in real life:\n"
            f"  * A thermostat → person gently touches it or walks past it on the wall, the DISPLAY changes — the product itself DOES NOT MOVE\n"
            f"  * A phone → person taps the screen, swipes, holds it naturally — does NOT spin it\n"
            f"  * A speaker → person speaks to it from across the room — does NOT pick it up and rotate it\n"
            f"  * A camera → it sits on its mount — person walks past it, it does NOT move\n"
            f"- NEVER show someone spinning, rotating, flipping, or tossing the product — this is NOT a product unboxing video\n"
            f"- The product's DISPLAY/SCREEN can change content (temperature, color, brightness) but the physical product stays fixed\n"
            f"- People walk naturally, sit naturally, hold things naturally — no supernatural movements\n"
            f"- Every scene must look like something that ACTUALLY HAPPENS in real life\n"
            f"- If you wouldn't see it in a real TV commercial filmed with real cameras, DON'T include it\n\n"
            f"SPATIAL LOGIC & CORRECT PRODUCT PLACEMENT:\n"
            f"- People MUST face/look at what they're using — a family watching TV must ALL face the screen\n"
            f"- Body orientation must match the activity — no one has their back to what they're watching/using\n"
            f"- Hands must contact the product correctly — holding phone = looking at screen, not away from it\n"
            f"- Product MUST be in its CORRECT installation/usage context:\n"
            f"  * Wall-mounted (thermostat, camera, doorbell, TV) → MOUNTED ON A WALL, never on a table. "
            f"Sits FLUSH against wall — NO thick base plate, NO mounting bracket, NO oversized shadow behind it.\n"
            f"  * Router/modem → on shelf near TV/desk, devices connected to it\n"
            f"  * Phone/tablet → in hands, screen facing user, user looking down at it\n"
            f"  * Headphones → on ears, person immersed in audio\n"
            f"  * Drink/food → on table or in hand, person engaged with it\n"
            f"- Product at CORRECT real-world SIZE — proportional to hands, walls, furniture\n"
            f"- ONLY show angles visible in reference images — do NOT fabricate back/bottom/internals\n"
            f"- If product has a SCREEN/DISPLAY, show realistic changing content — not frozen\n"
            f"- COMMON SENSE: 'If I walked into this room, would everyone's position and attention make sense?'\n\n"
            f"MOTION MANDATE — CRITICAL:\n"
            f"- EVERY motion_prompt MUST describe CONTINUOUS camera and/or subject movement for the FULL {CLIP_SEC} seconds\n"
            f"- The camera MUST ALWAYS be moving: dolly, steadicam track, crane, orbit, handheld walk, push-in, pull-out\n"
            f"- NO static shots. NO still frames. The video must have constant cinematic motion throughout\n"
            f"- Also describe subject movement: person walking, wind blowing, hands gently interacting with the product\n"
            f"- NEVER describe the product rotating, spinning, or moving — only the CAMERA moves around the product\n\n"
            f"PRODUCT FIDELITY — CRITICAL:\n"
            f"- The product MUST appear EXACTLY as in the reference image — same shape, color, screen content, size\n"
            f"- Do NOT remove, add, or alter ANY part of the product. Do NOT fabricate back/bottom/internals.\n"
            f"- Product must be shown in its CORRECT installation context (wall-mounted on wall, handheld in hand, etc.)\n"
            f"- PRODUCT BEHAVIOR: study ALL reference images AND the product description to understand how it ACTUALLY works.\n"
            f"- ONLY show features and behaviors that are CONFIRMED in the product description or visible in reference images.\n"
            f"- Do NOT invent features, interactions, or visual behaviors that aren't documented.\n"
            f"- If unsure how the product works, just show it in its installed position with the CAMERA moving around it "
            f"and people in the environment — do NOT show anyone manipulating the product in ways you're not sure about.\n"
            f"- The story revolves AROUND the product — the product stays in place, the world moves around it.\n\n"
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
            f"],\n"
            f'"storyline": "Combined voiceover script for all 3 acts (~{words_per_act * ACTS} words total)",\n'
            f'"lyria_prompt": "A concise prompt (under 80 words) for instrumental background music that PERFECTLY matches the storyline mood and energy. '
            f"The music must make viewers feel the SAME emotion as the video — if the ad is luxurious, the music is sophisticated; "
            f"if the ad is adventurous, the music is thrilling; if the ad is heartwarming, the music is tender then uplifting. "
            f"Must build progressively with the storyline arc — start engaging, build momentum, finish with an unforgettable crescendo. "
            f"STRICTLY INSTRUMENTAL — NO vocals, NO lyrics, NO singing. "
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
            client,
            STORYLINE_MODEL,
            prompt,
            config=types.GenerateContentConfig(
                temperature=1.0, top_p=0.95, max_output_tokens=8192
            ),
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


async def _generate_single_veo_clip(
    prompt: str,
    start_frame_gcs_uri: str,
    clip_duration: int = 6,
    end_frame_gcs_uri: str | None = None,
    label: str = "clip",
) -> bytes | None:
    """Generates a single VEO video clip from a keyframe image."""
    mode = "interpolation" if end_frame_gcs_uri else "i2v"
    try:
        client = genai.Client(
            vertexai=True, project=GOOGLE_CLOUD_PROJECT, location="global"
        )
        img_mime = "image/png"

        last_frame = None
        if end_frame_gcs_uri:
            last_frame = types.Image(
                gcs_uri=end_frame_gcs_uri, mime_type=img_mime
            )

        veo_config = types.GenerateVideosConfig(
            number_of_videos=1,
            duration_seconds=clip_duration,
            aspect_ratio="16:9",
            last_frame=last_frame,
            generate_audio=False,
            person_generation="allow_all",
        )

        log_message(
            f"VEO {label} ({mode}): submitting {clip_duration}s clip...",
            Severity.INFO,
        )

        operation = None
        for veo_attempt in range(3):
            try:
                operation = client.models.generate_videos(
                    model=VEO_MODEL,
                    prompt=prompt,
                    image=types.Image(
                        gcs_uri=start_frame_gcs_uri, mime_type=img_mime
                    ),
                    config=veo_config,
                )
                break
            except Exception as submit_err:
                if "429" in str(submit_err) or "RESOURCE_EXHAUSTED" in str(
                    submit_err
                ):
                    backoff = (2**veo_attempt) * 5 + random.uniform(0, 3)
                    log_message(
                        f"VEO {label}: 429 on submit, backoff {backoff:.1f}s (attempt {veo_attempt+1}/3)",
                        Severity.WARNING,
                    )
                    await asyncio.sleep(backoff)
                else:
                    raise
        if not operation:
            log_message(
                f"VEO {label} ({mode}): failed to submit after 3 retries",
                Severity.ERROR,
            )
            return None

        for poll in range(80):
            if operation.done:
                break
            await asyncio.sleep(10)
            operation = client.operations.get(operation)

        if not operation.done:
            log_message(
                f"VEO {label} ({mode}): timed out after {80 * 10}s polling",
                Severity.ERROR,
            )
            return None
        if operation.error:
            log_message(
                f"VEO {label} ({mode}): operation error: {operation.error}",
                Severity.ERROR,
            )
            return None
        if not operation.response or not operation.response.generated_videos:
            log_message(
                f"VEO {label} ({mode}): no videos in response", Severity.ERROR
            )
            return None

        generated = operation.response.generated_videos[0]
        if not generated.video or not generated.video.video_bytes:
            log_message(
                f"VEO {label} ({mode}): generated video has no bytes",
                Severity.ERROR,
            )
            return None

        log_message(
            f"VEO {label} ({mode}): success, {len(generated.video.video_bytes):,} bytes",
            Severity.INFO,
        )
        return generated.video.video_bytes
    except Exception as e:
        log_message(f"VEO {label} ({mode}) exception: {e}", Severity.ERROR)
        return None


async def _generate_lyria_music(
    lyria_prompt: str, product_name: str
) -> bytes | None:
    """Generates instrumental background music using Lyria from the storyline's lyria_prompt."""
    try:
        client = genai.Client(
            vertexai=True, project=GOOGLE_CLOUD_PROJECT, location="global"
        )

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
            client,
            LYRIA_MODEL,
            lyria_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO", "TEXT"]
            ),
            label="lyria-music",
        )
        for part in response.parts:
            if part.inline_data and part.inline_data.data:
                log_message(
                    f"Lyria music generated: {len(part.inline_data.data) // 1024} KB",
                    Severity.INFO,
                )
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
                log_message(
                    f"Voiceover generated: {len(response.audio_content)} bytes",
                    Severity.INFO,
                )
                return response.audio_content
        except Exception as e:
            log_message(
                f"TTS attempt {attempt + 1}/3 failed: {e}", Severity.WARNING
            )
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

        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_file,
            "-c",
            "copy",
            out_path,
        ]
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


def _mix_audio_onto_video(
    video_bytes: bytes, voiceover_bytes: bytes | None, music_bytes: bytes | None
) -> bytes:
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
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                vid_path,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        video_duration = (
            float(probe.stdout.strip()) if probe.returncode == 0 else 24.0
        )
        log_message(
            f"Video duration for audio mix: {video_duration}s", Severity.INFO
        )

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
            "ffmpeg",
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
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            out_path,
        ]

        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode == 0:
            with open(out_path, "rb") as f:
                return f.read()
        else:
            log_message(
                f"Audio mix failed: {result.stderr.decode()[:300]}",
                Severity.WARNING,
            )
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


def _overlay_logo_on_video(
    video_bytes: bytes, logo_bytes: bytes, opacity: float = 0.8
) -> bytes:
    """Overlays logo on video top-right corner using ffmpeg. Preserves transparency."""
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
            "ffmpeg",
            "-y",
            "-i",
            vid_path,
            "-i",
            logo_path,
            "-filter_complex",
            f"[1:v]scale=iw*0.15:-1,format=rgba,colorchannelmixer=aa={opacity}[logo];"
            f"[0:v][logo]overlay=W-w-20:20[out]",
            "-map",
            "[out]",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-c:a",
            "copy",
            out_path,
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


def _add_text_overlays(
    video_bytes: bytes,
    company_name: str,
    tagline: str,
    video_duration: float,
    product_name: str = "",
    price: str = "",
) -> bytes:
    """Adds cinematic text overlays: brand + product at start, tagline mid-video, price near end."""
    import subprocess

    vid_path = "/tmp/_text_video.mp4"
    out_path = "/tmp/_text_output.mp4"

    try:
        with open(vid_path, "wb") as f:
            f.write(video_bytes)

        def _sanitize(text):
            return (
                text.replace("'", "")
                .replace(":", "")
                .replace("\\", "")
                .replace('"', "")
            )

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
            "ffmpeg",
            "-y",
            "-i",
            vid_path,
            "-vf",
            filter_str,
            "-c:a",
            "copy",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-movflags",
            "+faststart",
            out_path,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        if result.returncode == 0:
            with open(out_path, "rb") as f:
                return f.read()
        log_message(
            f"Text overlay failed: {result.stderr.decode()[:200]}",
            Severity.WARNING,
        )
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


def _add_end_card(
    video_bytes: bytes,
    logo_bytes: bytes | None,
    company_name: str,
    tagline: str,
    duration: float = 3.0,
    product_bytes: bytes | None = None,
) -> bytes:
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
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,r_frame_rate",
                "-of",
                "csv=p=0",
                vid_path,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        parts = probe.stdout.strip().split(",")
        w, h = int(parts[0]), int(parts[1])

        safe_company = company_name.replace("'", "").replace(":", "")
        safe_tagline = (
            (tagline.replace("'", "").replace(":", "")[:50]) if tagline else ""
        )

        inputs = [
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s={w}x{h}:d={duration}:r=24",
        ]
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
        inputs.extend(
            ["-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={duration}"]
        )
        audio_idx = overlay_idx

        # Build filter: product on left, logo+text on right
        filter_complex = ""
        current_label = "0:v"

        if has_product:
            filter_complex += (
                f"[{product_input_idx}:v]scale=-1:{int(h*0.6)}[prod];"
            )
            filter_complex += (
                f"[{current_label}][prod]overlay=W*0.08:(H-h)/2[withprod];"
            )
            current_label = "withprod"

        if has_logo:
            filter_complex += f"[{logo_input_idx}:v]scale=-1:{h//6}[logo];"
            logo_x = "W*0.65" if has_product else "(W-w)/2"
            logo_y = "H*0.25" if has_product else "H*0.3"
            filter_complex += (
                f"[{current_label}][logo]overlay={logo_x}:{logo_y}[withlogo];"
            )
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
            "ffmpeg",
            "-y",
            *inputs,
            "-filter_complex",
            filter_complex,
            "-map",
            "[out]",
            "-map",
            f"{audio_idx}:a",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-c:a",
            "aac",
            "-shortest",
            card_path,
        ]

        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode != 0:
            log_message(
                f"End card generation failed: {result.stderr.decode()[:200]}",
                Severity.WARNING,
            )
            return video_bytes

        # Concat video + end card
        list_file = "/tmp/_endcard_list.txt"
        with open(list_file, "w") as f:
            f.write(f"file '{vid_path}'\nfile '{card_path}'\n")

        concat_cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_file,
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            out_path,
        ]
        result = subprocess.run(concat_cmd, capture_output=True, timeout=60)
        if result.returncode == 0:
            with open(out_path, "rb") as f:
                return f.read()
        log_message(
            f"End card concat failed: {result.stderr.decode()[:200]}",
            Severity.WARNING,
        )
        return video_bytes
    except Exception as e:
        log_message(f"End card error: {e}", Severity.WARNING)
        return video_bytes
    finally:
        for p in [
            vid_path,
            logo_path,
            product_path,
            card_path,
            out_path,
            "/tmp/_endcard_list.txt",
        ]:
            try:
                os.unlink(p)
            except Exception:
                pass


def _add_end_card_overlay(
    video_bytes: bytes, company_name: str, tagline: str, product_price: str = ""
) -> bytes:
    """Overlays brand name, tagline, and price on the last 3 seconds of the video — no separate end card."""
    import subprocess

    vid_path = "/tmp/_endoverlay_video.mp4"
    out_path = "/tmp/_endoverlay_output.mp4"

    try:
        with open(vid_path, "wb") as f:
            f.write(video_bytes)

        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                vid_path,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        duration = (
            float(probe.stdout.strip()) if probe.returncode == 0 else 24.0
        )
        start = max(0, duration - 3)

        def _s(text):
            return (
                text.replace("'", "")
                .replace(":", "")
                .replace("\\", "")
                .replace('"', "")
            )

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
            "ffmpeg",
            "-y",
            "-i",
            vid_path,
            "-vf",
            ",".join(filters),
            "-c:a",
            "copy",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-movflags",
            "+faststart",
            out_path,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        if result.returncode == 0:
            with open(out_path, "rb") as f:
                return f.read()
        log_message(
            f"End card overlay failed: {result.stderr.decode()[:200]}",
            Severity.WARNING,
        )
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
    rationale: str,
    product_image_uri: str,
    company_name: str,
    product_name: str,
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
        product_bytes, _ = utils_agents.download_bytes_from_reference(
            product_image_uri
        )
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

    # Retrieve reference guidelines, fidelity prompt, and customer persona from session state
    ref_guidelines = tool_context.state.get(REFERENCE_GUIDELINES_STATE_KEY, "")
    fidelity_prompt = tool_context.state.get("PRODUCT_FIDELITY_PROMPT", "")
    if fidelity_prompt:
        ref_guidelines = (
            f"{ref_guidelines}\n\nPRODUCT FIDELITY GUIDE:\n{fidelity_prompt}"
            if ref_guidelines
            else f"PRODUCT FIDELITY GUIDE:\n{fidelity_prompt}"
        )
    customer_persona = tool_context.state.get(CUSTOMER_PERSONA_STATE_KEY, "")

    # ================================================================
    # PHASE 1: Storyline (needed before keyframes)
    # Lyria + Voiceover start later alongside VEO to overlap
    # ================================================================
    log_message("Phase 1: Storyline...", Severity.INFO)

    storyline_data = {}
    try:
        storyline_data = await _generate_storyline(
            company_name,
            product_name,
            rationale,
            reference_guidelines=ref_guidelines,
            customer_persona=customer_persona,
        )
        if not isinstance(storyline_data, dict):
            storyline_data = {}
    except Exception as e:
        log_message(f"Storyline failed: {e}", Severity.WARNING)

    voiceover_script = storyline_data.get("storyline", "")
    lyria_prompt_from_storyline = storyline_data.get("lyria_prompt", "")
    acts = storyline_data.get("acts", [])
    while len(acts) < ACTS:
        acts.append(
            acts[-1]
            if acts
            else {
                "scene_description": "Hero shot",
                "motion_prompt": "Slow push-in",
            }
        )
    acts = acts[:ACTS]

    import re as _val_re

    hallucination_words = [
        "glowing",
        "radiating",
        "pulsing",
        "transforming",
        "revealing",
        "emerging",
        "morphing",
        "floating",
        "hovering",
        "spinning",
        "rotating",
        "flying",
        "exploding",
        "disassembling",
        "opening up",
        "unfolding",
        "activating",
        "powering on",
        "turning on",
        "lighting up",
        "blinking",
        "twisting",
    ]
    for act in acts:
        for field in [
            "scene_description",
            "motion_prompt",
            "end_scene_description",
        ]:
            text = act.get(field, "")
            for word in hallucination_words:
                if word.lower() in text.lower():
                    text = _val_re.sub(
                        word, "visible", text, flags=_val_re.IGNORECASE
                    )
                    log_message(
                        f"Storyline validation: replaced '{word}' with 'visible' in {field}",
                        Severity.WARNING,
                    )
            act[field] = text

    # Start voiceover + Lyria immediately — they run alongside keyframes + VEO
    vo_task = asyncio.create_task(_generate_voiceover_audio(voiceover_script))
    lyria_task = asyncio.create_task(
        _generate_lyria_music(lyria_prompt_from_storyline, product_name)
    )

    # ================================================================
    # PHASE 2: Generate 5 keyframe images in parallel
    # Each keyframe MUST be a COMPLETELY DIFFERENT scene/environment
    # ================================================================
    log_message(
        f"Phase 2: Generating {NUM_KEYFRAMES} distinct keyframes...",
        Severity.INFO,
    )
    refs = [product_bytes] + ([logo_bytes] if logo_bytes else [])

    # 4 keyframes with DRAMATIC bright-to-dark progression — wow visual transitions
    kf_environments = [
        "BRIGHT DAYLIGHT — vivid sunlight, clean blue sky, sharp shadows. Fresh, energetic, vibrant. High-key lighting.",
        "GOLDEN HOUR — warm amber backlighting, lens flares, dramatic long shadows. Wind visible in environment. Magical warmth.",
        "DRAMATIC DUSK — deep orange and purple sky, silhouette edges, moody atmosphere. Cinematic transition moment. Wow factor.",
        "NIGHT / NEON — dark environment with dramatic artificial lighting. City lights, neon reflections, glowing edges on product. High contrast, bold.",
    ]

    kf_descriptions = [
        acts[0].get(
            "scene_description", f"Bright reveal of {product_name} in daylight"
        ),
        acts[0].get(
            "end_scene_description",
            acts[1].get("scene_description", f"{product_name} in golden hour"),
        ),
        acts[1].get(
            "end_scene_description",
            acts[2].get(
                "scene_description", f"{product_name} at dramatic dusk"
            ),
        ),
        acts[2].get(
            "end_scene_description",
            f"Hero shot of {product_name} in dramatic night lighting with {company_name}",
        ),
    ]

    # Build guidelines and persona context for keyframes
    kf_guidelines = ""
    if ref_guidelines:
        kf_guidelines = f"\nBRAND GUIDELINES (follow for visual style and tone): {ref_guidelines[:500]}\n"
    kf_persona = ""
    if customer_persona:
        kf_persona = (
            f"\nCUSTOMER PERSONA (tailor scene to this audience): {customer_persona}\n"
            f"Show people, environments, and scenarios that resonate with this specific customer type.\n"
        )

    kf_placement = tool_context.state.get("PRODUCT_KEYFRAME_INSTRUCTION", "")

    async def _gen_kf(idx):
        is_final = idx == NUM_KEYFRAMES - 1
        placement_line = ""
        if kf_placement:
            placement_line = f"MANDATORY PRODUCT PLACEMENT: {kf_placement}\n\n"
        prompt = (
            f"Photorealistic commercial photograph for a {product_name} ad by {company_name}.\n"
            f"Keyframe #{idx + 1} of {NUM_KEYFRAMES} — these keyframes form a connected visual story.\n\n"
            f"{placement_line}"
            f"SCENE: {kf_descriptions[idx]}\n\n"
            f"LIGHTING & ATMOSPHERE: {kf_environments[idx]}\n\n"
            f"PRODUCT IN REAL LIFE — ABSOLUTELY CRITICAL:\n"
            f"- Study the reference image(s) to understand EXACTLY what the product looks like from ALL angles\n"
            f"- Show the product in its CORRECT INSTALLATION/USAGE CONTEXT — how it is actually used in real life:\n"
            f"  * Wall-mounted products (thermostats, cameras, switches, TVs) → MOUNTED ON A WALL, never on a table. "
            f"Product sits FLUSH against the wall — NO thick base plate, NO visible mounting bracket, NO oversized shadow behind it. "
            f"The product should look like it's seamlessly part of the wall.\n"
            f"  * Tabletop products (speakers, routers, bottles) → on a table, shelf, or counter\n"
            f"  * Wearable products (watches, headphones, glasses) → being WORN by a person\n"
            f"  * Handheld products (phones, tablets, controllers) → being HELD in hands\n"
            f"  * Bottles/drinks → standing on a solid surface, being poured, held in hand\n"
            f"  * Boots/shoes → being WORN on feet, on the ground, on a shelf\n"
            f"- ONLY show angles/sides of the product that are visible in the reference images\n"
            f"- Do NOT fabricate or imagine the back, bottom, or internal parts of a product if not shown in reference\n"
            f"- If you only have a FRONT view, only show the front — do not invent what the back looks like\n"
            f"- Product MUST be at CORRECT REAL-WORLD physical size — a thermostat is ~4 inches, not 2 feet\n"
            f"- A person's hand should be proportional to the product — check real-world dimensions\n"
            f"- PHYSICS MUST BE REAL: gravity applies, liquids flow downward, objects rest on surfaces\n"
            f"- NOTHING floats, hovers, or defies gravity unless it's an actual flying product (drone)\n"
            f"- NO magical suspended ingredients, NO floating particles, NO surreal compositions\n"
            f"- Reproduce the product with exact fidelity — same shape, color, design, SCREEN CONTENT as reference\n"
            f"- PRODUCT BEHAVIOR — study the reference images to understand HOW the product works:\n"
            f"  * If the product has a DISPLAY/SCREEN that changes (thermostat, phone, watch), show DIFFERENT "
            f"realistic content in each shot — different temperatures, different apps, different times\n"
            f"  * If the display has COLOR CODING (e.g. thermostat: blue=cool, orange=warm, green=eco), "
            f"the color MUST match the displayed value — do NOT show orange at 65°F or blue at 80°F\n"
            f"  * If the product changes appearance based on state (LED colors, screen brightness), show it accurately\n"
            f"  * Study ALL reference images to learn the product's visual language and apply it correctly\n"
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
            f"SPATIAL LOGIC — CRITICAL:\n"
            f"- People MUST face/look at what they're using — a family watching TV ALL face the screen\n"
            f"- Body orientation matches the activity — sitting toward the TV, facing the counter while cooking\n"
            f"- Hands contact the product correctly — holding phone means eyes on screen, pouring means hand on bottle\n"
            f"- Product placement must make physical sense — router near TV/desk, phone in hand, headphones on ears\n"
            f"- Every person's gaze, posture, and hands must be coherent with the scene's story\n"
            f"- COMMON SENSE: 'If I walked into this room, would this scene look normal?'\n\n"
            f"{'Include brand name ' + company_name + ' as elegant text in the scene.' if is_final else ''}"
            f"{kf_guidelines}{kf_persona}"
            f"Product at CORRECT real-world scale. 16:9 landscape. Single image. Return only the image."
        )
        return await _generate_gemini_image(
            prompt, refs, label=f"keyframe {idx + 1}/{NUM_KEYFRAMES}"
        )

    # Generate all keyframes in parallel
    kf_results = await asyncio.gather(
        *[_gen_kf(i) for i in range(NUM_KEYFRAMES)],
        return_exceptions=True,
    )
    keyframes = [
        r if isinstance(r, bytes) else product_bytes for r in kf_results
    ]
    log_message(
        f"Keyframes: {sum(1 for r in kf_results if isinstance(r, bytes))}/{NUM_KEYFRAMES} generated",
        Severity.INFO,
    )

    # Upload keyframes to GCS — parallel
    kf_blobs = [
        f"{OUTPUT_FOLDER}/_keyframe_{i + 1}.png" for i in range(NUM_KEYFRAMES)
    ]
    await asyncio.gather(
        *[
            asyncio.to_thread(
                utils_gcs.upload_to_gcs,
                GOOGLE_CLOUD_BUCKET_ARTIFACTS,
                img,
                blob,
            )
            for img, blob in zip(keyframes, kf_blobs)
        ]
    )
    kf_uris = [
        f"gs://{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{blob}" for blob in kf_blobs
    ]

    # ================================================================
    # PHASE 3: VEO clips — all parallel (voiceover + Lyria already in flight)
    # ================================================================
    log_message(
        "Phase 3: VEO clips (parallel, voiceover + Lyria already in flight)...",
        Severity.INFO,
    )

    transition_effects = [
        "WALKING THROUGH THE HOME: Camera moves like a person walking naturally through the space — entering the room, noticing the environment, and gradually discovering the product in its installed position. Smooth steadicam walk-through. No abrupt cuts or zooms.",
        "LIFE UNFOLDING: Camera follows a person's natural movement through the space — they go about their daily routine while the product sits naturally in its environment. The camera gently drifts toward the product as part of the scene, never forcing attention. Organic, documentary-style.",
        "GENTLE APPROACH: Camera slowly pushes in from a wide establishing shot, revealing more detail of the room and the product's context. Like walking toward it from across the room. The product grows naturally in frame — no dramatic zoom, no abrupt close-up.",
    ]

    def _build_motion_prompt(act_idx):
        act = acts[act_idx]
        base_motion = act.get(
            "motion_prompt", f"Cinematic shot of {product_name}"
        )
        transition = transition_effects[
            min(act_idx, len(transition_effects) - 1)
        ]
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
            f"The product must NEVER change size, shape, open, close, fold, unfold, transform, morph, or animate. "
            f"NO lens opening, NO shutter closing, NO parts moving, NO lights blinking on/off, NO mechanical motion. "
            f"NO adding extra parts, screens, buttons, rings, or components that are NOT in the reference image. "
            f"The product is a FIXED, STATIC object in its CORRECT installation position (wall-mounted stays on wall, tabletop stays on table). "
            f"It does NOT move. Only its DISPLAY/SCREEN content may change if it has one. "
            f"Only the ENVIRONMENT, CAMERA, and PEOPLE move around it. "
            f"The product looks PIXEL-PERFECT IDENTICAL to the reference photo at ALL times — same shape, same color, same size, same details. "
            f"Do NOT show the back, bottom, or internal parts of the product unless they are in the reference image. "
            f"NO thick base plates, brackets, or oversized shadows behind the product. Wall-mounted products sit FLUSH against the wall. "
            f"Camera CAN zoom in/out and focus on the product — that's fine and encouraged. "
            f"But do NOT hallucinate about the product — no opening it, no adding parts, no showing internals. "
            f"When the camera focuses on the product, show it EXACTLY as it looks in the reference — nothing added, nothing removed. "
            f"NO thick base plates, NO mounting brackets, NO oversized shadows behind wall-mounted products. "
            f"Wall-mounted products sit FLUSH against the wall with minimal visible depth — they look seamlessly integrated. "
            f"The product is the HERO of the scene but presented HONESTLY — no fake features, no imagined behaviors. "
            f"PEOPLE MOVE NATURALLY: walking is smooth, arms move realistically, no sudden jumps or teleporting. "
            f"Think of this as a REAL video shot with a REAL camera — nothing magical, nothing impossible."
        )

    async def _gen_clip(act_idx):
        label = f"act{act_idx + 1}/{ACTS}"
        motion = _sanitize_veo_prompt(_build_motion_prompt(act_idx))
        start_uri = kf_uris[act_idx]
        end_uri = kf_uris[act_idx + 1]

        result = await _generate_single_veo_clip(
            motion, start_uri, CLIP_SEC, end_uri, label=label
        )
        if result is None:
            log_message(
                f"Clip {label} interpolation failed, retrying as i2v (no end frame)",
                Severity.WARNING,
            )
            result = await _generate_single_veo_clip(
                motion, start_uri, CLIP_SEC, None, label=f"{label}-retry"
            )
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
        result = await _generate_single_veo_clip(
            motion, kf_uris[act_idx], CLIP_SEC, None, label=label
        )
        if isinstance(result, bytes):
            clip_map[act_idx] = result
        else:
            log_message(
                f"Clip {label} failed after all retries", Severity.ERROR
            )

    # SAFETY NET: If any clips still missing, regenerate with safe product-only keyframe
    missing_acts = [i for i in range(ACTS) if i not in clip_map]
    if missing_acts:
        log_message(
            f"Safety net: {len(missing_acts)} clips still missing. Regenerating with product-only keyframes.",
            Severity.WARNING,
        )
        for act_idx in missing_acts:
            safe_prompt = (
                f"Photorealistic commercial photograph of {product_name} by {company_name}. "
                f"PRODUCT ONLY — no people, no faces, no hands. "
                f"The product sits on a beautiful surface with dramatic {kf_environments[act_idx].split('—')[0].strip()} lighting. "
                f"Clean, elegant, cinematic. 16:9 landscape. Return only the image."
            )
            log_message(
                f"Generating safe keyframe for act {act_idx + 1}", Severity.INFO
            )
            safe_kf = await _generate_gemini_image(
                safe_prompt, refs, label=f"safe-keyframe-{act_idx + 1}"
            )
            if safe_kf:
                safe_blob = f"{OUTPUT_FOLDER}/_safe_keyframe_{act_idx + 1}.png"
                await asyncio.to_thread(
                    utils_gcs.upload_to_gcs,
                    GOOGLE_CLOUD_BUCKET_ARTIFACTS,
                    safe_kf,
                    safe_blob,
                )
                safe_uri = f"gs://{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{safe_blob}"
                safe_motion = (
                    f"Slow cinematic camera movement around {product_name}. "
                    f"Product sits still on a surface. Camera smoothly orbits or pushes in. "
                    f"Dramatic lighting shifts. No people, no hands, just the product and environment. "
                    f"Continuous smooth motion for {CLIP_SEC} seconds."
                )
                safe_motion = _sanitize_veo_prompt(safe_motion)
                log_message(
                    f"Generating safe VEO clip for act {act_idx + 1}",
                    Severity.INFO,
                )
                result = await _generate_single_veo_clip(
                    safe_motion,
                    safe_uri,
                    CLIP_SEC,
                    None,
                    label=f"safe-act{act_idx + 1}",
                )
                if isinstance(result, bytes):
                    clip_map[act_idx] = result
                    log_message(
                        f"Safety net clip act {act_idx + 1} generated successfully",
                        Severity.INFO,
                    )
                else:
                    log_message(
                        f"Safety net clip act {act_idx + 1} also failed",
                        Severity.ERROR,
                    )

    # Final check — ensure we have all 3 clips
    still_missing = [i for i in range(ACTS) if i not in clip_map]
    if still_missing:
        log_message(
            f"WARNING: {len(still_missing)} clips still missing after safety net. Video will be {len(clip_map) * CLIP_SEC}s instead of {ACTS * CLIP_SEC}s",
            Severity.WARNING,
        )

    # Save individual clips to GCS
    for act_idx, clip_bytes in clip_map.items():
        clip_blob = f"{OUTPUT_FOLDER}/clip_act{act_idx + 1}.mp4"
        try:
            await asyncio.to_thread(
                utils_gcs.upload_to_gcs,
                GOOGLE_CLOUD_BUCKET_ARTIFACTS,
                clip_bytes,
                clip_blob,
            )
            log_message(
                f"Saved clip act{act_idx + 1} to GCS: {clip_blob}",
                Severity.INFO,
            )
        except Exception as e:
            log_message(
                f"Failed to save clip act{act_idx + 1} to GCS: {e}",
                Severity.WARNING,
            )

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
            log_message(
                f"Lyria music saved to GCS: {OUTPUT_FOLDER}/{music_filename}",
                Severity.INFO,
            )
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
    log_message(
        "Phase 4: Stitch + audio + text overlays + end card...", Severity.INFO
    )
    stitched = _stitch_videos(clips) if len(clips) > 1 else clips[0]
    if not stitched:
        stitched = clips[0]

    final = _mix_audio_onto_video(stitched, vo_bytes, music_bytes)

    if logo_bytes:
        final = _overlay_logo_on_video(final, logo_bytes, opacity=0.8)

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
    final = _add_text_overlays(
        final,
        company_name,
        campaign_tagline,
        video_dur,
        product_name=product_name,
        price=product_price,
    )

    # End card overlay — brand + tagline + price on the last 3 seconds of the video (no separate card)
    final = _add_end_card_overlay(
        final, company_name, campaign_tagline, product_price=product_price
    )

    # Rename keyframes from temp prefix to permanent names
    for i in range(NUM_KEYFRAMES):
        try:
            old_blob = f"{OUTPUT_FOLDER}/_keyframe_{i + 1}.png"
            new_blob = f"{OUTPUT_FOLDER}/keyframe_{i + 1}.png"
            from google.cloud import storage as gcs_storage

            bucket = gcs_storage.Client(project=GOOGLE_CLOUD_PROJECT).bucket(
                GOOGLE_CLOUD_BUCKET_ARTIFACTS
            )
            src = bucket.blob(old_blob)
            if src.exists():
                bucket.rename_blob(src, new_blob)
                log_message(
                    f"Kept keyframe {i + 1} in GCS: {new_blob}", Severity.INFO
                )
        except Exception:
            pass

    processing_time = _time.time() - _pipeline_start
    video_length = len(clips) * CLIP_SEC
    log_message(
        f"Video ad complete: processing_time={processing_time:.0f}s, "
        f"video_length={video_length}s, size={len(final):,} bytes, clips={len(clips)}",
        Severity.INFO,
    )
    storyline_summary = []
    for i, act in enumerate(acts):
        storyline_summary.append(
            {
                "act": i + 1,
                "scene": act.get("scene_description", ""),
                "voiceover": act.get("voiceover_chunk", ""),
            }
        )
    return final, processing_time, video_length, storyline_summary


def save_selected_asset_sheet(
    asset_sheet_uri: str, tool_context: ToolContext, selected_campaign_name: str
):
    """Saves the user's chosen asset sheet.

    Args:
        asset_sheet_uri: URL of the selected asset sheet.
        selected_campaign_name: Name of the selected campaign.
    """
    tool_context.state[CHOSEN_ASSET_SHEET_ID_STATE_KEY] = asset_sheet_uri
    return {
        "status": "success",
        "details": f"Saved asset sheet: {asset_sheet_uri}",
    }


def recommend_campaign_settings(
    tool_context: ToolContext, segment_name: str, selected_campaign_name: str
):
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


def get_stocking_projection(
    tool_context: ToolContext, selected_campaign_name: str
):
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
    return {
        "status": "success",
        "details": "Personalization cleared. Ads will use default targeting.",
    }


# ============================================================
# Text Ad Generation
# ============================================================


async def generate_text_ad(
    tool_context: ToolContext,
    segment_name: str,
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
        return {
            "status": "error",
            "details": f"No campaign named '{selected_campaign_name}'",
        }

    segment = campaign.get_segment_by_name(segment_name)
    if not segment:
        return {
            "status": "error",
            "details": f"No segment named '{segment_name}'",
        }

    company_name = tool_context.state.get(PRODUCT_COMPANY_NAME_STATE_KEY, "")
    product_name = tool_context.state.get("PRODUCT_NAME", "product")
    ref_guidelines = tool_context.state.get(REFERENCE_GUIDELINES_STATE_KEY, "")
    fidelity_prompt = tool_context.state.get("PRODUCT_FIDELITY_PROMPT", "")
    customer_persona = tool_context.state.get(CUSTOMER_PERSONA_STATE_KEY, "")

    client = genai.Client(
        vertexai=True, project=GOOGLE_CLOUD_PROJECT, location="global"
    )

    guidelines_context = ""
    if ref_guidelines:
        guidelines_context = (
            f"\nBrand Guidelines (MUST follow): {ref_guidelines[:500]}\n"
        )
    if fidelity_prompt:
        guidelines_context += f"\nProduct Fidelity Guide (use for accurate product descriptions): {fidelity_prompt[:800]}\n"

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
        f"- headlines: EXACTLY 3 headlines, each MUST be 30 characters or fewer. COUNT the characters. If a headline exceeds 30 chars, REWRITE it shorter.\n"
        f"- descriptions: EXACTLY 3 descriptions, each MUST be 90 characters or fewer\n"
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
            client,
            "gemini-3.1-pro-preview",
            prompt,
            config=types.GenerateContentConfig(
                temperature=0.8,
                max_output_tokens=1024,
                response_mime_type="application/json",
            ),
            label="text-ad",
        )
        text_ad_data = json.loads(response.text)
    except Exception as e:
        log_message(
            f"Text ad generation failed, using fallback: {e}", Severity.WARNING
        )
        short_name = product_name.split(" - ")[0].split(" by ")[0].strip()
        if len(short_name) > 25:
            short_name = " ".join(short_name.split()[:3])
        text_ad_data = {
            "headlines": [
                (
                    campaign.tagline[:30]
                    if len(campaign.tagline) <= 30
                    else " ".join(campaign.tagline.split()[:4])
                ),
                (
                    f"{short_name} by {company_name}"[:30]
                    if len(f"{short_name} by {company_name}") <= 30
                    else short_name[:30]
                ),
                f"Discover {short_name}"[:30],
            ],
            "descriptions": [
                campaign.hook[:90],
                f"Shop {short_name} by {company_name}. {campaign.tagline}"[:90],
                f"{short_name} for {segment.name}. Learn more."[:90],
            ],
        }

    def _smart_trim(text, limit):
        if len(text) <= limit:
            return text
        trimmed = text[:limit]
        last_space = trimmed.rfind(" ")
        if last_space > limit * 0.5:
            return trimmed[:last_space].rstrip(".,!? ")
        return trimmed.rstrip(".,!? ")

    text_ad_data["headlines"] = [
        _smart_trim(h, 30) for h in text_ad_data.get("headlines", [])
    ]
    text_ad_data["descriptions"] = [
        _smart_trim(d, 90) for d in text_ad_data.get("descriptions", [])
    ]

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

    company_name = context.state.get(
        PRODUCT_COMPANY_NAME_STATE_KEY, DEMO_COMPANY_NAME
    )
    selected_campaign = context.state.get(
        CHOSEN_CAMPAIGN_IDEA_STATE_KEY, "Not selected yet"
    )
    selected_asset_sheet = context.state.get(
        CHOSEN_ASSET_SHEET_ID_STATE_KEY, "Not selected yet"
    )
    product_setup_done = context.state.get(PRODUCT_SETUP_DONE_STATE_KEY, False)

    reference_guidelines = context.state.get(REFERENCE_GUIDELINES_STATE_KEY, "")
    has_guidelines = (
        "Yes — guidelines loaded and active"
        if reference_guidelines
        else "No reference documents provided"
    )

    prompt = prompt_template.replace("{{AGENT_NAME}}", "LayoAgent")
    prompt = prompt_template.replace("{{DEMO_COMPANY_NAME}}", str(company_name))
    prompt = prompt.replace(
        "{{SELECTED_CAMPAIGN_NAME}}", str(selected_campaign)
    )
    prompt = prompt.replace(
        "{{SELECTED_ASSET_SHEET_URI}}", str(selected_asset_sheet)
    )
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
        account_id: The Google Ads login customer ID (e.g. "YOUR_ACCOUNT_ID").
        customer_id: The target customer ID (e.g. "YOUR_CUSTOMER_ID").
        is_mcc: Whether account_id is a Manager (MCC) account.
        budget: Daily budget in the account's currency.
        final_urls: Landing page URLs (e.g. ["http://www.example.com"]).
        location_id_targeting: Comma-separated location IDs (e.g. "1023191").
        language_id_targeting: Language ID (e.g. "1000" for English).
    """
    # Use env var defaults if agent didn't provide valid values or passed placeholders
    if not account_id or not account_id.strip().isdigit():
        account_id = os.getenv("GOOGLE_ADS_ACCOUNT_ID", "")
    if not customer_id or not customer_id.strip().isdigit():
        customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "")

    # Auto-populate from session state
    business_name = tool_context.state.get(PRODUCT_COMPANY_NAME_STATE_KEY, "")
    product_name = tool_context.state.get("PRODUCT_NAME", "")
    logo_uri = tool_context.state.get(LOGO_IMAGE_URI_STATE_KEY, "")

    # Collect generated asset URIs — always scan GCS for actual existing files
    # This is more reliable than session state which can have stale URIs from deleted/regenerated assets
    _set_output_folder(tool_context)
    image_uris = []
    video_uris = []
    try:
        from google.cloud import storage as gcs_storage

        storage_client = gcs_storage.Client(project=GOOGLE_CLOUD_PROJECT)
        bucket = storage_client.bucket(GOOGLE_CLOUD_BUCKET_ARTIFACTS)
        for blob in bucket.list_blobs(
            prefix=f"{OUTPUT_FOLDER}/", max_results=50
        ):
            uri = f"gs://{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{blob.name}"
            name = blob.name.split("/")[-1]
            if (
                name.startswith("_")
                or name.startswith("keyframe_")
                or name.startswith("clip_act")
                or name.startswith("background_music")
                or name.endswith(".json")
            ):
                continue
            if (
                name.endswith(".png") or name.endswith(".jpg")
            ) and not name.endswith("_resized.png"):
                image_uris.append(uri)
            elif name.endswith(".mp4"):
                video_uris.append(uri)
        log_message(
            f"GCS scan for publish: {len(image_uris)} images, {len(video_uris)} videos in {OUTPUT_FOLDER}/",
            Severity.INFO,
        )
    except Exception as e:
        log_message(
            f"GCS scan failed, falling back to session state: {e}",
            Severity.WARNING,
        )
        session_artifacts = tool_context.state.get(
            "SESSION_ARTIFACTS_STATE", {}
        )
        for entry in session_artifacts.values():
            asset = entry.get("asset", {})
            gcs_uri = asset.get("gcs_uri", "")
            mime = asset.get("mime_type", "")
            if "image" in mime and gcs_uri:
                image_uris.append(gcs_uri)
            elif "video" in mime and gcs_uri:
                video_uris.append(gcs_uri)

    # Get headlines/descriptions — first try session, then try GCS text ad JSON
    headlines = tool_context.state.get("_last_text_ad_headlines", [])
    descriptions = tool_context.state.get("_last_text_ad_descriptions", [])
    if not headlines:
        try:
            from google.cloud import storage as gcs_storage

            storage_client = gcs_storage.Client(project=GOOGLE_CLOUD_PROJECT)
            bucket = storage_client.bucket(GOOGLE_CLOUD_BUCKET_ARTIFACTS)
            for blob in bucket.list_blobs(
                prefix=f"{OUTPUT_FOLDER}/text_ad_", max_results=1
            ):
                text_ad_json = json.loads(blob.download_as_text())
                headlines = text_ad_json.get("headlines", [])
                descriptions = text_ad_json.get("descriptions", [])
                break
        except Exception:
            pass
    if not headlines:
        headlines = [
            product_name[:30],
            business_name[:30],
            f"Discover {product_name}"[:30],
        ]
    if not descriptions:
        descriptions = [
            f"Discover {product_name} by {business_name}."[:90],
            f"Premium {product_name}. Shop now."[:90],
        ]

    # Auto-square the logo if needed
    if logo_uri:
        try:
            import io as _io

            from PIL import Image as _PILImage

            logo_bytes_raw, _ = utils_agents.download_bytes_from_reference(
                logo_uri
            )
            if logo_bytes_raw:
                _img = _PILImage.open(_io.BytesIO(logo_bytes_raw))
                if _img.width != _img.height:
                    _size = max(_img.width, _img.height)
                    _canvas = _PILImage.new(
                        "RGB", (_size, _size), (255, 255, 255)
                    )
                    _px = (_size - _img.width) // 2
                    _py = (_size - _img.height) // 2
                    if _img.mode == "RGBA":
                        _canvas.paste(_img, (_px, _py), _img)
                    else:
                        _canvas.paste(_img, (_px, _py))
                    _buf = _io.BytesIO()
                    _canvas.save(_buf, format="PNG")
                    _sq_blob = f"{OUTPUT_FOLDER}/logo_square.png"
                    utils_gcs.upload_to_gcs(
                        GOOGLE_CLOUD_BUCKET_ARTIFACTS, _buf.getvalue(), _sq_blob
                    )
                    logo_uri = (
                        f"gs://{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{_sq_blob}"
                    )
                    log_message(
                        f"Logo squared and uploaded: {logo_uri}", Severity.INFO
                    )
        except Exception as e:
            log_message(f"Logo squaring failed: {e}", Severity.WARNING)

    import re as _clean_re

    clean_search_theme = _clean_re.sub(
        r"[^a-zA-Z0-9 \-]", "", product_name
    ).strip()[:80]
    clean_headlines = [
        _clean_re.sub(r"[^\w\s.,!?$%&\-]", "", h)[:30] for h in headlines
    ]
    clean_descriptions = [
        _clean_re.sub(r"[^\w\s.,!?$%&\-]", "", d)[:90] for d in descriptions
    ]

    # Build payload matching create_pmax_campaign signature exactly
    publish_payload = {
        "account_id": account_id,
        "is_mcc": is_mcc,
        "customer_id": customer_id,
        "business_name": business_name,
        "logo_uri": logo_uri,
        "brand_guidelines_enabled": False,
        "final_urls": final_urls,
        "final_mobile_urls": final_urls,
        "budget": budget,
        "location_id_targeting": location_id_targeting,
        "negative_location_id_targeting": "1022762",
        "language_id_targeting": language_id_targeting,
        "headlines": clean_headlines,
        "descriptions": clean_descriptions,
        "long_headlines": clean_headlines[:3],
        "marketing_image_asset_gcs_uris": image_uris[:20],
        "square_marketing_image_asset_gcs_uris": [logo_uri] if logo_uri else [],
        "search_theme": clean_search_theme,
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
        log_message(
            "ads_agent not available, returning payload for manual publish",
            Severity.WARNING,
        )
        return {
            "status": "manual_review",
            "published_payload": publish_payload,
            "details": "Google Ads agent not available. Use the payload above to create the campaign manually.",
        }
    except Exception as e:
        log_message(f"Google Ads publish failed: {e}", Severity.ERROR)
        return {
            "status": "error",
            "details": str(e),
            "published_payload": publish_payload,
        }


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
        generate_product_fidelity_prompt,
        recommend_campaign_settings,
        get_stocking_projection,
        check_existing_assets,
        delete_asset_from_gcs,
        # --- Retail Pipeline ---
        identify_inventory_opportunities,
        get_product_by_sku,
        display_product_image,
        extract_product_from_url,
        # --- Sub-agents ---
        AgentTool(agent=trend_spotter_agent.agent),
        # --- A2A — Google Ads Publisher ---
        publish_to_google_ads,
    ],
)
