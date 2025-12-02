# Feature Implementation Plan: customer_support_agent

## 📋 Todo Checklist

- [ ] Create the agent directory structure.
- [ ] Create the in-memory ticket database.
- [ ] Implement the ticket lookup tool.
- [ ] Implement the ticket summarization tool.
- [ ] Define the main customer support agent.
- [ ] Final Review and Testing.

## 🔍 Analysis & Investigation

### Codebase Structure

The current project is a clean slate. Based on the `AGENTS.md` documentation,
ADK agents should be organized into their own directories. The convention is to
have a directory (e.g., `customer_support_agent/`) containing an `agent.py` file
(which defines the `root_agent`) and an `__init__.py` file (which exports the
agent module). Other related files, like tools and data, can be co-located in
this directory.

### Current Architecture

There is no existing architecture. The plan proposes a simple, single-agent
architecture. A single `LlmAgent` will be equipped with tools to interact with
an in-memory ticket database. This is a straightforward approach that aligns
well with the capabilities of the ADK framework as described in the
documentation.

### Dependencies & Integration Points

The agent will depend on the `google-adk` library. The core integration points
are:

- An in-memory data source for tickets.
- Tools (Python functions) that the agent can call.
- The `LlmAgent` itself, which orchestrates the use of tools based on user
  input.

### Considerations & Challenges

- **Summarization Strategy**: The summarization tool can be implemented in two
  ways: either as a simple function that calls another LLM for summarization or
  as a dedicated `LlmAgent`. For this plan, we will use a separate `LlmAgent`
  for summarization to demonstrate a multi-agent (in a sense) setup, where one
  agent uses another as a tool.
- **Error Handling**: The tools should handle cases where a ticket ID is not
  found.
- **Scalability**: An in-memory database is suitable for the requested 20 sample
  tickets but will not scale for a production system. For a real-world
  application, this would be replaced with a connection to a proper database or
  API.

## 📝 Implementation Plan

### Prerequisites

- `google-adk` installed (`pip install google-adk`).
- A configured Gemini API key (typically in a `.env` file).

### Step-by-Step Implementation

1.  **Create Agent Directory Structure**:
    - Files to create:
        - `customer_support_agent/`
        - `customer_support_agent/__init__.py`
    - Changes needed:
        - In `customer_support_agent/__init__.py`, add the line:
          `from . import agent`

1.  **Create In-Memory Ticket Database**:
    - File to create: `customer_support_agent/tickets.py`
    - Changes needed:
        - Define a list of 20 dictionaries, where each dictionary represents a
          ticket with `id`, `title`, and `description` keys.
        - The `id` should be a unique string.
        - The `title` and `description` should be descriptive strings.

1.  **Implement Agent Tools**:
    - File to create: `customer_support_agent/tools.py`
    - Changes needed:
        - Import the ticket data from `customer_support_agent.tickets`.
        - Create a function `get_ticket_details(ticket_id: str) -> str` that
          takes a ticket ID and returns the ticket details as a formatted string
          or a JSON string. It should handle cases where the ticket is not
          found.
        - Import `LlmAgent` from `google.adk.agents`.
        - Define a `summarizer_agent` using `LlmAgent`. This agent's instruction
          will be to summarize the provided text.
        - Create a function `summarize_ticket(ticket_id: str) -> str`. This
          function will first call `get_ticket_details` to get the ticket's
          description, and then it will use the `summarizer_agent` to summarize
          the description.

1.  **Define the Main Customer Support Agent**:
    - File to create: `customer_support_agent/agent.py`
    - Changes needed:
        - Import `LlmAgent` from `google.adk.agents`.
        - Import the `get_ticket_details` and `summarize_ticket` functions from
          `customer_support_agent.tools`.
        - Define the `root_agent` as an `LlmAgent`.
        - Set the `name` to `customer_support_agent`.
        - Use the `gemini-2.5-flash` model.
        - Write a clear `instruction` that tells the agent it is a customer
          support assistant and explains how to use the `get_ticket_details` and
          `summarize_ticket` tools.
        - Provide the `get_ticket_details` and `summarize_ticket` functions in
          the `tools` list.

## 🎯 Testing Strategy

The user will run `adk web .` from the root of the project. This will start the
ADK web server. The user can then interact with the `customer_support_agent`
through the web UI to test its ability to retrieve and summarize tickets.

## ✅ Success Criteria

- The agent can successfully find and return the full details of a ticket when
  given a valid ID.
- The agent provides a helpful message when a ticket ID is not found.
- The agent can provide a concise summary of a ticket when requested.
- The agent correctly uses the tools to perform these actions.
