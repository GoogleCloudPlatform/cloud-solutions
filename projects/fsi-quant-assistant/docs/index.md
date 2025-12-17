# FSI Financial Assistant

This demo showcases how customers can make natural language requests for
sophisticated financial analysis. By combining real-time market data from open
financial APIs with stored portfolio information, the system delivers AI-powered
insights, identifies market relationships, and generates future predictions
using the TimesFM forecasting model.

Here are the core functionalities that the repo provides:

- **AI/Infrastructure**: Illustrating the use of AI and GCP infrastructure.

- **Deploying** and illustrating the performance and flexibility of open models
  on GCP.

- **ADK**: Showing the ease of using Agent Development Kit (ADK) to build
  powerful financial solutions.

## Solution Diagram

![A diagram of the solution](solution_diagram.png)

## Prerequisites

- A Google Cloud Project:
    - Project ID of a new or existing Google Cloud Project, preferably with no
      APIs enabled.
    - You must have roles/owner or equivalent IAM permissions on the project.
- Development environment with:
    - [Google Cloud SDK](https://cloud.google.com/sdk) (gcloud CLI)
    - [Terraform](https://www.terraform.io/) (version 1.0+)
    - [git](https://git-scm.com/)
- You can also use [Cloud Shell](https://shell.cloud.google.com) which comes
  preinstalled with all required tools.
- Familiarity with:
    - [Terraform](https://www.terraform.io/)

## Getting Started

### Login, initialize terraform state buckets, and apply terraform

```bash
# Log in with Application Default Credentials (ADC)
gcloud auth application-default login

# Set the specified project as the active project in your configuration
GCP_PROJECT_ID=[YOUR_PROJECT_ID]
gcloud config set project $GCP_PROJECT_ID

# Create Terraform state bucket
BUCKET_NAME="${GCP_PROJECT_ID}-tf-state"
LOCATION="us"

gcloud storage buckets create "gs://${BUCKET_NAME}" --location="${LOCATION}" --uniform-bucket-level-access

cd ./deployment/terraform

# Create tfbackend file
TF_BACKEND=${BUCKET_NAME}.tfbackend
echo -n 'bucket = "'${BUCKET_NAME}'"' > environment/${TF_BACKEND}

# Create TF vars file
echo -n 'project_id = "'${GCP_PROJECT_ID}'"' > terraform.tfvars

# Open up terraform.tfvars and add an entry for your finnhub api key. You can get a finnhub api key at https://finnhub.io/.
project_id = "[YOUR_PROJECT_ID]"
finnhub_api_key = "[YOUR_FINNHUB_API_KEY]"

gcloud services enable \
    compute.googleapis.com \
    cloudresourcemanager.googleapis.com

terraform init -backend-config=./environment/${TF_BACKEND}
terraform plan -var-file ./terraform.tfvars -out=tfplan
terraform apply tfplan

REGION=$(terraform output -raw region)
CLOUDBUILD_SERVICE_ACCOUNT_ID=$(terraform output -raw cloudbuild_service_account_id)
ADK_STAGING_BUCKET=$(terraform output -raw adk_staging_bucket)
```

### Create objects in AlloyDB instance

<!-- markdownlint-disable MD013 -->
```bash
open -a "Google Chrome" "https://console.cloud.google.com/alloydb/locations/${REGION}/clusters/alloydb-cluster/studio?project=${GCP_PROJECT_ID}"
```
<!-- markdownlint-enable MD013 -->

Login to the postgres database using IAM database authentication.
Copy and paste in order the sql from:

- deployment/postgres/exchange/create.sql
- deployment/postgres/exchange/cron.sql

into AlloyDB Studio and run it.

### Deploy the services

```bash
cd ../../

# Build and push the image for the forecast service to artifact registry
gcloud builds submit \
    --config=./forecast-service/cloudbuild-publish.yaml \
    --substitutions=_REGION=${REGION} \
    --project=${GCP_PROJECT_ID} \
    --service-account=${CLOUDBUILD_SERVICE_ACCOUNT_ID} \
    --region=${REGION} \
    .

IMAGE_URI=${REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/finance-bundle/forecast-service:latest

# Deploy the forecast service to the model registry and deploy to vertex endpoint
# The deployment to the vertex endpoint may take many minutes to complete.
gcloud builds submit \
    --config=./forecast-service/cloudbuild-deploy.yaml \
    --substitutions=_REGION=${REGION},_IMAGE_URI=${IMAGE_URI} \
    --project=${GCP_PROJECT_ID} \
    --service-account=${CLOUDBUILD_SERVICE_ACCOUNT_ID} \
    --region=${REGION} \
    .

# Deploy the order service
gcloud builds submit \
    --config=./order-service/cloudbuild-deploy.yaml \
    --substitutions=_REGION=${REGION} \
    --project=${GCP_PROJECT_ID} \
    --service-account=${CLOUDBUILD_SERVICE_ACCOUNT_ID} \
    --region=${REGION} \
    .

cd deployment/terraform

# Update terraform.tfvars and set
deploy_order_service = true

# Run a plan and apply for the order service cloud run configuration to be applied
terraform plan -var-file ./terraform.tfvars -out=tfplan
terraform apply tfplan

# Terraform will create a .env file for the adk agent
# Deploy the adk agent to agent engine
cd ../../

gcloud builds submit \
    --config=./adk-agent/cloudbuild-deploy.yaml \
    --substitutions=_REGION=${REGION},_STAGING_BUCKET=${ADK_STAGING_BUCKET} \
    --project=${GCP_PROJECT_ID} \
    --service-account=${CLOUDBUILD_SERVICE_ACCOUNT_ID} \
    --region=${REGION} \
    .
```

## Clearing old versions

To delete previous versions of the adk agent, run the following:

```bash
gcloud builds submit \
    --config=./adk-agent/cloudbuild-clear-agents.yaml \
    --substitutions=_REGION=${REGION} \
    --project=${GCP_PROJECT_ID} \
    --service-account=${CLOUDBUILD_SERVICE_ACCOUNT_ID} \
    --region=${REGION} \
    .
```

To delete previous versions of the forecast service, run the following:

```bash
gcloud builds submit \
    --config=./forecast-service/cloudbuild-clear-models.yaml \
    --substitutions=_REGION=${REGION} \
    --project=${GCP_PROJECT_ID} \
    --service-account=${CLOUDBUILD_SERVICE_ACCOUNT_ID} \
    --region=${REGION} \
    --no-source
```
