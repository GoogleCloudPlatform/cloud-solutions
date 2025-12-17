# Forecast Service

This service is a FastAPI application that provides a REST API for making
predictions using the TimesFM model.

## Running Locally

```bash
./setup.sh
```

## Prediction API

Example request for /predict endpoint:

```json
{
  "instances": [
    {
      "input": [0, 1, 2, 3, 4, 5],
      "horizon": 5
    }
  ]
}
```

## Docker

```bash
docker build -t forecast-service .
docker run -p 8080:8080 forecast-service

docker build --build-arg USE_JAX=true -t forecast-service-jax .
docker run -p 8080:8080 forecast-service-jax
```

## Vertex Endpoint

Example curl command:

```bash
ENDPOINT_ID="forecast-service-timesfm-endpoint"
PROJECT_ID="63187675619"

curl \
-X POST \
-H "Authorization: Bearer $(gcloud auth print-access-token)" \
-H "Content-Type: application/json" \
"https://us-central1-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/us-central1/endpoints/${ENDPOINT_ID}:predict" \
-d '{
  "instances": [
    {
      "input": [0, 1, 2, 3, 4, 5],
      "horizon": 5
    }
  ]
}'
```
