# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Forecast service main module."""

import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Optional

import numpy as np
import timesfm
import utils
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

load_dotenv()
use_jax = utils.is_env_flag_enabled("USE_JAX")

# Global model variable
if use_jax:
    # Force JAX to see only 1 chip to prevent sharding bug
    os.environ["TPU_CHIPS_PER_HOST_BOUNDS"] = "1,1,1"

    tfm: timesfm.TimesFM_2p5_200M_flax
    model_path = "google/timesfm-2.5-200m-flax"
else:
    import torch

    torch.set_float32_matmul_precision("high")
    tfm: timesfm.TimesFM_2p5_200M_torch
    model_path = "google/timesfm-2.5-200m-pytorch"

logging.info("Using model: %s", model_path)


def check_tpu():
    try:
        import jax  # pylint: disable=import-outside-toplevel

        devices = jax.devices()
        print(f"JAX sees the following devices: {devices}")

        # Check if we are actually on TPU
        device_type = devices[0].platform
        if device_type == "tpu":
            print("SUCCESS: Running on TPU!")
        else:
            print(f"WARNING: JAX is running on {device_type}, NOT TPU.")
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"JAX Initialization failed: {e}")


@asynccontextmanager
async def lifespan(app_instance: FastAPI):  # pylint: disable=unused-argument
    check_tpu()

    global tfm
    checkpoint_path = os.getenv("CHECKPOINT_PATH", model_path)

    # Load model on startup to avoid reloading per request
    logging.info("Loading TimesFM from %s...", checkpoint_path)

    if use_jax:
        tfm = timesfm.TimesFM_2p5_200M_flax.from_pretrained(checkpoint_path)
    else:
        tfm = timesfm.TimesFM_2p5_200M_torch.from_pretrained(checkpoint_path)

    tfm.compile(
        timesfm.ForecastConfig(
            max_context=1024,
            max_horizon=256,
            normalize_inputs=True,
            use_continuous_quantile_head=True,
            force_flip_invariance=True,
            infer_is_positive=True,
            fix_quantile_crossing=True,
        )
    )

    logging.info("Model loaded successfully.")
    yield

    # Clean up resources if necessary
    tfm = None


app = FastAPI(lifespan=lifespan)


class ForecastRequest(BaseModel):
    input: list[float]
    horizon: Optional[int] = 10


class VertexPayload(BaseModel):
    instances: list[ForecastRequest]
    parameters: Optional[dict] = {}


class ForecastRequestOld(BaseModel):
    input: list[float]
    horizon: Optional[int] = 10


@app.post("/predict")
async def predict(payload: VertexPayload):
    logging.info("Received request: %s", payload)
    batch_inputs = [inst.input for inst in payload.instances]

    try:
        horizon = payload.instances[0].horizon
        point_forecast, _ = tfm.forecast(horizon=horizon, inputs=batch_inputs)
        forecast_values = point_forecast[0].tolist()
        logging.info("forecast_values=%s", forecast_values)
        return {"predictions": forecast_values}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/predict2")
async def predict2(req: ForecastRequestOld):
    logging.info("Received request: %s", req)
    input_data = req.input
    forecast_context_length = len(input_data)

    try:
        context_data = np.array(input_data[-forecast_context_length:])
        forecast_input = [context_data]
        point_forecast, _ = tfm.forecast(
            horizon=req.horizon, inputs=forecast_input
        )
        forecast_values = point_forecast[0].tolist()
        logging.info("forecast_values=%s", forecast_values)
        return {"forecast": forecast_values}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/health")
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
        reload=True,
    )
