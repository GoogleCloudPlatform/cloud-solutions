# MovieLenz

A comprehensive video evaluation and prompt optimization framework powered by
AI. MovieLenz provides three main capabilities:

1.  **Video Evaluation**: Assess video quality against text queries using UVQ
    and VQA metrics
1.  **Prompt Creation**: Generate optimized prompts for video generation
1.  **Prompt Optimization**: Iteratively refine prompts based on video feedback

## Overview

MovieLenz combines prompt optimization, video quality assessment (VQA), and
machine learning models to provide a complete workflow for video generation and
evaluation:

- **Evaluate videos** against textual queries and visual inputs
- **Create optimized prompts** for video generation using DSG (Davidsonian Scene
  Graphs) and CMQ (Common Mistake Questions)
- **Optimize prompts** iteratively by analyzing generated videos and providing
  feedback

## Architecture

### High-Level Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│                            main.py                               │
│                    (CLI Entry Point)                             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                          runner.py                               │
│           (Orchestration & Temporary File Management)            │
└─────────────┬──────────────────────────────┬────────────────────┘
              │                              │
              ▼                              ▼
┌─────────────────────────────┐   ┌────────────────────────────────┐
│  prompt_optimizer_main.py   │   │     evaluate_media.py          │
│  (DSG/CMQ Question Gen)     │   │   (Video Evaluation Logic)     │
└──────────────┬──────────────┘   └────────────┬───────────────────┘
               │                               │
               ▼                               ▼
┌─────────────────────────────┐   ┌────────────────────────────────┐
│   llm_interaction_vertex.py │   │  uvq_pytorch/inference.py      │
│  (LLM API Calls)            │   │  (PyTorch Video Quality Model) │
└─────────────────────────────┘   └────────────────────────────────┘
```

### Component Details

#### 1. **main.py** - Command-Line Interface

- Entry point for the application
- Handles argument parsing and validation
- Manages input/output and logging configuration
- Provides user-friendly error messages

#### 2. **runner.py** - Orchestration Layer

- Core workflow orchestration
- Manages temporary file creation and cleanup
- Handles video and image byte conversion
- Coordinates between prompt optimization and evaluation modules
- **Key Function**: `run_evaluate_media_for_video_path()`
    - Input: Video query, video path/bytes, image path/bytes, duration, optional
      questions
    - Output: Evaluation results dictionary

#### 3. **prompt_optimizer_main.py** - Question Generation

- Generates Domain-Specific Generation (DSG) questions
- Generates Common Mistake Questions (CMQ)
- Uses LLM to optimize prompts based on video content
- **Key Function**: `get_dsg_cmq_questions()`

#### 4. **evaluate_media.py** - Video Evaluation

- Performs actual video quality assessment
- Integrates with PyTorch-based UVQ model
- Analyzes video against generated questions
- **Key Function**: `evaluate_video()`

#### 5. **llm_interaction_vertex.py** - LLM Integration

- Handles communication with Vertex AI LLM models
- Manages API calls and response parsing
- Provides prompt engineering utilities

#### 6. **uvq_pytorch/** - Video Quality Model

- PyTorch-based neural network models
- Includes:
    - `inference.py`: Model inference logic
    - `utils/`: Network components (aggregation, compression, content,
      distortion)
- Processes video frames and generates quality scores

#### 7. **video_reader.py** - Video Processing

- Reads and processes video files
- Extracts frames for analysis
- Handles various video formats

### Data Flow

1.  **Input**: User provides video query, video file, and start frame image
1.  **Prompt Optimization**: System generates DSG and CMQ questions (if not
    provided)
1.  **Video Processing**: Video is read and frames are extracted
1.  **Evaluation**: Video quality model analyzes content against questions
1.  **Output**: Results are returned as a structured dictionary

## Installation

### Prerequisites

- Python 3.10 or higher
- pip package manager
- Virtual environment (recommended)
- Google Cloud Project with Vertex AI API enabled
- Google Cloud authentication configured (Application Default Credentials)

### Setup

1.  Clone the repository:

```bash
git clone <repository-url>
cd movieLenz
```

1.  Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Linux/Mac
# or
venv\Scripts\activate     # On Windows
```

