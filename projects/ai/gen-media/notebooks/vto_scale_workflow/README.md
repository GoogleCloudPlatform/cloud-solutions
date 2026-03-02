# Virtual Try-On (VTO) Scale Workflow

A comprehensive, end-to-end pipeline for generating diverse, photorealistic
Virtual Try-On (VTO) images and motion videos using Google's Generative AI
models on Vertex AI.

## Author

Layolin Jesudhass

## Overview

This project demonstrates a scalable workflow for fashion e-commerce
applications that:

- Generates diverse digital models with various demographics
- Performs high-fidelity virtual garment try-on
- Adds realistic motion to showcase garments in runway-style videos
- Processes inputs at scale from CSV files using Google Cloud Storage

## Key Features

### Multi-Model AI Pipeline

- **Model Generation**: Creates photorealistic digital models with diverse
  demographics (race, body type, age)
- **Virtual Try-On**: Performs garment swapping using Vertex AI's VTO model
- **AI Critique**: Automatically selects best results using Gemini for quality
  assessment
- **Motion Synthesis**: Generates runway walk videos to showcase garments in
  motion
- **Scalable Architecture**: Processes batch inputs from CSV with parallel
  execution

### Technologies Used

- **Google Vertex AI**: Primary platform for all AI operations
- **Gemini 2.5 Flash**: Orchestration, prompt generation, and quality critique
- **Gemini 2.5 Flash Image**: Digital model image generation
- **Vertex AI Virtual Try-On**: High-fidelity garment transfer
- **Veo 3.0**: Video generation for motion synthesis
- **Google Cloud Storage**: Asset management and storage

## Project Structure

```text
vto_scale_workflow/
├── VTO_GenMedia_Workflow.ipynb   # Main Jupyter notebook with complete pipeline
├── VTO_GenMedia_Workflow.nb.py   # Python script version of the notebook
├── dress/                       # Sample dress images for VTO
│   ├── blue-front.png
│   ├── multi-front.png
│   ├── pink-front.png
│   └── red-front.png
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

## Workflow Architecture

The pipeline follows a sequential 5-step process:

### Step 1: Model Definition Generation

- Generates diverse model prompts using structured output from Gemini
- Creates a CSV manifest with model demographics and descriptions
- Ensures diversity across ethnicity, age, skin tone, body type, and hair style

### Step 2: Digital Model Image Creation

- Reads CSV manifest and generates base model images
- Uses consistent styling (white t-shirt, black jeans, white sneakers)
- Maintains specified demographics while ensuring uniform outfit presentation

### Step 3: Virtual Try-On Processing

- Pairs generated models with garment images
- Generates multiple VTO candidates (default: 4) per model-outfit combination
- Processes in parallel for efficiency using ThreadPoolExecutor
- Includes automatic retry mechanism for failed attempts

### Step 4: AI-Powered Quality Assessment

- Evaluates all VTO candidates using Gemini's multimodal capabilities
- Judges based on:
    - Garment fidelity and transfer quality
    - Fit realism and body proportions
    - Image clarity and lack of artifacts
    - Complete outfit transfer (no original clothing visible)
- Selects best candidate and provides reasoning
- Generates evaluation summary CSV

### Step 5: Motion Video Generation

- Creates runway walk videos from selected VTO images
- Preserves model identity and outfit details
- Generates smooth, professional fashion presentation videos
- Outputs in 1080p resolution, 16:9 aspect ratio, 8-second duration

## Prerequisites

### Google Cloud Requirements

- Active Google Cloud Project with billing enabled
- Required APIs enabled:
    - Vertex AI API
    - Generative Language API
    - Cloud Storage API
- Proper authentication configured:
    - Local: `gcloud auth application-default login`
    - Vertex AI Workbench: Automatic authentication

### Preparing Input Images

Before running the notebook end-to-end, copy the sample dress images from the
`dress/` folder to your Google Cloud Storage bucket:

```bash
# Copy all sample dress images to your GCS bucket
gsutil cp dress/*.png gs://YOUR_BUCKET_NAME/dress/
```

The notebook configuration uses `OUTFITS_PREFIX = "dress"` to specify where it
looks for input dress images.

### Storage Setup

Google Cloud Storage bucket with structure:

```text
your-bucket/
├── Model_Creation.csv        # Generated model definitions
├── models/                   # Generated base model images
├── dress/                    # Input garment images (copied from dress/ folder)
│   ├── blue-front.png
│   ├── multi-front.png
│   ├── pink-front.png
│   ├── red-front.png
│   └── ...
├── dress/4tryon/            # VTO output images
├── dress/4tryon/final/      # Selected best VTO images
│   └── eval_summary.csv     # Critique results
└── dress/4tryon/final_motion/ # Generated videos
```

## Installation

1.  **Create Python Environment**

```bash
python -m venv venv
source venv/bin/activate  # On Linux/macOS
# OR
.\venv\Scripts\activate   # On Windows
```

1.  **Install Dependencies**

```bash
pip install --require-hashes -r requirements.txt
```

## Configuration

Update the following variables in the notebook's configuration cell:

```python
# Project Settings
PROJECT_ID = "your-project-id"
LOCATION = "us-central1"
BUCKET_NAME = "your-bucket-name"

# Processing Parameters
NUM_MODELS_TO_GENERATE = 5      # Number of diverse models
PARALLEL_JOBS_PER_MODEL = 10    # Concurrent VTO jobs
VTO_VARIATIONS = 4               # Candidates per try-on

# Model Versions (update as needed)
MODEL_TEXT = "gemini-2.5-flash"
MODEL_IMAGE_GEN = "gemini-2.5-flash-image"
MODEL_ID_VTO = "virtual-try-on-001"
MODEL_VIDEO = "veo-3.0-generate-001"
```

## Usage

1.  **Open the Notebook**

- Launch `VTO_GenMedia_Workflow.ipynb` in Jupyter or Vertex AI Workbench

1.  **Run Configuration Cell**

- Ensure all parameters are correctly set for your environment

1.  **Execute Pipeline Steps**

- Run cells sequentially to process the complete workflow
- Monitor progress through console outputs

1.  **Access Results**

- Final VTO images: `gs://your-bucket/dress/4tryon/final/`
- Motion videos: `gs://your-bucket/dress/4tryon/final_motion/`
- Evaluation summary: `gs://your-bucket/dress/4tryon/final/eval_summary.csv`
