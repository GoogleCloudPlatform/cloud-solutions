# Copyright 2024 Google LLC
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

"""
Update Search for Retail product attribute configurations.
"""

import argparse
import logging

from collections.abc import MutableMapping
from google.cloud import retail_v2
from google.cloud.retail_v2.types import AttributesConfig, CatalogAttribute

logging.basicConfig(level=logging.INFO)

def prepare_arguments() -> dict:
    """
    Configure and parse commandline arguments.

    Returns:
        A Dict holds commandline arguments.
    """
    parser = argparse.ArgumentParser(
        description=("Converting Flipkart dataset to"
            "Search for Retail data format.")
    )
    parser.add_argument("-n",
                        "--project-number",
                        help="Search for Retail Project number.",
                        required=True)
    args = vars(parser.parse_args())
    return {
        "project_number": args["project_number"]
    }

def get_attributes_config(
        project_number:str
    ) ->MutableMapping[str, CatalogAttribute]:
    """
    Get existing product attribute configurations.

    Args:
        project_number (str): Google Cloud Project number.
    Returns:
        A Dict holds product attribute configurations.
    """
    # Create a client
    client = retail_v2.CatalogServiceClient()
    request = retail_v2.GetAttributesConfigRequest(
            name=(f"projects/{project_number}/locations/global/"
                "catalogs/default_catalog/attributesConfig")
        )
    # Make the request
    response = client.get_attributes_config(request=request)

    return response.catalog_attributes

def update_catalog_attribute(project_number:str,
            attributes:MutableMapping[str, CatalogAttribute]):
    """
    Update the catalog attributes.

    Args:
        project_number (str): Google Cloud Project number.
        attributes (MutableMapping[str, CatalogAttribute]): Product attributes.
    Returns:
        None
    """
    # Create a client
    client = retail_v2.CatalogServiceClient()

    # Initialize request argument(s)
    attributes_config = AttributesConfig() # retail_v2.AttributesConfig()
    attributes_config.name = (f"projects/{project_number}/locations/global"
        "/catalogs/default_catalog/attributesConfig")
    attributes_config.catalog_attributes = attributes

    request = retail_v2.UpdateAttributesConfigRequest(
        attributes_config=attributes_config,
    )

    # Make the request
    response = client.update_attributes_config(request=request)

    # Handle the response
    logging.info(response)

def get_default_serving_configs(project_number:str) -> any:
    """
    Get the default serving config.

    Args:
        project_number (str): Google Cloud Project number.
    Returns:
        A ServingConfig object.
    """
    # Create a client
    client = retail_v2.ServingConfigServiceClient()

    # Initialize request argument(s)
    request = retail_v2.ListServingConfigsRequest(
        parent=(f"projects/{project_number}/locations/global"
            "/catalogs/default_catalog")
    )

    # Make the request
    page_result = client.list_serving_configs(request=request)

    # Handle the response
    for response in page_result:
        if response.display_name == "default_search":
            return response

    return None

def update_serving_config(serving_config:retail_v2.ServingConfig):
    """
    Update the serving config.

    Args:
        serving_config (retail_v2.ServingConfig): Serving config object.
    Returns:
        None
    """
    # Create a client
    client = retail_v2.ServingConfigServiceClient()

    serving_config.dynamic_facet_spec = (
        retail_v2.types.SearchRequest.DynamicFacetSpec(
            mode=retail_v2.types.SearchRequest.DynamicFacetSpec.Mode(
                retail_v2.types.SearchRequest.DynamicFacetSpec.Mode.ENABLED
            )
        )
    )
    request = retail_v2.UpdateServingConfigRequest(
        serving_config=serving_config,
    )

    # Make the request
    response = client.update_serving_config(request=request)
    logging.info(response)

if __name__ == "__main__":
    params = prepare_arguments()
    gcp_project_number = params["project_number"]

    attr_cfg = get_attributes_config(project_number=gcp_project_number)

    # Make these attributes retrievable.
    RETRIEVABLE_ATTRIBUTES = [
            "ageGroups",
            "attributes.Occasion",
            "brands",
            "categories",
            "colorFamilies",
            "conditions",
            "description",
            "materials",
            "patterns",
            "sizes",
            "title",
            "attributes.offer",
            "availability",
            "colors",
            "discount",
            "price",
            "cost",
            "currencyCode",
            "images",
            "attributes.Tags"
        ]

    # Make these attributes not searchable.
    NON_SEARCHABLE_ATTRIBUTES = [
        "price",
        "cost",
        "availability",
        "discount",
        "currencyCode",
        "images",
        "colors"
    ]
    SEARCH_ABLE_ATTRIBUTES = [
        "ageGroups",
        "occasion",
        "brands",
        "categories",
        "colorFamilies",
        "conditions",
        "description",
        "materials"
        "patterns",
        "sizes",
        "title",
        "fabric",
        "Type",
        "Fabric",
        "Ideal for",
        "attributes.Fabric",
        "type",
        "attributes.Type",
        "attributes.Ideal For",
        "attributes.Tags"
    ]
    # The update attribute config API takes <1000 attributes per API call.
    # We first fetch all attributes then updates only required attributes.
    updates = {}
    for key in attr_cfg.keys():
        if key in RETRIEVABLE_ATTRIBUTES:
            attr_cfg[key].retrievable_option = (
                CatalogAttribute.RetrievableOption(
                    CatalogAttribute.RetrievableOption.RETRIEVABLE_ENABLED)
            )
            if key in NON_SEARCHABLE_ATTRIBUTES:
                attr_cfg[key].searchable_option = (
                    CatalogAttribute.SearchableOption(
                        CatalogAttribute.SearchableOption.SEARCHABLE_DISABLED)
                )
            updates[key] = attr_cfg[key]

        if key in SEARCH_ABLE_ATTRIBUTES:
            attr_cfg[key].searchable_option = (
                CatalogAttribute.SearchableOption(
                    CatalogAttribute.SearchableOption.SEARCHABLE_ENABLED)
            )
            updates[key] = attr_cfg[key]
    update_catalog_attribute(
        project_number=gcp_project_number,
        attributes=updates,
    )
    default_config = get_default_serving_configs(
                project_number=gcp_project_number
            )
    update_serving_config(serving_config=default_config)
