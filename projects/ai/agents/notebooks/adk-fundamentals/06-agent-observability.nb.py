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
#     language: python
#     name: python3
# ---

# %% [markdown]
# Copyright 2025 Google LLC.

# %%
# @title Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# %% [markdown]
# # 🔎 Agent Observability - Logs, Traces & Metrics
#
# ## What is Agent Observability?
#
# **🚨 The challenge:** Unlike traditional software that fails predictably, AI agents can fail mysteriously. Example:
#
# ```
# User: "Find quantum computing papers"
# Agent: "I cannot help with that request."
# You: 😭 WHY?? Is it the prompt? Missing tools? API error?
# ```
#
# **💡 The Solution:** Agent observability gives you complete visibility into your agent's decision-making process. You'll see exactly what prompts are sent to the LLM, which tools are available, how the model responds, and where failures occur.
#
# ```
# DEBUG Log: LLM Request shows "Functions: []" (no tools!)
# You: 🎯 Aha! Missing google_search tool - easy fix!
# ```
#
# ## Foundational pillars of Agent Observability
#
# 1. **Logs:** A log is a record of a single event, telling you **what** happened at a specific moment.
# 2. **Traces:** A trace connects the logs into a single story, showing you **why** a final result occurred by revealing the entire sequence of steps.
# 3. **Metrics:** Metrics are the summary numbers (like averages and error rates) that tell you **how** well the agent is performing overall.
#
# <center>
#     <img src="https://storage.googleapis.com/github-repo/kaggle-5days-ai/day4/observability-intro.png">
# </center>
#
# **In this notebook, you'll:**
#
# * ✅ Set up logging configuration
# * ✅ Create a broken agent. Use `adk web` UI & logs to identify exactly why the agent fails
# * ✅ Understand how to implement logging in production
# * ✅ Learn when to use built-in logging vs custom solutions

# %% [markdown]
# ## ⚙️ Section 1: Setup
#
# ### 1.1: Install dependencies

# %%
# %pip install -U -q 'google-adk'

# %% [markdown]
# ### 1.2: Restart runtime (Colab only)
#
# To use the newly installed packages in this Jupyter runtime, you must restart the runtime. You can do this by running the cell below, which restarts the current kernel.
#
# **Note:** If you're running locally in VS Code, you can skip this cell.

# %%
import sys

if "google.colab" in sys.modules:
    import IPython

    app = IPython.Application.instance()
    app.kernel.do_shutdown(True)

# %% [markdown]
# ### 1.3: Authenticate your notebook environment
#
# If you are running this notebook on Google Colab, run the cell below to authenticate your environment.

# %%
import sys

if "google.colab" in sys.modules:
    from google.colab import auth

    auth.authenticate_user()

# %% [markdown]
# ### 1.4: Set Google Cloud project information
#
# To get started using Vertex AI, you must have an existing Google Cloud project and [enable the Vertex AI API](https://console.cloud.google.com/flows/enableapi?apiid=aiplatform.googleapis.com).
#
# Learn more about [setting up a project and a development environment](https://cloud.google.com/vertex-ai/docs/start/cloud-environment).

# %%
import os

PROJECT_ID = "[your-project-id]"  # @param {type: "string", placeholder: "[your-project-id]", isTemplate: true}
LOCATION = "global"  # @param {type: "string", placeholder: "[your-region]", isTemplate: true}

# Set environment vars
os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT_ID
os.environ["GOOGLE_CLOUD_LOCATION"] = LOCATION
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "1"

print(f"✅ Using Vertex AI in project: {PROJECT_ID}")
print(f"✅ Region: {LOCATION}")

# %% [markdown]
# ### 1.5: Set up logging and cleanup old files
# Let's configure logging for our debugging session. The following cell makes sure we also capture other log levels, like DEBUG.

# %%
import logging
import os

# Clean up any previous logs
for log_file in ["logger.log", "web.log", "tunnel.log"]:
    if os.path.exists(log_file):
        os.remove(log_file)
        print(f"🧹 Cleaned up {log_file}")

