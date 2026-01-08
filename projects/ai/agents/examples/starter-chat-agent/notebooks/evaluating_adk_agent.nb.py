# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.18.1
#   kernelspec:
#     display_name: Python 3
#     name: python3
# ---

# %% id="ur8xi4C7S06n"
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

# %% [markdown] id="JAPoU8Sm5E6e"
# # Evaluate your ADK agent using Vertex AI Gen AI Evaluation service
#
# <table align="left">
#   <td style="text-align: center">
#     <a href="https://colab.research.google.com/github/GoogleCloudPlatform/generative-ai/blob/main/gemini/evaluation/evaluating_adk_agent.ipynb">
#       <img width="32px" src="https://www.gstatic.com/pantheon/images/bigquery/welcome_page/colab-logo.svg" alt="Google Colaboratory logo"><br> Open in Colab
#     </a>
#   </td>
#   <td style="text-align: center">
#     <a href="https://console.cloud.google.com/vertex-ai/colab/import/https:%2F%2Fraw.githubusercontent.com%2FGoogleCloudPlatform%2Fgenerative-ai%2Fmain%2Fgemini%2Fevaluation%2Fevaluating_adk_agent.ipynb">
#       <img width="32px" src="https://lh3.googleusercontent.com/JmcxdQi-qOpctIvWKgPtrzZdJJK-J3sWE1RsfjZNwshCFgE_9fULcNpuXYTilIR2hjwN" alt="Google Cloud Colab Enterprise logo"><br> Open in Colab Enterprise
#     </a>
#   </td>
#   <td style="text-align: center">
#     <a href="https://console.cloud.google.com/vertex-ai/workbench/deploy-notebook?download_url=https://raw.githubusercontent.com/GoogleCloudPlatform/generative-ai/main/gemini/evaluation/evaluating_adk_agent.ipynb">
#       <img src="https://www.gstatic.com/images/branding/gcpiconscolors/vertexai/v1/32px.svg" alt="Vertex AI logo"><br> Open in Vertex AI Workbench
#     </a>
#   </td>
#   <td style="text-align: center">
#     <a href="https://github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/evaluation/evaluating_adk_agent.ipynb">
#       <img width="32px" src="https://www.svgrepo.com/download/217753/github.svg" alt="GitHub logo"><br> View on GitHub
#     </a>
#   </td>
# </table>
#
# <div style="clear: both;"></div>
#
# <b>Share to:</b>
#
# <a href="https://www.linkedin.com/sharing/share-offsite/?url=https%3A//github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/evaluation/evaluating_adk_agent.ipynb" target="_blank">
#   <img width="20px" src="https://upload.wikimedia.org/wikipedia/commons/8/81/LinkedIn_icon.svg" alt="LinkedIn logo">
# </a>
#
# <a href="https://bsky.app/intent/compose?text=https%3A//github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/evaluation/evaluating_adk_agent.ipynb" target="_blank">
#   <img width="20px" src="https://upload.wikimedia.org/wikipedia/commons/7/7a/Bluesky_Logo.svg" alt="Bluesky logo">
# </a>
#
# <a href="https://twitter.com/intent/tweet?url=https%3A//github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/evaluation/evaluating_adk_agent.ipynb" target="_blank">
#   <img width="20px" src="https://upload.wikimedia.org/wikipedia/commons/5/5a/X_icon_2.svg" alt="X logo">
# </a>
#
# <a href="https://reddit.com/submit?url=https%3A//github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/evaluation/evaluating_adk_agent.ipynb" target="_blank">
#   <img width="20px" src="https://redditinc.com/hubfs/Reddit%20Inc/Brand/Reddit_Logo.png" alt="Reddit logo">
# </a>
#
# <a href="https://www.facebook.com/sharer/sharer.php?u=https%3A//github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/evaluation/evaluating_adk_agent.ipynb" target="_blank">
#   <img width="20px" src="https://upload.wikimedia.org/wikipedia/commons/5/51/Facebook_f_logo_%282019%29.svg" alt="Facebook logo">
# </a>

# %% [markdown] id="84f0f73a0f76"
# | Author(s) |
# | --- |
# | [Ivan Nardini](https://github.com/inardini) |

