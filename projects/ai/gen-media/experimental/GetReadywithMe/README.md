# Get Ready With Me - Deployment Guide

AI-Powered Virtual Try-On & Beauty Platform with Model
Creation, Single/Multi VTO, Beauty Demo, and Size & Fit.

## Prerequisites

1.  **Python 3.12+** required (f-string syntax used requires 3.12+)
1.  **Google Cloud CLI** installed and authenticated

    ```bash
    gcloud auth login
    ```

1.  **Google Cloud Project** with billing enabled
1.  **Vertex AI API** access (for Gemini, Veo, and VTO APIs)

## First-Time Deployment

### Option 1: Clone from GitHub

```bash
git clone https://github.com/GoogleCloudPlatform/cloud-solutions.git
cd cloud-solutions/projects/ai/gen-media/experimental/GetReadywithMe
./deploy.sh
```

### Option 2: Download and Run

Download just the `GetReadywithMe` folder without cloning the
entire repository:

```bash
echo "Downloading GetReadywithMe..." \
  && curl -sL https://github.com/GoogleCloudPlatform/cloud-solutions/archive/refs/heads/main.tar.gz | tar -xz \
  && mv cloud-solutions-main/projects/ai/gen-media/experimental/GetReadywithMe . \
  && rm -rf cloud-solutions-main \
  && echo "Download complete."

cd GetReadywithMe
chmod +x deploy.sh redeploy.sh
./deploy.sh
```

The script will:

1.  Ask for your Google Cloud Project ID (or auto-detect it)
1.  Generate a unique GCS bucket name
1.  Enable required APIs (Cloud Run, Storage, Cloud Build,
    Artifact Registry, Vertex AI)
1.  Create the GCS bucket
1.  Upload assets to the bucket
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

## Local Development

To run the app locally:

```bash
# Ensure Python 3.12+ is installed
python3 --version

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export GCP_PROJECT_ID=your-project-id
export GCS_BUCKET_NAME=your-bucket-name
export GOOGLE_CLOUD_PROJECT=your-project-id

# Authenticate with Google Cloud
gcloud auth application-default login

# Run the app
streamlit run src/app.py
```

## Cleanup

To remove the deployed app and bucket:

```bash
gcloud run services delete vto-demo --region us-central1 --quiet
gsutil -m rm -r gs://YOUR_BUCKET_NAME
```
