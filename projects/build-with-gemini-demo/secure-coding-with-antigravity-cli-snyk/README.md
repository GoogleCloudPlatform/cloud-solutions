# Secure coding with Antigravity CLI and Snyk

This guide demonstrates how to integrate [Snyk](https://snyk.io/) with the
Antigravity CLI to scan and fix code vulnerabilities, accelerating secure
software delivery. It covers setting up Snyk, configuring the Snyk Model Context
Protocol (MCP) server, and using the Antigravity CLI with natural language
prompts to orchestrate Snyk scans and resolve issues. This integration enables
rapid identification and remediation of security issues, streamlining the secure
software delivery lifecycle by providing proactive security checks and ensuring
fixes are suggested and applied quickly.

## Requirements

To follow this demo, you need:

- A Google Cloud project with the `Owner` role.
- An active Snyk account.
- Antigravity CLI: Installed and configured. For installation instructions,
  visit [antigravity.google](https://antigravity.google/docs/cli/install/).

## Create Snyk account

The authentication flow requires an active Snyk account.

1.  [Log in with a Google account](https://app.snyk.io/login) to create your
    Snyk organization.

1.  Copy your "Auth Token" value from the Snyk Account settings > General page:
    [https://app.snyk.io/account](https://app.snyk.io/account)

1.  Activate Snyk Code in the
    [Settings page](https://app.snyk.io/manage/snyk-code?from=mcp).

## Install Snyk

1.  Open
    [Cloud Shell](https://cloud.google.com/shell/docs/launching-cloud-shell).

1.  Install the Snyk CLI. In Cloud Shell, you can use npm:

    ```bash
    npm install -g snyk@1.1307.4
    ```

    Alternatively, download and install the Snyk CLI appropriate for your
    operating system.
    [Docs](https://docs.snyk.io/developer-tools/snyk-cli/install-or-update-the-snyk-cli).

## Authenticate with Snyk

To authenticate in a local environment, run browser-based authentication:

```bash
snyk auth
```

For CI/CD configurations, this step requires your Auth Token key from the
settings page: [https://app.snyk.io/account](https://app.snyk.io/account)

Set the token variable. After running the following command, paste the token
value and press Enter:

```bash
read -s SNYK_TOKEN
```

Export the environment variable:

```bash
export SNYK_TOKEN
```

Authenticate using an API token:

```bash
snyk auth $SNYK_TOKEN
```

## Sample Git repository

Clone the [sample repo](https://github.com/GoogleCloudPlatform/cymbal-eats.git):

```bash
git clone https://github.com/GoogleCloudPlatform/cymbal-eats.git && \
cd cymbal-eats
```

## MCP servers configuration

Create the `.agents/mcp_config.json` file and folder within the cloned project,
then add the following MCP server configuration:

```bash
mkdir -p .agents && cat > .agents/mcp_config.json <<EOF
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

## Start Antigravity CLI and check Snyk MCP server

Launch the Antigravity CLI.

```bash
agy
```

List available MCP servers to confirm that Snyk is configured.

```text
/mcp
```

The output should include `✓ Snyk Security Scanner`.

## Run security scan

Send the following prompt to start a security scan:

```text
Execute a security scan on the employee-ui component and generate a detailed
vulnerability report without applying any automatic remediation.
```

**Expected Output:** The Antigravity CLI orchestrates a Snyk scan and outputs a
detailed report of security vulnerabilities found in the `employee-ui`
application. This report typically includes vulnerability severity, type,
affected files/lines, and potential remediation advice.

Sample report:

```text
  A security scan has been completed for the employee-ui component across
  both static source code (SAST) and open-source supply-chain dependencies
  (SCA). In accordance with your request, no automatic remediation has been
  applied, and the codebase remains untouched.

  A detailed vulnerability report has been generated:
  📄 **Security Vulnerability Assessment Report**
  ──────
  ### Key Scan Takeaways

  1. Static Application Security (SAST / Snyk Code):
      • High-Severity Path Traversal in index.js:42-46: User-controlled
      menuItemId from the request body flows directly into path.resolve and
      req.files.picture.mv, which allows an attacker to overwrite or delete
      arbitrary files on the server instance.
      • Missing Rate Limiting on the file upload route in index.js:34,
      leaving the service susceptible to resource exhaustion and DoS attacks.
      • Information Exposure (X-Powered-By) in index.js:21.
  2. Supply Chain Dependencies (SCA / Snyk Open Source):
      • Frontend (package.json): 46 vulnerabilities (2 Critical, 26 High, 17
      Medium, 1 Low). Key critical issues include arbitrary code injection in
      protobufjs (CVSS 9.5) and framing inconsistencies in websocket-driver
      (CVSS 9.2).
      • Cloud Run Backend (package.json): 29 vulnerabilities (3 Critical, 11
      High, 13 Medium, 2 Low). Key critical issues include user impersonation
      via proxy-addr (CVSS 9.3) and certificate validation / interpretation
      conflicts in node-forge (CVSS 9.3 & 9.1).
  3. Secrets Scanning:
      • Secrets scanning was checked; the feature is currently disabled at
      the Snyk organization level (SNYK-CLI-0016). Manual review verified
      that sensitive keys are loaded via runtime environment variables rather
      than hardcoded in the repository.

  ──────
  ### Next Steps & Decisions Needed

  Please review the **detailed report** to decide how you would like to
  proceed:

  • Would you like to patch the Path Traversal and hardening concerns in
  index.js?
  • Would you like to review upgrade paths and bump the dependencies in
  package.json and package.json?
                                                1 artifact · /artifact to review
```

## Fix security issues

Send the following prompt to fix the issues discovered in the previous step:

```text
Resolve these security vulnerabilities and re-run the verification scan.
```

**Expected Output:** The Antigravity CLI analyzes the previous scan report and,
with Snyk, attempts to fix the identified vulnerabilities. This may involve
modifying code and rerunning a scan to confirm the issues are resolved. The
output shows the progress of applying fixes, any code changes made, and a
confirmation of whether the vulnerabilities have been remediated.
