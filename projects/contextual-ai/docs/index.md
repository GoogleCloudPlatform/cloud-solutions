# Contextual AI

This document describes steps to deploy the solution.

For detailed architecture diagram and flows, please refer to
[this document](./architecture.md).

## Setup the solution

To setup the solution, follow these steps:

- Configure default Google Cloud Project and Region.

```shell
export GOOGLE_CLOUD_PROJECT="YOUR PROJECT"
export GOOGLE_GENAI_USE_VERTEXAI=True
export GOOGLE_CLOUD_LOCATION=us-central1

gcloud config set project $GOOGLE_CLOUD_PROJECT

```

- Enable Required Services.

```shell
gcloud services enable aiplatform.googleapis.com \
storage.googleapis.com \
compute.googleapis.com \
bigquery.googleapis.com \
run.googleapis.com \
cloudbuild.googleapis.com \
artifactregistry.googleapis.com \
discoveryengine.googleapis.com \
iam.googleapis.com

```

- Ensure Organization Policy allows unauthenticated requests. Allow the
  following policies.

    - `constraints/iam.allowedPolicyMemberDomains`
    - `constraints/gcp.resourceLocations`

- Provision cloud resources.

```shell
export CURRENT_DIR=$(pwd)

cd ${CURRENT_DIR}/terraform

terraform init
terraform apply -var="project_id=$(gcloud config get-value project)" \
    -var="region=${GOOGLE_CLOUD_LOCATION}" \
    --auto-approve
```

- Deploy the solution.

```shell

cd ${CURRENT_DIR}

gcloud config set gcloudignore/enabled true

. deploy-app.sh

```

- Generate Data

```bash
cd ${CURRENT_DIR}/data
python3 -m venv .venv
source .venv/bin/activate
pip install pandas numpy
python generate_ecommerce_data.py
```

- Import to BigQuery

```bash
pip install google-cloud-bigquery

python import_to_bigquery.py
```
