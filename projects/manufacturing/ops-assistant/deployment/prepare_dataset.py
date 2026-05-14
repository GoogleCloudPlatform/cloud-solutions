# Copyright 2026 Google LLC
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

"""Script to prepare the BigQuery dataset and tables from CSV files."""

import os
import sys

import google.auth
from dotenv import load_dotenv
from google.api_core import exceptions
from google.cloud import bigquery


def main():
    # Load configuration from .env file
    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
    env_paths = [
        os.path.join(project_root, ".env"),
        os.path.join(project_root, "ops_assistant_agent", ".env"),
    ]
    for path in env_paths:
        if os.path.exists(path):
            load_dotenv(path)
            print(f"Loaded configuration from: {path}")
            break
    else:
        load_dotenv()

    try:
        credentials, project_id = google.auth.default()
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Error authenticating: {e}")
        sys.exit(1)

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", project_id)
    if not project_id:
        print(
            "Error: GOOGLE_CLOUD_PROJECT is not set and could not be "
            "determined."
        )
        sys.exit(1)

    # Use configured names or defaults
    dataset_id = os.environ.get("ASSET_DATASET", "mfg_assets")
    # Replace invalid characters like dash with underscore
    if "-" in dataset_id:
        cleaned_dataset_id = dataset_id.replace("-", "_")
        print(
            f"⚠️ Warning: BigQuery dataset ID '{dataset_id}' contains "
            f"invalid character '-'. Replacing with '{cleaned_dataset_id}' "
            f"for BigQuery compatibility."
        )
        dataset_id = cleaned_dataset_id

    asset_table_id = os.environ.get(
        "ASSET_TABLE", "vertex_high_pressure_coolant_pump"
    )
    historical_failures_table_id = os.environ.get(
        "HISTORICAL_FAILURES_TABLE", "historical_failures"
    )
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

    print(
        f"Preparing BigQuery Dataset: {project_id}.{dataset_id} "
        f"in {location}..."
    )

    try:
        client = bigquery.Client(project=project_id, credentials=credentials)
        dataset_ref = f"{project_id}.{dataset_id}"
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = location

        try:
            existing_dataset = client.get_dataset(dataset_ref)
            if existing_dataset.location.upper() != location.upper():
                print(
                    f"❌ Error: Dataset {dataset_id} already exists in location "
                    f"{existing_dataset.location}, but we need it "
                    f"in {location}."
                )
                sys.exit(2)
            print(
                f"✅ Dataset {dataset_ref} already exists in the correct "
                f"location ({location})."
            )
        except exceptions.NotFound:
            client.create_dataset(dataset)
            print(
                f"✅ Successfully created BigQuery dataset {dataset_ref} "
                f"in {location}."
            )

        # Load the two CSV files directly into BigQuery
        csv_dir = os.path.dirname(__file__)
        tables_to_load = [asset_table_id, historical_failures_table_id]

        for table_id in tables_to_load:
            csv_filename = f"{table_id}.csv"
            csv_path = os.path.join(csv_dir, csv_filename)
            if not os.path.exists(csv_path):
                print(f"❌ Error: CSV file not found at {csv_path}")
                sys.exit(1)

            table_ref = f"{dataset_ref}.{table_id}"
            print(f"Loading {csv_filename} into BigQuery table {table_ref}...")

            job_config = bigquery.LoadJobConfig(
                source_format=bigquery.SourceFormat.CSV,
                skip_leading_rows=1,
                autodetect=True,
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            )

            with open(csv_path, "rb") as source_file:
                load_job = client.load_table_from_file(
                    source_file, table_ref, job_config=job_config
                )

            # Wait for completion
            load_job.result()

            destination_table = client.get_table(table_ref)
            print(
                f"✅ Successfully loaded {destination_table.num_rows} rows "
                f"into {table_ref}."
            )

    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"❌ Failed to prepare BigQuery dataset and tables: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
