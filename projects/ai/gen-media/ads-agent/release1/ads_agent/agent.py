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


# pylint: disable=C0301, W0718, W1203
"""Agent definition for the Google Ads Campaigns Practitioner."""

import json
import logging
import os

import google.cloud.logging as gcp_logging
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.tool_context import ToolContext
from google.ads.googleads import errors
from google.genai import types

try:
    from . import utils
    from .models import agent_models
    from .services import google_ads_api_service_pmax
    from .targeting_config import targeting_lookup
except (ImportError, ValueError) as ex:
    import utils
    from models import agent_models
    from services import google_ads_api_service_pmax
    from targeting_config import targeting_lookup


# Attach the Cloud Logging handler to the Python root logger
try:
    logging_client = gcp_logging.Client(project=os.environ.get("GOOGLE_CLOUD_PROJECT"))
    logging_client.setup_logging()
except Exception:
    logging.basicConfig(level=logging.INFO)


def create_pmax_campaign(
    account_id: str,
    is_mcc: bool,
    customer_id: str,
    business_name: str,
    logo_uri: str,
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
):
    """Creates a Performance Max (PMAX) campaign in Google Ads using the provided configuration and assets.

    Args:
        account_id: The login customer ID for the Google Ads account.
        is_mcc: Whether the account_id refers to a Manager (MCC) account.
        customer_id: The target customer ID where the campaign will be created.
        business_name: The name of the business for the campaign.
        logo_uri: URI for the business logo asset.
        brand_guidelines_enabled: Whether to enable brand guidelines for the campaign.
        final_urls: List of final URLs (landing pages) for the campaign.
        final_mobile_urls: List of final mobile URLs.
        location_id_targeting: Comma-separated string of numeric location IDs to target.
        negative_location_id_targeting: Comma-separated string of numeric location IDs to exclude.
        language_id_targeting: Com_a-separated string of numeric language IDs to target.
        headlines: List of headlines (3 to 15, max 30 characters each).
        descriptions: List of descriptions (2 to 5, max 90 characters each).
        long_headlines: List of long headlines (1 to 5, max 90 characters each).
        marketing_image_asset_gcs_uris: List of URIs for the main marketing image assets.
        square_marketing_image_asset_gcs_uris: List of URIs for the square marketing image assets.
        search_theme: A string representing key phrases for search theme signals.
        audience_id: Optional numeric ID of an existing audience to target.
        portrait_marketing_image_asset_gcs_uris: Optional list of URIs for the portrait marketing image assets.
        video_asset_gcs_uris: Optional list of GCS URIs for the video assets (e.g., gs://bucket/video.mp4).

    Returns:
        A dictionary containing the status ("SUCCESS" or "ERROR") and the service response or error message.
    """
    try:
        # Resize images if needed, it's only required for 16:9, 1.91/1, 9:16, 4:5

        # Landscape: 1.91:1 (1.91/1)
        marketing_image_asset_gcs_uris = utils.resize_images(
            uris=marketing_image_asset_gcs_uris,
            target_width=1200,
            target_ratio=(1.91 / 1),
        )

        # Portrait: 4:5 (4/5)
        if portrait_marketing_image_asset_gcs_uris:
            portrait_marketing_image_asset_gcs_uris = utils.resize_images(
                uris=portrait_marketing_image_asset_gcs_uris,
                target_width=960,
                target_ratio=(4 / 5),
            )

        response = google_ads_api_service_pmax.create_pmax_campaign(
            account_id,
            is_mcc,
            customer_id,
            business_name,
            logo_uri,
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

        logging.info(
            "SUCCESS - The PMAX campaign was created successfully for customer ID %s",
            customer_id,
        )
        logging.info("Campaign Details: %s", response)

        return {
            "status": "SUCCESS",
            "response": (
                f"SUCCESS - The PMAX campaign was created successfully for customer ID {customer_id}.",
                f"Campaign Details {response}"
                "Please review it directly in the Google Ads platform.",
            ),
        }
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

        return {
            "status": "ERROR",
            "response": str(ex),
        }

    except Exception as ex:
        logging.error("ERROR: %s", str(ex))

        return {
            "status": "ERROR",
            "response": str(ex),
        }


async def init_targeting_config(callback_context: CallbackContext):
    """Saves targeting configurations as artifacts for the agent.

    Args:
        context: The callback context for saving artifacts.
    """
    logging.info("CALLBACK: init_targeting_config called.")
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Save Geotargets
    geotargets_path = os.path.join(current_dir, "targeting_config", "geotargets.json")
    if os.path.exists(geotargets_path):
        with open(geotargets_path, "rb") as f:
            geotargets_bytes = f.read()
        artifact = types.Part.from_bytes(
            data=geotargets_bytes, mime_type="application/json"
        )
        await callback_context.save_artifact(
            filename="geotargets.json", artifact=artifact
        )
        logging.info("Geotargets saved as artifact.")

    # Save Language Codes
    languages_path = os.path.join(current_dir, "targeting_config", "languagecodes.json")
    if os.path.exists(languages_path):
        with open(languages_path, "rb") as f:
            languages_bytes = f.read()
        artifact = types.Part.from_bytes(
            data=languages_bytes, mime_type="application/json"
        )
        await callback_context.save_artifact(
            filename="languagecodes.json", artifact=artifact
        )
        logging.info("Language codes saved as artifact.")


async def resolve_location_id_from_context(
    location_name: str, tool_context: ToolContext
):
    """Resolves a location name using data from context artifacts.

    Args:
        location_name: The name of the location to resolve.
        context: The context for loading artifacts.

    Returns:
        The numeric ID as a string.
    """
    logging.info(
        "TOOL: resolve_location_id_from_context called with name: %s", location_name
    )
    try:
        artifact = await tool_context.load_artifact("geotargets.json")
        if artifact and artifact.inline_data and artifact.inline_data.data:
            geotargets_dict = json.loads(artifact.inline_data.data)
            result = targeting_lookup.TargetingLookupTool.search_in_dict(
                geotargets_dict, location_name, "Criteria ID"
            )
            if "id" in result:
                logging.info(
                    "SUCCESS: Resolved %s to ID %s", location_name, result["id"]
                )
                return result["id"]
            else:
                # Default to US
                return "2840"
    except Exception as e:
        logging.error(f"Error loading geotargets artifact: {e}")
    return ""


async def resolve_language_id_from_context(
    language_name: str, tool_context: ToolContext
):
    """Resolves a language name using data from context artifacts.

    Args:
        language_name: The name of the language to resolve.
        context: The context for loading artifacts.

    Returns:
        The numeric ID as a string.
    """
    logging.info(
        "TOOL: resolve_language_id_from_context called with name: %s", language_name
    )
    try:
        artifact = await tool_context.load_artifact("languagecodes.json")
        if artifact and artifact.inline_data and artifact.inline_data.data:
            languages_dict = json.loads(artifact.inline_data.data)
            result = targeting_lookup.TargetingLookupTool.search_in_dict(
                languages_dict, language_name, "Criterion ID"
            )
            if "id" in result:
                logging.info(
                    "SUCCESS: Resolved %s to ID %s", language_name, result["id"]
                )
                return result["id"]
            else:
                # Default to English
                return "1000"
    except Exception as e:
        logging.error(f"Error loading languagecodes artifact: {e}")
    return ""


root_agent = Agent(
    name="google_ads_practitioner_agent",
    model="gemini-2.5-flash",
    description=(
        """You are a Google Ads Campaign Practitioner and specialized AI assistant designed to streamline
        the creation of campaigns in Google Ads (Performance Max (PMAX), Search, DemandGen etc.) using the API.
        Youe leverage your deep knowledge of Google Ads campaign structures, asset requirements,
        and targeting options to guide users through the complex process of setting up effective campaigns.
        """
    ),
    instruction=(
        """You are an expert Google Ads campaign practitioner specialized in Google Ads campaigns
        (Performance Max (PMAX), Search, DemandGen etc.).
        Your primary goal is to help users create high-performing campaigns by meticulously collecting all
        necessary configuration details and assets, then executing the campaign creation tool.

        Greet the user the first time with: "I am your Google Ads Campaign Practitioner. I can help you
        create and manage Google Ads campaigns to maximize your reach across all of Google's channels.
        Let's get started by setting up your new campaign."

        Instructions:
        - You only support the creation of PMAX campaigns for now. Other type of campaigns support is coming soon.
        - **Strict Requirement**: If the user provides a location name string (e.g., "New York") instead of a numeric ID,
          you MUST use the 'resolve_location_id_from_context' tool to resolve it to its numeric Criteria ID before calling
          any 'create_*_campaign' functions.
        - **Strict Requirement**: If the user provides a language name string (e.g., "English") instead of a numeric ID,
        you MUST use the 'resolve_language_id_from_context' tool to resolve it to its numeric Criterion ID before calling
        any 'create_*_campaign' functions.
        - Whenever you have ALL the required parameters, show a summary to the user and ALWAYS CONFIRM before calling
        any 'create_*_campaign' functions.
        - Provided assets live in Google Cloud Storage, so GCS URLs are totally valid.

        Detailed Workflow for the creation of a PMAX campaigns:
        1. **Account Context**: First, identify the account hierarchy. Ask for the 'account_id' (the login ID)
           and whether it's an MCC (Manager) account. Confirm the target 'customer_id' where the campaign will reside.
        2. **Campaign Foundation**: Collect the 'business_name' and a 'logo_uri'. Ask the user if
           'brand_guidelines_enabled' should be active for this campaign.
        3. **Targeting & Reach**:
           - **Budget**: Request a daily 'budget' (numeric value in the account's currency).
           - **URLs**: Request 'final_urls' (the main landing pages where users are directed after clicking the ad) and 'final_mobile_urls' (optional landing pages optimized for mobile).
           - **Geography**: Ask for 'location_id_targeting' (positive targets) and 'negative_location_id_targeting' (exclusions). If names are provided, resolve them to IDs first.
           - **Language**: Confirm the 'language_id_targeting' (e.g., '1000' for English). If a language name is provided, resolve it to an ID first.
        4. **Asset Assembly**: PMAX relies heavily on asset variety. Request the following from the user, ensuring they meet the requirements:
           - **Text Assets**:
             - **Headlines**: 3 to 15 headlines (max 30 characters each).
             - **Descriptions**: 2 to 5 descriptions (max 90 characters each).
             - **Long Headlines**: 1 to 5 long headlines (max 90 characters each).
           - **Image Assets**:
             - **Marketing Images**: 1 to 20 landscape GCS URIs (1.91:1 ratio).
             - **Square Marketing Images**: 1 to 20 square GCS URIs (1:1 ratio).
             - **Portrait Marketing Images**: Optional 1 to 20 portrait GCS URIs (4:5 ratio).
           - **Video Assets**:
             - **Videos**: Optional 1 to 20 video GCS URIs (gs://bucket/video.mp4).
        5. **Signals**: Ask for a 'search_theme' (key phrases) and an optional 'audience_id' to help Google's AI find the right customers.
        6. **Verification & Launch**: Once all data is gathered, summarize it for the user and call the
           'create_pmax_campaign' tool to execute the creation.

        Always ensure that URLs are valid and assets meet the length requirements. If assets are missing,
        advise the user on the benefits of providing a full set of creatives for better ad rotation and performance.
        """
    ),
    generate_content_config=types.GenerateContentConfig(
        temperature=0.5,
        top_p=0.95,
        seed=0,
        max_output_tokens=65535,
        response_modalities=["TEXT"],
        safety_settings=[
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"
            ),
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
        ],
    ),
    tools=[
        create_pmax_campaign,
        resolve_location_id_from_context,
        resolve_language_id_from_context,
    ],
    before_agent_callback=init_targeting_config,
    output_schema=agent_models.ADKAgentInvocationResponse,
)
