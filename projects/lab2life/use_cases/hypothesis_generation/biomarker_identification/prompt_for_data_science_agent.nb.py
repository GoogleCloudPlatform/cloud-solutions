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
# ## Step 2: Use Data Science Agent in Colab Enterprise

# %% [markdown]
# # Directions
#
# 1. Save this Notebook locally to your disk
# 2. Switch to your Argolis account and open Colab Enterprise: "Vertex AI->Colab Enteprise"
# 3. Select "Import" and import this Notebook
# 4. Expand the Gemini Assistant at the bottom of the screen
# 5. Usually, you can specify tables by clicking on the "+" icon and then select "BigQuery Table". However, sometimes newly created tables are not listed, so the best way is to specify the table name directly in the prompt
# 6. In the code cell below, specify your table name following the BigQuery name convention: PROJECT-ID.DATASET-NAME.TABLE-NAME
# 7. Enter the generated prompt below in the Gemini assistant 

# %%
project_id = "YOUR_PROJECT_ID"
dataset_name = "YOUR_DATASET_NAME"
table_name = "YOUR_TABLE_NAME"

prompt = """The table {project_id}.{dataset_name}.{table_name} has data about a clinical trial. 
The tables have several fields called biomarkers. I want to identify which biomarker has the strongest influence 
on the outcome of the field PFS_P. Use BigQueryML to do this analyzes. 
You should build predictive models using the training dataset and evaluate model performance using the test dataset. 
You should build the models that are most appropriate to identify biomarker influence, 
and use model explainability to identify the strongest biomarkers. 
Provide a comparative analyzes of the models built and provide an analyzes of the 3 strongest biomarkers."""

prompt = prompt.format(
    project_id=project_id,
    dataset_name=dataset_name,
    table_name=table_name
)

print(prompt)
