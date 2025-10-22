"""This script downloads and caches the TimesFM models."""

# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import timesfm

# List of models and their hyperparameters to download and cache
models_to_cache = {
    "timesfm-2.0-500m-pytorch": 50,  # This model has 50 layers
    "timesfm-1.0-200m-pytorch": 20,  # This model has 20 layers
}

# Set a minimal horizon length for the hparams object
MIN_HORIZON_LEN = 1

for model_name, num_layers in models_to_cache.items():
    print(f"Downloading and caching model: {model_name}")
    try:
        # Pass the correct num_layers for each model
        tfm = timesfm.TimesFm(
            hparams=timesfm.TimesFmHparams(
                horizon_len=MIN_HORIZON_LEN, num_layers=num_layers
            ),
            checkpoint=timesfm.TimesFmCheckpoint(
                huggingface_repo_id=f"google/{model_name}"
            ),
        )
        print(f"Successfully cached {model_name}")
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Error caching {model_name}: {e}")