# %% [markdown] id="tvgnzT1CKxrO"
# ## Overview
#
# Agent Development Kit (ADK in short) is a flexible and modular open source framework for developing and deploying AI agents. While ADK has its own evaluation module, using Vertex AI Gen AI Evaluation provides a toolkit of quality controlled and explainable methods and metrics to evaluate any generative model or application, including agents, and benchmark the evaluation results against your own judgment, using your own evaluation criteria.
#
# This tutorial shows how to evaluate an ADK agent using Vertex AI Gen AI Evaluation for agent evaluation.
#
# The steps performed include:
#
# * Build local agent using ADK
# * Prepare Agent Evaluation dataset
# * Single tool usage evaluation
# * Trajectory evaluation
# * Response evaluation

# %% [markdown] id="61RBz8LLbxCR"
# ## Get started

# %% [markdown] id="No17Cw5hgx12"
# ### Install Google Gen AI SDK and other required packages
#

# %% id="tFy3H3aPgx12"
# %pip install --upgrade --quiet 'google-adk'
# %pip install --upgrade --quiet 'google-cloud-aiplatform[evaluation]'

# %% [markdown] id="dmWOrTJ3gx13"
# ### Authenticate your notebook environment (Colab only)
#
# If you're running this notebook on Google Colab, run the cell below to authenticate your environment.

# %% id="NyKGtVQjgx13"
import sys

if "google.colab" in sys.modules:
    from google.colab import auth

    auth.authenticate_user()

# %% [markdown] id="DF4l8DTdWgPY"
# ### Set Google Cloud project information
#
# To get started using Vertex AI, you must have an existing Google Cloud project and [enable the Vertex AI API](https://console.cloud.google.com/flows/enableapi?apiid=aiplatform.googleapis.com).
#
# Learn more about [setting up a project and a development environment](https://cloud.google.com/vertex-ai/docs/start/cloud-environment).

# %% id="Nqwi-5ufWp_B"
# Use the environment variable if the user doesn't provide Project ID.
import os

import vertexai

PROJECT_ID = "[your-project-id]"  # @param {type: "string", placeholder: "[your-project-id]", isTemplate: true}
if not PROJECT_ID or PROJECT_ID == "[your-project-id]":
    PROJECT_ID = str(os.environ.get("GOOGLE_CLOUD_PROJECT"))

LOCATION = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")

BUCKET_NAME = "[your-bucket-name]"  # @param {type: "string", placeholder: "[your-bucket-name]", isTemplate: true}
BUCKET_URI = f"gs://{BUCKET_NAME}"

# !gcloud storage buckets create --location={LOCATION} {BUCKET_URI}

os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT_ID
os.environ["GOOGLE_CLOUD_LOCATION"] = LOCATION
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

EXPERIMENT_NAME = "evaluate-adk-agent"  # @param {type:"string"}

vertexai.init(project=PROJECT_ID, location=LOCATION, experiment=EXPERIMENT_NAME)

# %% [markdown] id="5303c05f7aa6"
# ## Import libraries
#
# Import tutorial libraries.

# %% id="6fc324893334"
import asyncio
import json

# General
import random
import string
from typing import Any

import pandas as pd
import plotly.graph_objects as go
from google.adk.agents import Agent

# Build agent with adk
from google.adk.events import Event
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

# Evaluate agent
from google.cloud import aiplatform
from google.genai import types
from IPython.display import HTML, Markdown, display
from vertexai.preview.evaluation import EvalTask
from vertexai.preview.evaluation.metrics import (
    PointwiseMetric,
    PointwiseMetricPromptTemplate,
    TrajectorySingleToolUse,
)


# %% [markdown] id="MVnBDX54gz7j"
# ## Define helper functions
#
# Initiate a set of helper functions to print tutorial results.

# %% id="uSgWjMD_g1_v"
def get_id(length: int = 8) -> str:
    """Generate a uuid of a specified length (default=8)."""
    return "".join(
        random.choices(string.ascii_lowercase + string.digits, k=length)
    )


def parse_adk_output_to_dictionary(
    events: list[Event], *, as_json: bool = False
):
    """
    Parse ADK event output into a structured dictionary format,
    with the predicted trajectory dumped as a JSON string.

    """

    final_response = ""
    trajectory = []

    for event in events:
        if not getattr(event, "content", None) or not getattr(
            event.content, "parts", None
        ):
            continue
        for part in event.content.parts:
            if getattr(part, "function_call", None):
                info = {
                    "tool_name": part.function_call.name,
                    "tool_input": dict(part.function_call.args),
                }
                if info not in trajectory:
                    trajectory.append(info)
            if event.content.role == "model" and getattr(part, "text", None):
                final_response = part.text.strip()

    if as_json:
        trajectory_out = json.dumps(trajectory)
    else:
        trajectory_out = trajectory

    return {"response": final_response, "predicted_trajectory": trajectory_out}


