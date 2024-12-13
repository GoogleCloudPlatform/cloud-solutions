# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.16.5
#   kernelspec:
#     display_name: Python 3
#     name: python3
# ---

# %% [markdown] id="yky13k5-MpJQ"
# # Convert COCO Segmentation Dataset to Vertex AI Segmentation
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
#@title Parameters & Authenticate
ANNOTATION_FILE = "gs://visual-inspection-demo-datasets-us-central1/car-damage-coco-segmentation-kaggle/train/COCO_train_annos.json" # @param {type:"string"}
TARGET_BUCKET = "gs://visual-inspection-demo-datasets-us-central1/car-damage-coco-segmentation-kaggle/train" # @param {type:"string"}

import sys

if "google.colab" in sys.modules:
    from google.colab import auth as google_auth

    google_auth.authenticate_user()

# %% cellView="form" colab={"base_uri": "https://localhost:8080/"} id="I14kn32rxX5w" outputId="0c5f243b-aff7-4267-c3f7-bbfbd8a0ae68"
#@title Load Annotations
# !gsutil cp $ANNOTATION_FILE .

import json
import os

with open(ANNOTATION_FILE.split(os.sep)[-1], 'r') as af:
  data = json.load(af)

# %% cellView="form" id="pKtahUNzNv6R"
#@title Helpers
import io
import numpy as np

from PIL import Image

from google.cloud import storage


def get_gcs_image_size(image_url):
  """Get the size of an image in Google Cloud Storage.

  Args:
    image_url: The gs:// url of the image.

  Returns:
    A tuple containing the width and height of the image in pixels.
  """

  # Initialize client that will be used to send requests. This client only needs to be created
  # once, and can be reused for multiple requests.
  storage_client = storage.Client()

  # Get the image from the bucket.
  bucket = storage_client.bucket(image_url.split("//")[1].split("/")[0])
  blob = bucket.blob("/".join(image_url.split("//")[1].split("/")[1:]))
  image_bytes = blob.download_as_bytes()

  # Open the image using Pillow.
  image = Image.open(io.BytesIO(image_bytes))

  # Return the width and height of the image.
  return image.size

def construct_img_path(img):
  return os.path.join(os.path.dirname(ANNOTATION_FILE), img)

def clip_float(float_nbr, min_val=0, max_val=1):
  return max(min(float_nbr, max_val), min_val)

def format_float(float_nbr, precision=7):
  return float(np.format_float_positional(float_nbr, precision=precision))


# %% cellView="form" colab={"base_uri": "https://localhost:8080/"} id="3_Efnl6CyxVE" outputId="297add10-14ca-4f46-cc45-34a1af8f506f"
#@title Convert Annotations

from tqdm import tqdm

vai_annotations = []
image_annotations = {construct_img_path(img['file_name']): []
                     for img in data['images']}

for annot in data['annotations']:
  image = construct_img_path(data['images'][annot['image_id']]['file_name'])
  image_annotations[image].append(annot)

category_names = [cat['name'] for cat in data['categories']]

for img, annot in tqdm(image_annotations.items()):
  width, height = get_gcs_image_size(img)
  vai_annotations.append(
    {
        "imageGcsUri": img,
        "polygonAnnotations": [{
            "displayName": category_names[ann['category_id']-1],
            "vertexes": [{"x": clip_float(x / width),
                      "y": clip_float(y / height)}
                      for x, y in zip(ann['segmentation'][0][::2],
                                      ann['segmentation'][0][1::2])]
          } for ann in annot]
    })

vai_annotations

# %% cellView="form" colab={"base_uri": "https://localhost:8080/"} id="8nuy67hm1QZK" outputId="9615dd5f-cbc7-4097-90fd-3b8e1c478f3d"
#@title Store Annotations
with open('vertexai_car_damage_segmentation_polygon.jsonl', 'w') as of:
  for l in vai_annotations:
    json.dump(l, of)
    of.write('\n')

# !gsutil cp 'vertexai_car_damage_segmentation_polygon.jsonl' $TARGET_BUCKET
