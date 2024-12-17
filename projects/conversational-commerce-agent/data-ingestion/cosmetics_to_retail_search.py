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
Converting Cosmetic dataset to
Google Cloud Search for Retail data format.

Kaggle dataset:
https://www.kaggle.com/datasets/shivd24coder/cosmetic-brand-products-dataset
"""
import argparse
import json
import logging
import uuid

logging.basicConfig(level=logging.INFO)

def update_attributes(source_obj) -> dict:
    """
    Update site level attribute controls
    Args:
        source_obj: source product attribute controls
    Returns:
        dict: updated attribute controls
    """
    target_obj = {
        "attributes" : {}
    }
    colors = source_obj.get("product_colors", [])
    if colors is not None and colors != []:
        c = {
            "text": [
                color["colour_name"] for color in colors
                     if "colour_name" in color and
                        color["colour_name"] is not None and
                        color["colour_name"] != ""
            ]
        }
        if c["text"] != []:
            target_obj["attributes"]["Color"] = c
            target_obj["attributes"]["Color"]["searchable"] = True
            target_obj["attributes"]["Color"]["indexable"] = True

    if ("tag_list" in source_obj and
        source_obj["tag_list"] is not None and
        source_obj["tag_list"] != []):
        target_obj["attributes"]["Tags"] = {
            "text": source_obj.get("tag_list", [])
        }
        target_obj["attributes"]["Tags"]["searchable"] = True
        target_obj["Tags"] =  {
            "text": source_obj.get("tag_list", [])
        }
    return target_obj["attributes"]

def convert_flipkart_to_retail_search_product(
    input_file:str,
    output_file:str,
    project_number:str,
    branch:str="1") -> str:

    """
    Transforms a Flipkart JSONL file to
    Google Cloud Retail Search Product Schema.

    Args:
      input_file: Path to the input Flipkart JSONL file.
      output_file: Path to the output JSONL file.
      project_number: Google Cloud Project number.
      branch: Retail Search Branch Id. defaults to 1
    Returns:
      Path to the output JSONL file.
    """

    processed_products = ""
    with open(input_file, "r", encoding="utf-8") as infile:
        with open(output_file, "w", encoding="utf-8") as outfile:
            source_objs = json.load(infile)
            for source_obj in source_objs:
                try:
                    target_obj = {}

                    # Required fields
                    target_obj["title"] = source_obj.get(
                        "name", "Unknown Product"
                    )

                    if "product_link" not in source_obj:
                        logging.warning(
                            (
                                "[Warning]Product doed not"
                                "have a product url:%s"
                            ),
                            target_obj["title"]
                        )
                        continue
                    source_obj_brand = source_obj.get("brand")
                    if source_obj_brand == "":
                        logging.warning(
                            "[Warning]Product doed not have a brand:%s",
                            target_obj["title"]
                        )
                        source_obj_brand = "Unknown"

                    target_obj["brands"] = [
                        source_obj_brand
                    ]

                    if target_obj["title"] in processed_products:
                        continue
                    else:
                        processed_products += f"""|{target_obj["title"]}"""

                    subcatagory = source_obj.get("category", "")

                    if subcatagory is None or subcatagory == "":
                        subcatagory = source_obj.get("product_type")

                    catagory = (
                        f"""{source_obj.get("product_type")} >> """
                        f"{subcatagory}"
                    )
                    target_obj["categories"] = catagory
                    prod_id = uuid.uuid4()
                    target_obj["id"] = f"""{source_obj.get("id", prod_id)}"""
                    target_obj["name"] = (
                    f"projects/{project_number}/locations/global/catalogs/"
                    f"""default_catalog/branches/{branch}"""
                    f"""/products/{target_obj["id"]}"""
                    )
                    target_obj["primaryProductId"] = target_obj["id"]
                    target_obj["type"] = "PRIMARY"  # Assuming all are primary
                    target_obj["description"] = source_obj.get(
                            "description", {"description": ""}
                            )
                    target_desc = target_obj.get("description", "")
                    if target_desc is not None and len(target_desc) >= 5000:
                         # Max description
                        target_obj["description"] = target_desc[:5000]

                    target_obj["languageCode"] = "en-us" # Default language

                    source_image = source_obj.get("image_link", None)
                    if source_image is not None:
                        target_obj["images"] = [
                            {"uri": source_image}
                        ]
                    else:
                        logging.error(
                        "[Error]product does not have images:%s",
                        target_obj["title"])
                        continue

                    target_obj["uri"] = source_obj["product_link"]

                    # Price Information
                    item_price = 0
                    item_original_price = 0
                    if "prince" in source_obj:
                        item_price = float(source_obj.get("price", 0))
                    if source_obj.get("price") is not None:
                        item_original_price = float(
                            source_obj.get("price")
                        )
                    if item_price > 0 or item_original_price > 0:
                        target_obj["priceInfo"] = {
                            "currencyCode": "USD",
                            "price": item_price
                                if item_price > 0 else item_original_price,
                            "originalPrice": item_original_price,
                            "priceRange": {},
                        }

                    # Attributes
                    target_obj["attributes"] = update_attributes(source_obj)

                    # Availability
                    target_obj["availability"] = "IN_STOCK"
                    target_obj["availableQuantity"] = 0
                    target_obj["fulfillmentInfo"] = [
                        {
                            "type": "custom-type-1",
                            "placeIds": ["mobile", "www"]
                         }
                    ]
                    target_obj["retrievableFields"] = (
                        "name,title,brands,uri,categories,"
                        "priceInfo,description,attributes.Tags"
                        )

                    # For Promotion flow
                    if  source_obj.get("product_type", "") == "mascara":
                        if ("Tags" in target_obj["attributes"] and
                            target_obj["attributes"]["Tags"] is not None):
                            target_obj["attributes"]["Tags"]["text"].append(
                                "PromotionItem"
                            )

                    outfile.write(json.dumps(target_obj) + "\n")

                    # For Blend recommendation flow
                    if target_obj["id"] == "828":
                        target_obj["id"] = "99828"
                        target_obj["categories"] = "foundation >> blend"
                        target_obj["attributes"]["Tags"] = {
                            "text": ["Natural", "Gluten Free"],
                            "searchable": True
                        }
                        target_obj["primaryProductId"] = "99828"
                        outfile.write(json.dumps(target_obj) + "\n")
                except json.JSONDecodeError as e:
                    logging.error("""
