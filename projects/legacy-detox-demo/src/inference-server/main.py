# Copyright 2026 Google LLC
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

"""
Inference server for Vertex AI, serving a Spark ML model using pure
Python/Numpy. This server loads model parameters from a JSON
file and replicates the pipeline math.
"""

import json
import logging
import os

import numpy as np
from fastapi import FastAPI, Request, Response, status
from google.cloud import storage

# Configure logging
logging.basicConfig(level=logging.INFO)

app = FastAPI()

LOCAL_MODEL_PATH = "/tmp/model.json"
model_params = None


def download_model():
    """Downloads the Lean model JSON file from Cloud Storage to local disk."""
    global model_params

    # Vertex AI injects the GCS URI where your model
    # artifacts live via this env var
    MODEL_ARTIFACT_DIR = os.environ.get("AIP_STORAGE_URI")
    logging.info(os.environ)
    if not MODEL_ARTIFACT_DIR:
        logging.error("AIP_STORAGE_URI is not set. Model download skipped.")
        return

    logging.info("Downloading model artifact from: %s", MODEL_ARTIFACT_DIR)

    try:
        # Parse gs:// bucket and path
        path_parts = MODEL_ARTIFACT_DIR.replace("gs://", "").split("/")
        bucket_name = path_parts[0]
        prefix = "/".join(path_parts[1:]).rstrip("/")
        blob_path = f"{prefix}/model.json"

        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_path)

        if not blob.exists():
            logging.error(
                "Model file %s not found in bucket %s",
                blob_path,
                bucket_name,
            )
            return

        blob.download_to_filename(LOCAL_MODEL_PATH)
        logging.info("Model downloaded to %s", LOCAL_MODEL_PATH)

        # Load the Lean model parameters
        with open(LOCAL_MODEL_PATH, "r", encoding="utf-8") as f:
            model_params = json.load(f)

        # Pre-convert lists to Numpy arrays for faster matrix operations
        model_params["scaler_std"] = np.array(model_params["scaler_std"])
        model_params["coefficients"] = np.array(model_params["coefficients"])
        model_params["intercept"] = np.array(model_params["intercept"])

        logging.info("Lean model parameters successfully loaded and prepared.")
    except Exception as e:  # pylint: disable=broad-exception-caught
        logging.error("Failed to download or load model: %s", e)


@app.on_event("startup")
async def startup_event():
    download_model()


@app.get("/health")
def health_check():
    """Vertex AI requirement: Return 200 OK to
    indicate the container is live."""
    if model_params is not None:
        return {"status": "HEALTHY"}
    return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


@app.post("/predict")
async def predict(request: Request):
    """
    Vertex AI requirement: Receive instances, score them using
    pure Python/Numpy, and return predictions.
    Bypasses Spark/JVM runtime entirely.
    """
    if model_params is None:
        return Response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content="Model not loaded",
        )

    try:
        body = await request.json()
        instances = body.get("instances", [])

        if not instances:
            return {"predictions": []}

        predictions = []
        for inst in instances:
            # 1. Replicate StringIndexer
            # (with 'keep' logic for unseen categories)
            gender = inst.get("gender", "M")
            country = inst.get("country", "United States")
            age = float(inst.get("age", 30.0))

            gender_map = model_params["gender_map"]
            country_map = model_params["country_map"]

            # If the value is not in the map, assign the index
            # len(map) (equivalent to 'keep' in Spark)
            gender_idx = (
                gender_map.index(gender)
                if gender in gender_map
                else len(gender_map)
            )
            country_idx = (
                country_map.index(country)
                if country in country_map
                else len(country_map)
            )

            # 2. Replicate VectorAssembler: [age, gender_idx, country_idx]
            features = np.array([age, gender_idx, country_idx])

            # 3. Replicate StandardScaler: x / std
            # (withMean=False, withStd=True)
            scaled_features = features / model_params["scaler_std"]

            # 4. Replicate Multinomial Logistic Regression: scores = W * x + b
            # coefficients shape: (num_classes, num_features)
            # intercept shape: (num_classes,)
            scores = (
                np.dot(model_params["coefficients"], scaled_features)
                + model_params["intercept"]
            )

            # 5. Replicate IndexToString: argmax to get class index,
            # then map to string
            predicted_idx = np.argmax(scores)
            predicted_category = model_params["label_map"][predicted_idx]

            predictions.append({"predicted_category": predicted_category})

        return {"predictions": predictions}
    except Exception as e:  # pylint: disable=broad-exception-caught
        logging.error("Prediction error: %s", e)
        return Response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=str(e)
        )
