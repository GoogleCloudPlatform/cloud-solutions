#!/usr/bin/env python
# Copyright 2021 Google LLC
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
# pylint: disable=C0301, W0212, W0621, W1203
"""This example shows how to create a Performance Max campaign.

For more information about Performance Max campaigns, see
https://developers.google.com/google-ads/api/docs/performance-max/overview

Prerequisites:
- You must have at least one conversion action in the account. For
more about conversion actions, see
https://developers.google.com/google-ads/api/docs/conversions/overview#conversion_actions

This example uses the default customer conversion goals. For an example
of setting campaign-specific conversion goals, see
shopping_ads/add_performance_max_retail_campaign.py
"""

import itertools
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Iterable, Iterator
from uuid import uuid4

import google.auth
from google.ads.googleads import client, errors, util
from google.ads.googleads.v23.enums.types.asset_field_type import (
    AssetFieldTypeEnum,
)
from google.ads.googleads.v23.enums.types.youtube_video_upload_state import (
    YouTubeVideoUploadStateEnum,
)
from google.ads.googleads.v23.resources.types.asset import Asset
from google.ads.googleads.v23.resources.types.asset_group import AssetGroup
from google.ads.googleads.v23.resources.types.asset_group_asset import (
    AssetGroupAsset,
)
from google.ads.googleads.v23.resources.types.asset_group_signal import (
    AssetGroupSignal,
)
from google.ads.googleads.v23.resources.types.campaign import Campaign
from google.ads.googleads.v23.resources.types.campaign_asset import (
    CampaignAsset,
)
from google.ads.googleads.v23.resources.types.campaign_budget import (
    CampaignBudget,
)
from google.ads.googleads.v23.resources.types.campaign_criterion import (
    CampaignCriterion,
)
from google.ads.googleads.v23.services.services.asset_group_service import (
    AssetGroupServiceClient,
)
from google.ads.googleads.v23.services.services.asset_service import (
    AssetServiceClient,
)
from google.ads.googleads.v23.services.services.campaign_service import (
    CampaignServiceClient,
)
from google.ads.googleads.v23.services.services.geo_target_constant_service import (
    GeoTargetConstantServiceClient,
)
from google.ads.googleads.v23.services.services.google_ads_service import (
    GoogleAdsServiceClient,
)
from google.ads.googleads.v23.services.types.campaign_budget_service import (
    CampaignBudgetOperation,
)
from google.ads.googleads.v23.services.types.google_ads_service import (
    MutateGoogleAdsResponse,
    MutateOperation,
    SearchGoogleAdsStreamResponse,
)
from google.cloud import storage

try:
    from .storage_service import StorageService
except (ImportError, ValueError):
    from storage_service import StorageService


# We specify temporary IDs that are specific to a single mutate request.
# Temporary IDs are always negative and unique within one mutate request.
#
# See https://developers.google.com/google-ads/api/docs/mutating/best-practices
# for further details.
#
# These temporary IDs are fixed because they are used in multiple places.
_BUDGET_TEMPORARY_ID = "-1"
_PERFORMANCE_MAX_CAMPAIGN_TEMPORARY_ID = "-2"
_ASSET_GROUP_TEMPORARY_ID = "-3"

# There are also entities that will be created in the same request but do not
# need to be fixed temporary IDs because they are referenced only once.
next_temp_id = int(_ASSET_GROUP_TEMPORARY_ID) - 1