# Configure logging with DEBUG log level.
logging.basicConfig(
    filename="logger.log",
    level=logging.DEBUG,
    format="%(filename)s:%(lineno)s %(levelname)s:%(message)s",
)

print("✅ Logging configured")

# %% [markdown]
# ### 1.6: Helper Functions
#
# This helper function enables the notebook to work in both local environments and Google Colab. If you're only running locally, you can skip this cell.

# %%
import sys


def get_adk_proxy_url(port=8000):
    """
    Determines the correct URL for the ADK Web UI based on the environment.
    """
    if "google.colab" in sys.modules:
        from google.colab.output import eval_js

        proxy_url = eval_js(f"google.colab.kernel.proxyPort({port})")
        return proxy_url, True

    return f"http://localhost:{port}", False


print("✅ Helper functions defined.")

# %% [markdown]
# ---
# ## 🐞 Section 2: Hands-On Debugging with ADK Web UI

# %% [markdown]
# ### 2.1: Create a "Research Paper Finder" Agent
#
#
# **Our goal:** Build a research paper finder agent that helps users find academic papers on any topic.
#
# But first, let's intentionally create an incorrect version of the agent to practice debugging! We'll start by creating a new agent folder using the `adk create` CLI command.

# %%
# !adk create research-agent --model gemini-2.5-flash-lite --api_key $GOOGLE_API_KEY

# %% [markdown]
# ### Agent definition
#
# Next, let's create our root agent. 
# - We'll configure it as an `LlmAgent`, give it a name, model and instruction.
# - The `root_agent` gets the user prompt and delegates the search to the `google_search_agent`.
# - Then, the agent uses the `count_papers` tool to count the number of papers returned.
#
# **👉 Pay attention to the root agent's instructions and the `count_papers` tool parameter!**

# %%
# %%writefile research-agent/agent.py

from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.google_search_tool import google_search

from google.genai import types
from typing import List

retry_config = types.HttpRetryOptions(
    attempts=5,  # Maximum retry attempts
    exp_base=7,  # Delay multiplier
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504],  # Retry on these HTTP errors
)

# ---- Intentionally pass incorrect datatype - `str` instead of `List[str]` ----
def count_papers(papers: str):
    """
    This function counts the number of papers in a list of strings.
    Args:
      papers: A list of strings, where each string is a research paper.
    Returns:
      The number of papers in the list.
    """
    return len(papers)


# Google Search agent
google_search_agent = LlmAgent(
    name="google_search_agent",
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
    description="Searches for information using Google search",
    instruction="""Use the google_search tool to find information on the given topic. Return the raw search results.
    If the user asks for a list of papers, then give them the list of research papers you found and not the summary.""",
    tools=[google_search]
)


# Root agent
root_agent = LlmAgent(
    name="research_paper_finder_agent",
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
    instruction="""Your task is to find research papers and count them. 

    You MUST ALWAYS follow these steps:
    1) Find research papers on the user provided topic using the 'google_search_agent'. 
    2) Then, pass the papers to 'count_papers' tool to count the number of papers returned.
    3) Return both the list of research papers and the total number of papers.
    """,
    tools=[AgentTool(agent=google_search_agent), count_papers]
)

# %% [markdown]
# ### 2.2: Run the agent
#
# Let's now run our agent with the `adk web --log_level DEBUG` CLI command.
#
# **📍 The key here is `--log_level DEBUG`** - this shows us:
#
#
# * **Full LLM Prompts:** The complete request sent to the language model, including system instructions, history, and tools.
# * Detailed API responses from services.
# * Internal state transitions and variable values.
#
# Other log levels include: INFO, ERROR and WARNING.

# %% [markdown]
# Get the proxied URL to access the ADK web UI in the Kaggle Notebooks environment:

# %%
url_prefix = get_adk_proxy_url()

# %% [markdown]
# Now you can start the ADK web UI with the `--log_level` parameter.
#
# 👉 **Note:** The following cell will not "complete", but will remain running and serving the ADK web UI until you manually stop the cell.

# %%
# !adk web --log_level DEBUG --url_prefix {url_prefix}

