# Copyright 2025 Google LLC
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
Module for fetching bakery trends from BigQuery and generating
visualization plots.
"""

import datetime
import json
import logging
import os

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()

# --- Setup Logger ---
logger = logging.getLogger(__name__)

FALL_SUBCATEGORIES = [
    "Pumpkin Cream Scone",
    "Apple Cider Donut",
    "Pumpkin Cheesecake",
    "Maple Pecan Tart",
    "Cranberry Orange Loaf",
    "Chai Spice Muffin",
    "Salted Caramel Brownie",
    "Pear and Ginger Tart",
]


def get_trends_from_bigquery(
    project_id: str,
    dataset_id: str,
    table_id: str,
    start_date: str,
    num_months: int,
) -> pd.DataFrame:
    """
    Fetches trend data from a BigQuery table within a specific date range.

    Args:
        project_id: The Google Cloud project ID where the BigQuery dataset
                    resides.
        dataset_id: The name of the BigQuery dataset containing the trends
                    table.
        table_id: The name of the table with the trend data.
        start_date: The beginning of the desired date range, formatted as
                    'YYYY-MM-DD'.
        num_months: The number of months of data to fetch, starting from
                    the `start_date`.

    Returns:
        A pandas DataFrame containing the queried trend data, with the 'Date'
        column parsed as datetime objects.
    """
    client = bigquery.Client(project=project_id)

    # Calculate end date
    start_date_obj = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
    end_date = (start_date_obj + pd.DateOffset(months=num_months)).date()

    # Construct a query to fetch data within the date range
    query = f"""
        SELECT *
        FROM `{project_id}.{dataset_id}.{table_id}`
        WHERE Date >= '{start_date_obj}'
        AND Date <= '{end_date}'
    """

    # Run the query and convert to a pandas DataFrame
    df = client.query(query).to_dataframe()
    df["Date"] = pd.to_datetime(df["Date"])
    return df


def create_static_trend_plot(
    subcategory_data: pd.DataFrame, output_folder: str
) -> str:
    """
    Generates and saves a static line plot visualizing trend data over time.

    Args:
        subcategory_data: A pandas DataFrame where the first column is 'Date'
                          and subsequent columns represent different trend
                          categories (e.g., product names).
        output_folder: The directory path where the generated plot image
                       will be saved.

    Returns:
        The absolute file path of the saved plot image.

    Side Effects:
        - Creates the `output_folder` if it does not already exist.
        - Saves a JPEG file to the specified `output_folder`.
        - Sets the file permissions of the saved image to be world-readable.
    """
    os.makedirs(output_folder, mode=0o755, exist_ok=True)
    filename = "fall_bakery_trends_google.jpg"
    full_path = os.path.join(output_folder, filename)

    if os.path.exists(full_path):
        os.remove(full_path)
        logger.info("Removed existing plot at %s", full_path)

    for item in FALL_SUBCATEGORIES:
        # Check if the column exists before trying to access it
        if item in subcategory_data.columns:
            subcategory_data[item] = (
                subcategory_data[item]
                .rolling(window=3, center=True, min_periods=1)
                .mean()
            )

    # --- Plotting Logic ---
    plt.style.use("default")
    sns.set_style("whitegrid")
    plt.figure(figsize=(12, 6))

    data_long = subcategory_data.melt(
        "Date", var_name="Item", value_name="Interest"
    )

    google_palette = {
        "Pumpkin Cream Scone": "#4285F4",  # Google Blue
        "Apple Cider Donut": "#DB4437",  # Google Red
        "Pumpkin Cheesecake": "#F4B400",  # Google Yellow
        "Maple Pecan Tart": "#AAAAAA",  # Gray for fading
        "Cranberry Orange Loaf": "#CCCCCC",  # Light gray for flat
        "Chai Spice Muffin": "#8E44AD",  # Purple
        "Salted Caramel Brownie": "#27AE60",  # Green
        "Pear and Ginger Tart": "#7F8C8D",  # Dark Gray
    }

    # Draw the line plot
    sns.lineplot(
        data=data_long,
        x="Date",
        y="Interest",
        hue="Item",
        linewidth=1.5,
        palette=google_palette,
        marker=True,
    )

    plt.title(
        "Google Trends - Interest over time",
        loc="left",
        fontsize=14,
        weight="bold",
        y=1.05,
    )

    # --- LEGEND LABELS ---
    plt.legend(
        title=None,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.05),
        ncol=5,
        frameon=False,
        fontsize=10,
    )

    # --- X-AXIS TICK LABELS ---
    plt.xticks(fontsize=10)

    sns.despine(left=True, bottom=True)

    plt.tight_layout()
    plt.savefig(full_path, format="jpeg", dpi=150)
    plt.close()
    os.chmod(full_path, 0o644)
    logger.info(
        "Newly generated plot path: %s, permissions: %s",
        os.path.abspath(full_path),
        oct(os.stat(full_path).st_mode),
    )

    return full_path


def get_bakery_trends(start_date: str, num_months: int) -> str:
    """
    Orchestrates the fetching of bakery trend data and the creation of
    a visualization.

    Args:
        start_date: The start date for the trend data query,
                    in 'YYYY-MM-DD' format.
        num_months: The duration of the trend analysis, in months,
                    from the start date.

    Returns:
        On success, the local file path of the generated trend plot image.
        On failure, a JSON string containing an error message.

    Raises:
        ValueError: If essential environment variables for BigQuery
                    connection are not set.
    """
    try:
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        dataset_id = os.getenv("BIGQUERY_DATASET_ID")
        table_id = os.getenv("BIGQUERY_TABLE_ID")

        if not all([project_id, dataset_id, table_id]):
            raise ValueError(
                "Missing one or more required environment variables: "
                "GOOGLE_CLOUD_PROJECT, BIGQUERY_DATASET_ID, BIGQUERY_TABLE_ID"
            )

        subcategory_data = get_trends_from_bigquery(
            project_id, dataset_id, table_id, start_date, num_months
        )

        output_folder = "output/trends"
        plot_path = create_static_trend_plot(subcategory_data, output_folder)

        return plot_path
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to generate trends plot from BigQuery: %s", e)
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    # This part is for direct script execution for testing and won't be
    # called by the agent. The agent calls get_bakery_trends directly.
    get_bakery_trends(start_date="2025-01-01", num_months=12)