# [START add_performance_max_campaign]
def create_pmax_campaign(
    account_id: str,
    is_mcc: bool,
    customer_id: str,
    business_name: str,
    logo_gcs_uri: str,
    brand_guidelines_enabled: bool,
    final_urls: list[str],
    final_mobile_urls: list[str],
    budget: float,
    location_id_targeting: str,
    negative_location_id_targeting: str,
    language_id_targeting: str,
    headlines: list[str],
    descriptions: list[str],
    long_headlines: list[str],
    marketing_image_asset_gcs_uris: list[str],
    square_marketing_image_asset_gcs_uris: list[str],
    search_theme: str = "",
    audience_id: str | None = None,
    portrait_marketing_image_asset_gcs_uris: list[str] | None = None,
    video_asset_gcs_uris: list[str] | None = None,
) -> list[str]:
    """The main method that creates all necessary entities for the example.

    Args:
        account_id: The login customer ID for the Google Ads account.
        is_mcc: Whether the account_id refers to a Manager (MCC) account.
        customer_id: The target customer ID where the campaign will be created.
        business_name: The name of the business for the campaign.
        logo_gcs_uri: GCS URI for the business logo asset.
        brand_guidelines_enabled: Whether to enable brand guidelines for the campaign.
        final_urls: List of final URLs (landing pages) for the campaign.
        final_mobile_urls: List of final mobile URLs.
        budget: The daily budget for the campaign.
        location_id_targeting: Numeric location IDs to target.
        negative_location_id_targeting: Numeric location IDs to exclude.
        language_id_targeting: Numeric language IDs to target.
        headlines: List of headlines.
        descriptions: List of descriptions.
        long_headlines: List of long headlines.
        marketing_image_asset_gcs_uris: List of GCS URIs for marketing images.
        square_marketing_image_asset_gcs_uris: List of GCS URIs for square marketing images.
        search_theme: Search theme string.
        audience_id: Optional audience ID.
        portrait_marketing_image_asset_gcs_uris: Optional list of GCS URIs for portrait marketing images.
        video_asset_gcs_uris: Optional list of GCS URIs for video assets.
    """
    logging.info(
        "Starting execution of create_pmax_campaign with params: "
        "account_id=%s, is_mcc=%s, customer_id=%s, business_name=%s, logo_gcs_uri=%s, "
        "brand_guidelines_enabled=%s, final_urls=%s, final_mobile_urls=%s, "
        "location_id_targeting=%s, negative_location_id_targeting=%s, language_id_targeting=%s, "
        "headlines=%s, descriptions=%s, long_headlines=%s, marketing_image_asset_gcs_uris=%s, "
        "square_marketing_image_asset_gcs_uris=%s, search_theme=%s, audience_id=%s, "
        "portrait_marketing_image_asset_gcs_uris=%s, video_asset_gcs_uris=%s",
        account_id,
        is_mcc,
        customer_id,
        business_name,
        logo_gcs_uri,
        brand_guidelines_enabled,
        final_urls,
        final_mobile_urls,
        location_id_targeting,
        negative_location_id_targeting,
        language_id_targeting,
        headlines,
        descriptions,
        long_headlines,
        marketing_image_asset_gcs_uris,
        square_marketing_image_asset_gcs_uris,
        search_theme,
        audience_id,
        portrait_marketing_image_asset_gcs_uris,
        video_asset_gcs_uris,
    )

    googleads_client: client.GoogleAdsClient = build_gads_client(
        account_id=account_id,
        is_mcc=is_mcc,
        developer_token=os.getenv("DEVELOPER_TOKEN", ""),
    )

    storage_service = StorageService()

    # Upload videos from GCS to YouTube via the API
    video_asset_youtube_video_ids = []
    if video_asset_gcs_uris:
        for video_gcs_uri in video_asset_gcs_uris:
            logging.info("Getting video blob from GCS: %s", video_gcs_uri)
            blob = storage_service.get_blob(video_gcs_uri)

            if not blob:
                raise ValueError(
                    f"The video {video_gcs_uri} was not found in GCS. Please check the URI."
                )

            logging.info("Uploading video to YouTube from GCS blob: %s", blob.name)
            video_asset_youtube_video_id = upload_video_asset(
                googleads_client, customer_id, blob
            )

            if video_asset_youtube_video_id:
                video_asset_youtube_video_ids.append(video_asset_youtube_video_id)

    # Wait 60 secs for the video to be available on YT
    # even though it is uploaded, looks like it's not available and we get and error
    # YOUTUBE_VIDEO_TOO_SHORT?
    if video_asset_youtube_video_ids:
        logging.info("Wait 60 secs for the videos to be available on YT...")
        time.sleep(60)

    # [START add_performance_max_campaign_1]
    googleads_service: GoogleAdsServiceClient = googleads_client.get_service(
        "GoogleAdsService"
    )

    # Performance Max campaigns require that repeated assets such as headlines
    # and descriptions be created before the campaign.
    # For the list of required assets for a Performance Max campaign, see
    # https://developers.google.com/google-ads/api/docs/performance-max/assets
    #
    # Create the headlines.
    headline_asset_resource_names: list[str] = create_multiple_text_assets(
        googleads_client, customer_id, headlines
    )
    # Create the descriptions.
    description_asset_resource_names: list[str] = create_multiple_text_assets(
        googleads_client,
        customer_id,
        descriptions,
    )

    # The below methods create and return MutateOperations that we later
    # provide to the GoogleAdsService.Mutate method in order to create the
    # entities in a single request. Since the entities for a Performance Max
    # campaign are closely tied to one-another, it's considered a best practice
    # to create them in a single Mutate request so they all complete
    # successfully or fail entirely, leaving no orphaned entities. See:
    # https://developers.google.com/google-ads/api/docs/mutating/overview
    campaign_budget_operation: MutateOperation = create_campaign_budget_operation(
        googleads_client, customer_id, budget
    )
    performance_max_campaign_operation: MutateOperation = (
        create_performance_max_campaign_operation(
            googleads_client,
            customer_id,
            brand_guidelines_enabled,
        )
    )
    campaign_criterion_operations: list[MutateOperation] = (
        create_campaign_criterion_operations(
            googleads_client,
            customer_id,
            location_id_targeting,
            negative_location_id_targeting,
            language_id_targeting,
        )
    )
    asset_group_operations: list[MutateOperation] = create_asset_group_operation(
        googleads_client,
        storage_service,
        customer_id,
        business_name,
        logo_gcs_uri,
        brand_guidelines_enabled,
        final_urls,
        final_mobile_urls,
        headline_asset_resource_names,
        description_asset_resource_names,
        long_headlines,
        marketing_image_asset_gcs_uris,
        square_marketing_image_asset_gcs_uris,
        portrait_marketing_image_asset_gcs_uris,
        video_asset_youtube_video_ids,
    )
    asset_group_signal_operations: list[MutateOperation] = (
        create_asset_group_signal_operations(
            googleads_client, customer_id, search_theme, audience_id
        )
    )

    mutate_operations: list[MutateOperation] = [
        # It's important to create these entities in this order because
        # they depend on each other.
        campaign_budget_operation,
        performance_max_campaign_operation,
        # Expand the list of multiple operations into the list of
        # other mutate operations
        *campaign_criterion_operations,
        *asset_group_operations,
        *asset_group_signal_operations,
    ]

    # Send the operations in a single Mutate request.
    response: MutateGoogleAdsResponse = googleads_service.mutate(
        customer_id=customer_id, mutate_operations=mutate_operations
    )

    # Log and gather response details to share back to the user
    response_details = get_response_details(response)

    return response_details
    # [END add_performance_max_campaign_1]


# [START add_performance_max_campaign_2]
def create_campaign_budget_operation(
    client: client.GoogleAdsClient, customer_id: str, budget: float
) -> MutateOperation:
    """Creates a MutateOperation that creates a new CampaignBudget.

    A temporary ID will be assigned to this campaign budget so that it can be
    referenced by other objects being created in the same Mutate request.

    Args:
        client (client.GoogleAdsClient): an initialized client.GoogleAdsClient instance.
        customer_id (str): a client customer ID.
        budget (float): The daily budget for the campaign.

    Returns:
        MutateOperation: a MutateOperation that creates a CampaignBudget.
    """
    logging.info(
        "Starting execution of create_campaign_budget_operation with params: customer_id=%s",
        customer_id,
    )
    mutate_operation: MutateOperation = client.get_type("MutateOperation")
    campaign_budget_operation: CampaignBudgetOperation = (
        mutate_operation.campaign_budget_operation
    )
    campaign_budget: CampaignBudget = campaign_budget_operation.create
    campaign_budget.name = f"Performance Max campaign budget #{uuid4()}"
    # The budget period already defaults to DAILY.
    campaign_budget.amount_micros = int(budget * 1000000)
    campaign_budget.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
    # A Performance Max campaign cannot use a shared campaign budget.
    campaign_budget.explicitly_shared = False

    # Set a temporary ID in the budget's resource name so it can be referenced
    # by the campaign in later steps.
    campaign_budget.resource_name = client.get_service(
        "CampaignBudgetService"
    ).campaign_budget_path(customer_id, _BUDGET_TEMPORARY_ID)

    return mutate_operation
    # [END add_performance_max_campaign_2]


