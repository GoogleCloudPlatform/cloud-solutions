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

from google.cloud import retail_v2, storage
from google.cloud.retail_v2.types import GcsSource, ImportErrorsConfig as ErrorsConfig

logging.basicConfig(level=logging.INFO)

def upload_dataset_to_gsc(
    gcs_bucket:str,
    project_id:str,
    input_file:str) -> str:
    """
    Upload Search for Retail dataset file to GCS bucket.

    Args:
        gcs_bucket (str): Target GCS Bucket name.
        project_id (str): Google Cloud Project ID.
        input_file (str): File to be uploaded.
    Returns:
        GCS URL of the uploaded file.
    """
    client = storage.Client(project=project_id)
    bucket = client.get_bucket(gcs_bucket)
    fn = input_file.split("/")[-1]
    blob = bucket.blob(fn)
    blob.upload_from_filename(input_file)
    return f"gs://{gcs_bucket}/{fn}"

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

    gcs_file = upload_dataset_to_gsc(
        params["gcs_bucket"],
        params["project_number"],
        params["input_file"])

    import_products(
        gcs_errors_path=f"""gs://{params["gcs_bucket"]}/errors""",
        gcs_url=gcs_file,
        project_number=params["project_number"],
        branch=params["branch"])

    if params["set_default_branch"]:
        set_default_branch(params["project_number"],
                           params["branch"])
