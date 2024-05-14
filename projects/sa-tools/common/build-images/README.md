# Initialization

1. Set your project ID
   Replace the value with your own GCP Project ID

   PROJECT_ID="prismatic-rock-386211"

## Create Builder base image for use in all dev containers

replace the value of `_CONTAINER_IMAGE_TAG` with your own artifact registry location

```shell
gcloud builds submit . \
--project "${PROJECT_ID}" \
--config all-language-builder-base-cloudbuild.yaml \
--substitutions=_CONTAINER_IMAGE_TAG="<image tag to your artifact registry>"
```
