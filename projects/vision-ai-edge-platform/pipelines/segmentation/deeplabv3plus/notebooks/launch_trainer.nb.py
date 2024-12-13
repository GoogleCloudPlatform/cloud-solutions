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
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Launch a Visual Inspection AI Model Training Job
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

# %% [markdown]
# Set parameters:

# %%
# Define project id and location for the pipeline
PROJECT_ID = 'visual-inspection-demo-2184'
LOCATION = 'us-central1'

# A staging bucket for the pipeline and training program
STAGING_BUCKET='gs://viai-demo-data-us-central1/ml-trainings/viai-segmentation-deeplabv3'
# The service account that the pipeline and training program acts as
SERVICE_ACCOUNT = '1047381110578-compute@developer.gserviceaccount.com'

# The dataset id in Vertex to use for model training
DATASET_ID = '1850063553663336448'

# Container image for the training program
CONTAINER_LOCATION = 'us'
CONTAINER_NAME = 'trainer'
CONTAINER_REPO = 'visual-inspection-ml-training'
CONTAINER_TAG = 'latest'
CONTAINER_URI = f'{CONTAINER_LOCATION}-docker.pkg.dev/{PROJECT_ID}/{CONTAINER_REPO}/segmentation-deeplabv3plus-{CONTAINER_NAME}:{CONTAINER_TAG}'

# Experiment to log metrics and parameters from the model training
EXPERIMENT = f'{PROJECT_ID}-viai-segmentation-deeplabv3'

# %% [markdown]
# Install dependencies:

# %%
# !pip install --upgrade -q google-cloud-aiplatform[autologging]==1.65.0

# %% [markdown]
# Import libraries and initialize the Vertex AI client:

# %%
from datetime import datetime
from google.cloud import aiplatform

TIMESTAMP = datetime.now().strftime('%Y%m%d%H%M%S')
JOB_NAME = f'{EXPERIMENT}-{TIMESTAMP}'

aiplatform.init(project=PROJECT_ID, 
                location=LOCATION,
                staging_bucket=STAGING_BUCKET)#, experiment=EXPERIMENT)

# %% [markdown]
# Launch a custom job with the training container:

# %%
vertex_ai_custom_job = aiplatform.CustomContainerTrainingJob(
    display_name=JOB_NAME,
    container_uri=CONTAINER_URI,
    model_serving_container_image_uri='us-docker.pkg.dev/vertex-ai/prediction/tf2-cpu.2-13:latest'
)
vertex_ai_custom_job.run(
    machine_type='n1-standard-8',
    replica_count=1,
    accelerator_type = 'NVIDIA_TESLA_V100',
    accelerator_count = 1,
    dataset=aiplatform.ImageDataset(DATASET_ID, location=LOCATION),
    annotation_schema_uri='gs://google-cloud-aiplatform/schema/dataset/annotation/image_segmentation_1.0.0.yaml',
    args=[f'--experiment={EXPERIMENT}',
          '--loss-function=dice_focal',
          '--num-epochs=200',
          '--batch-size=16',
          '--patience-epochs=50'],
    restart_job_on_worker_restart=True,
    service_account=SERVICE_ACCOUNT,
    sync=False
)
