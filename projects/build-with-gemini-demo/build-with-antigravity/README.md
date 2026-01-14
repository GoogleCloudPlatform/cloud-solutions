# Build with Antigravity

This guide demonstrates how Antigravity's agentic development platform can
accelerate your software development. You'll learn how to prototype a new
application, generate unit tests, perform security scans, create documentation,
and open a GitHub pull request — all by leveraging Antigravity's powerful,
customizable workflows to automate and streamline your development process.

## Requirements

- Google Antigravity installed
- GitHub account, repository and personal access token
- [Snyk installation](https://googlecloudplatform.github.io/cloud-solutions/build-with-gemini-demo/security-scan-fix/#create-snyk-account)
  for security code scanning
- Python 3.11 or higher

## Antigravity

Antigravity is Google's agentic development platform designed to streamline and
automate various stages of the software development lifecycle. It empowers
developers to build, test, and deploy applications more efficiently by
leveraging intelligent agents and customizable workflows. For more details,
refer to the Antigravity [documentation](https://antigravity.google/docs/home).

## Antigravity Customizations

### Agent's Guardrails: Rules

Rules function as the governance layer of the development environment, allowing
developers to embed specific coding standards and behavioral expectations
directly into the agent's logic. By utilizing Markdown-based configuration files
at either a global or project-specific level, teams can enforce persistent
compliance with organization-wide patterns or repository requirements.

### Process Orchestration: Workflows

While Rules establish the boundaries of behavior, Workflows codify complex,
multi-stage procedures into repeatable sequences. For example, a developer can
trigger a single workflow that sequentially scans code for security
vulnerabilities, generates comprehensive unit tests for new logic, and finally
automates the creation of a Pull Request with all necessary documentation.

Check out Antigravity
[documentation](https://antigravity.google/docs/rules-workflows) for more
details.

### Agent Skills

[Skills](https://antigravity.google/docs/skills) are agent-triggered
capabilities. Skills are reusable knowledge packages, typically organized as
folders containing a `SKILL.md` file, that extend an agent's capabilities by
providing specific instructions, best practices, and resources for various
tasks. They can be defined as workspace-specific or global utilities and are
automatically discovered and activated by the agent when they are relevant to
the current context.

### MCP Servers Integration

MCP Support enables Antigravity to securely interface with local tools,
databases, and external services via the
[Model Context Protocol](https://modelcontextprotocol.io/) standard. By acting
as a dynamic bridge to the broader development environment, it allows the agent
to autonomously fetch real-time context - such as GitHub issues or JIRA
tickets - directly when needed, providing deep insights that extend well beyond
the active files in the editor.

## Workflows configuration

This repository comes with several custom workflows and rules examples located
under `.agent/rules` and `.agent/workflows` folders.

### Prepare the environment

1.  Clone the repository:

    ```bash
    git clone https://github.com/GoogleCloudPlatform/cloud-solutions && \
    cd cloud-solutions/build-with-gemini-demo/build-with-antigravity
    ```

1.  [Download](https://antigravity.google/download) and install Antigravity
    locally. Select `Review-driven development` mode for Antigravity Agent.

1.  Launch Antigravity and click `Open Workspace` > `Open New Workspace`.

    Select cloned repository location.

    Example: `cloud-solutions/build-with-gemini-demo/build-with-antigravity`

1.  Click `Open Editor` and explore existing workflows and rules from the
    Explorer panel.

1.  **(Optional) GitHub Account and Repository**: The final step of this guide
    involves creating a GitHub Pull Request. If you wish to complete the entire
    guide, you will need a [GitHub account](https://github.com/signup), a
    personal access token, and a new repository.

### From Idea to Application

Now, let's bring your idea to life! This guided walkthrough will show you how to
build a fully functional web application from a single prompt using the custom
`/idea-to-app` workflow. While we're building a conference event tracker,
remember that you can customize this workflow for your own needs. Want to use a
different web framework like Django, or connect to a different database? Simply
modify the `.agent/workflows/idea-to-app.yaml` file to fit your stack.

Let's get started. In the Antigravity Editor's Agent Side Panel, type the
following prompt:

```text
/idea-to-app build a web app to track conference events, add new events and view lists of upcoming events.
```

Once you send this prompt, the agent will begin to outline a plan. It will
suggest a specification for the application. Take a moment to review it, and if
you're happy with the direction, simply tell the agent to proceed.

Next, the agent will present an implementation plan. This is where you can
provide more specific instructions as comments.

Click `Proceed` to approve the plan.

The agent will now get to work, creating the necessary files and writing the
code for your application. You'll see the files appear in the Explorer as the
agent works. Follow along with the agent's output, and approve its suggestions.

Once the agent has finished, it will automatically open the application in your
browser so you can see your creation in action. You can also review the updated
information in the `Walkthrough` and `Task` views to see a summary of what has
been accomplished.

Before moving to the next step, ask agent to stop the application.

### Generating Unit Tests Automatically

Now that we have a functional application, let's ensure it's robust by
generating unit tests. With the `/unit-tests` workflow, you can automate the
creation of comprehensive test suites for your codebase. This workflow is
adaptable to your project's specific needs. For example, you can configure it to
use different testing frameworks like `pytest` or `jest`, or to support various
programming languages. To make these customizations, simply edit the
`.agent/workflows/unit-tests.yaml` file.

To begin, type the following command in the Antigravity Editor's Agent Side
Panel:

```text
/unit-tests
```

The agent will analyze the source code, identify the key functions and logic,
and then generate a corresponding set of unit tests. You can follow the agent's
progress and see the new test files as they are created.

After generating the tests, the agent will automatically execute them to
validate the newly generated code. This ensures that your application's
functionality is working as expected. Once the process is complete, you can
review the generated tests and their execution results to ensure they meet your
standards. You'll also see updated information in the `Walkthrough` view, which
provides a summary of the newly created tests and their validation status.

### Proactive Security Scanning

Ensuring your application is secure is a critical step in the development
process. The `/security-scan` workflow helps you identify potential
vulnerabilities in your codebase proactively. This workflow can be tailored to
your security requirements, allowing you to integrate your preferred scanning
tools, such as `Snyk` or `Bandit`, and define custom rules for vulnerability
detection. To make these adjustments, edit the
`.agent/workflows/security-scan.yaml` file.

To initiate a security scan, enter the following command in the Antigravity
Editor's Agent Side Panel:

```text
/security-scan
```

The agent will perform a comprehensive scan of your codebase, looking for common
security issues and potential vulnerabilities. Once the scan is complete, the
agent will present its findings. You can then review the identified issues and
accept the agent's suggestions to address them. This proactive approach to
security helps you build more secure and reliable applications.

### Documentation Generation

Good documentation is essential for any project. The `/documentation` workflow
automates the generation of comprehensive application documentation. This
workflow is highly configurable, allowing you to use your preferred
documentation tools, and to generate documentation in various formats to suit
your project's needs. To customize these settings, modify the
`.agent/workflows/documentation.yaml` file.

To generate your application's documentation, simply send the following prompt
in the Antigravity Editor's Agent Side Panel:

```text
/documentation
```

The agent will analyze your codebase and automatically generate relevant
documentation, including API references, usage guides, or conceptual overviews,
depending on your configuration. You can review the generated documentation and
the agent's output to ensure it aligns with your expectations.

### Automated Code Review

Maintaining code quality and adhering to team coding standards are crucial. With
the `/code-review` workflow, you can automate the process of reviewing your code
for style, best practices, and potential issues. This workflow is highly
customizable, allowing you to integrate different linters and code formatters to
enforce your team's specific guidelines. To make these adjustments, edit the
`.agent/workflows/code-review.yaml` file.

To perform a local code review, send the following prompt in the Antigravity
Editor's Agent Side Panel:

```text
/code-review
```

The agent will analyze your code against the configured rules and standards,
providing feedback on areas that could be improved. You can review the agent's
suggestions and apply them to enhance your code quality. The `Walkthrough` and
`Task` views will also be updated with a summary of the code review findings.

### Streamlined GitHub Pull Request Creation

Once your code is thoroughly tested, scanned for security, and reviewed for
quality, the final step in your development workflow is to propose your changes.
With the `/open-pr` workflow, you can automate the creation of GitHub Pull
Requests, streamlining your contribution process.

To use this workflow, you'll first need a GitHub repository.

1.  **Create a new repository on GitHub**: Go to [repo.new](https://repo.new) to
    create a new GitHub repository. Let's call it `build-with-antigravity-demo`.
1.  **Initialize local repository and set remote**: In your terminal, navigate
    to your project directory (e.g.,
    `cloud-solutions/build-with-gemini-demo/build-with-antigravity`) and run the
    following commands to initialize the repository and link it to your GitHub
    remote. Replace `YOUR-USERNAME` with your actual GitHub username.

    ```bash
    git init -b main
    git add README.md
    git commit -m "Initial commit"
    git remote add origin git@github.com:YOUR-USERNAME/build-with-antigravity-demo.git
    git push -u origin main
    ```

Before you can use this feature, you also need to configure your environment to
allow the agent to interact with GitHub. This involves setting up the GitHub MCP
server and providing a GitHub Access Token. Follow these steps:

1.  **Create GitHub Access Token**: Create a new GitHub Personal Access
    [Token (Fine-grained)](https://github.com/settings/personal-access-tokens)
    and select the repository you created in the previous step. Grant following
    permissions:
    - `Contents`: Read and write access
    - `Pull requests`: Read and write access
    - `Metadata`: Read-only access

1.  **Configure GitHub MCP Server**: Open or create your Antigravity MCP
    configuration file at `~/.gemini/antigravity/mcp_config.json` file.

1.  **Add Configuration**: Insert the following configuration into your
    configuration file, replacing `"YOUR-GITHUB-ACCESS-TOKEN"` with the token
    you just generated:

    ```yaml
    {
      "mcpServers":
        {
          "GitHub":
            {
              "command": "npx",
              "args": ["-y", "@modelcontextprotocol/server-github"],
              "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "YOUR-GITHUB-ACCESS-TOKEN" },
            },
        },
    }
    ```

You might need to restart Antigravity to load updated configuration.

Once configured, you can create a new pull request by sending the following
prompt in the Antigravity Editor's Agent Side Panel:

```text
/open-pr
```

The agent will then create a new pull request on GitHub with your changes and
according to your specified configurations. You can review the updated
information in the `Walkthrough` and `Task` views to see the details of the
created pull request.

### Next Steps

Now it's your turn to explore! Adapt these workflows to your own projects,
integrate your favorite tools, and discover how Antigravity can help you build
better software, faster.
