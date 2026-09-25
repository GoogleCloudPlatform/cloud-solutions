# Roman numeral converter

This sample Python Flask web application converts numbers to Roman numerals. It
demonstrates automated User Interface (UI) testing workflows with the Playwright
Model Context Protocol (MCP) server and AI assistants using Antigravity CLI.

## Features

- **Web User Interface**: Simple HTML forms for user input and result
  presentation.
- **Roman Numeral Conversion**: Converts integer inputs into Roman numeral
  strings.
- **Lightweight Stack**: Built using standard Python and Flask.

## Repository structure

```text
.
├── buildtest.dockerfile # Presubmit CI container test configuration
├── converter.py         # Logic for converting integers to Roman numerals
├── converter_test.py    # Unit tests for Roman numeral converter
├── main.py              # Flask web server and routing handlers
├── main_test.py         # Unit tests for Flask web application
├── requirements.in      # Top-level Python package dependencies
├── requirements.txt     # Locked Python package dependencies with hashes
├── templates/
│   ├── index.html       # Input form page
│   └── convert.html     # Results display page
└── README.md            # Project documentation
```

## Requirements

- Python 3.8 or higher
- `pip` package manager

## Getting started

### 1. Repository setup

Clone the repository and navigate to the application folder:

```bash
git clone https://github.com/GoogleCloudPlatform/cloud-solutions.git
cd cloud-solutions/projects/build-with-gemini-demo/automating-ui-tests-with-antigravity/roman-numeral-converter
```

If you already have this repository cloned locally, navigate directly to:

```bash
cd projects/build-with-gemini-demo/automating-ui-tests-with-antigravity/roman-numeral-converter
```

### 2. Set up a virtual environment

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows:

```cmd
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt --require-hashes
```

### 4. Run the application

```bash
python main.py
```

The application starts on port `8080` by default (or the port specified by the
`PORT` environment variable).

Access the application in your browser at:
[http://127.0.0.1:8080](http://127.0.0.1:8080)

## Application endpoints

- `GET /`: Renders `templates/index.html` featuring a numeric input form.
- `POST /convert`: Processes the form submission (`number`), calls
  `converter.number_to_roman(number)`, and renders `templates/convert.html` with
  the result.
