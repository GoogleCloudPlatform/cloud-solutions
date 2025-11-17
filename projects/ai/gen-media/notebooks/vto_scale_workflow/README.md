# Virtual Try-On (VTO) Scale Workflow

A comprehensive, end-to-end pipeline for generating diverse, photorealistic
Virtual Try-On (VTO) images and motion videos using Google's Generative AI
models on Vertex AI.

## Overview

This project demonstrates a scalable workflow for fashion e-commerce
applications that:

- Generates diverse digital models with various demographics
- Performs high-fidelity virtual garment try-on
- Adds realistic motion to showcase garments in runway-style videos
- Processes inputs at scale from CSV files using Google Cloud Storage

## Key Features

### 🎯 Multi-Model AI Pipeline

- **Model Generation**: Creates photorealistic digital models with diverse
  demographics (race, body type, age)
- **Virtual Try-On**: Performs garment swapping using Vertex AI's VTO model
- **AI Critique**: Automatically selects best results using Gemini for quality
  assessment
- **Motion Synthesis**: Generates runway walk videos to showcase garments in
  motion
- **Scalable Architecture**: Processes batch inputs from CSV with parallel
  execution

### 🔧 Technologies Used

- **Google Vertex AI**: Primary platform for all AI operations
- **Gemini 2.5 Flash**: Orchestration, prompt generation, and quality critique
- **Gemini 2.5 Flash Image**: Digital model image generation
- **Vertex AI Virtual Try-On**: High-fidelity garment transfer
- **Veo 3.0**: Video generation for motion synthesis
- **Google Cloud Storage**: Asset management and storage

## Project Structure

```text
vto_scale_workflow/
├── LJ_GenMedia_Workflow.ipynb   # Main Jupyter notebook with complete pipeline
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

### Storage Setup

Google Cloud Storage bucket with structure:

```text
your-bucket/
├── Model_Creation.csv        # Generated model definitions
├── models/                   # Generated base model images
├── Dress/                    # Input garment images
│   ├── dress1.png
│   ├── dress2.png
│   └── ...
├── Dress/4tryon/            # VTO output images
├── Dress/4tryon/final/      # Selected best VTO images
│   └── eval_summary.csv     # Critique results
└── Dress/4tryon/final_motion/ # Generated videos
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
pip install -r requirements.txt
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
MODEL_ID_VTO = "virtual-try-on-preview-08-04"
MODEL_VIDEO = "veo-3.0-generate-001"
```

## Usage

1.  **Open the Notebook**

- Launch `LJ_GenMedia_Workflow.ipynb` in Jupyter or Vertex AI Workbench

1.  **Run Configuration Cell**

- Ensure all parameters are correctly set for your environment

1.  **Execute Pipeline Steps**

- Run cells sequentially to process the complete workflow
- Monitor progress through console outputs

1.  **Access Results**

- Final VTO images: `gs://your-bucket/Dress/4tryon/final/`
- Motion videos: `gs://your-bucket/Dress/4tryon/final_motion/`
- Evaluation summary: `gs://your-bucket/Dress/4tryon/final/eval_summary.csv`

## Performance Considerations

- **Parallel Processing**: Utilizes ThreadPoolExecutor for concurrent operations
- **Retry Mechanism**: Automatic retry for failed VTO attempts (3 attempts by
  default)
- **Batch Processing**: Efficient handling of multiple model-outfit combinations
- **Resource Management**: Configurable worker limits to control API usage

## Output Examples

### Generated Assets

- **Model Images**: Diverse digital models in standardized outfit
- **VTO Images**: High-quality garment transfers on each model
- **Motion Videos**: 8-second runway walk showcasing garments
- **Evaluation CSV**: Detailed critique results with selection reasoning

### Quality Metrics

The AI critique evaluates:

- Garment transfer completeness
- Fabric texture preservation
- Fit accuracy and realism
- Absence of visual artifacts
- Body proportion maintenance

## Troubleshooting

### Common Issues

1.  **Authentication Errors**

- Ensure proper GCP authentication
- Verify project permissions

1.  **API Quotas**

- Monitor Vertex AI quotas
- Adjust `PARALLEL_JOBS_PER_MODEL` if needed

1.  **Storage Access**

- Verify bucket exists and is accessible
- Check file paths and prefixes

1.  **Model Availability**

- Confirm model versions are available in your region
- Update model IDs if using newer versions

## Dependencies

Core requirements (see `requirements.txt`):

- `pandas==2.2.2` - Data manipulation
- `Pillow==11.1.0` - Image processing
- `google-genai==1.45.0` - Generative AI SDK
- `google-cloud-storage==2.19.0` - GCS operations
- `google-cloud-aiplatform==1.74.0` - Vertex AI integration

## License

This project is for demonstration purposes. Please ensure compliance with Google
Cloud's terms of service and any applicable licensing requirements for
production use.

## Contributing

This is a demonstration workflow. For production implementations, consider:

- Error handling enhancements
- Monitoring and logging integration
- Cost optimization strategies
- Custom quality assessment metrics
- Extended diversity parameters

## Support

For issues related to:

- Google Cloud setup: Consult
  [Google Cloud Documentation](https://cloud.google.com/docs)
- Vertex AI models: See
  [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- Code issues: Review the notebook comments and inline documentation

## Acknowledgments

Created on 11/12/2025 using Google's suite of Generative AI models on Vertex AI
platform.

### Author: Layolin Jesudhass
