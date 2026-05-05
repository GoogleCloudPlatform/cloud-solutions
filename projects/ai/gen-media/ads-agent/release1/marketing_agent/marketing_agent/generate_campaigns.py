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

# pylint: disable=C0301, C0415, W0718

"""Generates data_campaigns.xml dynamically using Gemini based on product info."""

import re
from xml.etree import ElementTree as ET

from adk_common.utils.constants import get_required_env_var
from adk_common.utils.utils_logging import Severity, log_message
from google import genai
from google.genai import types

GOOGLE_CLOUD_PROJECT = get_required_env_var("GOOGLE_CLOUD_PROJECT")
GOOGLE_CLOUD_LOCATION = get_required_env_var("GOOGLE_CLOUD_LOCATION")
GOOGLE_CLOUD_BUCKET_ARTIFACTS = get_required_env_var("GOOGLE_CLOUD_BUCKET_ARTIFACTS")

MAX_RETRIES = 3

CAMPAIGN_GENERATION_PROMPT = """Generate campaigns XML for a product. Output ONLY valid XML, no markdown, no explanation.

CRITICAL: You MUST output the COMPLETE XML including the closing </campaigns> tag. Do NOT stop early.

Product: {company_name} - {product_name}
Description: {product_description}
Audience: {target_audience}
Logo: {logo_uri} | Product Image: {product_image_uri} | Bucket: {artifacts_bucket}
{reference_guidelines_section}
IMPORTANT — TREND RESEARCH (you have Google Search enabled):
Before generating campaigns, search for current market trends, competitor campaigns, and social media buzz
related to "{product_name}" and its category. Use real, current trends to make each campaign culturally relevant.
Reference specific trends, cultural moments, or competitor strategies in your hooks and insights.

Rules:
- {num_campaigns} campaigns, each with: {num_segments} segments, {num_asset_sheets} asset sheets, {num_image_ads} image ads/segment ({ads_per_sheet} per asset sheet), {num_video_ads} video ads/segment ({ads_per_sheet} per asset sheet)
- CRITICAL: Each segment MUST have exactly {num_image_ads} image ads and {num_video_ads} video ads. For each segment, distribute ads evenly across all {num_asset_sheets} asset sheets ({ads_per_sheet} per sheet). Same for video ads.
- Every URI must be UNIQUE. Never reuse URIs across assets.
  - Asset sheets: gs://{artifacts_bucket}/asset_sheet_<id>.png
  - Image ads: gs://{artifacts_bucket}/img_<seg>_<concept>_<n>.png (use distinct concept names per ad)
  - Video ads: gs://{artifacts_bucket}/vid_<seg>_<concept>_<n>.mp4 (use distinct concept names per ad)
- Each rationale: 1 SHORT sentence only (under 15 words). DISTINCT per asset.
- relevant_brief: 2-3 SHORT sentences, plain text only
- suggested_optimization: 2-3 SHORT sentences, plain text only (NO tables)
- campaign_settings: Budget|Bidding|Targeting|Format|Duration (1 pipe row only)
- optimization_note: 1-2 SHORT sentences, plain text
- NEVER use & < > in text content. Use "and" instead of "&". No Markdown.
- Each asset needs unique id and source_asset_sheet_id linking ads to their sheet
- KEEP ALL TEXT FIELDS SHORT. Brevity is critical to avoid truncation.

Creative Direction:
- Each campaign MUST have a unique, creative angle tailored to the SPECIFIC product category
- For TECH products: innovation, precision engineering, futuristic aesthetics
- For FOOD/BEVERAGE: sensory experience, craftsmanship, origin stories, ritual moments
- For AUTOMOTIVE: performance, freedom, engineering excellence, open road
- For FITNESS/SPORTS: personal achievement, pushing limits, transformation
- For BEAUTY: confidence, self-expression, radiance, natural ingredients
- For HOME: comfort, sanctuary, design, lifestyle upgrade
- For PET: bond, protection, joy, adventure with your companion
- Taglines must be poetic, evocative, and memorable — no generic marketing speak
- Visual keys should reference specific cinematic techniques appropriate to the product
- Hooks should provoke emotion, curiosity, or awe — never generic product descriptions
- Each campaign concept must feel DISTINCTLY different from the others — different mood, different angle, different audience insight
- NO hallucinated claims — do not invent product features not mentioned in the description

```xml
<campaigns>
  <campaign name="Campaign Name">
    <primary_target>Target description</primary_target>
    <hook>Hook</hook>
    <insight>Insight</insight>
    <visual_key>Visual direction</visual_key>
    <tagline>Tagline</tagline>
    <why_it_works>Why it works</why_it_works>
    <relevant_brief>Concise creative brief in plain text</relevant_brief>
    <suggested_optimization>Concise optimization with pipe table</suggested_optimization>
    <asset_sheets>
      <asset_sheet>
        <uri>gs://{artifacts_bucket}/asset_sheet_concept1.png</uri>
        <rationale>Distinct visual concept</rationale>
        <id>sheet_id_1</id>
      </asset_sheet>
    </asset_sheets>
    <segments>
      <segment>
        <name>Segment Name</name>
        <image_ads_uris>
          <asset>
            <uri>gs://{artifacts_bucket}/img_seg_conceptA_1.png</uri>
            <rationale>Unique ad concept A1</rationale>
            <id>img_s1_a1</id>
            <source_asset_sheet_id>sheet_id_1</source_asset_sheet_id>
          </asset>
          <asset>
            <uri>gs://{artifacts_bucket}/img_seg_conceptA_2.png</uri>
            <rationale>Unique ad concept A2</rationale>
            <id>img_s1_a2</id>
            <source_asset_sheet_id>sheet_id_1</source_asset_sheet_id>
          </asset>
          <asset>
            <uri>gs://{artifacts_bucket}/img_seg_conceptB_1.png</uri>
            <rationale>Unique ad concept B1</rationale>
            <id>img_s1_b1</id>
            <source_asset_sheet_id>sheet_id_2</source_asset_sheet_id>
          </asset>
          <asset>
            <uri>gs://{artifacts_bucket}/img_seg_conceptB_2.png</uri>
            <rationale>Unique ad concept B2</rationale>
            <id>img_s1_b2</id>
            <source_asset_sheet_id>sheet_id_2</source_asset_sheet_id>
          </asset>
        </image_ads_uris>
        <video_ads_uris>
          <asset>
            <uri>gs://{artifacts_bucket}/vid_seg_conceptA_1.mp4</uri>
            <rationale>Unique video concept A1</rationale>
            <id>vid_s1_a1</id>
            <source_asset_sheet_id>sheet_id_1</source_asset_sheet_id>
          </asset>
          <asset>
            <uri>gs://{artifacts_bucket}/vid_seg_conceptA_2.mp4</uri>
            <rationale>Unique video concept A2</rationale>
            <id>vid_s1_a2</id>
            <source_asset_sheet_id>sheet_id_1</source_asset_sheet_id>
          </asset>
          <asset>
            <uri>gs://{artifacts_bucket}/vid_seg_conceptB_1.mp4</uri>
            <rationale>Unique video concept B1</rationale>
            <id>vid_s1_b1</id>
            <source_asset_sheet_id>sheet_id_2</source_asset_sheet_id>
          </asset>
          <asset>
            <uri>gs://{artifacts_bucket}/vid_seg_conceptB_2.mp4</uri>
            <rationale>Unique video concept B2</rationale>
            <id>vid_s1_b2</id>
            <source_asset_sheet_id>sheet_id_2</source_asset_sheet_id>
          </asset>
        </video_ads_uris>
        <optimization_note>2-3 actionable recommendations</optimization_note>
        <campaign_settings>Compact settings table</campaign_settings>
      </segment>
    </segments>
  </campaign>
</campaigns>
```
"""


