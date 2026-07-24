# pylint: disable=line-too-long,broad-exception-caught,wrong-import-position,import-outside-toplevel,inconsistent-quotes,redefined-outer-name,logging-fstring-interpolation,missing-module-docstring,wrong-import-order,protected-access,undefined-variable
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


from pydantic import BaseModel


class CoreIdentifiers(BaseModel):
    sku: str
    upc: str | None = None
    brand: str | None = None
    product_name: str


class Attributes(BaseModel):
    size: str | None = None
    color_name: str | None = None
    color_hex: str | None = None
    material: str | None = None
    fit_type: str | None = None
    care_instructions: str | None = None


class Categorization(BaseModel):
    department: str | None = None
    category: str | None = None
    sub_category: str | None = None
    collection: str | None = None


class CommercialStatus(BaseModel):
    currency: str | None = "USD"
    msrp: float | None = None
    current_price: float | None = None
    cost_price: float | None = None
    in_stock: bool = False
    stock_quantity: int = 0
    # Extended fields for internal app usage
    sales_velocity: str | None = None
    sales_reasoning: str | None = None
    q4_2025: str | None = ""
    q1_2026: str | None = ""


class Media(BaseModel):
    main_image_url: str | None = None
    web_image_url: str | None = None
    gallery_urls: list[str] = []
    alt_text: str | None = None


class Description(BaseModel):
    short: str | None = None
    long: str | None = None


class Product(BaseModel):
    core_identifiers: CoreIdentifiers
    attributes: Attributes
    categorization: Categorization
    commercial_status: CommercialStatus | None = None
    media: Media | None = None
    description: Description | None = None


class ProductList(BaseModel):
    products: list[Product]


class TaxonomyAttributes(BaseModel):
    primary_aesthetic: str
    secondary_aesthetic: str
    key_garments: list[str]
    materials_and_textures: list[str]
    color_palette: list[str]
    mood_keywords: list[str]
    target_occasion: list[str]
    seasonality: str


class TargetAudienceProfile(BaseModel):
    age_segments: list[str]
    gender_focus: str
    income_level: str
    psychographics: list[str]
    geo_targeting: str
    shopping_behavior: str


class MarketingAttributes(BaseModel):
    commercial_maturity: str | None = None
    purchase_driver: str | None = None
    ad_creative_direction: str | None = None
    recommended_influencer_archetype: str | None = None
    ad_copy_hook: str | None = None
    target_demographic_segments: list[str] | None = None
    target_audience_profile: TargetAudienceProfile | None = None


class VisualAssets(BaseModel):
    google_images_url: str | None = None
    pinterest_url: str | None = None
    tiktok_search_url: str | None = None
    ai_generation_prompt: str | None = None


class Trend(BaseModel):
    """Schema representing a trend in the marketing campaign."""

    trend_name: str
    moodboard_url: str | None = None
    executive_summary: str | None = None
    trend_start_date: str | None = None
    trend_scope: str | None = None
    trend_lifecycle_stage: str | None = None
    primary_sources: list[str] = []
    key_designers: list[str] = []
    social_media_tags: list[str] = []
    key_influencer_handles: list[str] = []
    essential_look_characteristics: dict[str, str] = {}
    taxonomy_attributes: TaxonomyAttributes
    search_vectors: list[str] | None = None
    visual_assets: VisualAssets | None = None
    marketing_attributes: MarketingAttributes | None = None


class TrendMatch(BaseModel):
    trend: Trend
    match_score: float
    reasoning: str


class ProductTrendMapping(BaseModel):
    product: Product
    micro_trends: list[TrendMatch]
    macro_trends: list[TrendMatch]


class TrendSpotterOutput(BaseModel):
    trends: list[Trend]


class Scene(BaseModel):
    scene_id: int
    scene_url: str
    scene_video_url: str | None = None
    setting: str
    lighting_style: str
    camera_movement: str
    styling_details: str
    action: str


class CreativeDirection(BaseModel):
    creative_direction_summary: str
    scenes: list[Scene]


class FinalAd(BaseModel):
    final_ad_url: str | None = None
    final_social_ad_url: str | None = None
    asset_sheet_url: str | None = None
    moodboard_url: str | None = None
    creative_direction: CreativeDirection | None = None


class CampaignDraft(BaseModel):
    campaign_name: str
    trend: str
    target_audience: str
    keyframes: list[str]
    video_url: str | None = None


class TrendStrategy(BaseModel):
    trend_name: str
    strategy_directive: str
    target_audience: str


class BrandCore(BaseModel):
    archetype: str | None = None
    mantra: str | None = None
    promise: str | None = None
    vibe: str | None = None
    target_audience: str | None = None
    key_differentiator: str | None = None


class Typography(BaseModel):
    headlines: str | None = None
    body_copy: str | None = None


class VisualIdentity(BaseModel):
    logo: str | None = None
    color_palette: list[str] = []
    typography: Typography | str | None = None


class PhotographyAndArtDirection(BaseModel):
    style: str | None = None
    lighting: str | None = None
    environment: str | None = None
    styling: str | None = None
    casting: str | None = None


class VoiceAndTone(BaseModel):
    tone: str | None = None
    keywords: list[str] | None = None
    do: str | None = None
    dont: str | None = None
    sample_copy: list[str] | None = None


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
    model_images: list[str]
    model_settings: list[SocialMediaModelSetting]
    model_social_media_platforms: list[SocialMediaPlatform]
    model_social_media_styles: list[SocialMediaStyle]


class Brand(BaseModel):
    brand_identifier: str
    name: str
    brand_guide_url: str | None = None
    brand_core: BrandCore
    visual_identity: VisualIdentity
    photography_and_art_direction: PhotographyAndArtDirection
    voice_and_tone: VoiceAndTone
    social_media_model: SocialAIModel | None = None
