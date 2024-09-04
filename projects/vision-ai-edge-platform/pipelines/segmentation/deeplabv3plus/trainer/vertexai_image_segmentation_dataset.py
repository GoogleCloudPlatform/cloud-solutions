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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import json
import numpy as np
import os
from PIL import Image, ImageDraw
import tensorflow as tf
import tensorflow_datasets as tfds
from tensorflow_datasets import features as tfds_features

_CITATION = 'Michael Menzel, Google'

_DESCRIPTION = 'This is an example of a image segmentation dataset ' + \
               'backed by a Vertex AI managed dataset.'


def _load_jsons(data_uri):
    return [json.loads(js)
                for data_file in tf.io.gfile.glob(data_uri)
                for js in (tf.io.read_file(data_file)
                           .numpy()
                           .decode('UTF-8')
                           .split('\n'))]

def _extract_classes(dataset_metadata):
    return set([pa['displayName']
                for el in dataset_metadata
                for pa in el['polygonAnnotations']])


def _vertexes_to_xy(polygonAnnots):
    return [[(v['x'], v['y'])
             for v in polygon['vertexes']]
            for polygon in polygonAnnots]

@tf.function(input_signature=(tf.TensorSpec(shape=None, dtype=tf.string),))
def _load_image(uri):
    return tf.io.decode_image(tf.io.read_file(uri),
                              channels=3,
                              expand_animations=False)


class VertexAIImageSegmentationDataset(tfds.core.GeneratorBasedBuilder):
    """Image Segmentation Dataset on Vertex AI
    """

    VERSION = tfds.core.Version('1.0.0')

    RELEASE_NOTES = {
        '1.0.0': 'Initial release.',
    }

    def __init__(self,
                 *,
                 training_data = os.environ.get('AIP_TRAINING_DATA_URI'),
                 validation_data = os.environ.get('AIP_VALIDATION_DATA_URI'),
                 test_data = os.environ.get('AIP_TEST_DATA_URI'),
                 width = 512,
                 height = 512,
                 **kwargs):

        self.image_width = width
        self.image_height = height

        self.training_data = training_data
        self.validation_data = validation_data
        self.test_data = test_data

        self._prepare_split_metadata()

        super().__init__(**kwargs)


    @staticmethod
    def load(*args, **kwargs):
        return tfds.load('VertexAIImageSegmentationDataset',
                         *args, **kwargs)  # pytype: disable=wrong-arg-count

    MANUAL_DOWNLOAD_INSTRUCTIONS = ''

    def _prepare_split_metadata(self):
        self.data_sources = {
            tfds.Split.VALIDATION: self.validation_data,
            tfds.Split.TRAIN: self.training_data,
            tfds.Split.TEST: self.test_data
        }

        self.dataset_metadata = {
            tfds.Split.VALIDATION:
                _load_jsons(self.data_sources[tfds.Split.VALIDATION]),
            tfds.Split.TRAIN:
                _load_jsons(self.data_sources[tfds.Split.TRAIN]),
            tfds.Split.TEST:
                _load_jsons(self.data_sources[tfds.Split.TEST]),
        }

        self.dataset_classes = ['background'] + list(
            _extract_classes(
                self.dataset_metadata[tfds.Split.VALIDATION]) |
            _extract_classes(
                self.dataset_metadata[tfds.Split.TRAIN]) |
            _extract_classes(
                self.dataset_metadata[tfds.Split.TEST])
        )

    def _info(self):
        return tfds.core.DatasetInfo(
            builder=self,
            description=_DESCRIPTION,
            features=tfds_features.FeaturesDict({
                'image':
                    tfds_features.Image(shape=(self.image_width,
                                               self.image_height, 3),
                                        dtype=np.uint8),
                'segmentation_mask':
                    tfds_features.Tensor(shape=(self.image_width,
                                                self.image_height,
                                                len(self.dataset_classes)),
                                         dtype=np.uint8),
            }),
            supervised_keys=('image', 'segmentation_mask'),
            citation=_CITATION,
        )

    def _split_generators(self, dl_manager): # pytype: disable=wrong-arg-count
        """Returns SplitGenerators."""
        del dl_manager
        return {
            tfds.Split.TRAIN:
                self._generate_examples(split=tfds.Split.TRAIN),
            tfds.Split.VALIDATION:
                self._generate_examples(split=tfds.Split.VALIDATION),
            tfds.Split.TEST:
                self._generate_examples(split=tfds.Split.TEST),
        }

    def _generate_examples(self, split):
        """Yields examples."""
        dataset_items = [{'uri': el['imageGcsUri'],
                          'classes': [pa['displayName']
                                      for pa in el['polygonAnnotations']],
                          'polygons': _vertexes_to_xy(el['polygonAnnotations'])}
                         for el in self.dataset_metadata[split]]

        #TODO: Turn into tf.function
        def create_mask(image, polygons, classes):
            size = tuple(image.shape[:-1])
            class_masks = [Image.new('L', size) for c in self.dataset_classes]
            class_draws = [ImageDraw.Draw(mask) for mask in class_masks]

            #TODO: consider cv2.drawContours()
            for i, xy in enumerate(polygons):
                class_id = self.dataset_classes.index(classes[i])
                scaled_xy = np.round(np.multiply(xy, size)).astype(int)
                tupled_xy = [(t[0], t[1]) for t in scaled_xy]
                class_draws[class_id].polygon(tupled_xy, fill = 255)

            mask_img = tf.concat([
                tf.cast(tf.keras.utils.img_to_array(mask), np.uint8)
                for mask in class_masks[1:]], axis=-1)

            #calculate background class channel
            mask_img = tf.concat([
                tf.expand_dims(
                    tf.math.scalar_mul(
                        255,
                        tf.cast(tf.reduce_sum(mask_img, axis=-1) == 0,
                                dtype=np.uint8)),
                    axis=-1),
                mask_img
            ], axis=-1)

            mask_img = tf.cast(
                tf.reshape(mask_img, (*size, len(self.dataset_classes))),
                np.uint8)

            return mask_img

        @tf.function
        def resize_image(img):
            return tf.cast(
                tf.image.resize_with_pad(img,
                                         self.image_height,
                                         self.image_width),
                np.uint8)


        for el in dataset_items:
            image = resize_image(_load_image(el['uri'])).numpy()
            mask = create_mask(image, el['polygons'], el['classes']).numpy()
            yield ('split_' + el['uri'],
                   {
                       'image': image,
                        'segmentation_mask': mask})
