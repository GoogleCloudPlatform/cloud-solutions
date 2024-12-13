# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.16.5
#   kernelspec:
#     display_name: .venv
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Launch a Visual Inspection AI Model Training Pipeline
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
# Set Parameters:

# %%
# Define project id and location for the pipeline
PROJECT_ID = 'visual-inspection-demo-2184'
LOCATION = 'us-central1'

# A staging bucket for the pipeline and training program
BUCKET = 'gs://viai-demo-data-us-central1/ml-trainings'
# The service account that the pipeline and training program acts as
SERVICE_ACCOUNT = '1047381110578-compute@developer.gserviceaccount.com'
# VPC network to deploy the model as private endpoint
VPC_NETWORK = 'projects/1047381110578/global/networks/viai-demo'

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

# Name of the pipeline in Vertex AI
PIPELINE_DISPLAY_NAME = 'viai-segmentation-pipeline'


# Change the folder names below if you want the pipeline and training program 
# to write in different folders
import os
STAGING_BUCKET=os.path.join(BUCKET, 'viai-oss-pipeline')
PIPELINE_BUCKET=os.path.join(STAGING_BUCKET, 'viai-segmentation-deeplabv3')
TRAINING_BUCKET=os.path.join(PIPELINE_BUCKET, 'trainer')
PIPELINE_ROOT = os.path.join(BUCKET, 'pipeline_root/viai-oss-pipeline')



# %% [markdown]
# Install dependencies:

# %%
# !pip install --upgrade -q matplotlib \
#     google-cloud-aiplatform[autologging]==1.65.0 \
#     google-cloud-pipeline-components==2.16.1

# %% [markdown]
# Import libraries and initialize the Vertex AI client:

# %%
from kfp import compiler, dsl

from google.cloud import aiplatform
from google_cloud_pipeline_components.v1.custom_job.component import custom_training_job as CustomTrainingJobOp
from google_cloud_pipeline_components.v1.dataset import GetVertexDatasetOp
from google_cloud_pipeline_components.v1.endpoint import (EndpointCreateOp,
                                                          ModelDeployOp)
from google_cloud_pipeline_components.v1.model import ModelUploadOp
from google_cloud_pipeline_components.types import artifact_types

aiplatform.init(project=PROJECT_ID, 
                location=LOCATION,
                staging_bucket=STAGING_BUCKET, 
                experiment=EXPERIMENT)


# %% [markdown]
# Implement a custom training function:

# %%
@dsl.component(base_image='python:3.11-slim', packages_to_install=['google-cloud-aiplatform', 'google-cloud-pipeline-components'])
def model_train(project_id: str, location: str, display_name: str, 
                trainer_bucket: str, container_uri: str,
                experiment: str, service_account: str, dataset: dsl.Input[artifact_types.VertexDataset], 
                deeplab_preset: str, img_width: int, img_height: int,
                batch_size: int, optimizer: str, num_epochs: int, patience_epochs: int,
                loss_function: str, augmentation_factor: int,
                model: dsl.Output[artifact_types.VertexModel]):

    from google.cloud import aiplatform as aip
    from google_cloud_pipeline_components.types import artifact_types
    
    aip.init(location=location, project=project_id, staging_bucket=trainer_bucket)
    
    vertex_ai_custom_job = aip.CustomContainerTrainingJob(
        display_name=display_name,
        container_uri=container_uri,
        model_serving_container_image_uri='us-docker.pkg.dev/vertex-ai/prediction/tf2-cpu.2-13:latest'
    )
    vertex_ai_model = vertex_ai_custom_job.run(
        machine_type='n1-standard-8',
        replica_count=1,
        accelerator_type = 'NVIDIA_TESLA_V100',
        accelerator_count = 1,
        dataset=aip.ImageDataset(dataset.metadata['resourceName'], location=location),
        annotation_schema_uri='gs://google-cloud-aiplatform/schema/dataset/annotation/image_segmentation_1.0.0.yaml',
        args=[f'--experiment={experiment}',
              f'--deeplab-preset={deeplab_preset}',
              f'--img-width={img_width}',
              f'--img-height={img_height}',
              f'--num-epochs={num_epochs}', 
              f'--batch-size={batch_size}',
              f'--optimizer={optimizer}',
              f'--patience-epochs={patience_epochs}',
              f'--loss-function={loss_function}',
              f'--augmentation-factor={augmentation_factor}'],
        restart_job_on_worker_restart=True,
        service_account=service_account
    )

    model.uri = f'https://{location}-aiplatform.googleapis.com/v1/{vertex_ai_model.versioned_resource_name}'
    model.metadata = {
        'resourceName': vertex_ai_model.resource_name,
    }


