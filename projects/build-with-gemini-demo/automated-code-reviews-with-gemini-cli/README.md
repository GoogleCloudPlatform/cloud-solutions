# Automated code reviews with Gemini CLI

This guide demonstrates how to integrate the Gemini CLI in non-interactive mode
(without requiring any user input) within GitHub Actions workflows to automate
various development tasks. By leveraging Gemini's capabilities directly within
your CI/CD pipelines, you can streamline processes such as generating code
review summaries, drafting documentation, or creating release notes. This
automation leads to faster, more consistent, and efficient development cycles by
reducing the need for manual intervention.

## Requirements

To follow this guide, you need:

- A Google Cloud project with the `Owner` role.
- Fork the sample repository into your GitHub account to use in the following
  steps. Sample repository:
  [GoogleCloudPlatform/cymbal-eats](https://github.com/GoogleCloudPlatform/cymbal-eats)

## API Key Configuration

The Gemini CLI requires authentication to interact with the Gemini API. When
running in a GitHub Actions workflow, the non-interactive mode uses an API key
for authentication.

1.  **Generate a Gemini API Key:** Generate a Gemini API key from
    [Google AI Studio](https://aistudio.google.com/api-keys). This key grants
    access to the Gemini model and must be treated as a sensitive secret.
1.  **Store the API Key as a GitHub Secret:** For security, the generated API
    key must not be hardcoded directly into the workflow file. Instead, it
    should be stored as a GitHub Repository Secret.
    - Navigate to your GitHub repository's **Settings** tab.
    - Click on **Secrets and variables > Actions**.
    - Click **New repository secret**.
    - Name the secret (e.g., `GEMINI_API_KEY`) and paste the generated API key
      into the **Secret value** field.
1.  **Reference the Secret in the Workflow:** The GitHub Actions workflow will
    reference this secret using the standard GitHub Actions syntax
    (`${{ secrets.GEMINI_API_KEY }}`) and pass it to the Gemini CLI command,
    typically via an environment variable. This ensures the key is never exposed
    in the build logs or committed to the repository.

## GitHub Actions Workflow File Configuration

The core of the GitHub Actions integration is the workflow file, typically a
YAML file located in the `.github/workflows/` directory of the repository (e.g.,
`.github/workflows/gemini-review.yml`). This file defines the automated process,
including the trigger event, the environment, and the steps to execute the
Gemini CLI. For an example, see the
[sample GitHub Actions workflow file](https://github.com/GoogleCloudPlatform/cymbal-eats/blob/main/.github/workflows/review.yml).

## Gemini CLI Non-interactive Mode

The Gemini CLI's non-interactive mode (using the `-p` or `--prompt` option) is
designed for automated environments like CI/CD pipelines. In this mode, the CLI
operates without requiring user input, making it ideal for script-based
execution within GitHub Actions workflows. It processes commands and prompts
directly, enabling automated tasks such as code analysis, content generation,
and structured output.

Sample non-interactive prompt to check for code documentation:

```bash
gemini -p 'Review Java code and check that all classes are properly documented and provide suggestions on how to improve the documentation in the code and return findings as text in markdown format to the console' >> $GITHUB_STEP_SUMMARY
```

## Essential Components of the Workflow

Review the
[sample GitHub Actions workflow file](https://github.com/GoogleCloudPlatform/cymbal-eats/blob/main/.github/workflows/review.yml).

```yaml
# AI powered code reviews using Gemini CLI
name: Code Reviews
run-name: Reviewing ${{ github.actor }}'s code changes  🚀
on: [push, workflow_dispatch]
env:
  GEMINI_API_KEY: '${{ secrets.GEMINI_API_KEY }}'
jobs:
  Gemini-CLI-Code-Reviews:
    runs-on: ubuntu-latest
    steps:
      - name: Check out repository code
        uses: actions/checkout@v4
      - name: List files in the repository
        run: |
          ls ${{ github.workspace }}

      - run: cd ${{ github.workspace }}/menu-service
      - run: npm install -g @google/gemini-cli

      - name: Documentation Coverage Review
        run: echo '## Documentation Coverage Review Results 🚀' >> $GITHUB_STEP_SUMMARY
      - run: gemini -p 'Review menu-service java code and check that all classes are properly documented and provide suggestions on how to improve the documentation in the code and return findings as text in markdown format to the console' >> $GITHUB_STEP_SUMMARY
        shell: bash

      - name: Test Coverage Review
        run: echo '## Test Coverage Review Results 🚀' >> $GITHUB_STEP_SUMMARY
      - run: gemini -p 'Review menu-service java code and check that all classes and methods have test coverage and provide suggestions on how to improve the test coverage in the code and return findings as text in markdown format to the console' -y >> $GITHUB_STEP_SUMMARY
        shell: bash
```

1.  **Name and Trigger:**
    - The `name` field provides a human-readable title for the workflow, visible
      in the GitHub Actions UI.
    - The `on` field specifies the GitHub event(s) that will run the workflow.
1.  **Jobs:**
    - A workflow is composed of one or more jobs. Each job runs in a specified
      environment (e.g., `runs-on: ubuntu-latest`) and can contain multiple
      steps.
1.  **Steps to Execute Gemini CLI:**
    - **Checkout:** The first step usually involves checking out the repository
      code using the `actions/checkout@v4` action, making the project files
      available to the workflow runner.
    - **Setup Environment:** If necessary, steps to set up the runtime
      environment (e.g., Node.js, Python) may be included.
    - **Install Gemini CLI:** The workflow must include a step to install the
      Gemini CLI. This can be done using a package manager like `npm`, or by
      directly executing a setup script.
    - **Execute the Command:** This is the critical step where the Gemini CLI is
      called in its non-interactive mode. The command must:
        - Be run with the API key passed via an environment variable.
        - Include the desired prompt and input data (e.g., file contents, git
          diff output, or recent commit messages).
        - Define the desired output behavior (e.g., writing the result to a new
          file, adding a comment to a pull request, or logging to the console)
          via CLI command parameters.

## Test The Workflow

To verify your GitHub Actions workflow with the Gemini CLI:

1.  **Clone the repo:** In your terminal, replace YOUR_GITHUB_USERNAME with your
    actual GitHub username and clone the repository locally.

    ```bash
    git clone git@github.com:YOUR_GITHUB_USERNAME/cymbal-eats.git
    ```

1.  **Create a New Branch:** From your repository, create a new branch to test
    your changes.

    ```bash
    git switch --create feature/test-gemini-review
    ```

1.  **Make a Code Change:** Modify a file in your repository. For example, add a
    comment to a Java file if your prompt is for Java code review.

1.  **Commit and Push:** Commit your changes and push the new branch to GitHub.

    ```bash
    git add .
    git commit -m "Test: Trigger Gemini CLI code review workflow"
    git push origin feature/test-gemini-review
    ```

1.  **Create a Pull Request (Optional, but Recommended for `pull_request`
    trigger):** If your workflow is configured to run on `pull_request` events,
    create a pull request from your `feature/test-gemini-review` branch to
    `main` (or your base branch).

1.  **Monitor GitHub Actions:**
    - Navigate to the "Actions" tab in your GitHub repository.
    - Find your workflow run (it should be triggered by your push or pull
      request).
    - Click on the workflow run to view its steps and logs.
    - Verify that the Gemini CLI step executed successfully and that the output
      (e.g., code review comments, generated summary) appears as expected.

        The output is similar to the following:

        ```text
        Documentation Coverage Review Results

        General Recommendations
        The codebase currently lacks Javadoc comments for all classes and methods. Adding Javadocs would significantly improve the maintainability and readability of the code.

        Each class should have a Javadoc comment that explains its purpose. Each method should have a Javadoc comment that explains what it does, its parameters (@param), and what it returns (@return).


        Test Coverage Review Results

        Okay, I will review the menu-service Java code, check for test coverage, and suggest improvements in markdown format.
        Based on the file list, Status.java, Menu.java, and MenuRepository.java are missing corresponding test files. I will now examine the existing source and test files to assess method-level test coverage.
        ```

1.  **Review Output:** Check the `Summary` of your workflow run for the output
    generated by the Gemini CLI.
