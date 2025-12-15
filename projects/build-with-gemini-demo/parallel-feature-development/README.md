# Parallel Feature Development with Gemini CLI

This demo guide illustrates a powerful workflow for accelerating software
development using the Gemini CLI in a multi-agent setup, enabling parallel
feature implementation. By utilizing Git worktrees, developers can simulate two
independent development streams—one focused on a UI feature (refactoring to use
Bootstrap) and the other on a Backend feature (adding an in-memory
database)—without interfering with the main branch.

The core of this demonstration showcases the ability of multiple Gemini CLI
sessions to autonomously work on separate, complex tasks concurrently, and the
subsequent process of merging these parallel changes, including conflict
resolution, back into the main branch.

## Requirements

To follow this demo, you need:

- A Google Cloud project with the `Owner` role.
- Gemini CLI: Installed and configured. For installation instructions, visit
  [geminicli.com](https://geminicli.com/docs/get-started/deployment/).

## Clone Git Repository

Open [Cloud Shell](https://cloud.google.com/shell/docs/launching-cloud-shell)
and clone the sample Python application repository:

```bash
git clone https://github.com/GoogleCloudPlatform/testing-with-duet-ai-codelab.git && \
cd testing-with-duet-ai-codelab
```

Set your Git account details:

```bash
git config --global user.email "you@example.com"
git config --global user.name "Your Name"
```

## Explain Codebase

Start the Gemini CLI and request a codebase explanation.

```bash
gemini
```

To learn the codebase, send the following prompt:

```text
Act as a Technical Lead. I am a new developer joining this project.
Please analyze this codebase and provide an Onboarding Guide.
Include the following:
- High-Level Architecture: What is the tech stack, and how do the components interact?
- Key Functionality: What are the top 3 primary features this code executes?
- Folder Structure: Briefly explain the purpose of the main directories.
- Data Flow: Trace the path of a request from the entry point to the database and back.
```

Sample output:

```text
✦ Welcome to the team! Here’s an onboarding guide to get you up to speed on this project.

  High-Level Architecture
   * Tech Stack: This is a Python application built with the Flask web framework.
   * Component Interaction:
       * main.py: Acts as the web server and handles routing for incoming HTTP requests.
       * calendar.py: Contains the core business logic for the application.
       * templates/: Holds the HTML files that make up the user interface.

  Key Functionality
   1. Home Page: Renders a simple web page with a form to accept user input.
   2. Number to Roman Numeral Conversion: The primary feature, which converts an integer into its Roman numeral equivalent.
   3. Result Display: Shows the conversion result on a dedicated page.

  Folder Structure
   * main.py: The main application entry point.
   * calendar.py: A module for the conversion logic.
   * requirements.txt: Lists project dependencies (just Flask).
   * templates/: Contains the HTML templates for the web pages.
       * index.html: The home page.
       * convert.html: The results page.

  Data Flow
   1. A user accesses the root URL (/).
   2. The home_page function in main.py renders the index.html template.
   3. The user submits a number through the form, sending a POST request to the /convert endpoint.
   4. The convert function in main.py receives the request and extracts the number.
   5. This function then calls number_to_roman from calendar.py to perform the conversion.
   6. The result is passed to the convert.html template, which is rendered and returned to the user's browser.
```

## Setup Git Worktrees

Git worktrees allow you to have multiple working directories attached to the
same repository, with different branches checked out in each. This enables
developers to work on multiple features simultaneously without constantly
switching branches in a single working directory.

To set up Git worktrees, send the following prompt:

```text
create a new folder .trees, use git command to create new worktree inside
.trees folder for two new features: ui_feature and backend_feature
```

Sample output:

```text
✦ I have created the .trees directory and the ui_feature and backend_feature worktrees.
```

Press `Ctrl + C` twice to exit Gemini CLI.

To verify the Git worktrees were created, you can run the following command in
the terminal:

```bash
git worktree list
```

Sample output:

```bash
~/testing-with-duet-ai-codelab                         3707559 [main]
~/testing-with-duet-ai-codelab/.trees/backend_feature  3707559 [backend_feature]
~/testing-with-duet-ai-codelab/.trees/ui_feature       3707559 [ui_feature]
```

## Before Parallel Tasks

Initially, the application has a basic Flask backend and a simple HTML/CSS
frontend. The Roman numeral conversion logic is functional, but there's no
database integration, and the UI lacks modern styling.

## Parallel Tasks

In this phase, we will use two separate Gemini CLI sessions, each operating
within its own Git worktree (`ui_feature` and `backend_feature`), to
independently implement new features.

### Backend Changes

Open a new terminal window and switch to the `backend_feature` folder:

```bash
cd ~/testing-with-duet-ai-codelab/.trees/backend_feature
```

Start Gemini CLI and request the Backend changes:

```text
Add in-memory database to keep track of the requests. Stop and report when you are done with the changes.
```

### UI Changes

Open a new terminal window and switch to the `ui_feature` folder:

```bash
cd ~/testing-with-duet-ai-codelab/.trees/ui_feature
```

Start Gemini CLI and request the UI changes:

```text
Refactor to use bootstrap. Stop and report when you are done with the changes.
```

Follow the steps to apply changes for both sessions. At any point, you can hit
“Escape” and redirect the agent if it’s going off course.

## After Parallel Tasks

After the Gemini CLI completes the tasks in both worktrees:

- **`backend_feature`**: The backend will include an in-memory database to log
  conversion requests.
- **`ui_feature`**: The frontend templates will be refactored to use Bootstrap
  for improved styling and responsiveness.

## Commit New Changes

To commit the changes in each session, send the following prompt:

```text
Add and commit files with descriptive message
```

## Merge Changes Into Main Branch

From the terminal with the main branch open, initiate a merge of the worktrees:

```text
Use git merge command to merge in all of the worktrees in the .trees folder
and fix any conflicts if there are any
```

Sample output:

```text
✦ Okay, I'm done. I merged and resolved conflicts between ui_feature, backend_feature, and main, then cleaned up by removing the worktrees, the .trees directory, and deleting the feature branches. I'll let the user know.
```

Press `Ctrl + C` twice to exit Gemini CLI.

## Test Application

Run commands to set up a virtual environment and install required dependencies:

```text
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start the application:

```bash
python main.py
```

Click the provided link to open the application in your browser.

In the Cloud Shell environment, select 'Web Preview' from the menu, change the
port (e.g., 8080), and then preview the application.

You should now see a visually updated application with Bootstrap styling
applied, and the backend will be tracking requests in-memory.