# %% [markdown]
# Once the ADK web UI starts, open the proxy link using the button in the previous cell.
#
# As you start chatting with the agent, you should see the DEBUG logs appear in the output cell below!
#
# ‼️ **IMPORTANT: DO NOT SHARE THE PROXY LINK** with anyone - treat it as sensitive data as it contains your authentication token in the URL.

# %% [markdown]
# ### 📝 2.3: Test the agent in ADK web UI
#
# #### **👉 Do: In the ADK web UI**
#
# 1. Select "research-agent" from the dropdown in the top-left.
# 2. In the chat interface, type: `Find latest quantum computing papers`
# 3. Send the message and observe the response. The agent should return a list of research papers and their count.
#
# It looks like our agent works and we got a response! 🤔 **But wait, isn't the count of papers unusually large? Let's look at the logs and trace.** 

# %% [markdown]
# #### **👉 Do: Events tab - Traces in detail**
#
# 1. In the web UI, click the **"Events"** tab on the left sidebar
# 2. You'll see a chronological list of all agent actions
# 3. Click on any event to expand its details in the bottom panel
# 4. Try clicking the **"Trace"** button to see timing information for each step.
# 5. **Click the `execute_tool count_papers` span. You'll see that the function call to `count_papers` returns the large number as the response**.
# 6. Let's look at what was passed as input to this function. 
# 7. **Find the `call_llm` span corresponding to the `count_papers` function call**.

# %% [markdown]
# #### **👉 Do: Inspect the Function call in Events:**
#
# - Click on the specific span to open the Events tab.
# - Examine the `function_call`, focusing on the `papers` argument.
# - Notice that `root_agent` passes the list of `papers` as a **str** instead of a **List[str]** - there's our bug! 

# %% [markdown]
# ![Demo](https://storage.googleapis.com/github-repo/kaggle-5days-ai/day4/observability-demo.gif)

# %% [markdown]
# ### 2.4: Your Turn - fix it! 👾 
#
# Update the datatype of the `papers` argument in the `count_papers` tool to a `List[str]` and rerun the `adk web` command!

# %% [markdown]
# ---
#
# ## ‼️ **Stop the ADK web UI** 🛑
#
# **In order to run cells in the remainder of this notebook,** please stop the running cell where you started `adk web` in Section 3.1.
#
# Otherwise that running cell will block / prevent other cells from running as long as the ADK web UI is running.
#
# ---

# %% [markdown]
# ### 2.5: Debug through local Logs
#
# Optionally, you can also examine the local DEBUG logs to find the root cause. Run the following cell to print the contents of the log file. Look for detailed logs like:
# ```
# DEBUG - google_adk.models.google_llm - LLM Request: ...
# DEBUG - google_adk.models.google_llm - LLM Response: ...
# ```

# %%
# Check the DEBUG logs from the broken agent
print("🔍 Examining web server logs for debugging clues...\n")
# !cat logger.log

# %% [markdown]
# **Other Observability questions you can now answer from logs and adk web:**
# - **Efficiency**: Is the agent making optimal tool choices?
# - **Reasoning Quality**: Are the prompts well-structured and context-appropriate?
# - **Performance**: Look at the traces to identify which steps take the longest?
# - **Failure Diagnosis**: When something goes wrong, where exactly did it fail?
#
# **Key Learning:** Core debugging pattern: `symptom → logs → root cause → fix`.
#
# **Debugging Victory:** You just went from "Agent mysteriously failed" to "I know exactly why and how to fix it!" This is the power of observability!
#

# %% [markdown]
# ---
# ## 🧑‍💻 Section 3: Logging in production
#
# **🎯 Great! You can now debug agent failures using ADK web UI and DEBUG logs.**
#
# But what happens when you move beyond development? Real-world scenarios where you need to move beyond the web UI:
#
# **❌ Problem 1: Production Deployment**
# ```
# You: "Let me open the ADK web UI to check why the agent failed"
# DevOps: "Um... this is a production server. No web UI access."
# You: 😱 "How do I debug production issues?"
# ```
#
# **❌ Problem 2: Automated Systems** 
# ```
# You: "The agent runs 1000 times per day in our pipeline"
# Boss: "Which runs are slow? What's our success rate?"
# You: 😰 "I'd have to manually check the web UI 1000 times..."
# ```
#
# **💡 The Solution:**
#
# We need a way to capture observability data or in other words, **add logs to our code**. 
#
# 👉 In traditional software development, this is done by adding log statements in Python functions - **and agents are no different!** We need to add log statements to our agent and a common approach is to add log statements to **Plugins**.
#

