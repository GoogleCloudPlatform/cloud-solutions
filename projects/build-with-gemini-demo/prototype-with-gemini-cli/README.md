# Prototype with Gemini CLI

This demo shows the power and efficiency of using the Gemini CLI for rapid
prototyping. It guides you from a conceptual idea to a running web application
prototype by leveraging the CLI's custom commands.

The Gemini CLI significantly shortens the prototyping cycle, allowing for faster
iteration and experimentation. By using the CLI, developers can quickly validate
ideas and focus on the core logic and unique aspects of their application while
automating boilerplate code generation and setup.

This demo guide walks you through the following steps:

1.  Prepare the environment
1.  Build a specification for an application idea
1.  Implement application using the specification
1.  Test application and iterate on the features

## Requirements

To follow this demo, you need:

- A Google Cloud project with the `Owner` role.
- Gemini CLI: Installed and configured. For installation instructions, visit
  [geminicli.com](https://geminicli.com/docs/get-started/deployment/).

## Custom Commands

The custom commands for this project are defined in the `.gemini/commands`
directory. These TOML files configure the prompts and behavior of the agent for
specific tasks.

### `/idea-to-spec` - Idea to specification

- Transforms a user's idea into a detailed specification for a prototype. The
  prompt for this command is defined in `.gemini/commands/idea-to-spec.toml`.

### `/spec-to-code` - Specification to code

- Generates a running application from a detailed specification. The prompt for
  this command is defined in `.gemini/commands/spec-to-code.toml`.

## Prepare the environment

1.  Open
    [Cloud Shell](https://cloud.google.com/shell/docs/launching-cloud-shell).

1.  Clone the repository and set the working directory:

    ```bash
    git clone https://github.com/GoogleCloudPlatform/cloud-solutions && \
    cd cloud-solutions
    ```

1.  Change the working directory:

    ```bash
    cd "$(git rev-parse --show-toplevel)/projects/build-with-gemini-demo/prototype-with-gemini-cli"
    ```

### Start prototyping

1.  Run Gemini CLI:

    ```bash
    gemini
    ```

1.  Type `/spec` to confirm the custom commands are loaded and available.

    ```text
    /spec
    ```

    The output will list two custom commands, each with a brief description.

### Idea to running application

1.  Send prompt to create specification for your idea:

    ```text
    /idea-to-spec build a web app to track conference events, add new events and view lists of upcoming events.
    ```

    Review the generated specification and send follow-up prompts to refine it
    as needed.

1.  Send prompt to build the application:

    ```text
    /spec-to-code build the application using the spec
    ```

    Review and approve tools and suggested code changes.

### Start the application

1.  Open a new terminal and change into the new application folder that was
    created in the previous step:

    ```bash
    cd REPLACE_WITH_YOUR_FOLDER_NAME
    ```

1.  Run commands to set up virtual environment and install required
    dependencies:

    ```bash
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

1.  Start the application:

    ```bash
    python app.py
    ```

    Click on the link to open the application in the browser.

    In the Cloud Shell environment, select `Web Preview` from the menu and
    change port (e.g., 5000) and preview the application.

### Iterate on the idea

Return to Gemini CLI and experiment by requesting modifications to the
application.

1.  Send prompt to refactor the application:

    ```text
    Refactor to use latest Google Material Design
    ```

    Reload application in the browser.

    In the Cloud Shell environment, select Web Preview from the menu and change
    port (e.g., 5000) and preview the application.