# [START add_performance_max_campaign_3]
def create_performance_max_campaign_operation(
    client: client.GoogleAdsClient,
    customer_id: str,
    brand_guidelines_enabled: bool,
) -> MutateOperation:
    """Creates a MutateOperation that creates a new Performance Max campaign.

    A temporary ID will be assigned to this campaign so that it can
    be referenced by other objects being created in the same Mutate request.

    Args:
        client: an initialized client.GoogleAdsClient instance.
        customer_id: a client customer ID.
        brand_guidelines_enabled: a boolean value indicating if the campaign is
          enabled for brand guidelines.

    Returns:
        a MutateOperation that creates a campaign.
    """
    logging.info(
        "Starting execution of create_performance_max_campaign_operation with params: "
        "customer_id=%s, brand_guidelines_enabled=%s",
        customer_id,
        brand_guidelines_enabled,
    )
    mutate_operation: MutateOperation = client.get_type("MutateOperation")
    campaign: Campaign = mutate_operation.campaign_operation.create
    campaign.name = f"Performance Max campaign #{uuid4()}"
    # Set the campaign status as PAUSED. The campaign is the only entity in
    # the mutate request that should have its status set.
    campaign.status = client.enums.CampaignStatusEnum.PAUSED
    # All Performance Max campaigns have an advertising_channel_type of
    # PERFORMANCE_MAX. The advertising_channel_sub_type should not be set.
    campaign.advertising_channel_type = (
        client.enums.AdvertisingChannelTypeEnum.PERFORMANCE_MAX
    )
    # Bidding strategy must be set directly on the campaign.
    # Setting a portfolio bidding strategy by resource name is not supported.
    # Max Conversion and Maximize Conversion Value are the only strategies
    # supported for Performance Max campaigns.
    # An optional ROAS (Return on Advertising Spend) can be set for
    # maximize_conversion_value. The ROAS value must be specified as a ratio in
    # the API. It is calculated by dividing "total value" by "total spend".
    # For more information on Maximize Conversion Value, see the support
    # article: http://support.google.com/google-ads/answer/7684216.
    # A target_roas of 3.5 corresponds to a 350% return on ad spend.
    campaign.bidding_strategy_type = (
        client.enums.BiddingStrategyTypeEnum.MAXIMIZE_CONVERSION_VALUE
    )
    campaign.maximize_conversion_value.target_roas = 3.5

    # Set if the campaign is enabled for brand guidelines. For more information
    # on brand guidelines, see https://support.google.com/google-ads/answer/14934472.
    campaign.brand_guidelines_enabled = brand_guidelines_enabled

    # Assign the resource name with a temporary ID.
    campaign_service: CampaignServiceClient = client.get_service("CampaignService")
    campaign.resource_name = campaign_service.campaign_path(
        customer_id, _PERFORMANCE_MAX_CAMPAIGN_TEMPORARY_ID
    )
    # Set the budget using the given budget resource name.
    campaign.campaign_budget = campaign_service.campaign_budget_path(
        customer_id, _BUDGET_TEMPORARY_ID
    )

    # Declare whether or not this campaign serves political ads targeting the
    # EU. Valid values are:
    #   CONTAINS_EU_POLITICAL_ADVERTISING
    #   DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING
    campaign.contains_eu_political_advertising = (
        client.enums.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING
    )

    # Optional fields
    campaign.start_date_time = (datetime.now() + timedelta(1)).strftime(
        "%Y%m%d 00:00:00"
    )
    campaign.end_date_time = (datetime.now() + timedelta(365)).strftime(
        "%Y%m%d 23:59:59"
    )

    # [START add_performance_max_text_guidelines]
    campaign.text_guidelines.term_exclusions = ["cheap", "free"]
    messaging_restriction = campaign.MessagingRestriction()
    messaging_restriction.restriction_text = "Don't mention competitor names"
    messaging_restriction.restriction_type = (
        client.enums.MessagingRestrictionTypeEnum.RESTRICTION_BASED_EXCLUSION
    )
    campaign.text_guidelines.messaging_restrictions.append(messaging_restriction)
    # [END add_performance_max_text_guidelines]

    # [START add_pmax_asset_automation_settings]
    # Configures the optional opt-in/out status for asset automation settings.
    for asset_automation_type_enum in [
        client.enums.AssetAutomationTypeEnum.GENERATE_IMAGE_EXTRACTION,
        client.enums.AssetAutomationTypeEnum.FINAL_URL_EXPANSION_TEXT_ASSET_AUTOMATION,
        client.enums.AssetAutomationTypeEnum.TEXT_ASSET_AUTOMATION,
        client.enums.AssetAutomationTypeEnum.GENERATE_ENHANCED_YOUTUBE_VIDEOS,
        client.enums.AssetAutomationTypeEnum.GENERATE_IMAGE_ENHANCEMENT,
    ]:
        asset_automattion_setting: Campaign.AssetAutomationSetting = client.get_type(
            "Campaign"
        ).AssetAutomationSetting()
        asset_automattion_setting.asset_automation_type = asset_automation_type_enum
        asset_automattion_setting.asset_automation_status = (
            client.enums.AssetAutomationStatusEnum.OPTED_IN
        )
        campaign.asset_automation_settings.append(asset_automattion_setting)
        # [END add_pmax_asset_automation_settings]

    return mutate_operation
    # [END add_performance_max_campaign_3]


# [START add_performance_max_campaign_4]
def create_campaign_criterion_operations(
    client: client.GoogleAdsClient,
    customer_id: str,
    location_id_targeting: str,
    negative_location_id_targeting: str,
    language_id_targeting: str,
) -> list[MutateOperation]:
    """Creates a list of MutateOperations that create new campaign criteria.

    Args:
        client (client.GoogleAdsClient): an initialized client.GoogleAdsClient instance.
        customer_id (str): a client customer ID.
        location_id_targeting (str): Numeric location IDs to target.
        negative_location_id_targeting (str): Numeric location IDs to exclude.
        language_id_targeting (str): Numeric language IDs to target.

    Returns:
        list[MutateOperation]: a list of MutateOperations that create new campaign criteria.
    """
    logging.info(
        "Starting execution of create_campaign_criterion_operations with params: "
        "customer_id=%s, location_id_targeting=%s, negative_location_id_targeting=%s, "
        "language_id_targeting=%s",
        customer_id,
        location_id_targeting,
        negative_location_id_targeting,
        language_id_targeting,
    )
    campaign_service: CampaignServiceClient = client.get_service("CampaignService")
    geo_target_constant_service: GeoTargetConstantServiceClient = client.get_service(
        "GeoTargetConstantService"
    )
    googleads_service: GoogleAdsServiceClient = client.get_service("GoogleAdsService")

    operations: list[MutateOperation] = []
    # Set the LOCATION campaign criteria.
    # Target all of New York City except Brooklyn.
    # Location IDs are listed here:
    # https://developers.google.com/google-ads/api/reference/data/geotargets
    # and they can also be retrieved using the GeoTargetConstantService as shown
    # here: https://developers.google.com/google-ads/api/docs/targeting/location-targeting
    #
    # We will add one positive location target for New York City (ID=1023191)
    # and one negative location target for Brooklyn (ID=1022762).
    # First, add the positive (negative = False) for New York City.
    mutate_operation: MutateOperation = client.get_type("MutateOperation")
    campaign_criterion: CampaignCriterion = (
        mutate_operation.campaign_criterion_operation.create
    )
    campaign_criterion.campaign = campaign_service.campaign_path(
        customer_id, _PERFORMANCE_MAX_CAMPAIGN_TEMPORARY_ID
    )
    campaign_criterion.location.geo_target_constant = (
        geo_target_constant_service.geo_target_constant_path(location_id_targeting)
    )
    campaign_criterion.negative = False
    operations.append(mutate_operation)

    # Next add the negative target for Brooklyn.
    mutate_operation: MutateOperation = client.get_type("MutateOperation")
    campaign_criterion: CampaignCriterion = (
        mutate_operation.campaign_criterion_operation.create
    )
    campaign_criterion.campaign = campaign_service.campaign_path(
        customer_id, _PERFORMANCE_MAX_CAMPAIGN_TEMPORARY_ID
    )
    campaign_criterion.location.geo_target_constant = (
        geo_target_constant_service.geo_target_constant_path(
            negative_location_id_targeting
        )
    )
    campaign_criterion.negative = True
    operations.append(mutate_operation)

    # Set the LANGUAGE campaign criterion.
    mutate_operation: MutateOperation = client.get_type("MutateOperation")
    campaign_criterion: CampaignCriterion = (
        mutate_operation.campaign_criterion_operation.create
    )
    campaign_criterion.campaign = campaign_service.campaign_path(
        customer_id, _PERFORMANCE_MAX_CAMPAIGN_TEMPORARY_ID
    )
    # Set the language.
    # For a list of all language codes, see:
    # https://developers.google.com/google-ads/api/reference/data/codes-formats#expandable-7
    campaign_criterion.language.language_constant = (
        googleads_service.language_constant_path(language_id_targeting)
    )  # English
    operations.append(mutate_operation)

    return operations
    # [END add_performance_max_campaign_4]


