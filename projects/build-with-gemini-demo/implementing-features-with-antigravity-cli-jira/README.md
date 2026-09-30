# Implementing features with Antigravity CLI and JIRA

This guide demonstrates how the Antigravity CLI accelerates feature development
across the Software Development Life Cycle (SDLC) by integrating with external
third-party task and requirements management systems using the Model Context
Protocol (MCP). By pulling user stories from JIRA and technical specifications
from Confluence directly into the Antigravity context, developers can understand
unfamiliar codebases, plan architectural modifications, generate verified
application code, such as adding ratings and validations to a Java microservice,
run unit tests, and transition JIRA ticket statuses without leaving the
development environment.

## Requirements

To follow this guide, you need:

- A Google Cloud project with the `Owner` role.
- A JIRA and Confluence project.
- Antigravity CLI: Installed and configured. For installation instructions,
  visit [antigravity.google](https://antigravity.google/docs/cli/install/).
- Java Development Kit (JDK): Version 21 or higher

## Atlassian projects setup (JIRA and Confluence)

1.  For this guide, you need to have JIRA and Confluence projects configured.
    [Sign up](https://www.atlassian.com/try/cloud/signup?bundle=jira-software&edition=free&editionIntent=free).

1.  Create a new Confluence page:

    ```text
    Title: Menu-Service: Rating capabilities

    Update Menu-Service to allow users to add ratings for menu items that they order.

    Required Test cases:

    Rating must be an integer value from 1 to 5.
    Can't be null.
    Can't be empty.
    Can't be zero.
    ```

1.  Create a new JIRA user story and assign it to yourself:

    ```text
    Title: Update Menu service

    Update Menu service:
    1. Add new fields: description and rating to Menu entity.
    2. Update other dependencies where Menu entity is used in the code, eg MenuResource.
    3. Add unit tests for all methods, including new fields.

    Link to Confluence page:
    https://YOUR-ORG.atlassian.net/wiki/spaces/SPACE-KEY/pages/NNNN/Menu-Service+Rating+capabilities
    ```

## Clone Git repository and navigate to workspace

1.  Open your local terminal, clone the demo repository, and navigate to the
    menu-service directory:

    ```text
    git clone --filter=blob:none --no-checkout https://github.com/GoogleCloudPlatform/cloud-solutions
    cd cloud-solutions
    git sparse-checkout set --cone projects/build-with-gemini-demo/gemini-powered-development/menu-service
    git checkout
    cd projects/build-with-gemini-demo/gemini-powered-development/menu-service
    ```

## Configure Antigravity MCP server in local environment

1.  The Antigravity CLI discovers workspace-scoped MCP servers located under the
    `.agents/` directory. Create the `.agents` folder and write
    `mcp_config.json` defining the Atlassian MCP server:

    ```text
    mkdir -p .agents && cat > .agents/mcp_config.json <<EOF
    {
    "mcpServers": {
        "atlassian": {
        "serverUrl": "https://mcp.atlassian.com/v2/mcp/"
        }
      }
    }
    EOF
    ```

## Authentication with service account API key (headless environments)

Follow these steps when configuring the MCP server in a CI/CD pipeline.

1.  Create a new service account for your JIRA instance in the Atlassian
    [admin console](https://admin.atlassian.com/), under
    `Directory / Service accounts`.

1.  Create a credential for the service account using the `API token`
    authentication type.

1.  Enable `Allow API token authentication` under `Rovo / Rovo MCP server`.

1.  Configure MCP server:

    You will use `Service account API key (Bearer token)` to configure the
    Atlassian MCP server.
    [Additional details](https://support.atlassian.com/atlassian-ai-gateway/docs/configure-authentication-via-api-token/).

## Prepare the environment for Atlassian integration

1.  Update JIRA/Confluence instance details in `AGENTS.md`:

    ```text
    ## Atlassian MCP

    When connected to atlassian-mcp server:
    - **MUST** use Jira project key = YOURPROJ
    - **MUST** use Confluence spaceId = "123456"
    - **MUST** use cloudId = "https://yoursite.atlassian.net" (do NOT call getAccessibleAtlassianResources)
    - **MUST** use `maxResults: 10` or `limit: 10` for ALL Jira JQL and Confluence CQL search operations.
    ```

## Check MCP server configuration

1.  Run Antigravity CLI:

    ```bash
    agy
    ```

1.  List configured MCP servers and tools:

    ```text
    /mcp
    ```

    The output confirms that the `atlassian` server is configured and ready. On
    the first run, you need to authenticate, select your JIRA instance and grant
    permissions.

    Press Esc or exit the overlay to return to the prompt panel.

## Codebase exploration and onboarding

1.  Prompt Antigravity to analyze the existing codebase and produce an
    onboarding guide:

    ```text
    Role & Context:  Assume the role of Technical Lead to onboard a developer
    joining this codebase.
    Objective:  Evaluate the project repository and generate a comprehensive
    Onboarding Guide containing:
    - High-Level Architecture: Details on the technical stack and component
    interactions.
    - Core Functionality: Overview of the 3 primary features delivered by the
    system.
    - Directory Layout: Concise descriptions outlining the intent of major
    folders.
    - Request Pipeline: Step-by-step lifecycle of an incoming request from entry
    point through database persistence and return.
    ```

## (Optional) If you did not configure JIRA and Confluence projects

1.  Send a prompt with the task requirements:

    ```text
    /plan Review the code and prepare the implementation plan for the requirements below.
    I will approve the plan before you can start implementation.

    Update Menu service:
    1. Add new fields: description and rating to Menu entity.
    2. Update other dependencies where Menu entity is used in the code, eg MenuResource.
    3. Add unit tests for all methods, including new fields.

    Rating must be an integer value from 1 to 5.
    Can't be null.
    Can't be empty.
    Can't be zero.
    ```

## Bring requirements into the context of an Antigravity CLI session

1.  Send a prompt to list assigned JIRA tasks or get the context for a specific
    issue:

    ```text
    List my JIRA tasks, include name, status and description.
    ```

1.  Replace the JIRA issue details and send the prompt below:

    ```text
    What's the context of JIRA user story YOURPROJECT-NNN?
    ```

1.  Send a prompt to query the context of the linked Confluence page:

    ```text
    What's the context of the Confluence page in my JIRA user story?
    ```

## Plan and implement feature changes

1.  Send a prompt to create an implementation plan:

    ```text
    /plan Review the code and prepare the implementation plan for this user
    story. I will approve it before you can start implementation.
    ```

    Start implementation by approving the plan using the `/artifact` command.

    Review and approve tools and suggested code changes. If the Antigravity CLI
    runs into issues, for example, test validation, multiple iterations might be
    required to fix and rerun until the generated code is valid.

1.  Send a prompt to update the JIRA user story:

    ```text
    Update the JIRA user story status to Done, add a summary of the changes as a
    comment.
    ```

1.  Exit the Antigravity CLI before moving to the next section.

    ```text
    /exit
    ```
