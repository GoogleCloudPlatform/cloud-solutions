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
from enum import Enum

import keras
import keras_cv


class DiceFocalLoss(keras.Loss):
    def __init__(self, name=None, reduction='sum_over_batch_size', dtype=None):
        super().__init__(name, reduction, dtype)
        self.focal = keras_cv.losses.FocalLoss()
        self.dice = keras.losses.Dice()

    def call(self, y_true, y_pred):
        return self.dice(y_true, y_pred) + \
               self.focal(y_true, y_pred)

class SegmentationLosses(Enum):
    focal = keras_cv.losses.FocalLoss()
    dice = keras.losses.Dice()
    dice_focal = DiceFocalLoss()
    binary_focal_crossentropy = \
        keras_cv.losses.BinaryPenaltyReducedFocalCrossEntropy()
    categorical_focal_crossentropy = \
        keras.losses.CategoricalFocalCrossentropy()

def build_model(params, dataset_info):
    num_classes = dataset_info.features['segmentation_mask'].shape[-1]
    model = keras_cv.models.DeepLabV3Plus.from_preset(
        params.deeplab_preset,
        num_classes=num_classes,
        input_shape=dataset_info.features['image'].shape,
    )

    optimizer = keras.optimizers.get({
        'class_name': params.optimizer,
        'config': {
            'learning_rate': params.learning_rate
        }
    })
    model.compile(optimizer=optimizer,
                  loss=SegmentationLosses[params.loss_function].value,
                  metrics=['accuracy',
                           keras.metrics.CategoricalAccuracy(),
                           keras.metrics.TopKCategoricalAccuracy(
                               k=max(1, min(5,num_classes//4))),
                           keras.metrics.CategoricalCrossentropy(),
                           keras.metrics.MeanAbsoluteError(),
                           keras.metrics.OneHotMeanIoU(
                               num_classes=num_classes),
                           keras.metrics.OneHotIoU(
                               num_classes=num_classes,
                               target_class_ids=range(num_classes))])
    model.summary()
    return model