def format_output_as_markdown(output: dict) -> str:
    """Convert the output dictionary to a formatted markdown string."""
    markdown = "### AI Response\n" + output["response"] + "\n\n"
    if output["predicted_trajectory"]:
        markdown += "### Function Calls\n"
        for call in output["predicted_trajectory"]:
            markdown += f"- **Function**: `{call['tool_name']}`\n"
            markdown += "  - **Arguments**\n"
            for key, value in call["tool_input"].items():
                markdown += f"    - `{key}`: `{value}`\n"
    return markdown


def display_eval_report(eval_result: pd.DataFrame) -> None:
    """Display the evaluation results."""
    display(Markdown("### Summary Metrics"))
    display(
        pd.DataFrame(
            eval_result.summary_metrics.items(), columns=["metric", "value"]
        )
    )
    if getattr(eval_result, "metrics_table", None) is not None:
        display(Markdown("### Row‑wise Metrics"))
        display(eval_result.metrics_table.head())


def display_drilldown(row: pd.Series) -> None:
    """Displays a drill-down view for trajectory data within a row."""

    style = "white-space: pre-wrap; width: 800px; overflow-x: auto;"

    if not (
        isinstance(row["predicted_trajectory"], list)
        and isinstance(row["reference_trajectory"], list)
    ):
        return

    for predicted_trajectory, reference_trajectory in zip(
        row["predicted_trajectory"], row["reference_trajectory"]
    ):
        display(
            HTML(
                f"<h3>Tool Names:</h3><div style='{style}'>{predicted_trajectory['tool_name'], reference_trajectory['tool_name']}</div>"
            )
        )

        if not (
            isinstance(predicted_trajectory.get("tool_input"), dict)
            and isinstance(reference_trajectory.get("tool_input"), dict)
        ):
            continue

        for tool_input_key in predicted_trajectory["tool_input"]:
            print("Tool Input Key: ", tool_input_key)

            if tool_input_key in reference_trajectory["tool_input"]:
                print(
                    "Tool Values: ",
                    predicted_trajectory["tool_input"][tool_input_key],
                    reference_trajectory["tool_input"][tool_input_key],
                )
            else:
                print(
                    "Tool Values: ",
                    predicted_trajectory["tool_input"][tool_input_key],
                    "N/A",
                )
        print("\n")
    display(HTML("<hr>"))


def display_dataframe_rows(
    df: pd.DataFrame,
    columns: list[str] | None = None,
    num_rows: int = 3,
    display_drilldown: bool = False,
) -> None:
    """Displays a subset of rows from a DataFrame, optionally including a drill-down view."""

    if columns:
        df = df[columns]

    base_style = "font-family: monospace; font-size: 14px; white-space: pre-wrap; width: auto; overflow-x: auto;"
    header_style = base_style + "font-weight: bold;"

    for _, row in df.head(num_rows).iterrows():
        for column in df.columns:
            display(
                HTML(
                    f"<span style='{header_style}'>{column.replace('_', ' ').title()}: </span>"
                )
            )
            display(
                HTML(f"<span style='{base_style}'>{row[column]}</span><br>")
            )

        display(HTML("<hr>"))

        if (
            display_drilldown
            and "predicted_trajectory" in df.columns
            and "reference_trajectory" in df.columns
        ):
            display_drilldown(row)


def plot_bar_plot(
    eval_result: pd.DataFrame, title: str, metrics: list[str] = None
) -> None:
    fig = go.Figure()
    data = []

    summary_metrics = eval_result.summary_metrics
    if metrics:
        summary_metrics = {
            k: summary_metrics[k]
            for k, v in summary_metrics.items()
            if any(selected_metric in k for selected_metric in metrics)
        }

    data.append(
        go.Bar(
            x=list(summary_metrics.keys()),
            y=list(summary_metrics.values()),
            name=title,
        )
    )

    fig = go.Figure(data=data)

    # Change the bar mode
    fig.update_layout(barmode="group")
    fig.show()


def display_radar_plot(eval_results, title: str, metrics=None):
    """Plot the radar plot."""
    fig = go.Figure()
    summary_metrics = eval_results.summary_metrics
    if metrics:
        summary_metrics = {
            k: summary_metrics[k]
            for k, v in summary_metrics.items()
            if any(selected_metric in k for selected_metric in metrics)
        }

    min_val = min(summary_metrics.values())
    max_val = max(summary_metrics.values())

    fig.add_trace(
        go.Scatterpolar(
            r=list(summary_metrics.values()),
            theta=list(summary_metrics.keys()),
            fill="toself",
            name=title,
        )
    )
    fig.update_layout(
        title=title,
        polar=dict(radialaxis=dict(visible=True, range=[min_val, max_val])),
        showlegend=True,
    )
    fig.show()


