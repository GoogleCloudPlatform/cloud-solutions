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
# # Dataset Experiments
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
# !pip install --upgrade -q matplotlib \
#     google-cloud-aiplatform[autologging]==1.65.0 \
#     tensorflow-datasets==4.9.6     keras==3.5.0 \
#     keras-cv==0.9.0 tensorflow==2.17.0

# %%
DATASET_ID = '1850063553663336448'
DATASET_EXPORT_BUCKET = 'gs://visual-inspection-demo-datasets-us-central1/car-damage-coco-segmentation-kaggle/vertexai-export/test'
DATA_DIR = 'gs://visual-inspection-demo-datadir-us-central1'
LOCATION = 'us-central1'

BATCH_SIZE = 2

# %%
# !gcloud storage buckets create --location $LOCATION $DATA_DIR

# %%
import os
os.environ["KERAS_BACKEND"] = "tensorflow"
import keras
import keras_cv

import tensorflow as tf
import numpy as np

import matplotlib.pyplot as plt

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

def prep_ds(ds):
    return (ds
            #.shuffle(ds.cardinality())
            .batch(BATCH_SIZE, drop_remainder=True)
            .map(lambda x,y: (x / 255, y / 255), num_parallel_calls=tf.data.AUTOTUNE)
            .prefetch(tf.data.AUTOTUNE)
           )

train_ds, val_ds, test_ds = map(prep_ds, (train_ds, val_ds, test_ds))

# %%
info

# %%
for x, y in test_ds.unbatch().take(1):
    plt.imshow(x)
    plt.show()
    plt.imshow(y[:,:,1])
    plt.show()

# %%
plot_ds = test_ds.unbatch().cache()

keras_cv.visualization.plot_image_gallery(
    np.array(list(plot_ds.take(1).map(lambda x,y: x).as_numpy_iterator())),
    value_range=(0, 1), rows=1, cols=1)
plt.show()

# %%
NUM_CLASSES = info.features['segmentation_mask'].shape[-1]
IMAGE_SHAPE = info.features['image'].shape

# %% [markdown]
# ## Train a DeepLabV3 Segmentation Model with Keras CV

# %%
model = keras_cv.models.DeepLabV3Plus.from_preset(
    "efficientnetv2_b0_imagenet",
    num_classes=NUM_CLASSES,
    input_shape=IMAGE_SHAPE,
)
model.compile(optimizer='adam', 
              loss=keras.losses.CategoricalCrossentropy(from_logits=False),
              metrics=["accuracy"])
model.summary()

# %%
model.evaluate(test_ds)

# %%
num_examples = min(info.splits['test'].num_examples, 8)
plot_ds = test_ds.unbatch().take(num_examples).cache()

keras_cv.visualization.plot_segmentation_mask_gallery(
    list(plot_ds.map(lambda x,y: x).as_numpy_iterator()),
    (0, 1),
    (NUM_CLASSES-1),
    y_true=list(plot_ds.map(lambda x,y: tf.expand_dims(tf.argmax(y, axis=-1), axis=-1)).as_numpy_iterator()),
    y_pred=list(plot_ds.map(lambda x,y: tf.expand_dims(tf.argmax(tf.squeeze(model(tf.expand_dims(x, axis=0))), axis=-1), axis=-1)).as_numpy_iterator()),
    rows=1,
    cols=num_examples
)

# %%
model.fit(
    train_ds, 
    validation_data=val_ds,
    epochs=2)

# %%
model.evaluate(test_ds)

# %%
num_examples = min(info.splits['test'].num_examples, 8)
plot_ds = test_ds.unbatch().take(num_examples).cache()

keras_cv.visualization.plot_segmentation_mask_gallery(
    list(plot_ds.map(lambda x,y: x).as_numpy_iterator()),
    (0, 1),
    (NUM_CLASSES-1),
    y_true=list(plot_ds.map(lambda x,y: tf.expand_dims(tf.argmax(y, axis=-1), axis=-1)).as_numpy_iterator()),
    y_pred=list(plot_ds.map(lambda x,y: tf.expand_dims(tf.argmax(tf.squeeze(model(tf.expand_dims(x, axis=0))), axis=-1), axis=-1)).as_numpy_iterator()),
    rows=1,
    cols=num_examples
)
