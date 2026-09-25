# Automating UI tests with Playwright and Antigravity CLI

This guide demonstrates how to automate User Interface (UI) testing using the
Antigravity CLI in conjunction with the [Playwright](https://playwright.dev/)
Model Context Protocol (MCP) server. By leveraging natural language prompts,
developers can quickly define and execute sophisticated end-to-end UI tests
against a running application. This approach streamlines UI test automation,
highlighting easy environment setup, effective natural language automation, and
comprehensive testing reports to accelerate software delivery and improve
application quality.

## Requirements

To follow this demo, you need:

- Antigravity CLI: Installed and configured. For installation instructions,
  visit [antigravity.google](https://antigravity.google/docs/cli/install/).
- Python version 3.12 or higher
- Node.js version 24 or higher
- A Google Cloud project with the `Owner` role.

## Clone Git repository

1.  Open
    [Cloud Shell](https://cloud.google.com/shell/docs/launching-cloud-shell).

1.  Clone the repository and navigate to the application folder:

    ```bash
    git clone https://github.com/GoogleCloudPlatform/cloud-solutions && \
    cd cloud-solutions/projects/build-with-gemini-demo/automating-ui-tests-with-antigravity/roman-numeral-converter
    ```

## Prepare and start application

1.  Run commands to set up a virtual environment and install required
    dependencies:

    ```bash
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt --require-hashes
    ```

1.  Start the application:

    ```bash
    python main.py
    ```

## MCP servers configuration

Antigravity CLI uses a local workspace configuration to discover MCP servers.

Start a new terminal session, change into the application folder.

```bash
cd cloud-solutions/projects/build-with-gemini-demo/automating-ui-tests-with-antigravity/roman-numeral-converter
```

Create the `.agents` folder and `mcp_config.json` file within the cloned
project.

```bash
mkdir -p .agents && cat > .agents/mcp_config.json <<EOF
{
 "mcpServers": {
  "playwright": {
   "command": "npx",
   "args": [
    "-y",
    "@playwright/mcp@latest"
   ]
  }
 }
}
EOF
```

Launch the Antigravity CLI:

```bash
agy
```

List available MCP servers to confirm Playwright is configured:

```text
/mcp
```

The output should include `playwright`.

## Test UI with Playwright MCP server

Send the following prompt to start testing the application:

```text
Open the app at http://127.0.0.1:8080/ and check
that text “Roman Numerals” is present and the user can enter a number and hit
Convert! Button. Run several conversions such as 10, 25, and 50 and verify
results. Close the browser after you are done and provide the testing report.
```

If prompted, confirm the installation of any necessary components, such as
Playwright Chrome dependencies.

If you run the steps in your local environment, a new browser window opens,
showcasing the executed actions. Conversely, when running in Cloud Shell,
Playwright operates in headless mode, providing only the final results.

Sample output:

```text
   Testing Report: Roman Numerals Web Application

  ## Overview

  The Roman Numerals web application running at  http://127.0.0.1:8080/  was
  tested using Playwright browser automation to verify page content, form
  inputs, button functionality, and conversion accuracy.
  ──────
  ## 1. Initial Page Verification ( http://127.0.0.1:8080/ )

  • Page Title:  Roman Numerals
  • Heading:  <h1>Roman Numerals</h1>  — PASSED (Text "Roman Numerals" is present)
  • Form Elements:
      • Input field ( <input type="text" name="number" id="number" required/> ) — PASSED
      • Submit button ( <button>Convert!</button> ) — PASSED

  ──────
  ## 2. Test Cases & Conversion Results

   Test Case │ Input … │ Expect… │ Actual Result                     │ Status
  ───────────┼─────────┼────────┼───────────────────────────────────┼────────
   Case 1    │  10     │  X     │  "The number 10 is X in Roman     │ PASSED
             │         │        │ Numerals."                        │
   Case 2    │  25     │  XXV   │  "The number 25 is XXV in Roman   │ PASSED
             │         │        │ Numerals."                        │
   Case 3    │  50     │  L     │  "The number 50 is L in Roman     │ PASSED
             │         │        │ Numerals."                        │
  ──────
  ## 3. Navigation & Flow

  • Submitted inputs via the  Convert!  button.
  • Verified that each submission redirected to  http://127.0.0.1:8080/convert
  and displayed the correct output.
  • Successfully returned to the home page using the "Return to home page."
  link after each conversion.
  ──────
  ## 4. Browser Cleanup

  • The Playwright browser session has been closed.
```

Save the interaction sequence into Playwright script files, such as Python and
TypeScript:

```bash
Save this flow as a playwright test script. Provide both TypeScript and Python versions.
```

Sample output:

```text
Both TypeScript and Python versions of the Playwright test script covering
the entire flow have been created and saved in the codebase.
```

Exit the Antigravity CLI:

```bash
/exit
```
