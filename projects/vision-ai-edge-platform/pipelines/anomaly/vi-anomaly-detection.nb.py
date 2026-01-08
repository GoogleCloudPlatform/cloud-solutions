# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.18.1
#   kernelspec:
#     display_name: .venv
#     language: python
#     name: python3
# ---

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

# cloud-solutions/vision-ai-edge-platform-v0.0.1

# %% [markdown]
# # Anomaly Detection ML Model using AutoML Vision
#
# ## Overview
# This notebook is an example Vertex AI Pipeline for bike pedal anomaly detection using AutoML Vision Classification model. With this notebook you can create a dataset and train a new AutoML Vision model for anomaly detection at the edge location.

# %% [markdown]
# ## Configuring Google Cloud Project
#
# Configure Google Cloud Project for preparing required services for training.

# %%
PROJECT_ID = "YOUR-PROJECT-ID"
LOCATION = "us-central1"
BUCKET_URI = f"gs://vision-ai-edge-{PROJECT_ID}"

# %% [markdown]
# Enable Google Cloud Service APIs required.

# %%
# ! gcloud services enable compute.googleapis.com
# ! gcloud services enable storage.googleapis.com
# ! gcloud services enable aiplatform.googleapis.com

# %% [markdown]
# Create a new Cloud Storage Bucket for dataset and training job.

# %%
# ! gcloud storage buckets create --location={LOCATION} {BUCKET_URI}

# %% [markdown]
# Create a service account for Vertex AI Pipeline.

# %%
SERVICE_ACCOUNT_NAME = "vision-ai-edge"
SERVICE_ACCOUNT_EMAIL = (
    SERVICE_ACCOUNT_NAME + "@" + PROJECT_ID + ".iam.gserviceaccount.com"
)

# ! gcloud iam service-accounts create {SERVICE_ACCOUNT_NAME} --display-name="Vision AI Edge Service Account"

# ! gcloud storage buckets add-iam-policy-binding $BUCKET_URI --member=serviceAccount:{SERVICE_ACCOUNT} --role=roles/storage.objectCreator

# ! gcloud storage buckets add-iam-policy-binding $BUCKET_URI --member=serviceAccount:{SERVICE_ACCOUNT} --role=roles/storage.objectViewer

# ! gcloud projects add-iam-policy-binding {PROJECT_ID} --member="serviceAccount:{SERVICE_ACCOUNT_EMAIL}" --role="roles/aiplatform.user"

# %% [markdown]
# ## Preparing example dataset
#
# Download the bike-pedal.zip file that contains example images and annotation.
#
# Create a bike-pedals folder and decompress the bike-pedals.zip file inside of the folder.

# %%
DATASET_URL = "https://storage.googleapis.com/solutions-public-assets/vision-ai-edge-platform/bike-pedals.zip"
DATASET_NAME = "bike-pedals"

# ! wget -qN {DATASET_URL}
# ! unzip -qn {DATASET_NAME}.zip -d {DATASET_NAME}

# %% [markdown]
# Generate input-files.jsonl from template file.

# %%
BUCKET_URI_SED=BUCKET_URI.replace('/', '\/')

# ! sed 's/<<BUCKET_URI>>/{BUCKET_URI_SED}/g' \
#     ./{DATASET_NAME}/input-files-template.jsonl > \
#     ./{DATASET_NAME}/input-files.jsonl

# ! head ./{DATASET_NAME}/input-files.jsonl

# %% [markdown]
# Upload the bike-pedal folder to the GCS Bucket.

# %%
# ! gcloud storage cp --recursive {DATASET_NAME} {BUCKET_URI}

# %% [markdown]
# ## Create a Vertex AI Dataset

# %%
from typing import Any, Dict, List

import google.cloud.aiplatform as aip
import kfp
from kfp import compiler

PIPELINE_ROOT = f"{BUCKET_URI}/pipeline_root/flowers"
aip.init(
    project=PROJECT_ID,
    staging_bucket=BUCKET_URI,
    service_account=SERVICE_ACCOUNT_EMAIL,
)


# %% [markdown]
# ## Define Vertex AI Pipeline

# %%
@kfp.dsl.pipeline(name="anomaly-detection-bike-pedals-v1")
def pipeline(project: str = PROJECT_ID, region: str = LOCATION):
    from google_cloud_pipeline_components.v1.automl.training_job import (
        AutoMLImageTrainingJobRunOp,
    )
    from google_cloud_pipeline_components.v1.dataset import ImageDatasetCreateOp

    ds_op = ImageDatasetCreateOp(
        project=project,
        display_name="bike-pedals",
        gcs_source=BUCKET_URI + "/bike-pedals/input-files.jsonl",
        import_schema_uri=aip.schema.dataset.ioformat.image.single_label_classification,
    )

    training_job_run_op = AutoMLImageTrainingJobRunOp(
        project=project,
        display_name="vi-anomaly-pedal",
        prediction_type="classification",
        model_type="MOBILE_TF_HIGH_ACCURACY_1",
        dataset=ds_op.outputs["dataset"],
        model_display_name="vi-anomaly-pedal",
        training_fraction_split=0.6,
        validation_fraction_split=0.2,
        test_fraction_split=0.2,
        budget_milli_node_hours=8000,
    )


# %% [markdown]
# ## Compile the pipeline

# %%
compiler.Compiler().compile(
    pipeline_func=pipeline, package_path="vi_anomaly_pedal_pipeline.yaml"
)

# %% [markdown]
# ## Run the pipeline

# %%
import random
import string

random_suffix = "".join(
    random.choice(string.ascii_lowercase + string.digits) for _ in range(16)
)

DISPLAY_NAME = "vi_anomaly_pedal_" + random_suffix

job = aip.PipelineJob(
    display_name=DISPLAY_NAME,
    template_path="vi_anomaly_pedal_pipeline.yaml",
    pipeline_root=PIPELINE_ROOT,
    enable_caching=False,
)

job.run()

# %% [markdown]
# ## Cleaning up
#
# To clean up all Google Cloud resources used in this project, you can [delete the Google Cloud
# project](https://cloud.google.com/resource-manager/docs/creating-managing-projects#shutting_down_projects) you used for the tutorial.
#
