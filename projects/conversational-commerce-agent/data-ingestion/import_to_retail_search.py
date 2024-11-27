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
Importing converted Flipkart dataset
to Google Cloud Search for Retail.
"""

import argparse
import logging
import os
import time

from google.cloud import retail_v2, storage
from google.cloud.retail_v2.types import GcsSource, ImportErrorsConfig as ErrorsConfig

logging.basicConfig(level=logging.INFO)

def split_jsonl(input_file:str,
                output_prefix:str,
                max_lines:int=500) -> list[str]:
    """
    Splits a large JSONL file into smaller files.

    Args:
        input_file: Path to the input JSONL file.
        output_prefix: Prefix for the output files (e.g., 'output_').
        max_lines: Maximum number of lines per output file.
    Returns:
        List of output file names.
    """

    file_names = []
    folder = os.path.dirname(input_file)

    with open(input_file, "r", encoding="utf-8") as infile:
        lines = infile.readlines()
        chunks = [
            lines[i:i + max_lines]
            for i in range(0, len(lines), max_lines)
        ]
        for index, chunk in enumerate(chunks):
            fn = f"{folder}/{output_prefix}{index}.jsonl"
            file_names.append(fn)
            with open(fn, "w", encoding="utf-8") as f:
                f.write("".join(chunk))
    return file_names

def upload_dataset_to_gcs(
    gcs_bucket:str,
    project_id:str,
    input_file:str) -> list[str]:
    """
    Upload Search for Retail dataset file to GCS bucket.

    Args:
        gcs_bucket (str): Target GCS Bucket name.
        project_id (str): Google Cloud Project ID.
        input_file (str): File to be uploaded.
    Returns:
        GCS URL of the uploaded file.
    """
    files = split_jsonl(
        input_file=input_file,
        output_prefix="flipkart-retail-search-"
    )
    client = storage.Client(project=project_id)
    bucket = client.get_bucket(gcs_bucket)

    gcs = []
    for file in files:
        fn = file.split("/")[-1]
        blob = bucket.blob(fn)
        blob.upload_from_filename(file)
        gcs.append(f"gs://{gcs_bucket}/{fn}")

    return gcs

def set_default_branch(project_number:str, branch:str="0"):
    """
    Set the default branch of the Search for Retail service.

    Args:
        project_number (str): Google Cloud Project number.
        branch (str): Branch ID. Must be one of 0,1,2.
    """
    client = retail_v2.CatalogServiceClient()

    request = retail_v2.SetDefaultBranchRequest(
        catalog=f"projects/{project_number}/locations/global/" + \
            "catalogs/default_catalog",
        branch_id=branch
    )
    client.set_default_branch(request=request)


def update_product_level():
    """
    Set the default branch of the Search for Retail service.

    Args:
        project_number (str): Google Cloud Project number.
        branch (str): Branch ID. Must be one of 0,1,2.
    """
    # Update Product Level before importing data
    # https://cloud.google.com/retail/docs/upload-catalog#json
    client = retail_v2.CatalogServiceClient()
    catalog = retail_v2.Catalog()
    catalog.name = "default_catalog"
    catalog.display_name = "default_catalog"
    catalog.product_level_config = retail_v2.types.ProductLevelConfig(
    )
    request = retail_v2.UpdateCatalogRequest(
        catalog=catalog,
    )
    response = client.update_catalog(request=request)
    logging.info("Update Catalog: %s", response)

def prepare_arguments() -> dict:
    """
    Configure and parse commandline arguments.

    Returns:
        A Dict holds commandline arguments.
    """
    parser = argparse.ArgumentParser(
        description="Converting Flipkart dataset to " + \
            "Search for Retail data format."
    )
    parser.add_argument("-i",
                        "--input",
                        help="Search for Retail data file path.",
                        required=True)
    parser.add_argument("-g", "--gcs-bucket",
                        help="Search for Retail import GCS bucket name.",
                        required=True)
    parser.add_argument("-n", "--project-number",
                        help="Search for Retail Project number.",
                        required=True)
    parser.add_argument("-b", "--branch",
                        help="Search for Retail Branch.",
                        required=True)
    parser.add_argument("--set-default-branch",
                        dest="set_default_branch",
                        action="store_true")
    parser.add_argument("--no-set-default-branch",
                        dest="set_default_branch",
                        action="store_false")
    parser.set_defaults(set_default_branch=False)

    args = vars(parser.parse_args())
    return {
        "input_file": args["input"],
        "gcs_bucket": args["gcs_bucket"],
        "project_number": args["project_number"],
        "branch": args["branch"],
        "set_default_branch": args["set_default_branch"]
    }

def import_products(gcs_errors_path:str,
                    gcs_url:str,
                    project_number:str,
                    branch:str) -> None:
    """
    Import products to Search for Retail.

    Args:
        gcs_errors_path (str): GCS path to store import errors.
        gcs_url (str): GCS URL of the input file.
        project_number (str): Google Cloud Project number.
        branch (str): Retail Search Branch Id.
    """
    # Create a client
    client = retail_v2.ProductServiceClient()

    # Initialize request argument(s)
    input_config = retail_v2.ProductInputConfig(
        gcs_source=GcsSource(input_uris=[gcs_url])
    )

    request = retail_v2.ImportProductsRequest(
        parent=(f"projects/{project_number}/locations/global/"
            f"catalogs/default_catalog/branches/{branch}"),
        input_config=input_config,
        errors_config=ErrorsConfig(gcs_prefix=gcs_errors_path)
    )

    # Make the request
    operation = client.import_products(request=request)
    response = operation.result()

    logging.info(response)


if __name__ == "__main__":
    params = prepare_arguments()

    if params["set_default_branch"]:
        set_default_branch(params["project_number"],
                           params["branch"])

    gcs_files = upload_dataset_to_gcs(
        params["gcs_bucket"],
        params["project_number"],
        params["input_file"])

    for gcs_file in gcs_files:
        logging.info("* Processing %s", gcs_file)
        import_products(
            gcs_errors_path=f"""gs://{params["gcs_bucket"]}/errors""",
            gcs_url=gcs_file,
            project_number=params["project_number"],
            branch=params["branch"])
        time.sleep(2)