======
* Error decoding JSON object in line:
Exception:%s
Line:%s}
======
""", e, source_obj)

    logging.info(
        "Successfully transformed %s to %s",
                 input_file,
                 output_file
        )
    return output_file

def prepare_arguments() -> dict:
    """
    Configure and parse commandline arguments.

    Returns:
        A Dict holds commandline arguments.
    """
    parser = argparse.ArgumentParser(
        description=("Converting Flipkart dataset "
                     "to Search for Retail data format.")
    )
    parser.add_argument("-i", "--input",
                        help="Flipkart JSON file path.",
                        required=True)
    parser.add_argument("-o", "--output",
                        help="Search for Retail Jsonl file path.",
                        required=True)
    parser.add_argument("-p", "--project-number",
                        help="Search for Retail Jsonl file path.",
                        required=True)
    parser.add_argument("-b", "--branch",
                        help="Search for Retail Jsonl file path.",
                        required=True)
    args = vars(parser.parse_args())
    return {
        "input_file": args["input"],
        "output_file": args["output"],
        "project_number": args["project_number"],
        "branch": args["branch"]
    }

if __name__ == "__main__":
    params = prepare_arguments()

    FLIPKART_JSON_FILE = params["input_file"]
    RETAIL_SEARCH_JSON_FILE = params["output_file"]
    PROJECT_NUMBER = params["project_number"]
    BRANCH = params["branch"]

    convert_flipkart_to_retail_search_product(
        input_file=FLIPKART_JSON_FILE,
        output_file=RETAIL_SEARCH_JSON_FILE,
        project_number=PROJECT_NUMBER,
        branch=BRANCH)