# [START add_performance_max_campaign_5]
def create_multiple_text_assets(
    client: client.GoogleAdsClient, customer_id: str, texts: list[str]
) -> list[str]:
    """Creates multiple text assets and returns the list of resource names.

    Args:
        client: an initialized client.GoogleAdsClient instance.
        customer_id: a client customer ID.
        texts: a list of strings, each of which will be used to create a text
          asset.

    Returns:
        asset_resource_names: a list of asset resource names.
    """
    logging.info(
        "Starting execution of create_multiple_text_assets with params: "
        "customer_id=%s, texts=%s",
        customer_id,
        texts,
    )
    # Here again we use the GoogleAdService to create multiple text
    # assets in a single request.
    googleads_service: GoogleAdsServiceClient = client.get_service("GoogleAdsService")

    operations: list[MutateOperation] = []
    for text in texts:
        mutate_operation: MutateOperation = client.get_type("MutateOperation")
        asset: Asset = mutate_operation.asset_operation.create
        asset.text_asset.text = text
        operations.append(mutate_operation)

    # Send the operations in a single Mutate request.
    response: MutateGoogleAdsResponse = googleads_service.mutate(
        customer_id=customer_id,
        mutate_operations=operations,
    )
    asset_resource_names: list[str] = []
    for result in response.mutate_operation_responses:
        if result._pb.HasField("asset_result"):
            asset_resource_names.append(result.asset_result.resource_name)

    return asset_resource_names
    # [END add_performance_max_campaign_5]


# [START add_performance_max_campaign_6]
def create_asset_group_operation(
    client: client.GoogleAdsClient,
    storage_service: StorageService,
    customer_id: str,
    business_name: str,
    logo_gcs_uri: str,
    brand_guidelines_enabled: bool,
    final_urls: list[str],
    final_mobile_urls: list[str],
    headline_asset_resource_names: list[str],
    description_asset_resource_names: list[str],
    long_headlines: list[str],
    marketing_image_asset_gcs_uris: list[str],
    square_marketing_image_asset_gcs_uris: list[str],
    portrait_marketing_image_asset_gcs_uris: list[str] | None,
    video_asset_youtube_video_ids: list[str] | None = None,
) -> list[MutateOperation]:
    """Creates a list of MutateOperations that create a new asset_group.

    A temporary ID will be assigned to this asset group so that it can
    be referenced by other objects being created in the same Mutate request.

    Args:
        client: an initialized client.GoogleAdsClient instance.
        storage_service: an initialized StorageService instance.
        customer_id: a client customer ID.
        business_name: The name of the business for the campaign.
        logo_gcs_uri: GCS URI for the business logo asset.
        brand_guidelines_enabled: Whether to enable brand guidelines for the campaign.
        final_urls: List of final URLs (landing pages) for the campaign.
        final_mobile_urls: List of final mobile URLs.
        headline_asset_resource_names: a list of headline resource names.
        description_asset_resource_names: a list of description resource names.
        long_headlines: List of long headlines.
        marketing_image_asset_gcs_uris: List of GCS URIs for marketing images.
        square_marketing_image_asset_gcs_uris: List of GCS URIs for square marketing images.
        portrait_marketing_image_asset_gcs_uris: Optional list of GCS URIs for portrait marketing images.
        video_asset_youtube_video_ids: Optional list of YouTube video IDs.

    Returns:
        MutateOperations that create a new asset group and related assets.
    """
    logging.info(
        "Starting execution of create_asset_group_operation with params: "
        "customer_id=%s, business_name=%s, logo_gcs_uri=%s, brand_guidelines_enabled=%s, "
        "final_urls=%s, final_mobile_urls=%s, headline_asset_resource_names=%s, "
        "description_asset_resource_names=%s, long_headlines=%s, marketing_image_asset_gcs_uris=%s, "
        "square_marketing_image_asset_gcs_uris=%s, portrait_marketing_image_asset_gcs_uris=%s, video_assets=%s",
        customer_id,
        business_name,
        logo_gcs_uri,
        brand_guidelines_enabled,
        final_urls,
        final_mobile_urls,
        headline_asset_resource_names,
        description_asset_resource_names,
        long_headlines,
        marketing_image_asset_gcs_uris,
        square_marketing_image_asset_gcs_uris,
        portrait_marketing_image_asset_gcs_uris,
        video_asset_youtube_video_ids,
    )
    asset_group_service: AssetGroupServiceClient = client.get_service(
        "AssetGroupService"
    )
    campaign_service: CampaignServiceClient = client.get_service("CampaignService")

    operations: list[MutateOperation] = []

    # Create the AssetGroup
    mutate_operation: MutateOperation = client.get_type("MutateOperation")
    asset_group: AssetGroup = mutate_operation.asset_group_operation.create
    asset_group.name = f"Performance Max asset group #{uuid4()}"
    asset_group.campaign = campaign_service.campaign_path(
        customer_id, _PERFORMANCE_MAX_CAMPAIGN_TEMPORARY_ID
    )
    asset_group.final_urls.extend(final_urls)
    asset_group.final_mobile_urls.extend(final_mobile_urls)
    asset_group.status = client.enums.AssetGroupStatusEnum.PAUSED
    asset_group.resource_name = asset_group_service.asset_group_path(
        customer_id,
        _ASSET_GROUP_TEMPORARY_ID,
    )
    operations.append(mutate_operation)

    # For the list of required assets for a Performance Max campaign, see
    # https://developers.google.com/google-ads/api/docs/performance-max/assets

    # An AssetGroup is linked to an Asset by creating a new AssetGroupAsset
    # and providing:
    #   the resource name of the AssetGroup
    #   the resource name of the Asset
    #   the field_type of the Asset in this AssetGroup.
    #
    # To learn more about AssetGroups, see
    # https://developers.google.com/google-ads/api/docs/performance-max/asset-groups

    # Link the previously created multiple text assets.

    # Link the headline assets.
    for resource_name in headline_asset_resource_names:
        mutate_operation: MutateOperation = client.get_type("MutateOperation")
        asset_group_asset: AssetGroupAsset = (
            mutate_operation.asset_group_asset_operation.create
        )
        asset_group_asset.field_type = client.enums.AssetFieldTypeEnum.HEADLINE
        asset_group_asset.asset_group = asset_group_service.asset_group_path(
            customer_id,
            _ASSET_GROUP_TEMPORARY_ID,
        )
        asset_group_asset.asset = resource_name
        operations.append(mutate_operation)

    #  Link the description assets.
    for resource_name in description_asset_resource_names:
        mutate_operation: MutateOperation = client.get_type("MutateOperation")
        asset_group_asset: AssetGroupAsset = (
            mutate_operation.asset_group_asset_operation.create
        )
        asset_group_asset.field_type = client.enums.AssetFieldTypeEnum.DESCRIPTION
        asset_group_asset.asset_group = asset_group_service.asset_group_path(
            customer_id,
            _ASSET_GROUP_TEMPORARY_ID,
        )
        asset_group_asset.asset = resource_name
        operations.append(mutate_operation)

    # Create and link the long headline text assets.
    for long_headline in long_headlines:
        mutate_operations: list[MutateOperation] = create_and_link_text_asset(
            client,
            customer_id,
            long_headline,
            client.enums.AssetFieldTypeEnum.LONG_HEADLINE,
        )
        operations.extend(mutate_operations)

    # Create and link the business name and logo asset.
    mutate_operations: list[MutateOperation] = create_and_link_brand_assets(
        client,
        customer_id,
        business_name,
        logo_gcs_uri,
        "Marketing Logo",  # Use this by default
        brand_guidelines_enabled,
        storage_service,
    )
    operations.extend(mutate_operations)

    # Create and link the image assets.

    # Create and link the Marketing Image Assets.
    for i, marketing_image_asset_gcs_uri in enumerate(marketing_image_asset_gcs_uris):
        mutate_operations: list[MutateOperation] = create_and_link_image_asset(
            client,
            storage_service,
            customer_id,
            marketing_image_asset_gcs_uri,
            client.enums.AssetFieldTypeEnum.MARKETING_IMAGE,
            f"Marketing Image {i+1} {int(time.time())}",
        )
        operations.extend(mutate_operations)

    # Create and link the Square Marketing Image Assets.
    for i, square_marketing_image_asset_gcs_uri in enumerate(square_marketing_image_asset_gcs_uris):
        mutate_operations: list[MutateOperation] = create_and_link_image_asset(
            client,
            storage_service,
            customer_id,
            square_marketing_image_asset_gcs_uri,
            client.enums.AssetFieldTypeEnum.SQUARE_MARKETING_IMAGE,
            f"Square Image {i+1} {int(time.time())}",
        )
        operations.extend(mutate_operations)

    # Create and link the Portrait Marketing Image Assets.
    if portrait_marketing_image_asset_gcs_uris:
        for (
            portrait_marketing_image_asset_gcs_uri
        ) in portrait_marketing_image_asset_gcs_uris:
            mutate_operations: list[MutateOperation] = create_and_link_image_asset(
                client,
                storage_service,
                customer_id,
                portrait_marketing_image_asset_gcs_uri,
                client.enums.AssetFieldTypeEnum.PORTRAIT_MARKETING_IMAGE,
                "Portrait Image Asset PORTRAIT_MARKETING_IMAGE",
            )
            operations.extend(mutate_operations)

    for video_asset_youtube_video_id in video_asset_youtube_video_ids:
        mutate_operations: list[MutateOperation] = create_and_link_video_asset(
            client,
            customer_id,
            video_asset_youtube_video_id,
            client.enums.AssetFieldTypeEnum.YOUTUBE_VIDEO,
            "Video Asset YOUTUBE_VIDEO",
        )
        operations.extend(mutate_operations)

    return operations
    # [END add_performance_max_campaign_6]


