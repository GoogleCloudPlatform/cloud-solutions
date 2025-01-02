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
Converting Flipkart dataset to
Google Cloud Search for Retail data format.
"""
import argparse
import csv
import json
import logging
import os
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

    item_name = source_obj["menuItemName"].lower()
    item_desc = source_obj["menuItemDescription"].lower()

    if ("vegan" in item_name or
        "vegan" in item_desc):
        target_obj["attributes"]["Vegan"] = {
            "text": ["yes"],
            "searchable": True,
            "indexable": True
        }
    else:
        target_obj["attributes"]["Vegan"] = {
            "text": ["no"],
            "searchable": True,
            "indexable": True
        }
    grill_items = ["chicken",
                   "beef",
                   "pork",
                   "seafood",
                   "fish",
                   "shrimp",
                   "duck",
                   "steak"]
    # any(item in string for item in array)
    if (any(item in item_name for item in grill_items) or
        any(item in item_desc for item in grill_items)):
        target_obj["attributes"]["Tags"] = {
            "text": ["grill"],
            "searchable": True,
            "indexable": True
        }
    if ("gluten free" in item_name.replace("-", " ") or
        "gluten free" in item_desc.replace("-", " ")):
        if target_obj["attributes"].get("Tags", None) is not None:
            target_obj["attributes"]["Tags"]["text"].append("gluten free")
        else:
            target_obj["attributes"]["Tags"] = {
                "text": ["gluten free"],
                "searchable": True,
                "indexable": True
            }

    return target_obj["attributes"]

def convert_csv_to_jsonl(input_file:str, output_file:str) -> str:
    """
    This function does a one-to-one mapping from CSV to Json

    Args:
      input_file: Path to the input CSV file.
      output_file: Path to the output JSONL file.

    Returns:
      Path to the output JSONL file.
    """

    with open(input_file, "r", encoding="utf-8") as csvfile, \
         open(output_file, "w", encoding="utf-8") as jsonlfile:
        input_data = csvfile.read().replace("\\\"", "").replace("\\", "")
        reader = csv.reader(input_data.split(os.linesep))
        header = next(reader)

        for row in reader:
            # Escape special characters in each field
            escaped_row = [
                value.replace("\\\"", "").replace("\\", "")
                for value in row
            ]
            row_dict = dict(zip(header, escaped_row))

            jsonlfile.write(json.dumps(row_dict) + os.linesep)
    return output_file

def convert_food_to_retail_search_product(
    input_file:str,
    output_file:str,
    project_number:str,
    branch:str="0") -> str:

    """
    Transforms a Flipkart JSONL file to
    Google Cloud Retail Search Product Schema.

    Args:
      input_file: Path to the input Flipkart JSONL file.
      output_file: Path to the output JSONL file.
      project_number: Google Cloud Project number.
      branch: Retail Search Branch Id. defaults to 0
    Returns:
      Path to the output JSONL file.
    """

    processed_products = ""
    with open(input_file, "r", encoding="utf-8") as infile:
        with open(output_file, "w", encoding="utf-8") as outfile:
            for line in infile:
                try:
                    source_obj = json.loads(line)
                    target_obj = {}

                    # Required fields
                    target_obj["title"] = source_obj.get(
                        "menuItemName", "Unknown Product"
                    )

                    if "menuItemImageUrl" not in source_obj:
                        logging.warning(
                            (
                                "[Warning]Product doed not"
                                "have a product url:%s"
                            ),
                            target_obj["title"]
                        )
                        continue

                    if target_obj["title"] in processed_products:
                        continue
                    else:
                        processed_products += f"""|{target_obj["title"]}"""

                    target_obj["categories"] = [source_obj["menuItemCategory"]]

                    target_obj["id"] = f"{uuid.uuid4()}"
                    target_obj["name"] = (
                    f"projects/{project_number}/locations/global/catalogs/"
                    f"""default_catalog/branches/{branch}"""
                    f"""/products/{target_obj["id"]}"""
                    )
                    target_obj["primaryProductId"] = target_obj["id"]
                    target_obj["type"] = "PRIMARY"  # Assuming all are primary

                    target_obj["description"] = source_obj.get(
                                "menuItemDescription", target_obj["title"]
                            )
                    if target_obj["description"] == target_obj["title"]:
                        print(f"""{target_obj["title"]} has no description.""")

                    target_desc = target_obj["description"]
                    if len(target_desc) >= 5000: # Max description
                        target_obj["description"] = target_desc[:5000]

                    target_obj["languageCode"] = "en-us" # Default language

                    source_images = source_obj["menuItemImageUrl"]
                    if source_images:
                        target_obj["images"] = [
                            {"uri": source_images}
                        ]
                    else:
                        logging.error(
                        "[Error]product does not have images:%s",
                        target_obj["title"],)
                        continue

                    target_obj["uri"] = source_obj.get("menuItemImageUrl", None)

                    # Price Information
                    source_obj["discounted_price"]= 0
                    source_obj["retail_price"]= 0
                    try:
                        item_price = float(
                            source_obj.get(
                                "menuItemCurrentPrice",
                                "0").replace("$", "")
                            )
                        target_obj["priceInfo"] = {
                            "currencyCode": "INR",
                            "price": item_price,
                            "originalPrice": item_price,
                            "priceRange": {},
                        }
                    except ValueError as e:
                        print(source_obj.get(
                                "menuItemCurrentPrice",
                                "0").replace("$", "")
                            )
                        logging.error(e)
                        logging.error("Unable to parse price for %s",
                                    target_obj["title"])
                        continue

                    target_obj["attributes"] = update_attributes(
                        source_obj=source_obj
                    )

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
                        "priceInfo,description"
                        )
                    outfile.write(json.dumps(target_obj) + "\n")

                except json.JSONDecodeError as e:
                    logging.error("""
======
* Error decoding JSON object in line:
Exception:%s
Line:%s}
======
""", e, line.strip())

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
                        help="Flipkart CSV file path.",
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

    FLIPKART_CSV_FILE = params["input_file"]
    FLIPKART_JSON_FILE = params["input_file"] + ".jsonl"

    RETAIL_SEARCH_JSON_FILE = params["output_file"]
    PROJECT_NUMBER = params["project_number"]
    BRANCH = params["branch"]

    convert_csv_to_jsonl(
        input_file=FLIPKART_CSV_FILE,
        output_file=FLIPKART_JSON_FILE
    )

    convert_food_to_retail_search_product(
        input_file=FLIPKART_JSON_FILE,
        output_file=RETAIL_SEARCH_JSON_FILE,
        project_number=PROJECT_NUMBER,
        branch=BRANCH)