# %% [markdown] id="bDaa2Mtsifmq"
# ## Build ADK agent
#
# Build your application using ADK, including the Gemini model and custom tools that you define.

# %% [markdown] id="KHwShhpOitKp"
# ### Set tools
#
# To start, set the tools that a customer support agent needs to do their job.

# %% id="gA2ZKvfeislw"
def get_product_details(product_name: str):
    """Gathers basic details about a product."""
    details = {
        "smartphone": "A cutting-edge smartphone with advanced camera features and lightning-fast processing.",
        "usb charger": "A super fast and light usb charger",
        "shoes": "High-performance running shoes designed for comfort, support, and speed.",
        "headphones": "Wireless headphones with advanced noise cancellation technology for immersive audio.",
        "speaker": "A voice-controlled smart speaker that plays music, sets alarms, and controls smart home devices.",
    }
    return details.get(product_name, "Product details not found.")


def get_product_price(product_name: str):
    """Gathers price about a product."""
    details = {
        "smartphone": 500,
        "usb charger": 10,
        "shoes": 100,
        "headphones": 50,
        "speaker": 80,
    }
    return details.get(product_name, "Product price not found.")


# %% [markdown] id="l4mk5XPui4Y1"
# ### Set the model
#
# Choose which Gemini AI model your agent will use. If you're curious about Gemini and its different capabilities, take a look at [the official documentation](https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models) for more details.

# %% id="BaYeo6K2i-w1"
model = "gemini-2.0-flash"


# %% [markdown] id="tNlAY9cojEWz"
# ### Assemble the agent
#
# The Vertex AI Gen AI Evaluation works directly with 'Queryable' agents, and also lets you add your own custom functions with a specific structure (signature).
#
# In this case, you assemble the agent using a custom function. The function triggers the agent for a given input and parse the agent outcome to extract the response and called tools.

# %% id="gD5OB44g4sc3"
async def agent_parsed_outcome(query):
    app_name = "product_research_app"
    user_id = "user_one"
    session_id = "session_one"

    product_research_agent = Agent(
        name="ProductResearchAgent",
        model=model,
        description="An agent that performs product research.",
        instruction=f"""
       Analyze this user request: '{query}'.
       If the request is about price, use get_product_price tool.
       Otherwise, use get_product_details tool to get product information.
       """,
        tools=[get_product_details, get_product_price],
    )

    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=app_name, user_id=user_id, session_id=session_id
    )

    runner = Runner(
        agent=product_research_agent,
        app_name=app_name,
        session_service=session_service,
    )

    content = types.Content(role="user", parts=[types.Part(text=query)])
    events = [
        event
        async for event in runner.run_async(
            user_id=user_id, session_id=session_id, new_message=content
        )
    ]

    return parse_adk_output_to_dictionary(events)

# %%
# --- Sync wrapper for Vertex‑AI evaluation


def agent_parsed_outcome_sync(prompt: str):
    result = asyncio.run(agent_parsed_outcome(prompt))
    result["predicted_trajectory"] = json.dumps(result["predicted_trajectory"])
    return result


# %% [markdown] id="_HGcs6PVjRj_"
# ### Test the agent
#
# Query your agent.

# %% id="lGb58OJkjUs9"
response = await agent_parsed_outcome(query="Get product details for shoes")
display(Markdown(format_output_as_markdown(response)))

# %% id="2wCFstt8w4Dx"
response = await agent_parsed_outcome(query="Get product price for shoes")
display(Markdown(format_output_as_markdown(response)))

# %% [markdown] id="aOGPePsorpUl"
# ## Evaluating a ADK agent with Vertex AI Gen AI Evaluation
#
# When working with AI agents, it's important to keep track of their performance and how well they're working. You can look at this in two main ways: **monitoring** and **observability**.
#
# Monitoring focuses on how well your agent is performing specific tasks:
#
# * **Single Tool Selection**: Is the agent choosing the right tools for the job?
#
# * **Multiple Tool Selection (or Trajectory)**: Is the agent making logical choices in the order it uses tools?
#
# * **Response generation**: Is the agent's output good, and does it make sense based on the tools it used?
#
# Observability is about understanding the overall health of the agent:
#
# * **Latency**: How long does it take the agent to respond?
#
# * **Failure Rate**: How often does the agent fail to produce a response?
#
# Vertex AI Gen AI Evaluation service helps you to assess all of these aspects both while you are prototyping the agent or after you deploy it in production. It provides [pre-built evaluation criteria and metrics](https://cloud.google.com/vertex-ai/generative-ai/docs/models/determine-eval) so you can see exactly how your agents are doing and identify areas for improvement.