# [START add_performance_max_campaign_7]
def create_and_link_text_asset(
    client: client.GoogleAdsClient,
    customer_id: str,
    text: str,
    field_type: AssetFieldTypeEnum.AssetFieldType,
) -> list[MutateOperation]:
    """Creates a list of MutateOperations that create a new linked text asset.

    Args:
        client: an initialized client.GoogleAdsClient instance.
        customer_id: a client customer ID.
        text: the text of the asset to be created.
        field_type: the field_type of the new asset in the AssetGroupAsset.

    Returns:
        MutateOperations that create a new linked text asset.
    """
    logging.info(
        "Starting execution of create_and_link_text_asset with params: "
        "customer_id=%s, text=%s, field_type=%s",
        customer_id,
        text,
        field_type,
    )
    global next_temp_id
    operations: list[MutateOperation] = []
    asset_service: AssetServiceClient = client.get_service("AssetService")
    asset_group_service: AssetGroupServiceClient = client.get_service(
        "AssetGroupService"
    )

    # Create the Text Asset.
    mutate_operation: MutateOperation = client.get_type("MutateOperation")
    asset: Asset = mutate_operation.asset_operation.create
    asset.resource_name = asset_service.asset_path(customer_id, next_temp_id)
    asset.text_asset.text = text
    operations.append(mutate_operation)

    # Create an AssetGroupAsset to link the Asset to the AssetGroup.
    mutate_operation: MutateOperation = client.get_type("MutateOperation")
    asset_group_asset: AssetGroupAsset = (
        mutate_operation.asset_group_asset_operation.create
    )
    asset_group_asset.field_type = field_type
    asset_group_asset.asset_group = asset_group_service.asset_group_path(
        customer_id,
        _ASSET_GROUP_TEMPORARY_ID,
    )
    asset_group_asset.asset = asset_service.asset_path(customer_id, next_temp_id)
    operations.append(mutate_operation)

    next_temp_id -= 1
    return operations
    # [END add_performance_max_campaign_7]


