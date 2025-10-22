"""This module provides a tool for performing time series forecasting."""

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

import logging
import os
import sys
from typing import Any, List, Literal

import numpy as np
import pandas as pd
import timesfm
import torch

# Conditionally import torch_xla only on Linux
_has_tpu = False
if sys.platform == "linux":
    try:
        import torch_xla.core.xla_model as xm

        # Check if an XLA device is actually available
        if xm.xla_device():
            _has_tpu = True
            logging.debug("TPU found")
        else:
            logging.debug("TPU not found")
    except (ImportError, RuntimeError):
        # The import failed, so _has_tpu remains False
        pass
    except OSError:
        # Handle potential exceptions during device check
        pass

MODEL_200M = "timesfm-1.0-200m-pytorch"
MODEL_500M = "timesfm-2.0-500m-pytorch"


def get_device() -> Literal["cpu", "gpu", "tpu"]:
    """
    Determines the available compute device.

    Checks for TPU, then GPU (CUDA), and defaults to CPU.

    :return: A literal string "cpu", "gpu", or "tpu".
    """
    # Check for TPU using the flag.
    if _has_tpu:
        return "tpu"

    if torch.cuda.is_available():
        return "gpu"

    return "cpu"


def perform_forecast(
    input_data: List[float], horizon_length: int = 7, context_frequency: int = 0
) -> List[Any]:
    """
    Perform a forecast using the TimesFM model.

    This function loads the pre-trained TimesFM model and uses it to predict
    the next `horizon_length` values based on the provided `input_data`.

    :param input_data: A list of historical data points.
        The last `context_length` points will be used as
        context for the forecast.
    :param horizon_length: The number of future data points to predict.
    :param context_frequency: The frequency of each context time series.
    :return: A list containing the forecasted values.
    """

    logging.debug(
        "perform_forecast function called with parameters: "
        "input_data=%s, horizon_length=%s, context_frequency=%s",
        input_data,
        horizon_length,
        context_frequency,
    )

    forecast_context_length = len(
        input_data
    )  # The number of past data points to use as context.

    model = os.getenv("MODEL_ID", "timesfm-2.0-500m-pytorch")

    device = get_device()
    logging.debug("device=%s, model=%s", device, model)

    # 1. Load the pre-trained TimesFM model
    if model == MODEL_200M:
        # The model is loaded onto the CPU.
        # If a GPU is available, 'cpu' can be changed to 'cuda'.
        tfm = timesfm.TimesFm(
            hparams=timesfm.TimesFmHparams(
                backend=device,
                # per_core_batch_size=32,
                horizon_len=horizon_length,
                # input_patch_len=32,
                # output_patch_len=128,
                num_layers=20,
                # model_dims=1280,
                use_positional_embedding=False,
            ),
            checkpoint=timesfm.TimesFmCheckpoint(
                huggingface_repo_id=f"google/{MODEL_200M}"
            ),
        )
    elif model == MODEL_500M:
        tfm = timesfm.TimesFm(
            hparams=timesfm.TimesFmHparams(
                backend=device,
                per_core_batch_size=32,
                horizon_len=horizon_length,
                num_layers=50,
                use_positional_embedding=False,
            ),
            checkpoint=timesfm.TimesFmCheckpoint(
                huggingface_repo_id=f"google/{MODEL_500M}"
            ),
        )
    else:
        raise ValueError(
            f"Unsupported or unknown MODEL_ID: {model}. "
            "Please set the environment variable to a valid model."
        )

    # The context is the last `context_length` points of the input data.
    context_data = np.array(input_data[-forecast_context_length:])

    # 3. Set up the evaluation data format
    forecast_input = [
        context_data,
        [context_frequency] * forecast_context_length,
    ]

    # 4. Run the forecast
    point_forecast, _ = tfm.forecast(forecast_input)

    # 5. Extract and return the forecast
    forecast_values = point_forecast[0].tolist()

    logging.debug("forecast_values=%s", forecast_values)

    return forecast_values


if __name__ == "__main__":
    # Example of how to use the function
    print("Performing forecast...")

    # Define the context and horizon lengths for the forecast
    context_length = 21  # Use the last 21 days of data
    horizon_days = 7  # Predict the next 14 days

    historical_dates = pd.to_datetime(
        pd.date_range(end="2025-07-29", periods=context_length, freq="D")
    )

    sample_input_data = []
    for day in historical_dates:
        base_sale = 50 + np.random.randint(-10, 10)
        if day.dayofweek >= 5:  # It's a weekend
            sample_input_data.append(base_sale * 1.5)
        else:  # It's a weekday
            sample_input_data.append(base_sale)

    print(
        f"Using {context_length} days of context from "
        f"input data of length {len(sample_input_data)}."
    )

    forecast_result = perform_forecast(
        input_data=sample_input_data,
        horizon_length=horizon_days,
    )

    print(f"\nForecast for the next {horizon_days} days:")
    for i, value in enumerate(forecast_result):
        print(f"  Day {i + 1}: {value:.4f}")

    print(f"\nTotal forecasted values: {len(forecast_result)}")
