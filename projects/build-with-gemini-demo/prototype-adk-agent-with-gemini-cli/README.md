# Prototype ADK Agents with Gemini CLI

This demonstration guide walks through the process of rapidly prototyping an ADK
(Agent Development Kit) agent using the Gemini CLI. You will leverage the Gemini
CLI's planning and implementation capabilities to quickly scaffold and refine a
functional customer support agent. This "vibe prototyping" approach allows for
fast iteration and development, showcasing how AI-assisted tools can accelerate
the creation of complex agents and services. By the end of this demo section,
you will have a working ADK agent capable of looking up and summarizing
in-memory ticket data, all built and debugged primarily through natural language
commands in the Gemini CLI.

## Key Files

1.  **GEMINI.md**: Provides instructions on how to use the reference
    documentation to build ADK agents.
1.  **AGENTS.txt**: Contains detailed information and best practices for agent
    development.

AGENTS.txt file is imported into the GEMINI.md and will be included in the
Gemini CLI session’s context when you interact with the Gemini CLI.

This feature facilitates the decomposition of large GEMINI.md files into
smaller, more manageable modules that can be seamlessly reused across varied
contexts. The import processor supports both relative and absolute paths,
incorporating robust safety mechanisms to avoid circular imports and ensure
secure file access.

## Custom Commands

These custom commands help you in both planning and implementing ADK agents.

1.  `/adk-plan:new` - this command leverages provided documentation (GEMINI.md,
    AGENTS.md) to generate an implementation plan, ensuring adherence to best
    practices.

1.  `/adk-plan:impl` - this command uses the implementation plan to generate the
    necessary Python files, reducing boilerplate and focusing on ADK
    requirements.

## Start building the agent

1.  Change the working directory:

    ```bash
    git clone --filter=blob:none --no-checkout https://github.com/GoogleCloudPlatform/cloud-solutions
    cd cloud-solutions
    git sparse-checkout init --cone
    git sparse-checkout set projects/build-with-gemini-demo/prototype-adk-agent-with-gemini-cli
    git checkout
    cd projects/build-with-gemini-demo/prototype-adk-agent-with-gemini-cli
    ```

1.  Rename `.env.sample` to `.env` file and update with your Google Cloud
    project information:

    ```text
    GOOGLE_GENAI_USE_VERTEXAI=TRUE
    GOOGLE_CLOUD_PROJECT="<ENTER_YOUR_PROJECT_ID>"
    GOOGLE_CLOUD_LOCATION="<ENTER_YOUR_PROJECT_LOCATION>" # e.g. us-central1
    ```

1.  Acquire new user credentials:

    ```bash
    gcloud auth application-default login
    ```

1.  Run Gemini CLI:

    ```bash
    gemini
    ```

1.  Send prompt to create implementation plan:

    ```text
    /adk-plan:new Build a customer support ADK agent that allows users to look
    up the full details of any ticket using its ID and also provide the ability
    to return a summary for any selected ticket. For summary requests return
    ticket description. Generate 20 sample tickets (each with an integer based
    ID, title, and description) and use them as an in-memory db.
    ```

    Review generated plan and request implementation. You can find an example
    plan in the
    `projects/build-with-gemini-demo/prototype-adk-agent-sample/plans/customer_support_agent.md`
    file.

1.  Send prompt to implement the plan:

    ```text
    /adk-plan:impl implement the plan and generate a requirements.txt
    file for more reproducible builds.
    ```

    Review and approve tools and suggested code changes.

    The `prototype-adk-agent-sample` folder contains sample implementation plan
    and customer support agent built with the prompts above.

1.  Exit from Gemini CLI and run commands to setup virtual environment and
    install required dependencies for ADK agent:

    ```bash
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

1.  Start ADK Web Server to test the agent:

    ```bash
    adk web .
    ```

    Click on the link to open application in the browser.

    In the Cloud Shell environment, select Web Preview from the menu and change
    port(eg. 8000) and preview the application.

1.  Testing the Agent

    After you start the application and select the agent from the dropdown in
    the top left corner. Send a greeting to the agent and ask how they can help.
    This will prompt the agent to describe available operations.

    Sample queries to try:

    ```text
    lookup ticket # 10
    ```

    ```text
    summarize ticket # 5
    ```

You can find an example implementation of this agent in the
`projects/build-with-gemini-demo/prototype-adk-agent-sample` directory.
