# Get Ready With Me - Deployment Guide

AI-Powered Virtual Try-On & Beauty Platform with Model
Creation, Single/Multi VTO, Beauty Demo, and Size & Fit.

## Prerequisites

1.  **Google Cloud CLI** installed and authenticated

    ```bash
    gcloud auth login
    ```

1.  **Google Cloud Project** with billing enabled
1.  **Vertex AI API** access (for Gemini, Veo, and VTO APIs)

## First-Time Deployment

After receiving the `App.zip` file, run:

```bash
unzip -o App.zip && cd GetReadywithMe && ./deploy.sh
```

The script will:

1.  Ask for your Google Cloud Project ID (or auto-detect it)
1.  Generate a unique GCS bucket name
1.  Enable required APIs (Cloud Run, Storage, Cloud Build,
    Artifact Registry, Vertex AI)
1.  Create the GCS bucket
1.  Automatically extract all asset zips and upload to the
    bucket
1.  Build and deploy the app to Cloud Run
1.  Print the live URL

## Redeploy (Code Updates Only)

After making code changes in `src/`, redeploy without
re-uploading assets:

```bash
./redeploy.sh
```

The script will:

1.  Auto-detect the project ID and existing bucket name from
    the running service
1.  Rebuild and deploy the updated code to Cloud Run
1.  Print the live URL

## What Gets Deployed

### Application (Cloud Run)

Streamlit web app with 5 tabs:

- **Model Creation** - Generate fashion models
- **Single Product VTO** - Virtual try-on with accessories
- **Multi Try-On** - Batch try-on across models and products
- **Beauty Demo** - Makeup try-on with video generation
- **Size & Fit** - Size recommendation engine

### Assets (GCS Bucket)

All assets are bundled as zip files in `assets/` and uploaded
automatically during first deployment.

## Cleanup

To remove the deployed app and bucket:

```bash
gcloud run services delete vto-demo --region us-central1 --quiet
gsutil -m rm -r gs://YOUR_BUCKET_NAME
```