# %% [markdown]
# ### 3.1: How to add logs for production observability?
#
# A Plugin is a custom code module that runs automatically at various stages of your agent's lifecycle. Plugins are composed of "**Callbacks**" which provide the hooks to interrupt an agent's flow. Think of it like this:
#
# - **Your agent workflow**: User message → Agent thinks → Calls tools → Returns response
# - **Plugin hooks into this**: Before agent starts → After tool runs → When LLM responds → etc.
# - **Plugin contains your custom code**: Logging, monitoring, security checks, caching, etc.

# %% [markdown]
# ![image.png](https://storage.googleapis.com/github-repo/kaggle-5days-ai/day4/plugins-callbacks.png)

# %% [markdown]
# #### Callbacks
#
# Callbacks are the **atomic components inside a Plugin** - these are just Python functions that run at specific points in an agent's lifecycle! **Callbacks are grouped together to create a Plugin.**
#
# There are different kinds of callbacks such as:
# * **before/after_agent_callbacks** - runs before/after an agent is invoked
# * **before/after_tool_callbacks** - runs before/after a tool is called
# * **before/after_model_callbacks** - similarly, runs before/after the LLM model is called
# * **on_model_error_callback** - which runs when a model error is encountered

# %% [markdown]
# ![image.png](https://storage.googleapis.com/github-repo/kaggle-5days-ai/day4/types_of_callbacks.png)

# %% [markdown]
# ### 3.2: To make things more concrete, what does a Plugin look like?

# %%
print("----- EXAMPLE PLUGIN - DOES NOTHING ----- ")

import logging

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.plugins.base_plugin import BasePlugin


# Applies to all agent and model calls
class CountInvocationPlugin(BasePlugin):
    """A custom plugin that counts agent and tool invocations."""

    def __init__(self) -> None:
        """Initialize the plugin with counters."""
        super().__init__(name="count_invocation")
        self.agent_count: int = 0
        self.tool_count: int = 0
        self.llm_request_count: int = 0

    # Callback 1: Runs before an agent is called. You can add any custom logic here.
    async def before_agent_callback(
        self, *, agent: BaseAgent, callback_context: CallbackContext
    ) -> None:
        """Count agent runs."""
        self.agent_count += 1
        logging.info(f"[Plugin] Agent run count: {self.agent_count}")

    # Callback 2: Runs before a model is called. You can add any custom logic here.
    async def before_model_callback(
        self, *, callback_context: CallbackContext, llm_request: LlmRequest
    ) -> None:
        """Count LLM requests."""
        self.llm_request_count += 1
        logging.info(f"[Plugin] LLM request count: {self.llm_request_count}")


# %% [markdown]
# **Key insight**: You register a plugin **once** on your runner, and it automatically applies to **every agent, tool call, and LLM request** in your system as per your definition. Read more about Plugin hooks [here](https://google.github.io/adk-docs/plugins/#plugin-callback-hooks).

# %% [markdown]
# You can follow along with the numbers in the diagram below to understand the flow.

# %% [markdown]
# ![image.png](https://storage.googleapis.com/github-repo/kaggle-5days-ai/day4/count-invocation-plugin.png)

# %% [markdown]
# ### 3.3: ADK's built-in `LoggingPlugin`
#
# But you don't have to define all the callbacks and plugins to capture *standard* Observability data in ADK. Instead, ADK provides a built-in **LoggingPlugin** that automatically captures all agent activity:
#
# - 🚀 User messages and agent responses
# - ⏱️ Timing data for performance analysis
# - 🧠 LLM requests and responses for debugging
# - 🔧 Tool calls and results
# - ✅ Complete execution traces

