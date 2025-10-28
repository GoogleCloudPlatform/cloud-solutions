# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""This module generates an S3 inventory and creates an summary."""

import argparse
import logging
import os

from config import EXTERNAL_CONTEXT_URL
from gemini import GeminiRecommender
from utils import get_bucket_inventory, get_object_inventory
from web_fetch import web_fetch


def main():
    """
    Main function to generate the S3 inventory and create an summary.
    """
    parser = argparse.ArgumentParser(
        description="Generate S3 inventory and migration recommendations."
    )
    parser.add_argument(
        "--no-gemini-recommendations",
        action="store_true",
        help="Do not generate Gemini recommendations.",
    )
    args = parser.parse_args()

    # Fetch external context and set as environment variable
    external_context = web_fetch(EXTERNAL_CONTEXT_URL)
    os.environ["EXTERNAL_CONTEXT"] = external_context

    # Get bucket and object inventories
    bucket_df = get_bucket_inventory(save_csv=True)
    if not bucket_df.empty:
        # Get object inventory for the first bucket
        first_bucket_name = bucket_df["Bucket Name"][0]
        object_df = get_object_inventory(first_bucket_name, save_csv=True)
        if not object_df.empty:
            # Generate recommendations
            if not args.no_gemini_recommendations:
                try:
                    gemini = GeminiRecommender()
                    recommendations = gemini.generate_recommendations(
                        bucket_df, object_df
                    )
                    if recommendations:
                        gemini.print_recommendations(recommendations)
                        with open(
                            "migration_recommendations.md",
                            "w",
                            encoding="utf-8",
                        ) as f:
                            f.write(recommendations)
                        logging.info(
                            "\nRecommendations also saved"
                            "to migration_recommendations.md"
                        )
                except ValueError as e:
                    logging.error(e)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    main()
