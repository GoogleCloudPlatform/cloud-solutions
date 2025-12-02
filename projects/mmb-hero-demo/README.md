# MMB Hero Demo

This document describes the Migrate, Modernize, and Build (MMB) hero demo.

## Requirements

To deploy this demo, you need:

- A Google Cloud project.
- An account that has the `owner` role on that Google Cloud project.
- The [gcloud CLI](https://docs.cloud.google.com/sdk/docs/install)
- [Gemini CLI](https://geminicli.com/docs/get-started/deployment/)
- The
  [codmod CLI](https://docs.cloud.google.com/migration-center/docs/app-modernization-assessment)
- [Docker Engine](https://docs.docker.com/engine/install/) (to test locally on
  your host). This guide assumes that you can
  [manage Docker as a non-root user](https://docs.docker.com/engine/install/linux-postinstall/#manage-docker-as-a-non-root-user),
  so you can run Docker commands without `sudo`.
- [Chrome DevTools MCP](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/main/README.md)

## Prepare the environment

1.  Open
    [Cloud Shell](https://cloud.google.com/shell/docs/launching-cloud-shell).

1.  Install the
    [codmod CLI](https://docs.cloud.google.com/migration-center/docs/app-modernization-assessment#set_up_codmod)

1.  Install the Chrome DevTools MCP in Gemini CLI:

    ```bash
    gemini mcp add chrome-devtools npx chrome-devtools-mcp@latest
    ```

    For more information, see the
    [Chrome DevTools MCP README](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/main/README.md):

1.  Clone the repository and set the working directory:

    ```bash
    git clone https://github.com/GoogleCloudPlatform/cloud-solutions && \
    cd cloud-solutions
    ```

## Chapter 1: Migrate pillar

TODO

## Chapter 2: Modernize pillar

### Gemini-powered .NET modernization

In this demo, you modernize a .NET Framework application to a Linux-ready .NET
application.

This demo guide walks you through the following steps:

1.  Prepare the environment
1.  Generate a modernization assessment
1.  Modernize the application
1.  Generate deployment descriptors
1.  Deploy on Google Cloud

#### Run the Migration Center App Modernization Assessment

To generate a Migration Center App Modernization Assessment report, you do the
following:

1.  Set the working directory:

    ```bash
    cd "$(git rev-parse --show-toplevel)/projects/dotnet-modernization-demo"
    ```

1.  Generate the report:

    ```bash
    codmod create full \
      --codebase ./dotnet-migration-sample \
      --output-path ./codmod-full-report-dotnet-mod.html \
      --experiments=enable_pdf,enable_images \
      --improve-fidelity \
      --intent=MICROSOFT_MODERNIZATION \
      --optional-sections "files,classes"
    ```

    This command takes about 15 minutes to run.

1.  Open the generated report with a web browser, such as Google Chrome.

To review how the output looks like, see the sample report:
`modernization-report-sample/third_party/codmod-full-report-dotnet-mod.html`.

#### Modernize the .NET application using Gemini CLI

1.  Change the working directory to the .NET application directory:

    ```bash
    cd "$(git rev-parse --show-toplevel)/projects/dotnet-modernization-demo/dotnet-migration-sample"
    ```

1.  Run Gemini CLI:

    ```bash
    gemini
    ```

1.  Copy the prompt defined in `modernization-prompt.md`, and paste the prompt
    in the Gemini CLI user interface, and press the Enter key.

To complete the execution, Gemini CLI takes about 25 minutes.

##### Sample modernized application

The `dotnet-migration-sample-modernized` directory contains an example of the
modernized .NET application resulting in running Gemini CLI with the above
prompt.

To run the example modernized application locally, you do the following:

1.  Change the working directory to the .NET application directory:

    ```bash
    cd "$(git rev-parse --show-toplevel)/projects/dotnet-modernization-demo/dotnet-migration-sample-modernized"
    ```

1.  Run the application using Docker Compose:

    ```bash
    docker compose up --build
    ```

1.  Wait for the application to accept connections. When the application is
    ready to accept connections, the output is similar to the following:

    ```text
    app-1  | {"EventId":14,"LogLevel":"Information","Category":"Microsoft.Hosting.Lifetime","Message":"Now listening on: http://0.0.0.0:8080","State":{"Message":"Now listening on: http://0.0.0.0:8080","address":"http://0.0.0.0:8080","{OriginalFormat}":"Now listening on: {address}"}}
    ```

1.  Open `http://localhost:8080/` with a web browser, such as Google Chrome.

1.  Navigate the application using the web browser.

After completing your test, stop the application by sending the `CTRL+C` key
combination.

#### Deploy the application to Google Cloud

To deploy the the example modernized application to Google Cloud using Cloud
Run, Artifact Registry, and Cloud SQL for PostgreSQL, follow the guidance in
this section.

You can follow similar steps to deploy your own modernized .NET application.

##### 1. Set up your Google Cloud environment

Set your project ID and region as environment variables in your shell.

```bash
export PROJECT_ID="[YOUR_PROJECT_ID]"
export REGION="[YOUR_REGION]" # e.g., us-central1
gcloud config set project $PROJECT_ID
gcloud config set run/region $REGION
```

##### 2. Enable necessary Google Cloud APIs

Enable the APIs for Artifact Registry, Cloud SQL, Cloud Build, and Cloud Run.
This allows the services to work together.

```bash
gcloud services enable \
    iam.googleapis.com \
    artifactregistry.googleapis.com \
    sqladmin.googleapis.com \
    run.googleapis.com \
    cloudbuild.googleapis.com
```

##### 3. Create an Artifact Registry repository

Create a Docker repository in Artifact Registry to store the container images
for your application.

```bash
export REPO_NAME="contoso-university-repo"
gcloud artifacts repositories create $REPO_NAME \
    --repository-format=docker \
    --location=$REGION \
    --description="Docker repository for Contoso University"
```

##### 4. Create a Cloud SQL for PostgreSQL instance

Create a PostgreSQL instance to host the application's database. This may take a
few minutes.

```bash
export INSTANCE_NAME="contoso-university-db"
export DB_PASSWORD="[YOUR_DB_PASSWORD]" # Choose a strong password
gcloud sql instances create $INSTANCE_NAME \
    --database-version=POSTGRES_13 \
    --tier=db-g1-small \
    --region=$REGION \
    --root-password=$DB_PASSWORD
```

After the instance is created, create a database for the application.

```bash
gcloud sql databases create contosouniversity --instance=$INSTANCE_NAME
```

##### 5. Build and push the container image

Use Google Cloud Build to build your container image and push it to the Artifact
Registry repository you created. Cloud Build uses the `Dockerfile` in your
project root.

```bash
cd "$(git rev-parse --show-toplevel)/projects/dotnet-modernization-demo/dotnet-migration-sample-modernized"
gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/contoso-university:latest .
```

##### 6. Deploy the application to Cloud Run

Deploy the container image from Artifact Registry to Cloud Run. This command
creates a new Cloud Run service and connects it to your Cloud SQL instance.

First, get your Cloud SQL instance connection name:

```bash
export INSTANCE_CONNECTION_NAME=$(gcloud sql instances describe $INSTANCE_NAME --format='value(connectionName)')
```

Now, deploy the service to Cloud Run:

```bash
gcloud run deploy contoso-university \
    --image=$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/contoso-university:latest \
    --platform managed \
    --allow-unauthenticated \
    --add-cloudsql-instances=$INSTANCE_CONNECTION_NAME \
    --region "${REGION}" \
    --set-env-vars "ConnectionStrings__SchoolContext=Host=/cloudsql/${INSTANCE_CONNECTION_NAME};Database=contosouniversity;Username=postgres;Password=${DB_PASSWORD}"
```

This command will prompt you to confirm the deployment. After it completes, it
will output the URL for your deployed service.

##### 7. Test the application

Once the deployment is complete, you can test the application:

1.  Copy the URL provided in the output of the `gcloud run deploy` command.
1.  Open the URL in a web browser.
1.  You should see the Contoso University application homepage. You can navigate
    through the site to view students, courses, instructors, and departments.
    The application is now running live on Cloud Run and connected to your Cloud
    SQL database.
1.  Optionally, you can go back to the Gemini CLI and ask it to run the
    automated UI tests again, this time against the deployed application's URL.

#### Clean up your Google Cloud environment

To avoid incurring unwanted charges, follow these steps to remove all the
resources provisioned for this demo.

1.  Delete the Cloud Run service

    ```bash
    gcloud run services delete contoso-university --platform managed --region=$REGION --quiet
    ```

1.  Delete the Artifact Registry repository

    ```bash
    gcloud artifacts repositories delete $REPO_NAME --location=$REGION --quiet
    ```

1.  Delete the Cloud SQL for PostgreSQL instance

    ```bash
    gcloud sql instances delete $INSTANCE_NAME --quiet
    ```

## Chapter 3: Build pillar

### Accelerating Development with Gemini: Prototyping, Implementation, and Code Review

In this demo, you prototype and implement application features with Gemini.

This demo guide walks you through the following steps:

1.  Prepare the environment
1.  Prototype ADK agents with Gemini CLI
1.  Implement new features with Gemini CLI
1.  Automate GitHub Pull Requests reviews with Code Review Agent

#### Build Pillar Requirements

In addition to the [requirements](#requirements), you also need the following to
follow this chapter:

- A Google Cloud project with the `Owner` role.
- JIRA/Confluence project
- GitHub account and repository
- Gemini CLI: Installed and configured. For installation instructions, visit
  [geminicli.com](https://geminicli.com/docs/get-started/deployment/).
- GitHub CLI: Installed and configured. For installation instructions, visit
  [Installation](https://github.com/cli/cli?tab=readme-ov-file#installation).

Detailed setup instructions for each demonstration are located within their
respective sections below.

#### Prototype ADK Agents with Gemini CLI

This demonstration guide walks through the process of rapidly prototyping an ADK
(Agent Development Kit) agent using the Gemini CLI. You will leverage the Gemini
CLI's planning and implementation capabilities to quickly scaffold and refine a
functional customer support agent. This "vibe prototyping" approach allows for
fast iteration and development, showcasing how AI-assisted tools can accelerate
the creation of complex agents and services. By the end of this demo section,
you will have a working ADK agent capable of looking up and summarizing
in-memory ticket data, all built and debugged primarily through natural language
commands in the Gemini CLI.

#### Key Files

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

#### Custom Commands

These custom commands help you in both planning and implementing ADK agents.

1.  `/plan:new` - this command leverages provided documentation (GEMINI.md,
    AGENTS.md) to generate an implementation plan, ensuring adherence to best
    practices.

1.  `/plan:impl` - this command uses the implementation plan to generate the
    necessary Python files, reducing boilerplate and focusing on ADK
    requirements.

#### Start building the agent

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

### Implement features with Gemini CLI

This guide demonstrates how Gemini CLI accelerate feature development within the
SDLC. Using Model Context Protocol (MCP) servers, it brings requirements from
external systems(eg. JIRA, Confluence) into Gemini chat for efficient planning,
review, and implementation. The workflow covers setup, code generation (adding
rating to a menu service), and automatic JIRA updates.

#### Prerequisites

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

#### Prepare the environment for Atlassian integration

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

#### Check MCP server configuration

1.  Run Gemini CLI:

    ```bash
    gemini
    ```

1.  List configured MCP servers and tools:

    ```text
    /mcp
    ```

    The output confirms that the `mcp-atlassian` server is configured and ready.

#### Codebase explanation

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

#### (Optional) If you did not configure JIRA and Confluence projects

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

#### Bring requirements into the context of Gemini CLI session

1.  Send prompt to list assigned JIRA tasks:

    ```text
    List my JIRA tasks, include name, status and description
    ```

1.  Send prompt to query context of linked Confluence page:

    ```text
    What's the context of the confluence page in my JIRA user story?
    ```

#### Start implementation

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

### Automate GitHub Pull Requests reviews with Code Review Agent

This section goes over the process of integrating and utilizing Gemini Code
Assist to improve GitHub code reviews. The demo will cover essential setup
procedures in both Google Cloud and GitHub, followed by a showcase of Gemini
Code Assist's capabilities in delivering smart suggestions, clear explanations,
and concise summaries to optimize the code review workflow.

#### GitHub Prerequisites

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

#### Google Cloud Project Prerequisites

You need `Admin` or `Owner` basic roles for your Google Cloud project.
[Setup details](https://developers.google.com/gemini-code-assist/docs/set-up-code-assist-github#before-you-begin).

#### Install Gemini Code Assist application on GitHub

Follow
[instructions](https://developers.google.com/gemini-code-assist/docs/set-up-code-assist-github#enterprise)
to install Gemini Code Assist on GitHub.

#### Code Review Agent Configuration

At this point, Code Review agent is enabled for the selected repositories.

1.  On the `Settings` screen for your Developer connection, you have an option
    to select comment severity level and also enable memory to improve review
    response quality.
1.  On the `Style Guide` tab, you have an option to provide a project specific
    style guide. If your repository already contains a `.gemini/styleguide.md`
    file, the instructions from both places will be concatenated and used as an
    input for the Code Review Agent during the PR review process.

#### GitHub MCP Server configuration

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

#### Pull Request Review

Open GitHub repository in the browser and observe the Code Review Agent
providing a summary and review for the created pull request.

#### Invoking Gemini

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