# [START add_performance_max_campaign_8]
def create_and_link_image_asset(
    client: client.GoogleAdsClient,
    storage_service: StorageService,
    customer_id: str,
    gcs_uri: str,
    field_type: AssetFieldTypeEnum.AssetFieldType,
    asset_name: str,
) -> list[MutateOperation]:
    """Creates a list of MutateOperations that create a new linked image asset.

    Args:
        client: an initialized client.GoogleAdsClient instance.
        customer_id: a client customer ID.
        gcs_uri: the GCS URI of the image to be retrieved and put into an asset.
        field_type: the field_type of the new asset in the AssetGroupAsset.
        asset_name: the asset name.
        storage_service: an initialized StorageService instance.

    Returns:
        MutateOperations that create a new linked image asset.
    """
    logging.info(
        "Starting execution of create_and_link_image_asset with params: "
        "customer_id=%s, gcs_uri=%s, field_type=%s, asset_name=%s",
        customer_id,
        gcs_uri,
        field_type,
        asset_name,
    )
    global next_temp_id
    operations: list[MutateOperation] = []
    asset_service: AssetServiceClient = client.get_service("AssetService")
    asset_group_service: AssetGroupServiceClient = client.get_service(
        "AssetGroupService"
    )

    # Create the Image Asset.
    mutate_operation: MutateOperation = client.get_type("MutateOperation")
    asset: Asset = mutate_operation.asset_operation.create
    asset.resource_name = asset_service.asset_path(customer_id, next_temp_id)
    # Provide a unique friendly name to identify your asset.
    # When there is an existing image asset with the same content but a different
    # name, the new name will be dropped silently.
    asset.name = asset_name
    asset.type_ = client.enums.AssetTypeEnum.IMAGE

    # Download image from GCS
    blob = storage_service.get_blob(gcs_uri)
    if not blob:
        raise ValueError(f"Could not find blob at {gcs_uri}")
    asset.image_asset.data = blob.download_as_bytes()

    operations.append(mutate_operation)

    # Create an AssetGroupAsset to link the Asset to the AssetGroup.
    mutate_operation: MutateOperation = client.get_type("MutateOperation")
    asset_group_asset: AssetGroupAsset = (
        mutate_operation.asset_group_asset_operation.create
    )
    asset_group_asset.field_type = field_type
    asset_group_asset.asset_group = asset_group_service.asset_group_path(
        customer_id,
        _ASSET_GROUP_TEMPORARY_ID,
    )
    asset_group_asset.asset = asset_service.asset_path(customer_id, next_temp_id)
    operations.append(mutate_operation)

    next_temp_id -= 1
    return operations
    # [END add_performance_max_campaign_8]


# [START add_performance_max_campaign_9]
def create_and_link_video_asset(
    client: client.GoogleAdsClient,
    customer_id: str,
    youtube_video_id: str,
    field_type: AssetFieldTypeEnum.AssetFieldType,
    asset_name: str,
):
    logging.info(
        "Starting execution of create_and_link_video_asset with params: "
        "customer_id=%s, youtube_video_id=%s, field_type=%s, asset_name=%s",
        customer_id,
        youtube_video_id,
        field_type,
        asset_name,
    )
    global next_temp_id
    operations: list[MutateOperation] = []
    asset_service = client.get_service("AssetService")
    asset_group_service = client.get_service("AssetGroupService")

    # 1. Create the Video Asset Operation
    mutate_operation: MutateOperation = client.get_type("MutateOperation")
    asset = mutate_operation.asset_operation.create

    # Use the temporary ID for the resource name
    video_asset_resource_name = asset_service.asset_path(customer_id, next_temp_id)
    asset.resource_name = video_asset_resource_name
    asset.name = asset_name

    # Set the type to YOUTUBE_VIDEO and provide the ID
    # asset.type_ = client.enums.AssetTypeEnum.VIDEO  # CHECK THIS!!!!
    asset.youtube_video_asset.youtube_video_id = youtube_video_id

    operations.append(mutate_operation)

    # 2. Create the AssetGroupAsset to link Video to AssetGroup
    mutate_operation: MutateOperation = client.get_type("MutateOperation")
    asset_group_asset = mutate_operation.asset_group_asset_operation.create

    # This field_type should be client.enums.AssetFieldTypeEnum.YOUTUBE_VIDEO
    asset_group_asset.field_type = field_type

    # Link to your Asset Group (using your existing constant)
    asset_group_asset.asset_group = asset_group_service.asset_group_path(
        customer_id,
        _ASSET_GROUP_TEMPORARY_ID,
    )

    # Link to the Video Asset we just defined above
    asset_group_asset.asset = video_asset_resource_name

    operations.append(mutate_operation)

    # Decrement the global ID for the next asset in the loop
    next_temp_id -= 1

    return operations


# [START add_performance_max_campaign_10]
def create_and_link_brand_assets(
    client: client.GoogleAdsClient,
    customer_id: str,
    business_name: str,
    logo_gcs_uri: str,
    logo_name: str,
    brand_guidelines_enabled: bool,
    storage_service: StorageService,
) -> list[MutateOperation]:
    """Creates a list of MutateOperations that create linked brand assets.

    Args:
        client (client.GoogleAdsClient): an initialized client.GoogleAdsClient instance.
        customer_id (str): a client customer ID.
        business_name (str): the business name text to be put into an asset.
        logo_gcs_uri (str): the GCS URI of the logo to be retrieved and put into an asset.
        logo_name (str): the asset name of the logo.
        brand_guidelines_enabled (bool): a boolean value indicating if the campaign is
          enabled for brand guidelines.
        storage_service (StorageService): an initialized StorageService instance.

    Returns:
        list[MutateOperation]: MutateOperations that create linked brand assets.
    """
    logging.info(
        "Starting execution of create_and_link_brand_assets with params: "
        "customer_id=%s, business_name=%s, logo_gcs_uri=%s, logo_name=%s, "
        "brand_guidelines_enabled=%s",
        customer_id,
        business_name,
        logo_gcs_uri,
        logo_name,
        brand_guidelines_enabled,
    )
    global next_temp_id
    operations: list[MutateOperation] = []
    asset_service: AssetServiceClient = client.get_service("AssetService")

    # Create the Text Asset.
    text_asset_temp_id = next_temp_id
    next_temp_id -= 1

    text_mutate_operation = client.get_type("MutateOperation")
    text_asset: Asset = text_mutate_operation.asset_operation.create
    text_asset.resource_name = asset_service.asset_path(customer_id, text_asset_temp_id)
    text_asset.text_asset.text = business_name
    operations.append(text_mutate_operation)

    # Create the Image Asset.
    image_asset_temp_id = next_temp_id
    next_temp_id -= 1

    image_mutate_operation = client.get_type("MutateOperation")
    image_asset: Asset = image_mutate_operation.asset_operation.create
    image_asset.resource_name = asset_service.asset_path(
        customer_id, image_asset_temp_id
    )
    # Provide a unique friendly name to identify your asset.
    # When there is an existing image asset with the same content but a different
    # name, the new name will be dropped silently.
    image_asset.name = logo_name
    image_asset.type_ = client.enums.AssetTypeEnum.IMAGE

    # Download logo from GCS
    blob = storage_service.get_blob(logo_gcs_uri)
    if not blob:
        raise ValueError(f"Could not find blob at {logo_gcs_uri}")
    image_asset.image_asset.data = blob.download_as_bytes()

    operations.append(image_mutate_operation)

    if brand_guidelines_enabled:
        # Create CampaignAsset resources to link the Asset resources to the Campaign.
        campaign_service: CampaignServiceClient = client.get_service("CampaignService")

        business_name_mutate_operation: MutateOperation = client.get_type(
            "MutateOperation"
        )
        business_name_campaign_asset: CampaignAsset = (
            business_name_mutate_operation.campaign_asset_operation.create
        )
        business_name_campaign_asset.field_type = (
            client.enums.AssetFieldTypeEnum.BUSINESS_NAME
        )
        business_name_campaign_asset.campaign = campaign_service.campaign_path(
            customer_id, _PERFORMANCE_MAX_CAMPAIGN_TEMPORARY_ID
        )
        business_name_campaign_asset.asset = asset_service.asset_path(
            customer_id, text_asset_temp_id
        )
        operations.append(business_name_mutate_operation)

        logo_mutate_operation: MutateOperation = client.get_type("MutateOperation")
        logo_campaign_asset: CampaignAsset = (
            logo_mutate_operation.campaign_asset_operation.create
        )
        logo_campaign_asset.field_type = client.enums.AssetFieldTypeEnum.LOGO
        logo_campaign_asset.campaign = campaign_service.campaign_path(
            customer_id, _PERFORMANCE_MAX_CAMPAIGN_TEMPORARY_ID
        )
        logo_campaign_asset.asset = asset_service.asset_path(
            customer_id, image_asset_temp_id
        )
        operations.append(logo_mutate_operation)

    else:
        # Create AssetGroupAsset resources to link the Asset resources to the AssetGroup.
        asset_group_service: AssetGroupServiceClient = client.get_service(
            "AssetGroupService"
        )

        business_name_mutate_operation: MutateOperation = client.get_type(
            "MutateOperation"
        )
        business_name_asset_group_asset: AssetGroupAsset = (
            business_name_mutate_operation.asset_group_asset_operation.create
        )
        business_name_asset_group_asset.field_type = (
            client.enums.AssetFieldTypeEnum.BUSINESS_NAME
        )
        business_name_asset_group_asset.asset_group = (
            asset_group_service.asset_group_path(
                customer_id,
                _ASSET_GROUP_TEMPORARY_ID,
            )
        )
        business_name_asset_group_asset.asset = asset_service.asset_path(
            customer_id, text_asset_temp_id
        )
        operations.append(business_name_mutate_operation)

        logo_mutate_operation: MutateOperation = client.get_type("MutateOperation")
        logo_asset_group_asset: AssetGroupAsset = (
            logo_mutate_operation.asset_group_asset_operation.create
        )
        logo_asset_group_asset.field_type = client.enums.AssetFieldTypeEnum.LOGO
        logo_asset_group_asset.asset_group = asset_group_service.asset_group_path(
            customer_id,
            _ASSET_GROUP_TEMPORARY_ID,
        )
        logo_asset_group_asset.asset = asset_service.asset_path(
            customer_id, image_asset_temp_id
        )
        operations.append(logo_mutate_operation)

    return operations
    # [END create_and_link_brand_assets]