# %% [markdown]
# #### Agent definition
#
# Let's use the same agent from the previous demo - the Research paper finder!

# %%
from typing import List

from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.google_search_tool import google_search
from google.genai import types

retry_config = types.HttpRetryOptions(
    attempts=5,  # Maximum retry attempts
    exp_base=7,  # Delay multiplier
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504],  # Retry on these HTTP errors
)


def count_papers(papers: List[str]):
    """
    This function counts the number of papers in a list of strings.
    Args:
      papers: A list of strings, where each string is a research paper.
    Returns:
      The number of papers in the list.
    """
    return len(papers)


# Google search agent
google_search_agent = LlmAgent(
    name="google_search_agent",
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
    description="Searches for information using Google search",
    instruction="Use the google_search tool to find information on the given topic. Return the raw search results.",
    tools=[google_search],
)

# Root agent
research_agent_with_plugin = LlmAgent(
    name="research_paper_finder_agent",
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
    instruction="""Your task is to find research papers and count them. 
   
   You must follow these steps:
   1) Find research papers on the user provided topic using the 'google_search_agent'. 
   2) Then, pass the papers to 'count_papers' tool to count the number of papers returned.
   3) Return both the list of research papers and the total number of papers.
   """,
    tools=[AgentTool(agent=google_search_agent), count_papers],
)

print("✅ Agent created")

# %% [markdown]
# ### 3.4: Add LoggingPlugin to Runner
#
# The following code creates the `InMemoryRunner`. This is used to programmatically invoke the agent.
#
# **To use `LoggingPlugin` in the above research agent,**
# 1) Import the plugin
# 2) Add it when initializing the `InMemoryRunner`.
#

# %%
import asyncio

from google.adk.plugins.logging_plugin import (  # <---- 1. Import the Plugin
    LoggingPlugin,
)
from google.adk.runners import InMemoryRunner
from google.genai import types

runner = InMemoryRunner(
    agent=research_agent_with_plugin,
    plugins=[
        LoggingPlugin()
    ],  # <---- 2. Add the plugin. Handles standard Observability logging across ALL agents
)

print("✅ Runner configured")

# %% [markdown]
# Let's now run the agent using `run_debug` function.

# %%
print("🚀 Running agent with LoggingPlugin...")
print("📊 Watch the comprehensive logging output below:\n")

response = await runner.run_debug("Find recent papers on quantum computing")

# %% [markdown]
# ---
#
# ## 📊 Summary
#
# **❓ When to use which type of Logging?**
# 1. **Development debugging?** → Use `adk web --log_level DEBUG`
# 2. **Common production observability?** → Use `LoggingPlugin()` 
# 3. **Custom requirements?** → Build Custom Callbacks and Plugins
#
# ### Try it out!
#
# 👉 Extend the agent's observability by implementing a **custom ADK plugin** that tracks and reports the total number of tool calls made during a session.

# %% [markdown]
# ## 🎯 Congratulations!
#
# **You now know how to:**
#
# - ✅ Debug agent failures through DEBUG logs and the ADK web UI
# - ✅ Use the core debugging pattern: symptom → logs → root cause → fix  
# - ✅ Scale observability with `LoggingPlugin` for production systems
# - ✅ Understand when to use the different logging types

# %% [markdown]
# ### 📚 Resources
#
# **Refer to the ADK documentation to learn more about observability:**
#
# - [ADK Observability Documentation](https://google.github.io/adk-docs/observability/logging/) - Complete guide to logging in ADK
# - [Custom Plugin](https://google.github.io/adk-docs/plugins/) - Build your own Plugins
# - [External Integrations](https://google.github.io/adk-docs/observability/cloud-trace/) - Explore external third-party observability integrations with ADK

# %% [markdown]
# ---
#
# <div align="center">
#   <table>
#     <tr>
#       <th style="text-align:center">Authors</th>
#     </tr>
#     <tr>
#       <td style="text-align:center"><a href="https://www.linkedin.com/in/sitalakshmi04/">Sita Lakshmi Sangameswaran</a></td>
#     </tr>
#   </table>
# </div>