1.  Install dependencies:

```bash
pip install -r requirements.txt
```

1.  Configure environment variables:

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and set your Google Cloud project ID
# GOOGLE_CLOUD_PROJECT=your-project-id
```

1.  Set up Google Cloud authentication:

```bash
# Authenticate with Google Cloud
gcloud auth application-default login

# Set your project (replace with your actual project ID)
gcloud config set project YOUR_PROJECT_ID
```

**Note**: Ensure the Vertex AI API is enabled for your Google Cloud project.

## Usage

MovieLenz provides three operation modes through the `main.py` command-line
interface:

### Mode 1: Evaluate Videos

Assess video quality against a query using UVQ and VQA metrics.

**Basic Usage:**

```bash
python main.py evaluate --query "An old man frustrated about cleaning lawn" \
  --video-path test.mp4 \
  --image-path oldman_image.png
```

**With Custom Duration:**

```bash
python main.py evaluate --query "Dancing" \
  --video-path video.mp4 \
  --image-path start_frame.png \
  --duration 10
```

**With Custom Questions (JSON format):**

```bash
python main.py evaluate --query "Running in a park" \
  --video-path running.mp4 \
  --image-path runner.png \
  --dsg-questions '{"scene_graph":[{"id":"action_running","element_type":"action","description":"Person running","question":"Is the person running?","children":[]}]}' \
  --cmq-questions '{"common_mistakes_graph":[{"id":"mistake_static","element_type":"mistake_category","description":"Static person","question":"Is the person moving?","children":[]}]}'
```

**Save Results:**

```bash
python main.py evaluate --query "Cooking demonstration" \
  --video-path cooking.mp4 \
  --image-path chef.png \
  --output results.json \
  --pretty
```

### Mode 2: Create Optimized Prompts

Generate optimized prompts for video generation using AI and scene
understanding.

**Basic Usage:**

```bash
python main.py create --prompt "A person running in a park"
```

**With Visual Context:**

```bash
python main.py create --prompt "Dancing" \
  --start-frame start.png \
  --end-frame end.png \
  --duration 10
```

**With Technical Notes:**

```bash
python main.py create --prompt "Cooking demonstration" \
  --technical-notes "Professional kitchen, bright lighting, close-up shots" \
  --duration 15
```

**Save Output:**

```bash
python main.py create --prompt "Swimming in ocean" \
  --start-frame ocean.png \
  --output optimized_prompt.json \
  --pretty
```

### Mode 3: Optimize Prompts with Feedback

Iteratively optimize prompts by analyzing generated videos and providing
feedback.

**Basic Usage:**

```bash
python main.py optimize --prompt "Running" \
  --video-path run.mp4 \
  --start-frame start.png
```

**With Full Context:**

```bash
python main.py optimize --prompt "Dancing" \
  --video-path dance.mp4 \
  --start-frame start.png \
  --end-frame end.png \
  --duration 10 \
  --technical-notes "Contemporary dance style"
```

**Save Refined Prompt:**

```bash
python main.py optimize --prompt "Cooking" \
  --video-path cooking.mp4 \
  --start-frame chef.png \
  --output refined_prompt.json