# [START add_performance_max_campaign_11]
def create_asset_group_signal_operations(
    client: client.GoogleAdsClient,
    customer_id: str,
    search_theme: str,
    audience_id: str | None = None,
) -> list[MutateOperation]:
    """Creates a list of MutateOperations that may create asset group signals.

    Args:
        client: an initialized client.GoogleAdsClient instance.
        customer_id: a client customer ID.
        audience_id: an optional audience ID.

    Returns:
        MutateOperations that create new asset group signals.
    """
    logging.info(
        "Starting execution of create_asset_group_signal_operations with params: "
        "customer_id=%s, search_theme=%s, audience_id=%s",
        customer_id,
        search_theme,
        audience_id,
    )
    googleads_service: GoogleAdsServiceClient = client.get_service("GoogleAdsService")
    asset_group_resource_name: str = googleads_service.asset_group_path(
        customer_id, _ASSET_GROUP_TEMPORARY_ID
    )

    operations: list[MutateOperation] = []

    if audience_id:
        # Create an audience asset group signal.
        # To learn more about Audience Signals, see:
        # https://developers.google.com/google-ads/api/performance-max/asset-group-signals#audiences
        # [START add_performance_max_campaign_9]
        mutate_operation: MutateOperation = client.get_type("MutateOperation")
        operation: AssetGroupSignal = (
            mutate_operation.asset_group_signal_operation.create
        )
        operation.asset_group = asset_group_resource_name
        operation.audience.audience = googleads_service.audience_path(
            customer_id, audience_id
        )
        operations.append(mutate_operation)
        # [END add_performance_max_campaign_9]

    # Create a search theme asset group signal.
    # To learn more about Search Themes Signals, see:
    # https://developers.google.com/google-ads/api/performance-max/asset-group-signals#search_themes
    # [START add_performance_max_campaign_10]
    mutate_operation: MutateOperation = client.get_type("MutateOperation")
    operation: AssetGroupSignal = mutate_operation.asset_group_signal_operation.create
    operation.asset_group = asset_group_resource_name
    operation.search_theme.text = search_theme
    operations.append(mutate_operation)
    # [END add_performance_max_campaign_10]

    return operations


# [END add_performance_max_campaign]


def get_response_details(response: MutateGoogleAdsResponse) -> list[str]:
    """Prints the details of a MutateGoogleAdsResponse.

    Parses the "response" oneof field name and uses it to extract the new
    entity's name and resource name.

    Args:
        response: a MutateGoogleAdsResponse object.
    """
    logging.info("Starting execution of print_response_details...")
    # Parse the Mutate response to print details about the entities that
    # were created by the request.
    results: Iterable[MutateOperation] = response.mutate_operation_responses
    results_messages: list[str] = []
    suffix = "_result"
    for result in results:
        for field_descriptor, value in result._pb.ListFields():
            if field_descriptor.name.endswith(suffix):
                name = field_descriptor.name[: -len(suffix)]
            else:
                name = field_descriptor.name
            message = (
                f"Created a(n) {util.convert_snake_case_to_upper_case(name)} with "
                f"{str(value).strip()}."
            )
            results_messages.append(message)
            logging.info(message)

    return results_messages


