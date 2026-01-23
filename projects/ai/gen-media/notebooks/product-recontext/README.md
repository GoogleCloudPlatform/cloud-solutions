# Product Image Recontextualization

## Author

Layolin Jesudhass

## Overview

Product Image Recontextualization is an AI-powered solution that transforms
standard product photos into engaging lifestyle images using Google's
Generative AI models.

### Notebook

**`product_recontext_gcs.ipynb` - Product Image Recontextualization Pipeline**

- Works with Google Cloud Storage (GCS) for scalable processing
- Designed for processing product images at scale
- Ideal for customer demonstrations and production workflows
- Handles bulk processing with parallel execution
- Includes comprehensive evaluation and quality scoring

## Features

- Transform product images into lifestyle/contextual scenes
- Batch processing capabilities for multiple products
- Quality evaluation system with 6-dimensional scoring
- Support for multiple input images per product (up to 3)
- Automated retry logic for API resilience

## Getting Started

### Prerequisites

Before you begin, ensure you have the following requirements:

- Python 3.8 or higher
- Required dependencies (see requirements.txt)
- Google Cloud Project with Vertex AI API enabled
- Google Cloud SDK (for GCS notebook)

### Installation

1.  Clone the repository:

    ```bash
    git clone <repository-url>
    cd product-recontext
    ```

1.  Install dependencies:

    ```bash
    pip install --require-hashes -r requirements.txt
    ```

### Usage

**Using the Product Recontextualization Pipeline:**

1.  Upload your product images to a GCS bucket
1.  Organize images in folders (one folder per product):

    ```text
    gs://your-bucket/product_images_input/
    ├── product1/
    ├── product2/
    └── product3/
    ```

1.  Configure the notebook with your GCS bucket and project ID
1.  Run the pipeline to process all products in parallel
1.  Results are saved to GCS in the output folder

**Sample Images Available:**

The repository includes sample product images in `./images/product_images_input/`:

- product1/ - Sample fashion items
- product2/ - Sample accessories
- product3/ - Sample products

To use these samples, upload them to your GCS bucket before running the notebook.

## Project Structure

```text
product-recontext/
├── README.md                       # This file
├── product_recontext_gcs.ipynb    # Main notebook for GCS processing
├── product_recontext_gcs.nb.py    # Python script version of notebook
├── requirements.txt                # Python dependencies
├── requirements.in                 # Base Python dependencies
├── jupytext.toml                  # Notebook synchronization config
├── CODEOWNERS                      # GitHub code ownership file
└── images/                         # Sample images for demo
    ├── product_images_input/      # Sample input images
    │   ├── product1/              # Sample product 1
    │   ├── product2/              # Sample product 2
    │   └── product3/              # Sample product 3
    └── product_images_output/     # Placeholder for outputs

```