def _get_genai_client() -> genai.Client:
    return genai.Client(
        vertexai=True,
        project=GOOGLE_CLOUD_PROJECT,
        location="global",
    )


def _sanitize_xml_text_content(xml_string: str) -> str:
    """Escapes unescaped XML-special characters in text content between tags.

    This fixes the common issue where Gemini generates & < > in free-text
    fields like <relevant_brief>, <optimization_note>, etc.
    """
    # Tags whose text content may contain unescaped special chars
    text_heavy_tags = [
        "relevant_brief", "suggested_optimization", "campaign_settings",
        "optimization_note", "rationale", "primary_target", "hook",
        "insight", "visual_key", "tagline", "why_it_works", "name",
    ]

    for tag in text_heavy_tags:
        pattern = re.compile(
            rf"(<{tag}>)(.*?)(</{tag}>)",
            re.DOTALL,
        )

        def _escape_content(match: re.Match) -> str:
            open_tag = match.group(1)
            content = match.group(2)
            close_tag = match.group(3)

            # Escape & first (but not already-escaped entities like &amp; &lt; &gt;)
            content = re.sub(r"&(?!amp;|lt;|gt;|apos;|quot;)", "&amp;", content)
            # Escape < and > that are NOT part of XML tags
            # Since we're inside a text-only element, ALL < and > should be escaped
            content = content.replace("<", "&lt;").replace(">", "&gt;")

            return f"{open_tag}{content}{close_tag}"

        xml_string = pattern.sub(_escape_content, xml_string)

    return xml_string


