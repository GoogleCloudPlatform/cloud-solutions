# Prototype with the Gemini CLI Conductor Extension

This demo showcases the power and efficiency of using the Gemini CLI for rapid
prototyping, guiding you from a conceptual idea to a running web application. It
leverages the Conductor extension for the Gemini CLI, which transforms the CLI
into a proactive project manager.

Conductor enables Context-Driven Development, ensuring a consistent lifecycle
for every task: Context -> Spec & Plan -> Implement. This approach significantly
shortens the prototyping cycle, allowing for faster iteration and
experimentation. By treating context as a managed artifact alongside your code,
developers can quickly validate ideas and focus on core logic while automating
boilerplate code generation and setup.

This demo guide walks you through the following steps:

1.  Prepare the environment
1.  Build a specification and a plan for an application idea
1.  Implement the application using the specification
1.  Test the application and iterate on the features

## Requirements

To follow this demo, you need:

- A Google Cloud project with the `Owner` role.
- Gemini CLI: Installed and configured. For installation instructions, visit
  [geminicli.com](https://geminicli.com/docs/get-started/deployment/).
- [Conductor Extension](https://github.com/gemini-cli-extensions/conductor) for
  Gemini CLI installed.

## Prepare the environment

1.  Open
    [Cloud Shell](https://cloud.google.com/shell/docs/launching-cloud-shell).

1.  Clone the repository and set the working directory:

    ```bash
    git clone --filter=blob:none --no-checkout https://github.com/GoogleCloudPlatform/cloud-solutions
    cd cloud-solutions
    git sparse-checkout set --cone projects/build-with-gemini-demo/prototype-with-gemini-cli-conductor
    git checkout
    cd projects/build-with-gemini-demo/prototype-with-gemini-cli-conductor
    ```

### Start prototyping

1.  Run the Gemini CLI:

    ```bash
    gemini
    ```

1.  Type `/conductor` to confirm the Conductor Extension is loaded and
    available.

    ```text
    /conductor
    ```

    The output will list Conductor commands, each with a brief description.

### Configure project context

This repository comes preconfigured with essential context files in the
`conductor` folder (`product.md`, `tech-stack.md`, `workflow.md`). For new
projects, you would typically use the `/conductor:setup` command to define these
initial project guidelines, tech stack, and workflow interactively.

### From idea to running application

1.  Send a prompt to create a specification for your idea:

    ```text
    /conductor:newTrack build a modern web app to track conference events, with features like adding new events, editing events and listing upcoming events.
    ```

    Review the generated specification and plan. Send follow-up prompts to
    refine them as needed.

1.  Send a prompt to build the application:

    ```text
    /conductor:implement
    ```

    Review and approve the tools and suggested code changes.

### Start the application

1.  Open a new terminal and change into the new application folder that was
    created in the previous step:

    ```bash
    cd REPLACE_WITH_APP_FOLDER_NAME
    ```

    Where `REPLACE_WITH_APP_FOLDER_NAME` is the application folder created in
    the previous step.

1.  Run commands to set up a virtual environment and install the required
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

    In the Cloud Shell environment, select `Web Preview` from the menu, change
    the port (e.g., 5000), and preview the application.

### Iterate on the idea

Return to the Gemini CLI and experiment by requesting modifications to the
application.

1.  Send a prompt to refactor the application:

    ```text
    /conductor:newTrack Refactor to use latest Google Material Design
    ```

    Review and approve tools and suggested code changes.

    In the Cloud Shell environment, select Web Preview from the menu and change
    port (e.g., 5000) and preview the application.

### Finalize the changes

Once you are done with the changes, you have several options:

1.  **Review:** Run the review command to verify changes before finalizing.
1.  **Archive:** Move the track's folder to `conductor/archive/` and remove it
    from the tracks file.
1.  **Delete:** Permanently delete the track's folder and remove it from the
    tracks file.
1.  **Skip:** Do nothing and leave it in the tracks file.
