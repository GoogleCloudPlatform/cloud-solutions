# Scanning and fixing security issues with Gemini CLI and Snyk

This guide demonstrates how to integrate [Snyk](https://snyk.io/) with the
Gemini CLI to scan and fix code vulnerabilities, accelerating secure software
delivery. It covers the setup process, configuring the Snyk MCP server, and
using Gemini CLI with natural language prompts to orchestrate Snyk scans and
automatically resolve issues. This integration enables rapid identification and
remediation of security issues, streamlining the secure software delivery
lifecycle by providing proactive security checks and ensuring fixes are
suggested and applied quickly.

## Requirements

To follow this demo, you need:

- A Google Cloud project with the `Owner` role.
- An active Snyk account
- Gemini CLI: Installed and configured. For installation instructions, visit
  [geminicli.com](https://geminicli.com/docs/get-started/deployment/).

## Create Snyk account

An active Snyk account is required for the authentication flow.

1.  [Log in with a Google account](http://app.snyk.io/login) to create your Snyk
    organization.

1.  Copy your "Auth Token" value from the Snyk Account settings > General page:
    [https://app.snyk.io/account](https://app.snyk.io/account)

1.  Activate Snyk Code in the
    [Settings page](https://app.snyk.io/manage/snyk-code?from=mcp).

## Install Snyk

1.  Open
    [Cloud Shell](https://cloud.google.com/shell/docs/launching-cloud-shell).

1.  Install the Snyk CLI. In Cloud Shell, you can use npm:

    ```bash
    npm install -g snyk
    ```

    Alternatively, download and install the Snyk CLI appropriate for your
    operating system.
    [Docs](https://docs.snyk.io/developer-tools/snyk-cli/install-or-update-the-snyk-cli).

## Snyk Authentication

For this step, you will need your Auth Token key from the settings page:
[https://app.snyk.io/account](https://app.snyk.io/account)

```bash
snyk auth YOUR_AUTH_TOKEN_KEY
```

For local environment demonstrations, a browser-based authentication flow is
available as an alternative.

```bash
snyk auth
```

## Sample Git Repository

Clone the [sample repo](https://github.com/GoogleCloudPlatform/cymbal-eats.git):

```bash
git clone https://github.com/GoogleCloudPlatform/cymbal-eats.git && \
cd cymbal-eats
```

## MCP Servers configuration

Create the `.gemini/settings.json` file and folder within the cloned project,
then add the following MCP server configuration:

```bash
mkdir -p .gemini && cat > .gemini/settings.json <<EOF
{
   "mcpServers": {
       "Snyk Security Scanner": {
           "command": "snyk",
           "args": [
               "mcp",
               "-t",
               "stdio",
               "--experimental"
           ],
           "env": {}
       }
   }
}
EOF
```

## Start Gemini CLI and check Snyk MCP server

Launch the Gemini CLI.

```bash
gemini
```

List available MCP servers to confirm Snyk is configured.

```text
/mcp list
```

The output should include `Snyk Security Scanner - Ready`.

## Run security scan

Send the following prompt to start security code scan:

```text
Run a security code scan for the employee-ui application and provide a detailed issue report without attempting fixes.
```

**Expected Output:** The Gemini CLI will orchestrate a Snyk scan, which will
output a detailed report of security vulnerabilities found in the `employee-ui`
application. This report typically includes vulnerability severity, type,
affected files/lines, and potential remediation advice.

Sample report:

```text
Snyk code scan found 3 issues:

## High Severity:
* **Path Traversal (CWE-23)**
    * File: `/home/user/cymbal-eats/employee-ui/cloud-run/index.js:45`
    * Description: Unsanitized input from the HTTP request body flows into `mv`, where it is used as a path. This could allow an attacker to write to arbitrary files on the system.

## Medium Severity:
* **Information Exposure – X-Powered-By Header (CWE-200)**
    * File: `/home/user/cymbal-eats/employee-ui/cloud-run/index.js:21`
    * Description: Disable `X-Powered-By` header for your Express app.
* **Allocation of Resources Without Limits or Throttling (CWE-770)**
    * File: `/home/andrey/mmb/cymbal-eats/employee-ui/cloud-run/index.js:34`
    * Description: Expensive operation (a file system operation) is not rate-limited. This could lead to a denial of service.
```

## Fix security issues

Send the following prompt to fix the issues discovered in the previous step:

```text
Fix these issues and test again.
```

**Expected Output:** The Gemini CLI will analyze the previous scan report and,
with Snyk, attempt to automatically fix the identified vulnerabilities. This may
involve modifying code and re-running a scan to confirm the issues are resolved.
The output will show the progress of applying fixes, any code changes made, and
a confirmation of whether the vulnerabilities have been remediated.
