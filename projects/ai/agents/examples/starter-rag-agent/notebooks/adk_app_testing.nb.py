# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.18.1
#   kernelspec:
#     display_name: myagent-1762384391
#     language: python
#     name: python3
# ---

# %%
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# %% [markdown]
# # 🧪 ADK Application Testing
#
# This notebook demonstrates how to test an ADK (Agent Development Kit) application.
# It covers both local and remote testing, both with Agent Engine and Cloud Run.
#
# > **Note**: This notebook assumes that the agent files are stored in the `app` folder. If your agent files are located in a different directory, please update all relevant file paths and references accordingly.

# %% [markdown]
# ## Set Up Your Environment
#
# > **Note:** For best results, use the same `.venv` created for local development with `uv` to ensure dependency compatibility and avoid environment-related issues.

# %%
# Uncomment the following lines if you're not using the virtual environment created by uv
# import sys

# sys.path.append("../")
# # !pip install google-cloud-aiplatform a2a-sdk --upgrade

# %% [markdown]
# ### Import libraries

# %%
import json

import requests
import vertexai

# %% [markdown]
# ### Initialize Vertex AI Client

# %%
# Initialize the Vertex AI client
LOCATION = "us-central1"

client = vertexai.Client(
    location=LOCATION,
)

# %% [markdown]
# ## If you are using Agent Engine
# See more documentation at [Agent Engine Overview](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/overview)

# %% [markdown]
# ### Remote Testing

# %%
# Set to None to auto-detect from ./deployment_metadata.json, or specify manually
# "projects/PROJECT_ID/locations/us-central1/reasoningEngines/ENGINE_ID"
REASONING_ENGINE_ID = None

if REASONING_ENGINE_ID is None:
    try:
        with open("../deployment_metadata.json") as f:
            metadata = json.load(f)
            REASONING_ENGINE_ID = metadata.get("remote_agent_engine_id")
    except (FileNotFoundError, json.JSONDecodeError):
        pass

print(f"Using REASONING_ENGINE_ID: {REASONING_ENGINE_ID}")
# Get the existing agent engine
remote_agent_engine = client.agent_engines.get(name=REASONING_ENGINE_ID)


# %%
async for event in remote_agent_engine.async_stream_query(
    message="hi!", user_id="test"
):
    print(event)


# %%
remote_agent_engine.register_feedback(
    feedback={
        "score": 5,
        "text": "Great response!",
        "user_id": "test-user-123",
        "session_id": "test-session-123",
    }
)

# %% [markdown]
# ### Local Testing
#
# You can import directly the AgentEngineApp class within your environment. 
# To run the agent locally, follow these steps:
# 1. Make sure all required packages are installed in your environment
# 2. The recommended approach is to use the same virtual environment created by the 'uv' tool
# 3. You can set up this environment by running 'make install' from your agent's root directory
# 4. Then select this kernel (.venv folder in your project) in your Jupyter notebook to ensure all dependencies are available

# %%
from app.agent_engine_app import agent_engine

agent_engine.set_up()


# %%
async for event in agent_engine.async_stream_query(
    message="hi!", user_id="test"
):
    print(event)


# %% [markdown]
# ## If you are using Cloud Run

# %% [markdown]
# #### Remote Testing
#
# For more information about authenticating HTTPS requests to Cloud Run services, see:
# [Cloud Run Authentication Documentation](https://cloud.google.com/run/docs/triggering/https-request)
#
# Remote testing involves using a deployed service URL instead of localhost.
#
# Authentication is handled using GCP identity tokens instead of local credentials.

# %%
ID_TOKEN = get_ipython().getoutput("gcloud auth print-identity-token -q")[0]

# %%
SERVICE_URL = "YOUR_SERVICE_URL_HERE"  # Replace with your Cloud Run service URL

# %% [markdown]
# You'll need to first create a Session

# %%
user_id = "test_user_123"
session_data = {"state": {"preferred_language": "English", "visit_count": 1}}

session_url = f"{SERVICE_URL}/apps/app/users/{user_id}/sessions"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {ID_TOKEN}",
}

session_response = requests.post(
    session_url, headers=headers, json=session_data
)
print(f"Session creation status code: {session_response.status_code}")
print(f"Session creation response: {session_response.json()}")
session_id = session_response.json()["id"]

# %% [markdown]
# Then you will be able to send a message

# %%
message_data = {
    "app_name": "app",
    "user_id": user_id,
    "session_id": session_id,
    "new_message": {
        "role": "user",
        "parts": [{"text": "Hello! Weather in New york?"}],
    },
    "streaming": True,
}

message_url = f"{SERVICE_URL}/run_sse"
message_response = requests.post(
    message_url, headers=headers, json=message_data, stream=True
)

print(f"Message send status code: {message_response.status_code}")

# Print streamed response
for line in message_response.iter_lines():
    if line:
        line_str = line.decode("utf-8")
        if line_str.startswith("data: "):
            event_json = line_str[6:]
            event = json.loads(event_json)
            print(f"Received event: {event}")

# %% [markdown]
# ### Local Testing
#
# > You can run the application locally via the `make local-backend` command.

# %% [markdown]
# #### Create a session
#  Create a new session with user preferences and state information
#

# %%
user_id = "test_user_123"
session_data = {"state": {"preferred_language": "English", "visit_count": 1}}

session_url = f"http://127.0.0.1:8000/apps/app/users/{user_id}/sessions"
headers = {"Content-Type": "application/json"}

session_response = requests.post(
    session_url, headers=headers, json=session_data
)
print(f"Session creation status code: {session_response.status_code}")
print(f"Session creation response: {session_response.json()}")
session_id = session_response.json()["id"]

# %% [markdown]
# #### Send a message
# Send a message to the backend service and receive a streaming response
#

# %%
message_data = {
    "app_name": "app",
    "user_id": user_id,
    "session_id": session_id,
    "new_message": {
        "role": "user",
        "parts": [{"text": "Hello! Weather in New york?"}],
    },
    "streaming": True,
}

message_url = "http://127.0.0.1:8000/run_sse"
message_response = requests.post(
    message_url, headers=headers, json=message_data, stream=True
)

print(f"Message send status code: {message_response.status_code}")

# Print streamed response
for line in message_response.iter_lines():
    if line:
        line_str = line.decode("utf-8")
        if line_str.startswith("data: "):
            event_json = line_str[6:]
            event = json.loads(event_json)
            print(f"Received event: {event}")

