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
from typing import List

import numpy as np
import pandas as pd
from google.cloud import aiplatform

aiplatform.init(
    project=os.getenv("GOOGLE_CLOUD_PROJECT"),
    location=os.getenv("GOOGLE_CLOUD_LOCATION"),
)


def perform_forecast(
        historical_values: List[float],
        horizon_length: int = 7,
        context_frequency: int = 0,
):
    """
    Generates a time-series forecast using the TimesFM model on Vertex AI.

    Args:
        historical_values: A list of numerical data points (floats/ints)
            representing past history.
        horizon_length: How many future time steps to predict (default is 5).

    Returns:
        An array containing the forecast predictions.
    """

    logging.debug(
        "perform_forecast function called with parameters: "
        "input_data=%s, horizon_length=%s, context_frequency=%s",
        historical_values,
        horizon_length,
        context_frequency,
    )

    endpoint_id = os.getenv("TIMESFM_ENDPOINT_ID")
    endpoint = aiplatform.Endpoint(endpoint_name=endpoint_id)

    instances = [{"input": historical_values, "horizon": horizon_length}]

    try:
        response = endpoint.predict(instances=instances)
        forecast_values = response.predictions[0]["point_forecast"]
        logging.debug("forecast_values=%s", forecast_values)
        return forecast_values

    except Exception as e:  # pylint: disable=broad-exception-caught
        return {"error": f"Failed to invoke Vertex AI endpoint: {str(e)}"}


if __name__ == "__main__":
    # Example of how to use the function
    print("Performing forecast...")

    # Define the context and horizon lengths for the forecast
    context_length = 21  # Use the last 21 days of data
    horizon_days = 7  # Predict the next 7 days

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
        historical_values=sample_input_data,
        horizon_length=horizon_days,
    )

    print(f"\nForecast for the next {horizon_days} days:")
    for i, value in enumerate(forecast_result):
        print(f"  Day {i + 1}: {value:.4f}")

    print(f"\nTotal forecasted values: {len(forecast_result)}")
