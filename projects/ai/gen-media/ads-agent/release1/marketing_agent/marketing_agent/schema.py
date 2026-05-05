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

# pylint: disable=C0114, C0115, W0611

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class CoreIdentifiers(BaseModel):
    sku: str
    upc: Optional[str] = None
    brand: Optional[str] = None
    product_name: str

class Attributes(BaseModel):
    size: Optional[str] = None
    color_name: Optional[str] = None
    color_hex: Optional[str] = None
    material: Optional[str] = None
    fit_type: Optional[str] = None
    care_instructions: Optional[str] = None

class Categorization(BaseModel):
    department: Optional[str] = None
    category: Optional[str] = None
    sub_category: Optional[str] = None
    collection: Optional[str] = None

class CommercialStatus(BaseModel):
    currency: Optional[str] = "USD"
    msrp: Optional[float] = None
    current_price: Optional[float] = None
    cost_price: Optional[float] = None
    in_stock: bool = False
    stock_quantity: int = 0
    # Extended fields for internal app usage
    sales_velocity: Optional[str] = None
    sales_reasoning: Optional[str] = None
    q4_2025: Optional[str] = ""
    q1_2026: Optional[str] = ""

class Media(BaseModel):
    main_image_url: Optional[str] = None
    web_image_url: Optional[str] = None
    gallery_urls: List[str] = []
    alt_text: Optional[str] = None

class Description(BaseModel):
    short: Optional[str] = None
    long: Optional[str] = None

class Product(BaseModel):
    core_identifiers: CoreIdentifiers
    attributes: Attributes
    categorization: Categorization
    commercial_status: Optional[CommercialStatus] = None
    media: Optional[Media] = None
    description: Optional[Description] = None

class ProductList(BaseModel):
    products: List[Product]

class TaxonomyAttributes(BaseModel):
    primary_aesthetic: str
    secondary_aesthetic: str
    key_garments: List[str]
    materials_and_textures: List[str]
    color_palette: List[str]
    mood_keywords: List[str]
    target_occasion: List[str]
    seasonality: str

class TargetAudienceProfile(BaseModel):
    age_segments: List[str]
    gender_focus: str
    income_level: str
    psychographics: List[str]
    geo_targeting: str
    shopping_behavior: str

class MarketingAttributes(BaseModel):
    commercial_maturity: Optional[str] = None
    purchase_driver: Optional[str] = None
    ad_creative_direction: Optional[str] = None
    recommended_influencer_archetype: Optional[str] = None
    ad_copy_hook: Optional[str] = None
    target_demographic_segments: Optional[List[str]] = None
    target_audience_profile: Optional[TargetAudienceProfile] = None

class VisualAssets(BaseModel):
    google_images_url: Optional[str] = None
    pinterest_url: Optional[str] = None
    tiktok_search_url: Optional[str] = None
    ai_generation_prompt: Optional[str] = None


class Trend(BaseModel):
    trend_name: str
    moodboard_url: Optional[str] = None
    executive_summary: Optional[str] = None
    trend_start_date: Optional[str] = None
    trend_scope: Optional[str] = None
    trend_lifecycle_stage: Optional[str] = None
    primary_sources: List[str] = []
    key_designers: List[str] = []
    social_media_tags: List[str] = []
    key_influencer_handles: List[str] = []
    essential_look_characteristics: Dict[str, str] = {}
    taxonomy_attributes: TaxonomyAttributes
    search_vectors: Optional[List[str]] = None
    visual_assets: Optional[VisualAssets] = None
    marketing_attributes: Optional[MarketingAttributes] = None

class TrendMatch(BaseModel):
    trend: Trend
    match_score: float
    reasoning: str

class ProductTrendMapping(BaseModel):
    product: Product
    micro_trends: List[TrendMatch]
    macro_trends: List[TrendMatch]

class TrendSpotterOutput(BaseModel):
    trends: List[Trend]

class Scene(BaseModel):
    scene_id: int
    scene_url: str
    scene_video_url: Optional[str] = None
    setting: str
    lighting_style: str
    camera_movement: str
    styling_details: str
    action: str

class CreativeDirection(BaseModel):
    creative_direction_summary: str
    scenes: List[Scene]

class FinalAd(BaseModel):
    final_ad_url: Optional[str] = None
    final_social_ad_url: Optional[str] = None
    asset_sheet_url: Optional[str] = None
    moodboard_url: Optional[str] = None
    creative_direction: Optional[CreativeDirection] = None

class CampaignDraft(BaseModel):
    campaign_name: str
    trend: str
    target_audience: str
    keyframes: List[str]
    video_url: Optional[str] = None

class TrendStrategy(BaseModel):
    trend_name: str
    strategy_directive: str
    target_audience: str

class BrandCore(BaseModel):
    archetype: Optional[str] = None
    mantra: Optional[str] = None
    promise: Optional[str] = None
    vibe: Optional[str] = None
    target_audience: Optional[str] = None
    key_differentiator: Optional[str] = None

class Typography(BaseModel):
    headlines: Optional[str] = None
    body_copy: Optional[str] = None

class VisualIdentity(BaseModel):
    logo: Optional[str] = None
    color_palette: List[str] = []
    typography: Optional[Typography | str] = None

class PhotographyAndArtDirection(BaseModel):
    style: Optional[str] = None
    lighting: Optional[str] = None
    environment: Optional[str] = None
    styling: Optional[str] = None
    casting: Optional[str] = None

class VoiceAndTone(BaseModel):
    tone: Optional[str] = None
    keywords: Optional[List[str]] = None
    do: Optional[str] = None
    dont: Optional[str] = None
    sample_copy: Optional[List[str]] = None

class SocialMediaModelSetting(BaseModel):
    setting_name: str
    setting_description: str
    setting_image_url: str

class SocialMediaPlatform(BaseModel):
    platform_name: str

class SocialMediaStyle(BaseModel):
    style_name: str
    style_description: str
    style_prompt_template: str

class SocialAIModel(BaseModel):
    model_name: str
    model_influencer_type: str
    model_consistency_desciption: str
    model_images: List[str]
    model_settings: List[SocialMediaModelSetting]
    model_social_media_platforms: List[SocialMediaPlatform]
    model_social_media_styles: List[SocialMediaStyle]

class Brand(BaseModel):
    brand_identifier: str
    name: str
    brand_guide_url: Optional[str] = None
    brand_core: BrandCore
    visual_identity: VisualIdentity
    photography_and_art_direction: PhotographyAndArtDirection
    voice_and_tone: VoiceAndTone
    social_media_model: Optional[SocialAIModel] = None

