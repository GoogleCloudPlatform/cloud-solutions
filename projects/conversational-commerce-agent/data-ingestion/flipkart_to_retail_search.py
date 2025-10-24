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
import re

import requests

logging.basicConfig(level=logging.INFO)

def convert_csv_to_jsonl(input_file:str, output_file:str) -> str:
    """
    This function does a one-to-one mapping from CSV to Json

    Args:
      input_file: Path to the input CSV file.
      output_file: Path to the output JSONL file.

    Returns:
      Path to the output JSONL file.
    """
    csvfile = open(input_file, "r",
                   encoding="utf-8")
    jsonfile = open(output_file, "w",
                    encoding="utf-8")
    # Remove \n in the end
    headers = csvfile.readline().replace(os.linesep, "").split(",")
    reader = csv.DictReader(csvfile, headers)
    for row in reader:
        json.dump(row, jsonfile)
        jsonfile.write(os.linesep)

    return output_file

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
    if "product_specifications" in source_obj:
        source_prod_specs = source_obj["product_specifications"]
        try:
            source_prod_specs = source_prod_specs.replace(
                    "=>nil", ":null"
                )
            source_prod_specs = source_prod_specs.replace(
                    "=>", ":"
                )
            specs = json.loads(
                source_prod_specs
            )
        except json.JSONDecodeError:
            logging.warning(
                ("[Warning]Could not decode "
                "product_specifications: %s"),
                source_obj
            )
            return {}

        if specs.get("product_specification") is None:
            return {}

        for attr in specs["product_specification"]:
            target_attrs = target_obj["attributes"]
            try:
                if not isinstance(attr, dict):
                    continue

                attr_key = ""
                attr_value = ""
                if "key" in attr:
                    logging.info("* processing: %s", attr)
                    attr_key = attr["key"]
                    attr_value = attr.get("value", "")

                if (attr_value == "" or
                    attr_key == ""):
                    continue

                target_attrs[attr_key] = {
                    "text": [attr_value]
                }
                if attr_key == "Type":
                    target_attrs[attr_key]["searchable"] = True
                    target_attrs[attr_key]["indexable"] = True
                elif not re.search(r"[ \-/\\]", attr_key):
                    target_attrs[attr_key]["searchable"] = True
                    target_attrs[attr_key]["indexable"] = True
            except KeyError as e:
                logging.error("[Error]%s", e)
                logging.error("* Attribute:%s", attr)
    else:
        logging.error("Product Spec not found.")
    return target_attrs

def replace_domain_host(
    url:str,
    new_domain:str) -> str:
    """Replaces the domain name of a given URL.

    Args:
        url: The URL to modify.
        new_domain: The new domain name to use.

    Returns:
        The modified URL with the new domain name.
    """

    try:
        start = url.index("//") + 2
        end = url.find("/", start)
        return f"""{url[:start]}{new_domain}{url[end:]}"""
    except ValueError:
        # Return original url if errors
        return url

def convert_flipkart_to_retail_search_product(
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
                        "product_name", "Unknown Product"
                    )

                    if "product_url" not in source_obj:
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

                    target_obj["categories"] = (
                        json.loads(source_obj["product_category_tree"])
                        if "product_category_tree" in source_obj
                        else ["Unknown"]
                    )
                    target_obj["id"] = source_obj["uniq_id"]
                    target_obj["name"] = (
                    f"projects/{project_number}/locations/global/catalogs/"
                    f"""default_catalog/branches/{branch}"""
                    f"""/products/{target_obj["id"]}"""
                    )
                    target_obj["primaryProductId"] = target_obj["id"]
                    target_obj["type"] = "PRIMARY"  # Assuming all are primary

                    target_obj["description"] = source_obj.get(
                                                "description", ""
                                                )
                    target_desc = target_obj["description"]
                    if len(target_desc) >= 5000: # Max description
                        target_obj["description"] = target_desc[:5000]

                    target_obj["languageCode"] = "en-us" # Default language

                    source_images = source_obj.get("image", None)
                    if source_images is not None:
                        target_obj["images"] = [
                            {"uri": img}
                            for img in json.loads(source_images)
                            if "image" in source_obj
                        ]

                        # Use the images on the shared GCS bucket.
                        for image_url in target_obj["images"]:
                            new_url = replace_domain_host(
                                url=image_url["uri"],
                                new_domain=(
                                    "storage.googleapis.com/"
                                    "gcp-retail-demo")
                                )
                            image_url["uri"] = new_url

                            continue
                    else:
                        logging.error(
                        "[Error]product does not have images:%s",
                        target_obj["title"])
                        continue

                    target_obj["uri"] = source_obj["product_url"]

                    # Price Information
                    if source_obj["discounted_price"] == "":
                        source_obj["discounted_price"]= 0
                    if source_obj["retail_price"] == "":
                        source_obj["retail_price"]= 0
                    item_price = float(source_obj.get("discounted_price", 0))
                    item_original_price = float(
                        source_obj.get("retail_price", 0)
                    )
                    target_obj["priceInfo"] = {
                        "currencyCode": "INR", # Replace with actual currency
                        "price": item_price,
                        "originalPrice": item_original_price,
                        "priceRange": {},
                    }
                    for image in target_obj["images"]:
                        if "height" in image:
                            del image["height"]
                        if "width" in image:
                            del image["width"]

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

def check_existense(url:str) -> bool:
    """
    Check if an URL exists.

    Args:
      url: An Flipkart product image URL.
    Returns:
      True if the image exists, otherwise False
    """
    headers = {"User-Agent": "Mozilla/5.0", "accept-language": "en-US,en"}
    try:
        response = requests.get(url, headers=headers, timeout=1)

        # The server returns HTTP 200 with `Error 404 Not Found`
        # in the payload when the image is not available.
        # Hence checking for text instead of HTTP status code
        return False if "Error 404 Not Found" in response.text else True
    except requests.exceptions.RequestException as err:
        logging.error("[HttpError]%s", err)
        return False
    except requests.exceptions.HTTPError as e:
        logging.error("[HttpError]%s}", e)
        return False

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

    convert_flipkart_to_retail_search_product(
        input_file=FLIPKART_JSON_FILE,
        output_file=RETAIL_SEARCH_JSON_FILE,
        project_number=PROJECT_NUMBER,
        branch=BRANCH)