```

### Question Format

Both DSG and CMQ questions must be provided as **JSON strings** with
hierarchical structures:

**DSG Questions** format:

```json
{
  "scene_graph": [
    {
      "id": "unique_id",
      "element_type": "agent|action|object|location|attribute",
      "description": "Brief description",
      "question": "Yes/no question where 'yes' indicates correct depiction",
      "children": [...]
    }
  ]
}
```

**CMQ Questions** format:

```json
{
  "common_mistakes_graph": [
    {
      "id": "unique_id",
      "element_type": "mistake_category|specific_mistake",
      "description": "Brief description of potential mistake",
      "question": "Yes/no question where 'yes' means no mistake present",
      "children": [...]
    }
  ]
}
```

If not provided, these questions are automatically generated by the system.

### Command-Line Arguments

**Global Options** (available for all modes):

| Argument    | Short | Description                              |
| ----------- | ----- | ---------------------------------------- |
| `--output`  | `-o`  | Output file path to save results as JSON |
| `--verbose` | -     | Enable verbose logging                   |
| `--pretty`  | -     | Pretty-print JSON output                 |

**Evaluate Mode**:

| Argument          | Short | Required | Default        | Description                  |
| ----------------- | ----- | -------- | -------------- | ---------------------------- |
| `--query`         | `-q`  | Yes      | -              | Video query/description text |
| `--video-path`    | `-v`  | Yes      | -              | Path to the video file       |
| `--image-path`    | `-i`  | Yes      | -              | Path to the input image file |
| `--duration`      | `-d`  | No       | 8              | Video duration in seconds    |
| `--dsg-questions` | -     | No       | Auto-generated | DSG questions (JSON string)  |
| `--cmq-questions` | -     | No       | Auto-generated | CMQ questions (JSON string)  |

**Create Mode**:

| Argument            | Short | Required | Description                       |
| ------------------- | ----- | -------- | --------------------------------- |
| `--prompt`          | `-p`  | Yes      | Initial prompt to optimize        |
| `--start-frame`     | -     | No       | Path to start frame image         |
| `--end-frame`       | -     | No       | Path to end frame image           |
| `--duration`        | `-d`  | No       | Target video duration in seconds  |
| `--technical-notes` | -     | No       | Technical notes or creative brief |

**Optimize Mode**:

| Argument            | Short | Required | Description                            |
| ------------------- | ----- | -------- | -------------------------------------- |
| `--prompt`          | `-p`  | Yes      | Initial prompt to optimize             |
| `--video-path`      | `-v`  | Yes      | Path to video for feedback             |
| `--start-frame`     | -     | No       | Path to start frame image              |
| `--end-frame`       | -     | No       | Path to end frame image                |
| `--duration`        | `-d`  | No       | Video duration in seconds (default: 8) |
| `--technical-notes` | -     | No       | Technical notes or creative brief      |

### Programmatic Usage

You can also use MovieLenz programmatically in your Python code:

```python
import runner

# Using file paths
results = runner.run_evaluate_media_for_video_path(
    video_query="An old man frustrated about cleaning lawn",
    video_path="test.mp4",
    input_image_path="oldman_image.png",
    duration=5
)

print(results)
```

```python
# Using bytes (e.g., from an API or database)
with open("video.mp4", "rb") as f:
    video_bytes = f.read()

with open("image.png", "rb") as f:
    image_bytes = f.read()

results = runner.run_evaluate_media_for_video_path(
    video_query="Cooking demonstration",
    video_bytes=video_bytes,
    input_image_bytes=image_bytes,
    duration=10
)
```

```python
# With custom questions (must be JSON strings)
import json

dsg_questions_json = json.dumps({
    "scene_graph": [{
        "id": "action_running",
        "element_type": "action",
        "description": "Person running",
        "question": "Is the person running?",
        "children": []
    }]
})

cmq_questions_json = json.dumps({
    "common_mistakes_graph": [{
        "id": "mistake_walking",
        "element_type": "specific_mistake",
        "description": "Person walking instead of running",
        "question": "Is the person running and not walking?",
        "children": []
    }]
})

results = runner.run_evaluate_media_for_video_path(
    video_query="Running",
    video_path="running.mp4",
    input_image_path="runner.png",
    duration=8,
    dsg_questions=dsg_questions_json,
    common_mistake_questions=cmq_questions_json
)
```

## Testing

### Running Tests

MovieLenz includes a comprehensive test suite for the `runner.py` module.

Run all tests:

```bash
python -m unittest tests/test_runner.py -v
```

Run with pytest (if installed):

```bash
pytest tests/test_runner.py -v
```

### Test Coverage

The test suite includes:

- Unit tests for all input variations (paths vs bytes)
- Error handling tests (missing inputs)
- Cleanup verification (temporary file removal)
- Integration tests with mocked dependencies
- Prompt optimization workflow tests

## Project Structure

```text
movieLenz/
├── main.py                      # CLI entry point
├── runner.py                    # Core orchestration logic
├── evaluate_media.py            # Video evaluation module
├── prompt_optimizer_main.py     # Question generation
├── prompt_optimizer.py          # Prompt optimization utilities
├── llm_interaction_vertex.py    # LLM API integration
├── video_reader.py              # Video processing utilities
├── utils.py                     # General utilities
├── metrics.py                   # Evaluation metrics
├── metrics_factory.py           # Metrics creation
├── prompts.py                   # Prompt templates
├── requirements.txt             # Python dependencies
├── README.md                    # This file
├── tests/
│   ├── __init__.py
│   └── test_runner.py          # Test suite for runner.py
└── uvq_pytorch/                # PyTorch video quality model
    ├── inference.py
    └── utils/
        ├── aggregationnet.py
        ├── compressionnet.py
        ├── contentnet.py
        └── distortionnet.py
