# Feature Implementation Plan: customer_support_adk_agent

## 📋 Todo Checklist
- [x] Create the `customer_support_agent` directory.
- [x] Create `customer_support_agent/agent.py` to hold the agent logic.
- [x] Populate `agent.py` with sample ticket data.
- [x] Implement `get_ticket_details` and `get_ticket_summary` tool functions.
- [x] Define the `LlmAgent` with instructions and tools.
- [x] Create `customer_support_agent/__init__.py` to export the agent.
- [x] Final Review and Testing.

## 🔍 Analysis & Investigation

### Codebase Structure
The current project is a blank slate for ADK agent development. The provided `AGENTS.txt` (within `GEMINI.md`) clearly documents the required structure for a Python ADK agent: a directory named after the agent, containing an `__init__.py` and an `agent.py`. The `agent.py` must define the root agent instance.

### Current Architecture
The architecture will be based on the Google ADK (Agent Development Kit) for Python. The core of the feature will be a single `LlmAgent`. This agent will use a Large Language Model for reasoning and will be equipped with custom tools to interact with a data source. This is a standard and effective pattern for building capable, tool-using agents as described in the ADK documentation.

### Dependencies & Integration Points
- **`google-adk`**: The primary dependency. The plan assumes this is installed in the environment. Version 2 was specified.
- **`gemini-2.5-flash`**: The specified model for the `LlmAgent`. This is an external dependency on Google's model APIs.
- **In-Memory Data**: The ticket data will be stored in a Python dictionary within the `agent.py` file itself. There are no external database integrations required for this implementation.

### Considerations & Challenges
- **Instruction Clarity**: The `instruction` for the `LlmAgent` must be very clear and explicitly guide the model on which tool to use for which type of request ("details" vs. "summary"). Ambiguous instructions could lead to the wrong tool being called.
- **Error Handling**: The tool functions should handle cases where a ticket ID does not exist gracefully. They should return a helpful message to the agent, which the agent can then relay to the user.
- **Data Scalability**: Using an in-memory dictionary is suitable for 20 sample tickets, but this approach will not scale. For a real-world application, this would be replaced with a database and the tool functions would make API calls. The plan will mention this as a future consideration.

## 📝 Implementation Plan

### Prerequisites
- Ensure the `google-adk` Python package is installed (`pip install google-adk`).

### Step-by-Step Implementation

1. **Create the Agent Directory Structure**
   - Files to create: `customer_support_agent/`
   - Command: `mkdir customer_support_agent`
   - Rationale: This follows the standard ADK project structure.

2. **Define the Agent Module (`agent.py`)**
   - Files to create: `customer_support_agent/agent.py`
   - Changes needed: Create the file and add the following components in the subsequent steps.

3. **Create In-Memory Database**
   - Files to modify: `customer_support_agent/agent.py`
   - Changes needed: Add a list of dictionaries to represent the 20 sample tickets. Each dictionary should have `id` (integer), `title` (string), and `description` (string).

    ```python
    # Sample structure
    TICKETS = [
        {"id": 1, "title": "Cannot Login", "description": "User reports they are unable to log into their account since the last update."},
        {"id": 2, "title": "Website Down", "description": "The main corporate website appears to be offline for several users."},
        # ... 18 more tickets
    ]
    ```

4. **Implement Tool Functions**
   - Files to modify: `customer_support_agent/agent.py`
   - Changes needed: Define two functions that will serve as tools for the LLM agent.

    ```python
    import json

    def get_ticket_details(ticket_id: int) -> str:
        """Retrieves the full details of a specific ticket by its ID."""
        for ticket in TICKETS:
            if ticket["id"] == ticket_id:
                return json.dumps(ticket)
        return f"Ticket with ID {ticket_id} not found."

    def get_ticket_summary(ticket_id: int) -> str:
        """Retrieves a summary (the description) of a specific ticket by its ID."""
        for ticket in TICKETS:
            if ticket["id"] == ticket_id:
                return ticket["description"]
        return f"Ticket with ID {ticket_id} not found."
    ```

5. **Define the LLM Agent**
   - Files to modify: `customer_support_agent/agent.py`
   - Changes needed: Instantiate an `LlmAgent`, providing the model, name, instructions, and the tool functions created in the previous step.

    ```python
    from google.adk.agents import Agent

    root_agent = Agent(
        name="customer_support",
        model="gemini-2.5-flash",
        description="A customer support agent that can look up ticket details and summaries.",
        instruction="""You are a customer support agent.
        - When a user asks for the 'details' or 'full details' of a ticket, use the `get_ticket_details` tool.
        - When a user asks for a 'summary' of a ticket, use the `get_ticket_summary` tool.
        - The user will provide the ticket ID. Identify it and pass it to the correct tool.
        - If a tool returns a 'not found' message, relay that information to the user.
        - Present the information clearly. If details are in JSON format, you can present them in a readable way.
        """,
        tools=[get_ticket_details, get_ticket_summary]
    )
    ```

6. **Create the `__init__.py` file**
   - Files to create: `customer_support_agent/__init__.py`
   - Changes needed: This file makes the `agent.py`'s contents available as a module.

    ```python
    from . import agent
    ```

### Testing Strategy
The user will test the agent by running the ADK web development UI.
1.  Navigate to the project's root directory in the terminal.
2.  Run the command: `adk web .`
3.  This will start a web server and open a UI in the browser.
4.  Interact with the agent using the chat interface. Sample prompts:
    - "Can you give me the full details for ticket ID 7?"
    - "I need a summary of ticket 15."
    - "What's happening with ticket 2?" (Let the agent infer the need for a summary)
    - "get details for ticket 99" (To test the not found case)

## 🎯 Success Criteria
- The agent correctly identifies whether the user is asking for "details" or a "summary".
- The agent calls the `get_ticket_details` tool for detail requests and returns the full ticket information.
- The agent calls the `get_ticket_summary` tool for summary requests and returns only the ticket's description.
- The agent provides a user-friendly message when a ticket ID is not found in the database.
- The ADK Web UI launches successfully and allows interaction with the `customer_support` agent.