# %% [markdown] id="e43229f3ad4f"
# ### Prepare Agent Evaluation dataset
#
# To evaluate your AI agent using the Vertex AI Gen AI Evaluation service, you need a specific dataset depending on what aspects you want to evaluate of your agent.  
#
# This dataset should include the prompts given to the agent. It can also contain the ideal or expected response (ground truth) and the intended sequence of tool calls the agent should take (reference trajectory) representing the sequence of tools you expect agent calls for each given prompt.
#
# > Optionally, you can provide both generated responses and predicted trajectory (**Bring-Your-Own-Dataset scenario**).
#
# Below you have an example of dataset you might have with a customer support agent with user prompt and the reference trajectory.

# %% id="fFf8uTdUiDt3"
eval_data = {
    "prompt": [
        "Get price for smartphone",
        "Get product details and price for headphones",
        "Get details for usb charger",
        "Get product details and price for shoes",
        "Get product details for speaker?",
    ],
    "predicted_trajectory": [
        [
            {
                "tool_name": "get_product_price",
                "tool_input": {"product_name": "smartphone"},
            }
        ],
        [
            {
                "tool_name": "get_product_details",
                "tool_input": {"product_name": "headphones"},
            },
            {
                "tool_name": "get_product_price",
                "tool_input": {"product_name": "headphones"},
            },
        ],
        [
            {
                "tool_name": "get_product_details",
                "tool_input": {"product_name": "usb charger"},
            }
        ],
        [
            {
                "tool_name": "get_product_details",
                "tool_input": {"product_name": "shoes"},
            },
            {
                "tool_name": "get_product_price",
                "tool_input": {"product_name": "shoes"},
            },
        ],
        [
            {
                "tool_name": "get_product_details",
                "tool_input": {"product_name": "speaker"},
            }
        ],
    ],
}

eval_sample_dataset = pd.DataFrame(eval_data)

# %% [markdown] id="PQEI1EcfvFHb"
# Print some samples from the dataset.

# %% id="EjsonqWWvIvE"
display_dataframe_rows(eval_sample_dataset, num_rows=3)

# %% [markdown] id="m4CvBuf1afHG"
# ### Single tool usage evaluation
#
# After you've set your AI agent and the evaluation dataset, you start evaluating if the agent is choosing the correct single tool for a given task.
#

# %% [markdown] id="_rS5GGKHd5bx"
# #### Set single tool usage metrics
#
# The `trajectory_single_tool_use` metric in Vertex AI Gen AI Evaluation gives you a quick way to evaluate whether your agent is using the tool you expect it to use, regardless of any specific tool order. It's a basic but useful way to start evaluating if the right tool was used at some point during the agent's process.
#
# To use the `trajectory_single_tool_use` metric, you need to set what tool should have been used for a particular user's request. For example, if a user asks to "send an email", you might expect the agent to use an "send_email" tool, and you'd specify that tool's name when using this metric.
#

# %% id="xixvq8dwd5by"
single_tool_usage_metrics = [
    TrajectorySingleToolUse(tool_name="get_product_price")
]

# %% [markdown] id="ktKZoT2Qd5by"
# #### Run an evaluation task
#
# To run the evaluation, you initiate an `EvalTask` using the pre-defined dataset (`eval_sample_dataset`) and metrics (`single_tool_usage_metrics` in this case) within an experiment. Then, you run the evaluation using agent_parsed_outcome function and assigns a unique identifier to this specific evaluation run, storing and visualizing the evaluation results.
#

# %% id="SRv43fDcd5by"
EXPERIMENT_RUN = f"single-metric-eval-{get_id()}"

single_tool_call_eval_task = EvalTask(
    dataset=eval_sample_dataset,
    metrics=single_tool_usage_metrics,
    experiment=EXPERIMENT_NAME,
    output_uri_prefix=BUCKET_URI + "/single-metric-eval",
)

single_tool_call_eval_result = single_tool_call_eval_task.evaluate(
    runnable=agent_parsed_outcome_sync, experiment_run_name=EXPERIMENT_RUN
)

display_eval_report(single_tool_call_eval_result)

# %% [markdown] id="6o5BjSTFKVMS"
# #### Visualize evaluation results
#
# Use some helper functions to visualize a sample of evaluation result.