# %% [markdown]
# Define the pipeline and steps:

# %%
@dsl.pipeline(
    name=PIPELINE_DISPLAY_NAME,
    description="A semantic segmentation with deeplabv3 training pipeline",
    pipeline_root=PIPELINE_ROOT,
)
def pipeline(project_id: str, location: str, staging_bucket: str, trainer_bucket: str,
             container_uri: str, deploy_model: bool, deploy_vpc: str,
             experiment: str, dataset_id: str, service_account: str,
             deeplab_preset: str, img_width: int, img_height: int,
             batch_size: int, optimizer: str,
             num_epochs: int, patience_epochs: int,
             loss_function: str, augmentation_factor: int):

    dataset_op = GetVertexDatasetOp(
        dataset_resource_name=f'projects/{project_id}/locations/{location}/datasets/{dataset_id}'
    )
    
    train_model_op = model_train(
        project_id=project_id,
        location=location,
        display_name=f'{PIPELINE_DISPLAY_NAME}-trainer',
        trainer_bucket=trainer_bucket,
        container_uri=container_uri,
        experiment=experiment,
        service_account=service_account,
        dataset=dataset_op.outputs['dataset'],
        deeplab_preset=deeplab_preset,
        img_width=img_width,
        img_height=img_height,
        batch_size=batch_size,
        optimizer=optimizer,
        num_epochs=num_epochs,
        patience_epochs=patience_epochs,
        loss_function=loss_function,
        augmentation_factor=augmentation_factor
    )

    
    with dsl.If(deploy_model == True, 'condition-should-model-deploy'):
        create_endpoint_op = EndpointCreateOp(
            project=project_id,
            location=location,
            network=deploy_vpc,
            display_name = f'{PIPELINE_DISPLAY_NAME}-ep',
        )
    
        model_deploy_yaml_op = ModelDeployOp(
            model=train_model_op.outputs['model'],
            endpoint=create_endpoint_op.outputs['endpoint'],
            dedicated_resources_machine_type='n1-standard-8',
            dedicated_resources_min_replica_count=1,
            dedicated_resources_max_replica_count=1,
        )


# %% [markdown]
# Compile the pipeline to JSON:

# %%
compiler.Compiler().compile(
    pipeline_func=pipeline, 
    package_path="build/training_pipeline.json",
    type_check=False
)

# %% [markdown]
# Launch a Vertex AI Pipelines job:

# %%
job = aiplatform.PipelineJob(
    display_name=PIPELINE_DISPLAY_NAME,
    template_path="build/training_pipeline.json",
    pipeline_root=PIPELINE_ROOT,
    parameter_values={
        'project_id': PROJECT_ID, 
        'location': LOCATION, 
        'staging_bucket': STAGING_BUCKET,
        'trainer_bucket': TRAINING_BUCKET,
        'container_uri': CONTAINER_URI,
        'deploy_model': True,
        'deploy_vpc': VPC_NETWORK,
        'experiment': EXPERIMENT,
        'dataset_id': DATASET_ID,
        'service_account': SERVICE_ACCOUNT,
        'deeplab_preset': 'resnet50_v2_imagenet',
        'img_width': 512,
        'img_height': 512,
        'num_epochs': 234,
        'patience_epochs': 50,
        'optimizer': 'adam',
        'batch_size': 2,
        'loss_function': 'dice_focal',
        'augmentation_factor': 10
    }
)

job.submit(experiment=EXPERIMENT)
