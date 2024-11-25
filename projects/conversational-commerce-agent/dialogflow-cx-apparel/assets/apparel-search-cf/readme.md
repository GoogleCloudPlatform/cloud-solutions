# Cloud function code for dialogflow to interact with

## Manually Deploy

```shell
export CONFIG_TOML_PATH=config.toml
export PROJECT_ID=<YOUR PROJECT ID>
export CLOUD_RUN_NAME=apparel-search-prod-2
export REGION=us-central1

gcloud functions deploy $CLOUD_RUN_NAME --gen2 --region=$REGION \
    --runtime=python312 --source=. --entry-point=main --trigger-http \
    --set-env-vars=LOG_EXECUTION_ID=true,CONFIG_TOML_PATH=$CONFIG_TOML_PATH --no-allow-unauthenticated \
    --project $PROJECT_ID \
    --concurrency=10 --cpu=2 --memory=512MB
```

## Run Locally

Assume you have google cloud function sdk locally.

Run the following code:

```shell
functions-framework --target=main
```
