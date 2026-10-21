# Build applications with the Antigravity IDE extension and Agent Skills

This guide demonstrates how Antigravity's agentic development platform
accelerates software development. In this guide, you prototype a new
application, generate unit tests, perform security scans, create documentation,
and open a GitHub pull request by using Antigravity's customizable skills and
rules to streamline your development process.

## Requirements

- Google Antigravity IDE extension for VS Code installed
- GitHub account, repository, and personal access token
- Python 3.11 or higher, with `uv` or `pip-tools` installed

## Antigravity

Antigravity is Google's agentic development platform designed to streamline and
automate stages of the software development lifecycle. It empowers developers to
build, test, and deploy applications more efficiently by leveraging intelligent
agents, customizable skills, and rules. For more details, refer to the
Antigravity [documentation](https://antigravity.google/docs/overview).

## Antigravity customizations

### Agent's guardrails: Rules

Rules function as the governance layer of the development environment, allowing
developers to embed specific coding standards and behavioral expectations
directly into the agent's logic. By using Markdown-based configuration files at
either a global or project-specific level, teams can enforce persistent
compliance with organization-wide patterns or repository requirements. Refer to
the Antigravity
[rules documentation](https://antigravity.google/docs/rules-workflows) for more
details.

### Agent Skills

[Skills](https://antigravity.google/docs/skills) are modular, reusable knowledge
packages that extend an agent's capabilities and codify complex, multi-stage
procedures into repeatable sequences. Organized as folders containing a
`SKILL.md` file, skills provide specific instructions, best practices, and
resources for various tasks. You can define skills as workspace-specific or
global utilities. The agent discovers and activates skills when they are
relevant to the current context, or you can invoke a skill directly using a
`/<skill-name>` slash command to orchestrate tasks such as scanning code for
security vulnerabilities, generating unit tests, or opening a pull request.

### MCP servers integration

Model Context Protocol (MCP) support enables Antigravity to interface with local
tools, databases, and external services through the
[Model Context Protocol](https://modelcontextprotocol.io/) standard. By acting
as a dynamic bridge to the broader development environment, it allows the agent
to fetch real-time context, such as GitHub issues or JIRA tickets, directly when
needed, providing insights that extend beyond the active files in the editor.

## Skills and rules configuration

This repository comes with several custom skills and rules examples located
under the `.agents/rules` and `.agents/skills` folders.

### Prepare the environment

1.  Clone the repository:

    ```bash
    git clone --filter=blob:none --no-checkout https://github.com/GoogleCloudPlatform/cloud-solutions
    cd cloud-solutions
    git sparse-checkout set --cone projects/build-with-gemini-demo/build-with-antigravity
    git checkout
    cd projects/build-with-gemini-demo/build-with-antigravity
    ```

1.  [Download](https://antigravity.google/docs/getting-started?tab=ide) and
    install the Antigravity IDE extension for VS Code locally.

1.  Launch VS Code and open the cloned repository folder.

    Example:
    `cloud-solutions/projects/build-with-gemini-demo/build-with-antigravity`

1.  Open the Antigravity panel and explore existing skills and rules from the
    Explorer panel under the `.agents` folder.

1.  **(Optional) GitHub account and repository**: The final step of this guide
    involves creating a GitHub pull request. To complete the entire guide, you
    need a [GitHub account](https://github.com/signup), a personal access token,
    and a new repository.

### From idea to application

This guided walkthrough shows you how to build a functional web application from
a single prompt using the custom `/idea-to-app` skill. While this example builds
a conference event tracker, you can customize this skill for your own needs. To
use a different web framework such as Django, or connect to a different
database, modify the `.agents/skills/idea-to-app/SKILL.md` file to fit your
stack.

In the Antigravity panel, enter the following prompt:

```text
/idea-to-app build a web app to track conference events, add new events and view lists of upcoming events.
```

After you send this prompt, the agent outlines a plan and suggests a
specification for the application. Review the specification, and if you are
satisfied with the direction, instruct the agent to proceed.

Next, the agent presents an implementation plan where you can provide more
specific instructions as comments.

Click `Proceed` to approve the plan.

The agent creates the local virtual environment (`venv`), compiles and installs
pinned dependencies, and writes the code for your application following
`.agents/rules/dev-rules.md`. The files appear in the Explorer as the agent
works. Follow the agent's output and approve its suggestions.

When the agent finishes, it opens the application in your browser so you can
inspect the running application. You can also review the updated information in
the `Walkthrough` and `Task` views to see a summary of the completed work.

Before moving to the next step, ask the agent to stop the application.

### Generate unit tests

Now that you have a functional application, ensure it is robust by generating
unit tests. With the `/unit-tests` skill, you can automate the creation of test
suites for your codebase. This skill is adaptable to your project's specific
needs. For example, you can configure it to use different testing frameworks
such as `pytest` or `jest`, or to support various programming languages. To make
these customizations, edit the `.agents/skills/unit-tests/SKILL.md` file.

To begin, enter the following command in the Antigravity panel:

```text
/unit-tests
```

The agent analyzes the source code, identifies the key functions and logic, and
generates a corresponding set of unit tests. Follow the agent's progress and
inspect the new test files as they are created.

After generating the tests, the agent executes them to validate the generated
code and verify that your application's functionality works as expected. Once
the process is complete, review the generated tests and their execution results
to ensure they meet your standards. The `Walkthrough` view also provides a
summary of the created tests and their validation status.

### Proactive security scanning

Ensuring your application is secure is a critical step in the development
process. The `/security-scan` skill audits your source code, templates, and
dependencies against common vulnerability classes, such as the Open Worldwide
Application Security Project (OWASP) Top 10 and Common Weakness Enumeration
(CWE). You can tailor this skill to your security requirements and define custom
instructions or rules for vulnerability detection by editing the
`.agents/skills/security-scan/SKILL.md` file.

To initiate a security scan, enter the following command in the Antigravity
panel:

```text
/security-scan
```

The agent scans your codebase for common security issues and potential
vulnerabilities. Once the scan is complete, the agent presents its findings.
Review the identified issues and accept the agent's suggestions to address them.

### Documentation generation

Good documentation is essential for any project. The `/documentation` skill
automates the generation of application documentation. You can configure this
skill to use your preferred documentation tools and generate documentation in
various formats to suit your project's needs. To customize these settings,
modify the `.agents/skills/documentation/SKILL.md` file.

To generate your application's documentation, send the following prompt in the
Antigravity panel:

```text
/documentation
```

The agent analyzes your codebase and generates relevant documentation, including
API references, usage guides, or conceptual overviews, depending on your
configuration. Review the generated documentation and the agent's output to
ensure it aligns with your expectations.

### Automated code review

Maintaining code quality and adhering to team coding standards are crucial. With
the `/code-review` skill, you can automate the process of reviewing your code
for style, best practices, and potential issues. You can customize your coding
standards and review workflow by editing `.agents/rules/dev-rules.md` and
`.agents/skills/code-review/SKILL.md`.

To perform a local code review, send the following prompt in the Antigravity
panel:

```text
/code-review
```

The agent verifies your code against the configured rules and standards in
`.agents/rules/dev-rules.md` and reports any findings or areas for improvement.
Review the agent's report and apply any suggested fixes to enhance your code
quality. The `Walkthrough` and `Task` views also update with a summary of the
code review findings.

### Streamlined GitHub pull request creation

Once your code is tested, scanned for security, and reviewed for quality—or
verified in a single step using the `/pre-commit` skill
(`.agents/skills/pre-commit/SKILL.md`)—the final step in your development
process is to propose your changes. With the `/open-pr` skill, you can automate
the creation of GitHub pull requests, streamlining your contribution process. To
customize this skill, edit the `.agents/skills/open-pr/SKILL.md` file.

To use this skill, you first need a GitHub repository:

1.  **Create a new repository on GitHub**: Go to [repo.new](https://repo.new) to
    create a new GitHub repository named `build-with-antigravity-demo`.
1.  **Initialize local repository and set remote**: In your terminal, navigate
    to your project directory, such as
    `cloud-solutions/projects/build-with-gemini-demo/build-with-antigravity`,
    and run the following commands to initialize the repository and link it to
    your GitHub remote. Replace `YOUR-USERNAME` with your GitHub username:

    ```bash
    git init -b main
    git add README.md
    git commit -m "Initial commit"
    git remote add origin git@github.com:YOUR-USERNAME/build-with-antigravity-demo.git
    git push -u origin main
    ```

Next, configure your environment to allow the agent to interact with GitHub by
setting up the GitHub MCP server and providing a GitHub personal access token:

1.  **Create GitHub access token**: Create a new GitHub
    [personal access token (fine-grained)](https://github.com/settings/personal-access-tokens)
    and select the repository you created in the previous step. Grant the
    following permissions:
    - `Contents`: Read and write access
    - `Pull requests`: Read and write access
    - `Metadata`: Read-only access

1.  **Configure GitHub MCP server**: Open or create your Antigravity MCP
    configuration file at `.agents/mcp_config.json`.

1.  **Add configuration**: Insert the following configuration into your
    configuration file, replacing `"YOUR-GITHUB-ACCESS-TOKEN"` with the token
    you generated:

    ```json
    {
      "mcpServers": {
        "GitHub": {
          "command": "npx",
          "args": ["-y", "@modelcontextprotocol/server-github"],
          "env": {
            "GITHUB_PERSONAL_ACCESS_TOKEN": "YOUR-GITHUB-ACCESS-TOKEN"
          }
        }
      }
    }
    ```

Reload or restart VS Code if needed to load the updated configuration.

Once configured, create a new pull request by sending the following prompt in
the Antigravity panel:

```text
/open-pr
```

The agent creates a new pull request on GitHub with your changes according to
your specified configuration. Review the updated information in the
`Walkthrough` and `Task` views to see the details of the created pull request.

### Next steps

Adapt these skills to your own projects, integrate your preferred tools, and
explore how Antigravity helps you build software faster.