# %% id="1Jopzw83k14w"
display_dataframe_rows(single_tool_call_eval_result.metrics_table, num_rows=3)

# %% [markdown] id="JlujdJpu5Kn6"
# ### Trajectory Evaluation
#
# After evaluating the agent's ability to select the single most appropriate tool for a given task, you generalize the evaluation by analyzing the tool sequence choices with respect to the user input (trajectory). This assesses whether the agent not only chooses the right tools but also utilizes them in a rational and effective order.

# %% [markdown] id="8s-nHdDJneHM"
# #### Set trajectory metrics
#
# To evaluate agent's trajectory, Vertex AI Gen AI Evaluation provides several ground-truth based metrics:
#
# * `trajectory_exact_match`: identical trajectories (same actions, same order)
#
# * `trajectory_in_order_match`: reference actions present in predicted trajectory, in order (extras allowed)
#
# * `trajectory_any_order_match`: all reference actions present in predicted trajectory (order, extras don't matter).
#
# * `trajectory_precision`: proportion of predicted actions present in reference
#
# * `trajectory_recall`: proportion of reference actions present in predicted.  
#
# All metrics score 0 or 1, except `trajectory_precision` and `trajectory_recall` which range from 0 to 1.

# %% id="c32WIS95neHN"
trajectory_metrics = [
    "trajectory_exact_match",
    "trajectory_in_order_match",
    "trajectory_any_order_match",
    "trajectory_precision",
    "trajectory_recall",
]

# %% [markdown] id="DF3jhTH3neHN"
# #### Run an evaluation task
#
# Submit an evaluation by running `evaluate` method of the new `EvalTask`.

# %% id="vOdS7TJUneHN"
EXPERIMENT_RUN = f"trajectory-{get_id()}"

trajectory_eval_task = EvalTask(
    dataset=eval_sample_dataset,
    metrics=trajectory_metrics,
    experiment=EXPERIMENT_NAME,
    output_uri_prefix=BUCKET_URI + "/multiple-metric-eval",
)

trajectory_eval_result = trajectory_eval_task.evaluate(
    runnable=agent_parsed_outcome_sync, experiment_run_name=EXPERIMENT_RUN
)

display_eval_report(trajectory_eval_result)

# %% [markdown] id="DBiUI3LyLBtj"
# #### Visualize evaluation results
#
# Print and visualize a sample of evaluation results.

# %% id="z7-LdM3mLBtk"
display_dataframe_rows(trajectory_eval_result.metrics_table, num_rows=3)

# %% id="sLVRdN5llA0h"
plot_bar_plot(
    trajectory_eval_result,
    title="Trajectory Metrics",
    metrics=[f"{metric}/mean" for metric in trajectory_metrics],
)

# %% [markdown] id="T8TipU2akHEd"
# ### Evaluate final response
#
# Similar to model evaluation, you can evaluate the final response of the agent using Vertex AI Gen AI Evaluation.

# %% [markdown] id="DeK-py7ykkDN"
# #### Set response metrics
#
# After agent inference, Vertex AI Gen AI Evaluation provides several metrics to evaluate generated responses. You can use computation-based metrics to compare the response to a reference (if needed) and using existing or custom model-based metrics to determine the quality of the final response.
#
# Check out the [documentation](https://cloud.google.com/vertex-ai/generative-ai/docs/models/determine-eval) to learn more.
#

# %% id="cyGHGgeVklvz"
response_metrics = ["safety", "coherence"]

# %% [markdown] id="DaBJWcg1kn55"
# #### Run an evaluation task
#
# To evaluate agent's generated responses, use the `evaluate` method of the EvalTask class.

# %% id="wRb2EC_hknSD"
EXPERIMENT_RUN = f"response-{get_id()}"

response_eval_task = EvalTask(
    dataset=eval_sample_dataset,
    metrics=response_metrics,
    experiment=EXPERIMENT_NAME,
    output_uri_prefix=BUCKET_URI + "/response-metric-eval",
)

response_eval_result = response_eval_task.evaluate(
    runnable=agent_parsed_outcome_sync, experiment_run_name=EXPERIMENT_RUN
)

display_eval_report(response_eval_result)

# %% [markdown] id="JtewTwiwg9qH"
# #### Visualize evaluation results
#
#
# Print new evaluation result sample.

# %% id="ZODTRuq2lF75"
display_dataframe_rows(response_eval_result.metrics_table, num_rows=3)

