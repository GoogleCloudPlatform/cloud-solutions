# Automate GitHub Pull Requests reviews with Code Review Agent

This demo goes over the process of integrating and utilizing Gemini Code Assist
to improve GitHub code reviews. The demo will cover essential setup procedures
in both Google Cloud and GitHub, followed by a showcase of Gemini Code Assist's
capabilities in delivering smart suggestions, clear explanations, and concise
summaries to optimize the code review workflow.

## Requirements

To follow this demo, you need:

- A Google Cloud project with the `Owner` role.
- GitHub account and repository
- Antigravity CLI: Installed and configured. For installation instructions,
  visit
  [antigravity.google](https://antigravity.google/docs/getting-started/?tab=cli#download-and-install).
- GitHub CLI: Installed and configured. For installation instructions, visit
  [Installation](https://github.com/cli/cli?tab=readme-ov-file#installation).

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

### Prepare to create GitHub Pull Request

Return to the Cloud Shell terminal and clone the repository. Update the path to
`~/gemini-code-review-agent` folder in the commands below, if you didn't clone
it in the home folder.

1.  Clone the repository:

    ```bash
    git clone --filter=blob:none --no-checkout https://github.com/GoogleCloudPlatform/cloud-solutions
    cd cloud-solutions
    git sparse-checkout set --cone projects/build-with-gemini-demo
    git checkout
    ```

1.  Copy `menu-service` folder:

    ```bash
    cp -r "$(git rev-parse --show-toplevel)/projects/build-with-gemini-demo/gemini-powered-development/menu-service" ~/gemini-code-review-agent
    ```

1.  Change into `~/gemini-code-review-agent` folder:

    ```bash
    cd ~/gemini-code-review-agent
    ```

1.  Start Antigravity CLI:

    ```bash
    agy
    ```

1.  Commit new changes and open a pull request:

    ```text
    Create a new feature branch, add/commit all the changes and open a new pull request using gh cli.
    ```

    Review and approve tools that Antigravity CLI requires to complete this
    task.

Exit from Antigravity CLI before moving to the next section.

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
