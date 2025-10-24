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
from functools import partial

import keras_cv
import tensorflow as tf
from vertexai_image_segmentation_dataset import VertexAIImageSegmentationDataset


class AugmentImages(tf.keras.layers.Layer):
    def __init__(self, seed=42):
        super().__init__()
        self.augment = tf.keras.Sequential([
            keras_cv.layers.RandAugment((0, 1), seed=seed),
            keras_cv.layers.AugMix((0, 1), seed=seed),
            keras_cv.layers.CutMix(seed=seed)
        ])

    def call(self, inputs, labels):
        outputs = self.augment({'images': inputs, 'segmentation_masks': labels})
        return outputs['images'], outputs['segmentation_masks']


def build_datasets(params):
    (train_ds, val_ds, test_ds), info = VertexAIImageSegmentationDataset.load(
        split=['train', 'validation', 'test'],
        with_info=True, as_supervised=True,
        builder_kwargs={
            'width': params.img_width,
            'height':params.img_height
            })


    def prep_ds(ds, params):
        augmentation_factor = params.augmentation_factor
        batch_size = min(params.batch_size, ds.cardinality())

        ds = (ds
              .shuffle(ds.cardinality())
              .map(lambda x,y: (x / 255, y / 255),
                   num_parallel_calls=tf.data.AUTOTUNE))
        ds_aug = (ds
                  .repeat(augmentation_factor)
                  .batch(batch_size, drop_remainder=True)
                  .map(AugmentImages(),
                       num_parallel_calls=tf.data.AUTOTUNE)
                  .unbatch())

        return (tf.data.Dataset.sample_from_datasets(
            [ds, ds_aug],
            weights=[(1/(augmentation_factor+1)),
                     ((augmentation_factor-1)/(augmentation_factor+1))],
            rerandomize_each_iteration=True)
            .batch(batch_size, drop_remainder=True)
            .prefetch(tf.data.AUTOTUNE))

    train_ds, val_ds, test_ds = map(partial(prep_ds, params=params),
                                    (train_ds, val_ds, test_ds))
    return train_ds, val_ds, test_ds, info
