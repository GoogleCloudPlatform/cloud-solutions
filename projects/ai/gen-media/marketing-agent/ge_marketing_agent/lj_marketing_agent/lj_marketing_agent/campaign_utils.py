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

from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

from pydantic import BaseModel, HttpUrl, ValidationError, field_validator
from ..adk_common.utils.utils_logging import Severity, log_message

LOGGING_PREFIX = "[CampaignUtils]"


class Asset(BaseModel):
    """Represents a media asset with a URI and a rationale."""

    uri: str
    rationale: str
    id: Optional[str] = None
    source_asset_sheet_id: Optional[str] = None

    @field_validator("uri")
    @classmethod
    def validate_uri(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("URI cannot be empty")
        # Basic check for common protocols
        if not (
            v.startswith("gs://") or v.startswith("http://") or v.startswith("https://")
        ):
            raise ValueError(
                f"URI must start with gs://, http://, or https://. Got: {v}"
            )
        return v

    @field_validator("rationale")
    @classmethod
    def validate_rationale(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Rationale cannot be empty")
        return v


class Segment(BaseModel):
    """Represents a specific audience segment within a campaign."""

    name: str
    image_ads: List[Asset]
    video_ads: List[Asset]
    optimization_note: str
    campaign_settings: str


class Campaign(BaseModel):
    """Represents a marketing campaign idea."""

    name: str
    primary_target: str
    hook: str
    insight: str
    visual_key: str
    tagline: str
    why_it_works: str
    relevant_brief: str
    suggested_optimization: str
    segments: List[Segment]
    asset_sheets: List[Asset]

    def get_segment_by_name(self, segment_name: str) -> Optional[Segment]:
        """Retrieves a segment by its name (case-insensitive)."""
        target = segment_name.strip().lower()
        for segment in self.segments:
            if segment.name.strip().lower() == target:
                return segment
        return None


def find_campaign_by_name(campaigns: List[Campaign], name: str) -> Optional[Campaign]:
    """Finds a campaign by name (case-insensitive)."""
    target = name.strip().lower()
    for campaign in campaigns:
        if campaign.name.strip().lower() == target:
            return campaign
    return None


def _get_required_text(element: ET.Element, tag_name: str, parent_name: str) -> str:
    """Helper to get text from a required tag, ensuring it's not empty."""
    found = element.find(tag_name)
    if found is None or not found.text or not found.text.strip():
        raise ValueError(f"Missing or empty <{tag_name}> in {parent_name}")
    return found.text.strip()


def _parse_asset(elem: Optional[ET.Element], context: str) -> Asset:
    """Parses an <asset> element, raising errors if invalid."""
    if elem is None:
        raise ValueError(f"Missing asset element in {context}")

    # Try parsing structured <asset> with <uri> and <rationale>
    if elem.find("uri") is not None:
        uri = _get_required_text(elem, "uri", context)
        rationale = _get_required_text(elem, "rationale", context)

        # Optional fields
        asset_id = None
        id_elem = elem.find("id")
        if id_elem is not None:
            asset_id = id_elem.text.strip() if id_elem.text else None

        source_sheet_id = None
        source_sheet_id_elem = elem.find("source_asset_sheet_id")
        if source_sheet_id_elem is not None:
            source_sheet_id = (
                source_sheet_id_elem.text.strip() if source_sheet_id_elem.text else None
            )

        return Asset(
            uri=uri,
            rationale=rationale,
            id=asset_id,
            source_asset_sheet_id=source_sheet_id,
        )

    # Fallback for simple text content (legacy support, though user asked for strictness,
    # the transition might have mixed states. But for "pristine" requirement, we could enforce strictness.
    # Let's support the legacy <uri> only if wrapped in an asset structure implied by the caller context?)
    # ACTUALLY: User said "pristine perfect". Let's enforce the structure.

    raise ValueError(
        f"Invalid asset structure in {context}. Must contain <uri> and <rationale>."
    )


def parse_campaigns_from_xml(xml_content: str) -> List[Campaign]:
    """
    Parses the ideas_and_briefs.xml content into Campaign objects using Pydantic.
    Raises ValueError with descriptive messages if parsing fails.
    """
    campaigns = []

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        raise ValueError(f"XML Syntax Error: {e}")

    for i, campaign_elem in enumerate(root.findall("campaign")):
        campaign_name = campaign_elem.get("name", f"Campaign #{i+1}")
        context_prefix = f"Campaign '{campaign_name}'"

        try:
            # 1. Parse Basic Fields
            primary_target = _get_required_text(
                campaign_elem, "primary_target", context_prefix
            )
            hook = _get_required_text(campaign_elem, "hook", context_prefix)
            insight = _get_required_text(campaign_elem, "insight", context_prefix)
            visual_key = _get_required_text(campaign_elem, "visual_key", context_prefix)
            tagline = _get_required_text(campaign_elem, "tagline", context_prefix)
            why_it_works = _get_required_text(
                campaign_elem, "why_it_works", context_prefix
            )
            relevant_brief = _get_required_text(
                campaign_elem, "relevant_brief", context_prefix
            )
            suggested_optimization = _get_required_text(
                campaign_elem, "suggested_optimization", context_prefix
            )

            # 2. Parse Asset Sheets (Support single or multiple)
            asset_sheets = []

            # Check for plural <asset_sheets> container first
            asset_sheets_container = campaign_elem.find("asset_sheets")
            if asset_sheets_container is not None:
                for k, asset_node in enumerate(
                    asset_sheets_container.findall("asset_sheet")
                ):
                    asset_sheets.append(
                        _parse_asset(
                            asset_node, f"{context_prefix} -> Asset Sheet #{k+1}"
                        )
                    )

            # If no container, check for single <asset_sheet> (Backward Compatibility)
            if not asset_sheets:
                single_sheet_elem = campaign_elem.find("asset_sheet")
                if single_sheet_elem is not None:
                    asset_sheets.append(
                        _parse_asset(
                            single_sheet_elem, f"{context_prefix} -> Single Asset Sheet"
                        )
                    )

            # Final Validation
            if not asset_sheets:
                # Check for legacy asset_sheet_uri to give a helpful error
                if campaign_elem.find("asset_sheet_uri") is not None:
                    raise ValueError(
                        f"{context_prefix}: Found legacy <asset_sheet_uri>. Please update to <asset_sheets><asset_sheet><uri>...</uri><rationale>...</rationale></asset_sheet></asset_sheets>."
                    )
                raise ValueError(
                    f"{context_prefix}: Missing required <asset_sheets> or <asset_sheet> element."
                )

            # 3. Parse Segments
            segments = []
            segments_elem = campaign_elem.find("segments")
            if segments_elem is None:
                raise ValueError(f"{context_prefix}: Missing <segments> block.")

            for j, segment_elem in enumerate(segments_elem.findall("segment")):
                seg_name = _get_required_text(
                    segment_elem, "name", f"{context_prefix} -> Segment #{j+1}"
                )
                seg_context = f"{context_prefix} -> Segment '{seg_name}'"

                # Parse Image Ads
                image_ads = []
                image_uris_elem = segment_elem.find("image_ads_uris")
                if image_uris_elem is not None:
                    for k, asset_node in enumerate(image_uris_elem.findall("asset")):
                        image_ads.append(
                            _parse_asset(
                                asset_node, f"{seg_context} -> Image Ad #{k+1}"
                            )
                        )

                # Parse Video Ads
                video_ads = []
                video_uris_elem = segment_elem.find("video_ads_uris")
                if video_uris_elem is not None:
                    for k, asset_node in enumerate(video_uris_elem.findall("asset")):
                        video_ads.append(
                            _parse_asset(
                                asset_node, f"{seg_context} -> Video Ad #{k+1}"
                            )
                        )

                if not image_ads and not video_ads:
                    raise ValueError(
                        f"{seg_context}: Segment must have at least one image or video ad."
                    )

                # Parse Optimization Note
                optimization_note = _get_required_text(
                    segment_elem, "optimization_note", seg_context
                )

                # Parse Campaign Settings
                campaign_settings = _get_required_text(
                    segment_elem, "campaign_settings", seg_context
                )

                segments.append(
                    Segment(
                        name=seg_name,
                        image_ads=image_ads,
                        video_ads=video_ads,
                        optimization_note=optimization_note,
                        campaign_settings=campaign_settings,
                    )
                )

            if not segments:
                raise ValueError(f"{context_prefix}: Must define at least one segment.")

            # Validate and Create Campaign Object
            campaigns.append(
                Campaign(
                    name=campaign_name,
                    primary_target=primary_target,
                    hook=hook,
                    insight=insight,
                    visual_key=visual_key,
                    tagline=tagline,
                    why_it_works=why_it_works,
                    relevant_brief=relevant_brief,
                    suggested_optimization=suggested_optimization,
                    segments=segments,
                    asset_sheets=asset_sheets,
                )
            )

        except ValidationError as e:
            # Catch Pydantic validation errors and re-raise as readable ValueError
            raise ValueError(f"Validation Error in {context_prefix}: {e}")
        except ValueError as e:
            # Re-raise explicit ValueErrors
            raise e

    return campaigns