# %% [markdown] id="ntRBK3Te6PEc"
# ### Evaluate generated response conditioned by tool choosing
#
# When evaluating AI agents that interact with environments, standard text generation metrics like coherence may not be sufficient. This is because these metrics primarily focus on text structure, while agent responses should be assessed based on their effectiveness within the environment.
#
# Instead, use custom metrics that assess whether the agent's response logically follows from its tools choices like the one you have in this section.

# %% [markdown] id="4bENwFcd6prX"
# #### Define a custom metric
#
# According to the [documentation](https://cloud.google.com/vertex-ai/generative-ai/docs/models/determine-eval#model-based-metrics), you can define a prompt template for evaluating whether an AI agent's response follows logically from its actions by setting up criteria and a rating system for this evaluation.
#
# Define a `criteria` to set the evaluation guidelines and a `pointwise_rating_rubric` to provide a scoring system (1 or 0). Then use a `PointwiseMetricPromptTemplate` to create the template using these components.
#

# %% id="txGEHcg76riI"
criteria = {
    "Follows trajectory": (
        "Evaluate whether the agent's response logically follows from the "
        "sequence of actions it took. Consider these sub-points:\n"
        "  - Does the response reflect the information gathered during the trajectory?\n"
        "  - Is the response consistent with the goals and constraints of the task?\n"
        "  - Are there any unexpected or illogical jumps in reasoning?\n"
        "Provide specific examples from the trajectory and response to support your evaluation."
    )
}

pointwise_rating_rubric = {
    "1": "Follows trajectory",
    "0": "Does not follow trajectory",
}

response_follows_trajectory_prompt_template = PointwiseMetricPromptTemplate(
    criteria=criteria,
    rating_rubric=pointwise_rating_rubric,
    input_variables=["prompt", "predicted_trajectory"],
)

# %% [markdown] id="8MJqXu0kikxd"
# Print the prompt_data of this template containing the combined criteria and rubric information ready for use in an evaluation.

# %% id="5EL7iEDMikNQ"
print(response_follows_trajectory_prompt_template.prompt_data)

# %% [markdown] id="e1djVp7Fi4Yy"
# After you define the evaluation prompt template, set up the associated metric to evaluate how well a response follows a specific trajectory. The `PointwiseMetric` creates a metric where `response_follows_trajectory` is the metric's name and `response_follows_trajectory_prompt_template` provides instructions or context for evaluation you set up before.
#

# %% id="Nx1xbZD87iMj"
response_follows_trajectory_metric = PointwiseMetric(
    metric="response_follows_trajectory",
    metric_prompt_template=response_follows_trajectory_prompt_template,
)

# %% [markdown] id="1pmxLwTe7Ywv"
# #### Set response metrics
#
# Set new generated response evaluation metrics by including the custom metric.
#

# %% id="wrsbVFDd7Ywv"
response_tool_metrics = [
    "trajectory_exact_match",
    "trajectory_in_order_match",
    "safety",
    response_follows_trajectory_metric,
]

# %% [markdown] id="Lo-Sza807Ywv"
# #### Run an evaluation task
#
# Run a new agent's evaluation.

# %% id="_dkb4gSn7Ywv"
EXPERIMENT_RUN = f"response-over-tools-{get_id()}"

response_eval_tool_task = EvalTask(
    dataset=eval_sample_dataset,
    metrics=response_tool_metrics,
    experiment=EXPERIMENT_NAME,
    output_uri_prefix=BUCKET_URI + "/reasoning-metric-eval",
)

response_eval_tool_result = response_eval_tool_task.evaluate(
    # Uncomment the line below if you are providing the agent with an unparsed dataset
    # runnable=agent_parsed_outcome_sync,
    experiment_run_name=EXPERIMENT_RUN
)

display_eval_report(response_eval_tool_result)

# %% [markdown] id="AtOfIFi2j88g"
# #### Visualize evaluation results
#
# Visualize evaluation result sample.

# %% id="GH2YvXgLlLH7"
display_dataframe_rows(response_eval_tool_result.metrics_table, num_rows=3)

# %% id="tdVhCURXMdLG"
plot_bar_plot(
    response_eval_tool_result,
    title="Response Metrics",
    metrics=[f"{metric}/mean" for metric in response_tool_metrics],
)

# %% [markdown] id="4nuUDP3a2eTB"
# ## Bonus: Bring-Your-Own-Dataset (BYOD) and evaluate a LangGraph agent using Vertex AI Gen AI Evaluation
#
# In Bring Your Own Dataset (BYOD) [scenarios](https://cloud.google.com/vertex-ai/generative-ai/docs/models/evaluation-dataset), you provide both the predicted trajectory and the generated response from the agent.
#