def upload_video_asset(
    client: client.GoogleAdsClient, customer_id: str, blob: storage.blob.Blob
) -> str | None:
    """Uploads a video to a Google-managed House channel via Google Ads API."""

    # 1. Get the specialized YouTube upload service
    yt_service = client.get_service("YouTubeVideoUploadService")

    # 2. Prepare the metadata request
    # Note: Use the factory to create the request object to ensure proper formatting
    upload_request = client.get_type("CreateYouTubeVideoUploadRequest")
    upload_request.customer_id = customer_id

    video_metadata = upload_request.you_tube_video_upload
    video_metadata.video_title = "PMax Campaign Video"
    video_metadata.video_description = "Uploaded via Google Ads API to House Channel"

    # House channels REQUIRE videos to be UNLISTED
    video_metadata.video_privacy = client.enums.YouTubeVideoPrivacyEnum.UNLISTED

    try:
        # 3. Execute the upload
        # 'stream' must be a readable binary file object
        with blob.open("rb") as video_stream:
            response = yt_service.create_you_tube_video_upload(
                request=upload_request,
                stream=video_stream,
                # Explicitly setting retry=None can sometimes prevent gRPC stream issues
                retry=None,
            )

        if not response or not response.resource_name:
            raise ValueError("There was an error uploading video")

        video_upload_resource_name = response.resource_name

        logging.info(
            f"The video {blob.name} was uploaded successfully! Resource Name: {video_upload_resource_name}"
        )

        # Retrieve the metadata of the newly uploaded video.
        query: str = f"""
            SELECT
            you_tube_video_upload.resource_name,
            you_tube_video_upload.video_id,
            you_tube_video_upload.state
            FROM you_tube_video_upload
            WHERE you_tube_video_upload.resource_name = '{video_upload_resource_name}'"""

        max_retries = 20
        retry_count = 0
        while retry_count < max_retries:
            ga_service: GoogleAdsServiceClient = client.get_service("GoogleAdsService")
            stream: Iterator[SearchGoogleAdsStreamResponse] = ga_service.search_stream(
                customer_id=customer_id, query=query
            )

            for row in itertools.chain.from_iterable(batch.results for batch in stream):
                video = row.you_tube_video_upload
                if (
                    video
                    and video.state
                    == YouTubeVideoUploadStateEnum.YouTubeVideoUploadState.UPLOADED
                ):
                    logging.info(
                        "Video with ID %s was found in state %s.",
                        video.video_id,
                        video.state,
                    )
                    return video.video_id

            retry_count += 1
            if retry_count < max_retries:
                logging.info(
                    f"Video not yet uploaded. Retry {retry_count}/{max_retries}. Sleeping for 15 seconds..."
                )
                time.sleep(15)

        logging.error(f"Video upload timed out after {max_retries} retries.")
        return None

    except errors.GoogleAdsException as ex:
        logging.error(f"Request ID: {ex.request_id}")
        for error in ex.failure.errors:
            logging.error(f"\tError: {error.message}")
        raise


def build_gads_client(
    account_id: str,
    is_mcc: bool,
    developer_token: str,
) -> client.GoogleAdsClient:
    """Builds the Google Ads client.

    Args:
        account_id (str): The Google Ads account ID.
        is_mcc (bool): Whether the account is an MCC account.
        developer_token (str): The developer token for the Google Ads API.

    Returns:
        client.GoogleAdsClient: An initialized client.GoogleAdsClient instance.
    """
    logging.info(
        "Starting execution of build_gads_client with params: "
        "account_id=%s, is_mcc=%s, developer_token=%s",
        account_id,
        is_mcc,
        developer_token,
    )

    if os.getenv("RUN_LOCAL") == "True":
        # Initialize with a dict instead of a file
        config = {
            "use_application_default_credentials": True,
            "developer_token": developer_token,
            "use_proto_plus": True,
        }
        if is_mcc:
            config["login_customer_id"] = account_id

        # The library automatically looks for ADC if no credentials are in the dict
        return client.GoogleAdsClient.load_from_dict(config, version="v23")

    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/adwords"]
    )
    # If MCC, include login_customer_id
    if is_mcc:
        return client.GoogleAdsClient(
            credentials=credentials,
            developer_token=developer_token,
            login_customer_id=account_id,
            # When use_proto_plus is enabled, the library wraps the raw protocol
            # buffer (the _pb object) in a more user-friendly Python class
            use_proto_plus=True,
        )
    else:
        return client.GoogleAdsClient(
            credentials=credentials,
            developer_token=developer_token,
            # When use_proto_plus is enabled, the library wraps the raw protocol
            # buffer (the _pb object) in a more user-friendly Python class
            use_proto_plus=True,
        )


if __name__ == "__main__":

    from dotenv import load_dotenv

    load_dotenv()

    # Check this link for more details on requirements: https://developers.google.com/google-ads/api/performance-max/asset-requirements

    # Google Ads account information
    account_id: str = ""  # Add your account_id here
    is_mcc: bool = True
    customer_id = ""  # Add your customer_id here

    # Brand Information

    # Requirements:
    # min 1 - max 1
    business_name: str = "Interplanetary Cruises"

    # Requirements:
    # (1:1) # min 1 - max 5
    logo_gcs_uri: str = "gs://co-op4all-deploy3-campaign-creator-agent/logo.png"

    brand_guidelines_enabled: bool = True

    # This is the primary landing page for your ads.
    final_urls: list[str] = ["http://www.example.com"]
    # This is an optional field specifically for mobile users.
    final_mobile_urls: list[str] = ["http://www.example.com"]

    # Budget information
    budget = 50

    location_id_targeting: str = "1023191"
    negative_location_id_targeting: str = "1022762"
    language_id_targeting: str = "1000"

    # Assets

    # Requirements:
    # min 3 - max 15
    # 30 characters limit
    headlines: list[str] = ["Travel", "Travel Reviews", "Book Travel"]

    # Requirements:
    # min 2 - max 5
    # 90 characters limit
    descriptions: list[str] = [
        "Take to the air!",
        "Fly to the sky!",
    ]

    # Requirements:
    # min 1 - max 5
    # 90 characters limit
    long_headlines: list[str] = ["Travel the World"]

    # Requirements:
    # min 1 - max 20
    # Landscape (1.91:1)
    marketing_image_asset_gcs_uris: list[str] = [
        "gs://co-op4all-deploy3-campaign-creator-agent/image_forced_ratio.png"
    ]

    # Requirements
    # min 1 - max 20
    # (1:1)
    square_marketing_image_asset_gcs_uris: list[str] = [
        "gs://co-op4all-deploy3-campaign-creator-agent/logo.png"
    ]

    # Requirements
    # Optional - max 20
    # (4:5)
    portrait_marketing_image_asset_gcs_uris: list[str] = [
        "gs://co-op4all-deploy3-campaign-creator-agent/logo.png"
    ]

    # Requirements:
    # Optional - max 20 Aspect ratio of horizontal (16:9), square (1:1),
    # or vertical (9:16); and greater than or equal to 10 seconds in duration
    video_asset_gcs_uris: list[str] = [
        "gs://co-op4all-deploy3-campaign-creator-agent/longer_video.mp4"
    ]

    # Signals
    search_theme: str = "travel"
    audience_id: str | None = None

    try:
        create_pmax_campaign(
            account_id,
            is_mcc,
            customer_id,
            business_name,
            logo_gcs_uri,
            brand_guidelines_enabled,
            final_urls,
            final_mobile_urls,
            budget,
            location_id_targeting,
            negative_location_id_targeting,
            language_id_targeting,
            headlines,
            descriptions,
            long_headlines,
            marketing_image_asset_gcs_uris,
            square_marketing_image_asset_gcs_uris,
            search_theme,
            audience_id,
            portrait_marketing_image_asset_gcs_uris,
            video_asset_gcs_uris,
        )
    except errors.GoogleAdsException as ex:
        print(
            f'Request with ID "{ex.request_id}" failed with status '
            f'"{ex.error.code().name}" and includes the following errors:'
        )
        for error in ex.failure.errors:
            print(f'Error with message "{error.message}".')
            if error.location:
                for field_path_element in error.location.field_path_elements:
                    print(f"\t\tOn field: {field_path_element.field_name}")
        sys.exit(1)