```

## Key Features

- **Three Operation Modes**: Evaluate videos, create optimized prompts, or
  refine prompts with feedback
- **Flexible Input**: Accepts both file paths and byte streams
- **Automatic Cleanup**: Temporary files are automatically removed
- **AI-Powered Optimization**: Automatically generates DSG and CMQ questions for
  comprehensive evaluation
- **Iterative Refinement**: Optimize prompts based on actual video generation
  results
- **Error Handling**: Comprehensive validation and error messages
- **Configurable**: Supports custom questions, technical notes, and duration
- **CLI & API**: Use via command-line or Python imports
- **Multi-Format Output**: JSON output with optional pretty-printing

## Output Format

### Evaluate Mode Output

Video evaluation results with UVQ and VQA metrics:

```json
{
  "woz-uvq": {
    "compression_content_distortion": 0.87,
    "compression_content": 0.92,
    "content_distortion": 0.85,
    "compression_distortion": 0.88
  },
  "woz-vqa": {
    "Refined Prompt": "Detailed optimized version of the original prompt",
    "Evaluation Score": 0.85,
    "Feedback": "Detailed feedback about video quality, how well it matches the prompt, and suggestions for improvement"
  }
}
```

**Fields:**

- `woz-uvq`: Universal Video Quality scores analyzing compression, content, and
  distortion features
- `woz-vqa`: Video Quality Assessment with refined prompt, score (0-1 ratio),
  and feedback

### Create Mode Output

Optimized prompt for video generation:

```json
{
  "original_prompt": "A person running",
  "optimized_prompt": "A fit adult person running energetically through a lush green park during golden hour. The runner maintains steady pace with proper form, arms pumping rhythmically. Background shows trees and walking paths with natural lighting creating dynamic shadows.",
  "duration": 10,
  "technical_notes": null
}
```

**Fields:**

- `original_prompt`: The initial prompt provided
- `optimized_prompt`: AI-enhanced prompt with detailed scene description
- `duration`: Target video duration
- `technical_notes`: Optional technical specifications

### Optimize Mode Output

Refined prompt based on video feedback:

```json
{
  "result": "Refined Prompt:\nA person dancing with improved fluidity...\n\nEvaluation Score: 0.78\n\nFeedback:\nThe video shows good adherence to the prompt..."
}
```

**Fields:**

- `result`: Combined output with refined prompt, evaluation score, and detailed
  feedback

## Dependencies

Key dependencies include:

- **PyTorch**: Neural network models
- **OpenCV**: Video processing
- **Google Cloud AI Platform**: LLM integration
- **NumPy/Pandas**: Data processing
- **MoviePy**: Video manipulation
- **ImageIO**: Image/video I/O

See `requirements.txt` for the complete list.

## Error Handling

The system includes robust error handling:

- **File Validation**: Checks if files exist before processing
- **Input Validation**: Ensures required parameters are provided
- **Cleanup Guarantees**: Temporary files are removed even on errors
- **Informative Messages**: Clear error messages for troubleshooting

## Performance Considerations

- Temporary files are used for byte inputs to ensure compatibility with video
  processing libraries
- Files are automatically cleaned up in finally blocks
- Video processing duration affects total runtime
- Model inference is GPU-accelerated when available

## Support

For issues, questions, or contributions, please open an issue in the repository.

## License

[Specify your license here]

## Authors

@amanty and @brhemanth
