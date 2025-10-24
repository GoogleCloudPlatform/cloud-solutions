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

from __future__ import absolute_import, division, print_function

import argparse
import logging
import os
from datetime import datetime

import keras
import keras_cv
import tensorflow as tf
import tensorflow_datasets as tfds
import utilities
from dataset import build_datasets
from google.cloud import aiplatform
from model import SegmentationLosses, build_model

os.environ['KERAS_BACKEND'] = 'tensorflow'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

tfds.disable_progress_bar()

def _train(params):

    train_ds, val_ds, test_ds, info = build_datasets(params)
    model = build_model(params, info)

    backup_dir = utilities.ensure_dir(
        os.path.join(os.getenv('AIP_CHECKPOINT_DIR'),
                     'backup'))
    steps_dir = utilities.ensure_dir(
        os.path.join(os.getenv('AIP_CHECKPOINT_DIR'),
                     'steps'))
    model_dir = utilities.ensure_dir(os.getenv('AIP_MODEL_DIR'))
    model_callbacks = [
        keras.callbacks.BackupAndRestore(backup_dir),
        keras.callbacks.ModelCheckpoint(
            os.path.join(steps_dir,
                        '{epoch:02d}-{batch:02d}.keras'),
            save_freq=params.checkpoint_frequency),
        keras.callbacks.EarlyStopping(
            patience=params.patience_epochs,
            restore_best_weights=True),
        keras.callbacks.TensorBoard(
            log_dir=os.getenv('AIP_TENSORBOARD_LOG_DIR')),
        keras.callbacks.ReduceLROnPlateau(verbose=1),
    ]

    model.fit(train_ds, validation_data=val_ds,
              epochs=params.num_epochs, verbose=2,
              callbacks=model_callbacks)

    model.evaluate(test_ds, verbose=2, callbacks=model_callbacks)

    model.save(os.path.join(steps_dir, 'final_model.keras'))
    model.export(model_dir)


def _get_args():
    """Argument parser.
    Returns:
    Dictionary of arguments.
    """
    cloud_ml_job_id = os.environ['CLOUD_ML_JOB_ID']

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--experiment',
        type=str,
        default=f'experiment-{cloud_ml_job_id}',
        help='experiment name to log metrics and checkpoints, ' +
             'default=experiment-[CLOUD_ML_JOB_ID]')
    parser.add_argument(
        '--img-width',
        type=int,
        default=512,
        help='input image width assumed by model, default=512')
    parser.add_argument(
        '--img-height',
        type=int,
        default=512,
        help='input image height assumed by model, default=512')
    parser.add_argument(
        '--deeplab-preset',
        default='efficientnetv2_b0_imagenet',
        type=str,
        choices=keras_cv.models.DeepLabV3Plus.presets,
        help='preset to load backbone with weights from, ' +
             'default=efficientnetv2_b0_imagenet')
    parser.add_argument(
        '--num-epochs',
        type=int,
        default=100,
        help='number of times to go through the data, default=100')
    parser.add_argument(
        '--batch-size',
        default=1,
        type=int,
        help='number of records to read during each training step, default=1')
    parser.add_argument(
        '--optimizer',
        default='adam',
        type=str,
        help='optimizer to use for training, default=adam')
    parser.add_argument(
        '--learning-rate',
        default=.001,
        type=float,
        help='learning rate for optimizer, default=.001')
    parser.add_argument(
        '--loss-function',
        default='dice_focal',
        type=str,
        choices=SegmentationLosses.__members__.keys(),
        help=f'loss function in {SegmentationLosses.__members__.keys()}, ' +
             'default=dice_focal')
    parser.add_argument(
        '--patience-epochs',
        type=int,
        default=5,
        help='number of epochs to wait before early stopping, default=5')
    parser.add_argument(
        '--checkpoint-frequency',
        type=int,
        default=1000,
        help='number of steps between checkpoints, default=1000')
    parser.add_argument(
        '--augmentation-factor',
        type=int,
        default=10,
        help='factor by which to increase dataset size with augmentations, ' +
             'default=10')
    parser.add_argument(
        '--verbosity',
        choices=['DEBUG', 'ERROR', 'FATAL', 'INFO', 'WARN'],
        default='INFO')
    return parser.parse_args()


if __name__ == '__main__':
    args = _get_args()
    if args:
        aiplatform.init(project=os.environ['CLOUD_ML_PROJECT_ID'],
                        location=os.environ['CLOUD_ML_REGION'],
                        experiment=args.experiment)

        aiplatform.autolog()
        loglevel = getattr(logging, args.verbosity.upper())
        tf.get_logger().setLevel(loglevel)
        logging.basicConfig(level=loglevel)

        datetime_now_fmt = datetime.now().strftime('%Y-%m-%d-%H-%M-%S-%f')
        aiplatform.start_run(
            run=f'deeplabv3plus-segmentation-trainer-{datetime_now_fmt}')
        aiplatform.log_params(vars(args))
        _train(args)
        aiplatform.end_run()
