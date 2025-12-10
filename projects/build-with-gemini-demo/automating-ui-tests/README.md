# Automating UI tests with Playwright & Gemini CLI

This guide demonstrates how to automate User Interface (UI) testing using the
Gemini CLI in conjunction with the [Playwright](https://playwright.dev/) MCP
server. By leveraging natural language prompts, developers can quickly define
and execute sophisticated end-to-end UI tests against a running application.
This approach streamlines UI test automation, highlighting easy environment
setup, effective natural language automation, and comprehensive testing reports
to accelerate software delivery and improve application quality.

## Requirements

To follow this demo, you need:

- A Google Cloud project with the `Owner` role.
- Gemini CLI: Installed and configured. For installation instructions, visit
  [geminicli.com](https://geminicli.com/docs/get-started/deployment/).

## Clone Git Repository

1.  Open
    [Cloud Shell](https://cloud.google.com/shell/docs/launching-cloud-shell).

1.  Clone the
    [sample repo](https://github.com/GoogleCloudPlatform/testing-with-duet-ai-codelab.git):

    ```bash
    git clone https://github.com/GoogleCloudPlatform/testing-with-duet-ai-codelab.git && \
    cd testing-with-duet-ai-codelab
    ```

## MCP Servers configuration

Create the `.gemini/settings.json` folder and file within the cloned project,
then add the following MCP server configuration:

```bash
mkdir -p .gemini && cat > .gemini/settings.json <<EOF
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": [
        "@playwright/mcp@latest"
      ]
    }
  }
}
EOF
```

Launch the Gemini CLI:

```bash
gemini
```

List available MCP servers to confirm Playwright is configured:

```text
/mcp list
```

The output should include `playwright - Ready`.

Press `Ctrl + C` twice to exit Gemini CLI.

## Prepare and Start Application

1.  Run commands to set up a virtual environment and install required
    dependencies:

    ```bash
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

1.  Start the application:

    ```bash
    python main.py
    ```

## Test UI with Playwright MCP server

With the application running, start a new terminal session, change into the
application folder and launch the Gemini CLI:

```bash
cd testing-with-duet-ai-codelab
```

Launch the Gemini CLI:

```bash
gemini
```

Send the following prompt to start testing the application:

```text
Open the app at http://127.0.0.1:8080/ and check
that text “Roman Numerals” is present and the user can enter a number and hit
Convert! Button. Run several conversions(10, 25, 50) and verify results. Close
the browser after you are done and provide the testing report.
```

If prompted, confirm the installation of any necessary components, such as
Chrome.

If you are running the steps in your local environment, a new browser window
will open, showcasing the executed actions. Conversely, when running in Cloud
Shell, Playwright will operate in headless mode, providing only the final
results.

Sample output:

```text
✦ Testing Report

  Application: Roman Numeral Converter
  URL: http://127.0.0.1:8080/

  Test Summary:
  The application was tested to verify its core functionality, which includes displaying the main page correctly and converting numbers to Roman numerals. All tests passed successfully.

  Test Cases:

   1. Main Page Verification:
       * Description: Opened the application URL and verified the presence of the main page elements.
       * Expected Result: The page should display the heading "Roman Numerals", an input field for numbers, and a "Convert!" button.
       * Actual Result: The page loaded successfully and all expected elements were present.
       * Status: PASS

   2. Conversion of 10:
       * Description: Entered the number 10 and clicked the "Convert!" button.
       * Expected Result: The application should display the Roman numeral "X".
       * Actual Result: The application correctly converted 10 to "X".
       * Status: PASS

   3. Conversion of 25:
       * Description: Entered the number 25 and clicked the "Convert!" button.
       * Expected Result: The application should display the Roman numeral "XXV".
       * Actual Result: The application correctly converted 25 to "XXV".
       * Status: PASS

   4. Conversion of 50:
       * Description: Entered the number 50 and clicked the "Convert!" button.
       * Expected Result: The application should display the Roman numeral "L".
       * Actual Result: The application correctly converted 50 to "L".
       * Status: PASS

  Conclusion:
  The Roman Numeral Converter application is functioning as expected. The user interface is clear and the conversion logic is correct for the tested values.
```