# %% [markdown] id="DRLKlmWd27PK"
# ### Bring your own evaluation dataset
#
# Define the evaluation dataset with the predicted trajectory and the generated response.

# %% id="y9hBgsg324Ej"
byod_eval_data = {
    "prompt": [
        "Get price for smartphone",
        "Get product details and price for headphones",
        "Get details for usb charger",
        "Get product details and price for shoes",
        "Get product details for speaker?",
    ],
    "reference_trajectory": [
        [
            {
                "tool_name": "get_product_price",
                "tool_input": {"product_name": "smartphone"},
            }
        ],
        [
            {
                "tool_name": "get_product_details",
                "tool_input": {"product_name": "headphones"},
            },
            {
                "tool_name": "get_product_price",
                "tool_input": {"product_name": "headphones"},
            },
        ],
        [
            {
                "tool_name": "get_product_details",
                "tool_input": {"product_name": "usb charger"},
            }
        ],
        [
            {
                "tool_name": "get_product_details",
                "tool_input": {"product_name": "shoes"},
            },
            {
                "tool_name": "get_product_price",
                "tool_input": {"product_name": "shoes"},
            },
        ],
        [
            {
                "tool_name": "get_product_details",
                "tool_input": {"product_name": "speaker"},
            }
        ],
    ],
    "predicted_trajectory": [
        [
            {
                "tool_name": "get_product_price",
                "tool_input": {"product_name": "smartphone"},
            }
        ],
        [
            {
                "tool_name": "get_product_details",
                "tool_input": {"product_name": "headphones"},
            },
            {
                "tool_name": "get_product_price",
                "tool_input": {"product_name": "headphones"},
            },
        ],
        [
            {
                "tool_name": "get_product_details",
                "tool_input": {"product_name": "usb charger"},
            }
        ],
        [
            {
                "tool_name": "get_product_details",
                "tool_input": {"product_name": "shoes"},
            },
            {
                "tool_name": "get_product_price",
                "tool_input": {"product_name": "shoes"},
            },
        ],
        [
            {
                "tool_name": "get_product_details",
                "tool_input": {"product_name": "speaker"},
            }
        ],
    ],
    "response": [
        "500",
        "50",
        "A super fast and light usb charger",
        "100",
        "A voice-controlled smart speaker that plays music, sets alarms, and controls smart home devices.",
    ],
}

byod_eval_sample_dataset = pd.DataFrame(byod_eval_data)
byod_eval_sample_dataset["predicted_trajectory"] = byod_eval_sample_dataset[
    "predicted_trajectory"
].apply(json.dumps)
byod_eval_sample_dataset["reference_trajectory"] = byod_eval_sample_dataset[
    "reference_trajectory"
].apply(json.dumps)
byod_eval_sample_dataset["response"] = byod_eval_sample_dataset[
    "response"
].apply(json.dumps)

# %% [markdown] id="oEYmU2eJ7q-1"
# ### Run an evaluation task
#
# Run a new agent's evaluation using your own dataset and the same setting of the latest evaluation.

# %% id="wBD-4wpB7q-3"
EXPERIMENT_RUN_NAME = f"response-over-tools-byod-{get_id()}"

byod_response_eval_tool_task = EvalTask(
    dataset=byod_eval_sample_dataset,
    metrics=response_tool_metrics,
    experiment=EXPERIMENT_NAME,
    output_uri_prefix=BUCKET_URI + "/byod-eval",
)

byod_response_eval_tool_result = byod_response_eval_tool_task.evaluate(
    experiment_run_name=EXPERIMENT_RUN_NAME
)

display_eval_report(byod_response_eval_tool_result)

# %% [markdown] id="9eU3LG6r7q-3"
# ### Visualize evaluation results
#
# Visualize evaluation result sample.

# %% id="pQFzmd2I7q-3"
display_dataframe_rows(byod_response_eval_tool_result.metrics_table, num_rows=3)

# %% id="84HiPDOkPseW"
display_radar_plot(
    byod_response_eval_tool_result,
    title="ADK agent evaluation",
    metrics=[f"{metric}/mean" for metric in response_tool_metrics],
)

# %% [markdown] id="fIppkS2jq_Dn"
# ## Cleaning up
#

# %% id="Ox2I3UfRlTOd"
delete_experiment = True

if delete_experiment:
    try:
        experiment = aiplatform.Experiment(EXPERIMENT_NAME)
        experiment.delete(delete_backing_tensorboard_runs=True)
    except Exception as e:
        print(e)
