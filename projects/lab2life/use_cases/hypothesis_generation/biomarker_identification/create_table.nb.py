# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.0
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: conda-base-py
# ---

# %%
# Copyright 2024 Google LLC
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


# %% [markdown]
# # Biomarker Identification Demo
#
# ## Step 1: Download Clinical Trial and upload to Big Query

# %%
# Get the clinical trial dataset
# !curl -O https://static-content.springer.com/esm/art%3A10.1038%2Fs41591-020-1044-8/MediaObjects/41591_2020_1044_MOESM3_ESM.xlsx

# %%
# !pip install --user pandas openpyxl

# %%
# Define a function to split the tabs of the excel file

import os
import sys

import pandas as pd

def split_excel_tabs(input_file):
    # Load the entire workbook
    xls = pd.ExcelFile(input_file)

    # Create an output directory
    output_dir = f"{os.path.splitext(input_file)[0]}_split"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print(f"Splitting '{input_file}' into directory: '{output_dir}'")

    # Iterate through each sheet name
    for sheet_name in xls.sheet_names:
        print(f"  - Processing sheet: '{sheet_name}'")
        # Read the specific sheet into a DataFrame
        df = pd.read_excel(xls, sheet_name=sheet_name)

        # Define the output file name
        output_file = os.path.join(output_dir, f"{sheet_name}.xlsx")

        # Save the DataFrame as a new Excel file
        df.to_excel(output_file, index=False)
        print(f"    Saved to: '{output_file}'")

    print("Done.")


# %%
split_excel_tabs("41591_2020_1044_MOESM3_ESM.xlsx")


# %%
# function to convert the clinical data to CSV
def convert_xlsx_to_csv(excel_file, csv_file_output):
    """
    Converts a single sheet from an Excel file to a CSV file using pandas.
    """
    try:
        # Read the Excel file into a pandas DataFrame
        df = pd.read_excel(excel_file)
        
        # Convert the DataFrame to a CSV file
        # index=False prevents writing the DataFrame index as a column in the CSV file
        df.to_csv(csv_file_output, index=False, encoding="utf-8")
        print(f"Successfully converted '{excel_file}' to '{csv_file_output}'")
        
    except Exception as e:
        print(f"An error occurred: {e}")



# %%
convert_xlsx_to_csv(
    "41591_2020_1044_MOESM3_ESM_split/S11_Clinical_data.xlsx",
    "S11_Clinical_data.csv"
)

# %%
# Strip the header line
# !sed -i '1d' S11_Clinical_data.csv

# %%
# create a BigQuery Dataset
# !bq mk --dataset javelin_trial

# %%
# !bq load --source_format=CSV --autodetect javelin_trial.S11_Clinical_data ./S11_Clinical_data.csv

# %%
# Load the clinical trial data into BigQuery
