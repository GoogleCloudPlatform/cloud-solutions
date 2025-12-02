# Accelerating Development with Gemini: Prototyping, Implementation, and Code Review

In this demo, you prototype and implement application features with Gemini.

This demo guide walks you through the following steps:

1.  Prepare the environment
1.  Prototype ADK agents with Gemini CLI
1.  Implement new features with Gemini CLI
1.  Automate GitHub Pull Requests reviews with Code Review Agent

## Requirements

To follow this demo, you need:

- A Google Cloud project with the `Owner` role.
- JIRA/Confluence project
- GitHub account and repository
- Gemini CLI: Installed and configured. For installation instructions, visit
  [geminicli.com](https://geminicli.com/docs/get-started/deployment/).
- GitHub CLI: Installed and configured. For installation instructions, visit
  [Installation](https://github.com/cli/cli?tab=readme-ov-file#installation).

Detailed setup instructions for each demonstration are located within their
respective sections below.

## Prototype ADK Agents with Gemini CLI

This demonstration guide walks through the process of rapidly prototyping an ADK
(Agent Development Kit) agent using the Gemini CLI. You will leverage the Gemini
CLI's planning and implementation capabilities to quickly scaffold and refine a
functional customer support agent. This "vibe prototyping" approach allows for
fast iteration and development, showcasing how AI-assisted tools can accelerate
the creation of complex agents and services. By the end of this demo section,
you will have a working ADK agent capable of looking up and summarizing
in-memory ticket data, all built and debugged primarily through natural language
commands in the Gemini CLI.

### Key Files

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

### Custom Commands

These custom commands help you with planning and implementing ADK agents.

1.  `/plan:new` - this command leverages provided documentation (GEMINI.md,
    AGENTS.txt) to generate an implementation plan, ensuring adherence to best
    practices.

1.  `/plan:impl` - this command uses the implementation plan to generate the
    necessary Python files, reducing boilerplate and focusing on ADK
    requirements.

### Prepare the environment for ADK agent development

1.  Open
    [Cloud Shell](https://cloud.google.com/shell/docs/launching-cloud-shell).

1.  Clone the repository and set the working directory:

    ```bash
    git clone https://github.com/GoogleCloudPlatform/cloud-solutions && \
    cd cloud-solutions
    ```

### Start building the agent

1.  Change the working directory:

    ```bash
    cd "$(git rev-parse --show-toplevel)/projects/build-with-gemini-demo/prototype-adk-agent-with-gemini-cli"
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
    /plan:new Build a customer support ADK agent that allows users to look up the full details of any ticket using its ID and also provide the ability to return a summary for any selected ticket. Generate 20 sample tickets (each with an ID, title, and description) and use them as an in-memory db.
    ```

    Review generated plan and request implementation. You can find an example
    plan in the
    `projects/build-with-gemini-demo/prototype-adk-agent-sample/plans/customer_support_agent.md`
    file.

1.  Send prompt to implement the plan:

    ```text
    /plan:impl implement the plan and generate a requirements.txt file for more reproducible builds.
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

## Implement features with Gemini CLI

This guide demonstrates how Gemini CLI accelerate feature development within the
SDLC. Using Model Context Protocol (MCP) servers, it brings requirements from
external systems(eg. JIRA, Confluence) into Gemini chat for efficient planning,
review, and implementation. The workflow covers setup, code generation (adding
rating to a menu service), and automatic JIRA updates.

### Prerequisites

1.  For this demo you need to have JIRA and Confluence projects configured.
    [Sign up](https://www.atlassian.com/try/cloud/signup?bundle=jira-software&edition=free&editionIntent=free).

1.  Create Atlassian API token:

    You will use `API Token Authentication` to configure Atlassian MCP server.
    [Additional details](https://github.com/sooperset/mcp-atlassian?tab=readme-ov-file#quick-start-guide).

    Go to
    [API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens)

    Click `Create API token`, give it a name and save the generated token to set
    environment variables.

1.  Create new Confluence page:

    ```text
    Title: Menu-Service: Rating capabilities

    Update Menu-Service to allow users to add ratings for menu items that they order.

    Required Test cases:

    Rating must be an integer value from 1 to 5.
    Can’t be null.
    Can’t be empty.
    Can’t be zero.
    ```

1.  Create new JIRA user story and assign it to yourself:

    ```text
    Title: Update Menu service

    Update Menu service: 1. add new fields: description and rating to Menu entity 2. update other dependencies where Menu entity is used in the code, eg MenuResource. 3. Add unit tests for all methods, including new fields.

    Link to Confluence page: https://YOUR-ORG.atlassian.net/wiki/spaces/SD/pages/87785484/Menu-Service+Rating+capabilities
    ```

### Prepare the environment for Atlassian integration

1.  Open
    [Cloud Shell](https://cloud.google.com/shell/docs/launching-cloud-shell).

1.  Set environment variables:

    ```bash
    export USERNAME="your.email@company.com"
    export JIRA_URL="https://your-company.atlassian.net"
    export CONFLUENCE_URL="https://your-company.atlassian.net/wiki"
    ```

    Set value in secure manner, after running this command, paste the token
    value and hit Enter:

    ```bash
    read -s ATLASSIAN_API_TOKEN
    ```

    Export environment variable:

    ```bash
    export ATLASSIAN_API_TOKEN
    ```

1.  Change the working directory:

    ```bash
    cd "$(git rev-parse --show-toplevel)/projects/build-with-gemini-demo/gemini-powered-development/menu-service"
    ```

1.  Review MCP servers configuration in `.gemini/settings.json` - no changes are
    required for this step.

1.  Update JIRA/Confluence instance in `.gemini/GEMINI.md`:

    ```text
    JIRA/Confluence instance is your-instance-name.atlassian.net
    ```

### Check MCP server configuration

1.  Run Gemini CLI:

    ```bash
    gemini
    ```

1.  List configured MCP servers and tools:

    ```text
    /mcp
    ```

    The output confirms that the `mcp-atlassian` server is configured and ready.

### Codebase explanation

1.  Send the prompt to help you learn the codebase:

    ```text
    Act as a Technical Lead. I am a new developer joining this project.
    Please analyze this codebase and provide an Onboarding Guide.
    Include the following:
    - High-Level Architecture: What is the tech stack, and how do the components interact?
    - Key Functionality: What are the top 3 primary features this code executes?
    - Folder Structure: Briefly explain the purpose of the main directories.
    - Data Flow: Trace the path of a request from the entry point to the database and back.
    ```

### (Optional) If you did not configure JIRA and Confluence projects

1.  Send prompt with the task requirements:

    ```text
    Review the code and prepare the implementation plan for requirements below.
    I will approve the plan before you can start implementation.

    Update Menu service:
    1. add new fields: description and rating to Menu entity
    2. update other dependencies where Menu entity is used in the code, eg MenuResource.
    3. Add unit tests for all methods, including new fields.

    Rating must be an integer value from 1 to 5.
    Can’t be null.
    Can’t be empty.
    Can’t be zero.
    ```

### Bring requirements into the context of Gemini CLI session

1.  Send prompt to list assigned JIRA tasks:

    ```text
    List my JIRA tasks, include name, status and description
    ```

1.  Send prompt to query context of linked Confluence page:

    ```text
    What's the context of the confluence page in my JIRA user story?
    ```

### Start implementation

1.  Send prompt to create an implementation plan:

    ```text
    Review the code and prepare the implementation plan. I will approve it before you can start implementation.
    ```

    Review the plan and request to implement the changes.

1.  Send prompt to start the implementation:

    ```text
    Implement the changes in menu-service app
    ```

    Review and approve tools and suggested code changes. If Gemini CLI runs into
    issues, for example test validation, multiple iterations might be required
    to fix and re-run until generated code is valid.

1.  Send prompt to update JIRA user story:

    ```text
    Update the JIRA user story status to Done, add a summary of the changes as a comment.
    ```

## Automate GitHub Pull Requests reviews with Code Review Agent

This section goes over the process of integrating and utilizing Gemini Code
Assist to improve GitHub code reviews. The demo will cover essential setup
procedures in both Google Cloud and GitHub, followed by a showcase of Gemini
Code Assist's capabilities in delivering smart suggestions, clear explanations,
and concise summaries to optimize the code review workflow.

### GitHub Prerequisites

Use existing or create a new GitHub repository to configure Gemini Code Assist
on GitHub.

Below are the steps to create a new GitHub repository using `gh` cli from the
Cloud Shell environment.

1.  Authenticate with GitHub using HTTPS option:

    ```bash
    gh auth login
    ```

1.  Create a new private repository:

    ```bash
    cd ~ && gh repo create gemini-code-review-agent --private \
    --clone --add-readme -d "Gemini Code Assist on GitHub"
    ```

### Google Cloud Project Prerequisites

You need `Admin` or `Owner` basic roles for your Google Cloud project.
[Setup details](https://developers.google.com/gemini-code-assist/docs/set-up-code-assist-github#before-you-begin).

### Install Gemini Code Assist application on GitHub

Follow
[instructions](https://developers.google.com/gemini-code-assist/docs/set-up-code-assist-github#enterprise)
to install Gemini Code Assist on GitHub.

### Code Review Agent Configuration

At this point, Code Review agent is enabled for the selected repositories.

1.  On the `Settings` screen for your Developer connection, you have an option
    to select comment severity level and also enable memory to improve review
    response quality.
1.  On the `Style Guide` tab, you have an option to provide a project specific
    style guide. If your repository already contains a `.gemini/styleguide.md`
    file, the instructions from both places will be concatenated and used as an
    input for the Code Review Agent during the PR review process.

### GitHub MCP Server configuration

Return to the Cloud Shell terminal and configure GitHub MCP Server:

1.  Change into `gemini-code-review-agent` folder:

    ```bash
    cd ~/gemini-code-review-agent
    ```

1.  Copy `menu-service` folder into the new project:

    ```bash
    cp -r ~/cloud-solutions/build-with-gemini-demo/gemini-powered-development/menu-service .
    ```

1.  Set environment variable in the terminal:

    ```bash
    export GITHUB_PERSONAL_ACCESS_TOKEN=$(gh auth token)
    ```

1.  Start Gemini CLI:

    ```bash
    gemini
    ```

1.  Commit new changes and open a pull request:

    ```text
    Create a new feature branch, add/commit all the changes and open a new pull request.
    ```

    Review and approve tools that Gemini CLI requires to complete this task.

### Pull Request Review

Open GitHub repository in the browser and observe the Code Review Agent
providing a summary and review for the created pull request.

### Invoking Gemini

You can request assistance from Gemini at any point by creating a PR comment in
the GitHub UI using either `/gemini <command>` or
`@gemini-code-assist <command>`.

1.  Code Review - Performs a code review of the pull request:

    ```text
    /gemini review
    ```

1.  Pull Request Summary - Provides a summary of the pull request:

    ```text
    /gemini summary
    ```

1.  Comment - Responds in comments when explicitly tagged, both in pull request
    comments and review comments:

    ```text
    @gemini-code-assist
    ```
