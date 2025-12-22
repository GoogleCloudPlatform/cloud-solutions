# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.18.1
#   kernelspec:
#     display_name: Python 3
#     name: python3
# ---

# %% [markdown] id="yky13k5-MpJQ"
# # Convert VIAI Cosmetic Defect Dataset to Vertex AI Segmentation
#
# Contributors: michaelmenzel@google.com

# %%
"""
Copyright 2024 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

# %% cellView="form" id="U1_Pz3T4gPky"
# @title Parameters & Authenticate
ANNOTATION_FILE = "gs://viai-demo-data-us-central1/cosmetic-test-data-public/data_with_polygon.jsonl"  # @param {type:"string"}
TARGET_BUCKET = "gs://viai-demo-data-us-central1/cosmetic-test-data-public/"  # @param {type:"string"}

import sys

if "google.colab" in sys.modules:
    from google.colab import auth as google_auth

    google_auth.authenticate_user()

# %% cellView="form" colab={"base_uri": "https://localhost:8080/"} id="I14kn32rxX5w" outputId="1b3f93f8-4fac-44be-8351-ccdeb7ae1e80"
# @title Load Annotations
# !gcloud storage cp $ANNOTATION_FILE .

import json
import os

with open(ANNOTATION_FILE.split(os.sep)[-1], "r") as af:
    data = [json.loads(line) for line in af]

# %% cellView="form" colab={"base_uri": "https://localhost:8080/"} id="3_Efnl6CyxVE" outputId="b3443fe4-24e8-4687-c4dc-28d2a614324e"
# @title Convert Annotations

from tqdm import tqdm

vai_annotations = []

for item in tqdm(data):
    vai_annotations.append(
        {
            "imageGcsUri": item["image_gcs_uri"],
            "polygonAnnotations": [
                {
                    "displayName": ann["annotation_spec"],
                    "vertexes": ann["vi_bounding_poly"]["vertex"],
                }
                for ann in item["vi_annotations"]
            ],
        }
    )

vai_annotations

# %% cellView="form" colab={"base_uri": "https://localhost:8080/"} id="8nuy67hm1QZK" outputId="59f32de1-3b05-4c40-e3b5-52d83057479a"
# @title Store Annotations
with open("vertexai_segmentation_polygon.jsonl", "w") as of:
    for l in vai_annotations:
        json.dump(l, of)
        of.write("\n")

# !gcloud storage cp 'vertexai_segmentation_polygon.jsonl' $TARGET_BUCKET
