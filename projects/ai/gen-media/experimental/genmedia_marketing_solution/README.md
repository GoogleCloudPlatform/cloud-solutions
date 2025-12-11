# GenMedia Marketing Agent

This project implements a proactive, multi-step marketing agent
using the Google Agent Development Kit (ADK). The agent assists
business owners by executing a complete marketing campaign workflow,
from trend analysis to final content creation.

## Getting Started

These instructions will get you a copy of the project
up and running on your local machine for development and testing.

### Prerequisites

* Python 3.13+
* Pip (Python package installer)
* Google Cloud SDK (for `gcloud` authentication)

### Installation & Setup

#### Step 1: Clone the Repository

Clone the project repository to your local machine.

```bash
git clone <your-repository-url>
cd genmedia_marketing_solutions
```

#### Step 2: Configure Environment Variables

Copy the example `.env.example` file to a new `.env` file and
update it with your specific Google Cloud project details.

```bash
cp .env.example .env

Now,edit the `.env` file and provide values for the following variables:

* `GOOGLE_CLOUD_PROJECT`
* `GOOGLE_CLOUD_LOCATION`
* `GCS_BUCKET_NAME`
* `GEMINI_MODEL_NAME`
* `IMAGE_GEMINI_MODEL`
* `VEO_MODEL_ID`
* `VEO_API_ENDPOINT`
* `LYRIA_MODEL_ID`
* `BIGQUERY_DATASET_ID`
* `BIGQUERY_TABLE_ID`
```

#### Step 3: Set Up Virtual Environment

Create and activate a Python virtual environment. This ensures that
dependencies are managed in an isolated environment.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### Step 4: Authenticate with Google Cloud

Log in with your Google Cloud credentials to allow the application to access
Google Cloud services.

```bash
gcloud auth application-default login
```

#### Step 5: Install Dependencies

Install the required Python packages using the `requirements.txt` file.

```bash
pip install -r requirements.txt
```

#### Step 6: Run the Application

Start the ADK web server. It's recommended to run the `adk` command via its
direct path to avoid shell path issues.

```bash
./.venv/bin/adk web --port 8001
```

#### Step 7: Access the Web UI

Open your web browser and navigate to the ADK development UI
to interact with the agent:
[http://127.0.0.1:8001](http://127.0.0.1:8001)

## Project Structure

The project is organized as follows:

```text
├── .env.example          # Example environment variables
├── .gitignore            # Git ignore file
├── README.md             # This file
├── requirements.txt      # Python dependencies
└── src/
    ├── __init__.py
    ├── agent.py          # The main MarketingAgent
    ├── prompt.py         # Core instructions and workflow for the MarketingAgent
    ├── context/
    │   ├── __init__.py
    │   └── betty_context.py # Business context data for the demo
    ├── marketing_solutions/ # Modules for specific marketing tasks
    │   ├── generate_contents/
    │   │   ├── __init__.py
    │   │   └── content_generator.py
    │   ├── generate_trends/
    │   │   ├── __init__.py
    │   │   └── get_bakery_trends.py
    │   ├── generate_videos/
    │   │   ├── __init__.py
    │   │   └── video_generator.py
    │   └── generate_visuals/
    │       ├── __init__.py
    │       └── image_generator.py
    └── tools/
        ├── __init__.py
        ├── cmo_tools.py
        └── state_tools.py
```

## How it Works

The application orchestrates a 7-step marketing workflow. The agent will
pause at each step to wait for explicit user confirmation before proceeding.

1.  **Analyze Trends and Propose Product:** Analyze Google Trends data to
    identify local market opportunities and recommend viable new products.
1.  **Create Customer Segment:** After user approval, the agent creates a
    detailed customer segment for the proposed product.
1.  **Generate Marketing Image:** After customer segment approval, the agent
    generates a promotional image for the new product.
1.  **Generate Marketing Video:** After image approval, the agent generates a
    promotional video and background music. The agent can generate a single
    video or a sequence of up to 3 videos from different camera angles, which
    are then combined into a single video with music.
1.  **Generate Marketing Content:** After video approval, the agent drafts
    marketing copy (social media posts and email content) using the product,
    customer segment, and generated image.
1.  **Generate Outreach Strategy:** After marketing content approval, the agent
    generates a comprehensive outreach strategy.
1.  **Create Final Marketing Plan Document:** After outreach strategy approval,
    the agent compiles all generated content (marketing content, customer
    segment, and outreach strategy) into a final, downloadable PDF marketing
    plan document.

## Contributing

Contributions are welcome! Please feel free to submit a pull request.

## License

Copyright 2025 Google LLC
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
https://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
