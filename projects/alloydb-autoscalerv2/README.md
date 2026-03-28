# AlloyDB Autoscaler v2

A Cloud Function that automatically scales AlloyDB instances based on CPU
utilization metrics, supporting both primary instances (CPU count) and read
pool instances (node count).

## Disclaimer

License: Apache 2.0

This is not an official Google product.

## Overview

The autoscaler runs on a schedule (e.g. via Cloud Scheduler) and performs the
following actions for each AlloyDB instance in the configured project and
region:

- **Primary instances** — scales CPU count up or down (doubles/halves) based on
  average CPU utilization over the last 5 minutes.
- **Read pool instances** — scales node count up or down by 1 based on average
  CPU utilization over the last 5 minutes.

Scaling thresholds:

| Condition | Action |
|---|---|
| CPU utilization > 80% | Scale up |
| CPU utilization < 20% | Scale down |

Instances that are not in `READY` state are skipped.

## Architecture

```
Cloud Scheduler
      │
      ▼
Cloud Function (main.py)
      │
      ├── Cloud Monitoring API  (reads CPU utilization metrics)
      └── AlloyDB API           (lists clusters/instances, patches machine config)
```

## Prerequisites

- Google Cloud project with AlloyDB clusters provisioned
- The following APIs enabled:
  - `alloydb.googleapis.com`
  - `monitoring.googleapis.com`
  - `cloudfunctions.googleapis.com`
  - `cloudscheduler.googleapis.com`
- A service account with the following roles:
  - `roles/alloydb.admin`
  - `roles/monitoring.viewer`

## Deployment

### 1. Deploy the Cloud Function

```bash
gcloud functions deploy alloydb-autoscaler \
  --gen2 \
  --runtime=python312 \
  --region=REGION \
  --source=cloud-function/ \
  --entry-point=scale_alloydb \
  --trigger-http \
  --no-allow-unauthenticated \
  --service-account=SERVICE_ACCOUNT_EMAIL \
  --set-env-vars="GCP_PROJECT=PROJECT_ID,ALLOYDB_REGION=REGION,MIN_CPU=2,MAX_CPU=16,MIN_NODES=1,MAX_NODES=5"
```

### 2. Schedule the function with Cloud Scheduler

```bash
gcloud scheduler jobs create http alloydb-autoscaler-job \
  --location=REGION \
  --schedule="*/5 * * * *" \
  --uri="https://REGION-PROJECT_ID.cloudfunctions.net/alloydb-autoscaler" \
  --oidc-service-account-email=SERVICE_ACCOUNT_EMAIL
```

## Configuration

All configuration is provided via environment variables:

| Variable | Required | Default | Description |
|---|---|---|---|
| `GCP_PROJECT` | Yes | — | Google Cloud project ID |
| `ALLOYDB_REGION` | Yes | — | Region where AlloyDB clusters are located |
| `MIN_CPU` | No | `2` | Minimum CPU count for primary instances |
| `MAX_CPU` | No | `16` | Maximum CPU count for primary instances |
| `MIN_NODES` | No | `1` | Minimum node count for read pool instances |
| `MAX_NODES` | No | `5` | Maximum node count for read pool instances |

## Local development

```bash
cd cloud-function
pip install -r requirements.txt

GCP_PROJECT=my-project \
ALLOYDB_REGION=us-central1 \
python -c "from main import scale_alloydb; scale_alloydb()"
```
