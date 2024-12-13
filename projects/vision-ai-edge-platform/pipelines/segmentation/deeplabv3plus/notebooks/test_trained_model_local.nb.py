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
# # Test Trained Model (Local)
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

# %%
# Define project id and location for the pipeline
PROJECT_ID = 'visual-inspection-demo-2184'
LOCATION = 'us-central1'

# The dataset id in Vertex to use for model tests
DATASET_ID = '1850063553663336448'
# A GCP bucket to export the dataset
DATASET_EXPORT_BUCKET = 'gs://visual-inspection-demo-datasets-us-central1/pixel-phone-damage-defects/vertexai-export/test/'

# Model export bucket to load the model from
BUCKET = 'gs://viai-demo-data-us-central1/ml-trainings/viai-oss-pipeline/viai-segmentation-deeplabv3/trainer/aiplatform-custom-training-2024-11-18-18:38:46.886'
import os
MODEL_URI =  os.path.join(BUCKET, 'checkpoints/steps/final_model.keras')
MODEL_TFSAVED_URI = os.path.join(BUCKET, 'model')

# Batch size to use with the model
BATCH_SIZE = 2

# %%
# !pip install --upgrade -q matplotlib \
#     google-cloud-aiplatform[autologging]==1.65.0 \
#     tensorflow-datasets==4.9.6     keras==3.5.0 \
#     keras-cv==0.9.0 tensorflow==2.17.0

# %%
import os
os.environ["KERAS_BACKEND"] = "tensorflow"
import keras
import keras_cv

import tensorflow as tf
import numpy as np

import matplotlib.pyplot as plt


# %%
#Helper functions

def display(display_list):
  plt.figure(figsize=(15, 15))

  title = ['Input Image', 'True Mask', 'Predicted Mask']

  for i in range(len(display_list)):
    plt.subplot(1, len(display_list), i+1)
    plt.title(title[i])
    plt.imshow(tf.keras.utils.array_to_img(display_list[i]), cmap='coolwarm')
    plt.axis('off')
  plt.show()

def prep_ds(ds):
  return (ds
          .batch(BATCH_SIZE, drop_remainder=True)
          .map(lambda x,y: (x / 255, y / 255),
               num_parallel_calls=tf.data.AUTOTUNE))


# %% [markdown]
# ## Load Vertex AI Image Segmentation Dataset with TFDS

# %%
from google.cloud import aiplatform

img_ds = aiplatform.ImageDataset(DATASET_ID, location=LOCATION)
exported_img_ds = img_ds.export_data_for_custom_training(
    DATASET_EXPORT_BUCKET,
    annotation_schema_uri='gs://google-cloud-aiplatform/schema/dataset/annotation/image_segmentation_1.0.0.yaml',
    split={ 'training_fraction': 0.8, 'validation_fraction': 0.1, 'test_fraction': 0.1}
)

# %%
exported_img_ds

# %%
import sys
sys.path.append('../trainer')
from vertexai_image_segmentation_dataset import VertexAIImageSegmentationDataset

(train_ds, val_ds, test_ds), info = VertexAIImageSegmentationDataset.load(
    split=['train', 'validation', 'test'], with_info=True, as_supervised=True,
    #data_dir=DATA_DIR, #currently not working with GCS in TFDS 
    builder_kwargs={
        'training_data': exported_img_ds['exportedFiles'][0],
        'validation_data': exported_img_ds['exportedFiles'][1],
        'test_data': exported_img_ds['exportedFiles'][2],
    })

train_ds, val_ds, test_ds = map(prep_ds, (train_ds, val_ds, test_ds))

# %%
info

# %%
NUM_CLASSES = info.features['segmentation_mask'].shape[-1]
IMAGE_SHAPE = info.features['image'].shape

# %%
examples = 8
plot_ds = train_ds.unbatch().take(examples).cache()

keras_cv.visualization.plot_segmentation_mask_gallery(
    list(plot_ds.map(lambda x,y: x).as_numpy_iterator()),
    (0, 1),
    NUM_CLASSES,
    y_true=list(plot_ds.map(lambda x,y: tf.expand_dims(tf.argmax(y, axis=-1), axis=-1)).as_numpy_iterator()),
    rows=2,
    cols=4,
    scale=4
)

# %%
import math
examples = list(plot_ds.map(lambda x,y: (x, tf.expand_dims(tf.argmax(y, axis=-1), axis=-1))).as_numpy_iterator())
for ex in examples:
    display(ex)

# %% [markdown]
# ## Load & Test Keras Model

# %%
model = keras.saving.load_model(MODEL_URI)
tf_model = tf.saved_model.load(MODEL_TFSAVED_URI)

# %% [markdown]
# ## Keras Model Tests

# %%
for x, y in test_ds.take(1).as_numpy_iterator():
    print(model(x))

# %%
examples = 2
plot_ds = test_ds.unbatch().take(examples).cache()

keras_cv.visualization.plot_segmentation_mask_gallery(
    list(plot_ds.map(lambda x,y: x).as_numpy_iterator()),
    (0, 1),
    NUM_CLASSES-1,
    y_true=list(plot_ds.map(lambda x,y: tf.expand_dims(tf.argmax(y, axis=-1), axis=-1)).as_numpy_iterator()),
    y_pred=list(plot_ds.map(lambda x,y: tf.expand_dims(tf.squeeze(tf.argmax(model(tf.expand_dims(x, axis=0)), axis=-1)), axis=-1)).as_numpy_iterator()),
    rows=1,
    cols=2,
    scale=4
)

# %%
examples = list(plot_ds.map(lambda x,y: (x, 
                                         tf.expand_dims(
                                            tf.argmax(y, axis=-1), axis=-1),
                                         tf.expand_dims(
                                            tf.squeeze(
                                                tf.argmax(model(tf.expand_dims(x, axis=0)), 
                                                           axis=-1)), 
                                                axis=-1)
                                        )
                            ).as_numpy_iterator())
for ex in examples:
    display(ex)

# %% [markdown]
# ## Tensorflow SavedModel Tests

# %%
for x, y in test_ds.take(1).as_numpy_iterator():
    print(tf_model.serve(x))

# %%
examples = 2
plot_ds = test_ds.unbatch().take(examples).cache()

keras_cv.visualization.plot_segmentation_mask_gallery(
    list(plot_ds.map(lambda x,y: x).as_numpy_iterator()),
    (0, 1),
    NUM_CLASSES,
    y_true=list(plot_ds.map(lambda x,y: tf.expand_dims(tf.argmax(y, axis=-1), axis=-1)).as_numpy_iterator()),
    y_pred=list(plot_ds.map(lambda x,y: tf.expand_dims(tf.squeeze(tf.argmax(tf_model.serve(tf.expand_dims(x, axis=0)), axis=-1)), axis=-1)).as_numpy_iterator()),
    rows=1,
    cols=2,
    scale=4
)

# %%
examples = list(plot_ds.map(lambda x,y: (x, 
                                         tf.expand_dims(
                                            tf.argmax(y, axis=-1), axis=-1),
                                         tf.expand_dims(
                                            tf.squeeze(
                                                tf.argmax(tf_model.serve(
                                                    tf.expand_dims(x, axis=0)), 
                                                           axis=-1)), 
                                                axis=-1)
                                        )
                            ).as_numpy_iterator())
for ex in examples:
    display(ex)