def _extract_xml(raw_text: str) -> str:
    """Extracts XML content from potential markdown code fences."""
    if "```xml" in raw_text:
        raw_text = raw_text.split("```xml", 1)[1]
        raw_text = raw_text.split("```", 1)[0]
    elif "```" in raw_text:
        raw_text = raw_text.split("```", 1)[1]
        raw_text = raw_text.split("```", 1)[0]

    xml_text = raw_text.strip()

    if not xml_text.startswith("<campaigns"):
        log_message("Generated XML doesn't start with <campaigns>. Wrapping.", Severity.WARNING)
        xml_text = f"<campaigns>\n{xml_text}\n</campaigns>"

    # Fix truncated XML: ensure closing tags exist
    if "</campaigns>" not in xml_text:
        log_message("XML appears truncated — adding closing tags", Severity.WARNING)
        # Close any open campaign and campaigns tags
        if "</campaign>" not in xml_text.split("<campaign")[-1]:
            xml_text += "\n</campaign>"
        xml_text += "\n</campaigns>"

    return xml_text


def generate_campaigns_xml(
    company_name: str,
    product_name: str,
    product_description: str,
    target_audience: str,
    logo_uri: str,
    product_image_uri: str,
    num_campaigns: int = 3,
    num_segments: int = 2,
    num_asset_sheets: int = 4,
    num_image_ads: int = 4,
    num_video_ads: int = 4,
    reference_guidelines: str = "",
) -> str:
    """Uses Gemini 3.1 Pro with Google Search grounding to generate campaign XML.

    First fetches current market trends for the product category, then generates
    trend-aware campaigns with real-world cultural context.

    Args:
        reference_guidelines: Optional extracted text from user-provided reference
            documents (product docs, marketing briefs, brand guidelines). When
            provided, campaigns MUST adhere to these guidelines.
    """
    # Ensure ads distribute evenly; round up if needed
    ads_per_sheet = max(1, -(-num_image_ads // num_asset_sheets))  # ceiling division

    # Build reference guidelines section if provided
    if reference_guidelines and reference_guidelines.strip():
        reference_guidelines_section = (
            "CRITICAL — REFERENCE DOCUMENTS & BRAND GUIDELINES:\n"
            "The user has provided the following reference documents (product docs, marketing briefs, "
            "brand guidelines). You MUST strictly follow these guidelines when generating campaigns. "
            "All creative direction, messaging, tone, visual style, taglines, and audience targeting "
            "MUST align with these documents. Do NOT contradict or ignore any guideline below.\n\n"
            f"--- BEGIN REFERENCE GUIDELINES ---\n{reference_guidelines.strip()}\n--- END REFERENCE GUIDELINES ---\n"
        )
    else:
        reference_guidelines_section = ""

    prompt = CAMPAIGN_GENERATION_PROMPT.format(
        company_name=company_name,
        product_name=product_name,
        product_description=product_description,
        target_audience=target_audience,
        logo_uri=logo_uri,
        product_image_uri=product_image_uri,
        artifacts_bucket=GOOGLE_CLOUD_BUCKET_ARTIFACTS,
        num_campaigns=num_campaigns,
        num_segments=num_segments,
        num_asset_sheets=num_asset_sheets,
        num_image_ads=num_image_ads,
        num_video_ads=num_video_ads,
        ads_per_sheet=ads_per_sheet,
        reference_guidelines_section=reference_guidelines_section,
    )

    client = _get_genai_client()
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        log_message(f"Generating campaigns XML (attempt {attempt}/{MAX_RETRIES})", Severity.INFO)

        try:
            response = client.models.generate_content(
                model="gemini-3.1-pro-preview",
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=prompt)],
                    )
                ],
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=32768,
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                ),
            )
        except Exception as e:
            last_error = str(e)
            is_429 = "429" in last_error or "RESOURCE_EXHAUSTED" in last_error
            log_message(f"Gemini API call failed on attempt {attempt} (429={is_429}): {last_error}", Severity.ERROR)
            if is_429 and attempt < MAX_RETRIES:
                import random as _random
                import time as _time
                backoff = (2 ** attempt) * 3 + _random.uniform(0, 2)
                log_message(f"429 backoff: {backoff:.1f}s", Severity.WARNING)
                _time.sleep(backoff)
            continue

        # Extract text from parts (grounded response may have multiple parts)
        raw_text = ""
        if response.candidates and response.candidates[0].content:
            for part in response.candidates[0].content.parts:
                if part.text:
                    raw_text += part.text
        log_message(f"Generated campaigns XML (length: {len(raw_text)})", Severity.INFO)

        # Extract and sanitize
        xml_text = _extract_xml(raw_text)
        xml_text = _sanitize_xml_text_content(xml_text)

        # Validate XML parses correctly
        try:
            ET.fromstring(xml_text)
            log_message(f"XML validation passed on attempt {attempt}", Severity.INFO)
            return xml_text
        except ET.ParseError as e:
            last_error = str(e)
            log_message(
                f"XML validation failed on attempt {attempt}: {last_error}",
                Severity.WARNING,
            )
            continue

    # All retries exhausted - raise with last error
    raise ValueError(
        f"Failed to generate valid XML after {MAX_RETRIES} attempts. Last error: {last_error}"
    )
