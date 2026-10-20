# Automated code reviews with Antigravity CLI

This guide shows you how to run the Antigravity CLI (`agy`) in non-interactive
mode within GitHub Actions workflows to automate code reviews. You configure
keyless authentication to Google Cloud using Workload Identity Federation (WIF)
and Application Default Credentials (ADC), then run `agy` in a Continuous
Integration and Continuous Delivery (CI/CD) pipeline to evaluate documentation
and test coverage.

## Requirements

To follow this guide, you need:

- A Google Cloud project with the `Owner` role (`roles/owner`), or the following
  Identity and Access Management (IAM) roles to enable APIs, create service
  accounts, bind project IAM policies, and configure WIF:
    - Service Usage Admin (`roles/serviceusage.serviceUsageAdmin`)
    - Service Account Admin (`roles/iam.serviceAccountAdmin`)
    - Project IAM Admin (`roles/resourcemanager.projectIamAdmin`)
    - IAM Workload Identity Pool Admin (`roles/iam.workloadIdentityPoolAdmin`)
- A GitHub account with **Admin** access to the target repository to configure
  GitHub Actions secrets and workflow files. Fork the sample repository into
  your GitHub account, which grants you admin access to your fork, to use in the
  following steps:
  [GoogleCloudPlatform/cymbal-eats](https://github.com/GoogleCloudPlatform/cymbal-eats)

## Google Cloud authentication setup

The GitHub Actions workflow authenticates the Antigravity CLI (`agy`) against
Google Cloud using WIF and ADC with `AGY_ADC_AUTH=1`.

### Set environment variables and enable APIs

Replace `YOUR_PROJECT_ID` with your Google Cloud project ID and
`YOUR_GITHUB_USERNAME/cymbal-eats` with your GitHub repository path, then enable
the required Google Cloud APIs:

```bash
export PROJECT_ID="YOUR_PROJECT_ID"
export GITHUB_REPO="YOUR_GITHUB_USERNAME/cymbal-eats"
export SA_NAME="agy-ci"
export SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
export POOL_ID="github-pool"
export PROVIDER_ID="github-provider"

if ! PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)") || [[ -z "${PROJECT_NUMBER}" ]]; then
  echo "Error: Failed to retrieve PROJECT_NUMBER. Ensure PROJECT_ID is set and gcloud is authenticated." >&2
else
  export PROJECT_NUMBER
  echo "Project Number: ${PROJECT_NUMBER}"
fi
```

Enable the required APIs, which requires the `Owner` role (`roles/owner`) or the
Service Usage Admin role (`roles/serviceusage.serviceUsageAdmin`) on the
project:

```bash
gcloud services enable \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  aiplatform.googleapis.com \
  cloudaicompanion.googleapis.com \
  serviceusage.googleapis.com \
  --project="${PROJECT_ID}"
```

### Create the service account and grant project roles

Create a dedicated Google Cloud service account that the GitHub Actions runner
impersonates through WIF. Instead of storing a static service account key in
GitHub, the workflow exchanges a short-lived GitHub OpenID Connect (OIDC) token
for temporary ADC credentials bound to this service account. When you set
`AGY_ADC_AUTH=1`, `agy` uses these credentials to authenticate requests to
Google Cloud.

```bash
gcloud iam service-accounts create "${SA_NAME}" \
  --display-name="Antigravity CI Service Account" \
  --project="${PROJECT_ID}"
```

Grant the service account the following IAM roles:

- **Gemini platform AI User (`roles/aiplatform.user`):** Allows `agy` to
  discover and invoke Gemini models on Gemini platform.
- **Gemini for Google Cloud User (`roles/cloudaicompanion.user`):** Grants
  access to the Cloud AI Companion APIs used by the Antigravity agent service.
- **Service Usage Consumer (`roles/serviceusage.serviceUsageConsumer`):** Allows
  the service account to bill API calls and consume quota against your Google
  Cloud project (`GOOGLE_CLOUD_QUOTA_PROJECT`).

```bash
for ROLE in \
  "roles/aiplatform.user" \
  "roles/cloudaicompanion.user" \
  "roles/serviceusage.serviceUsageConsumer"; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}" \
    --condition=None
done
```

### Create Workload Identity Pool and GitHub OIDC provider

WIF lets external workloads such as GitHub Actions authenticate to Google Cloud
without exported service account keys. At runtime, the
`google-github-actions/auth` step requests a signed OIDC JSON Web Token (JWT)
from GitHub's token issuer (`https://token.actions.githubusercontent.com`) and
sends it to the Google Cloud Security Token Service (STS). STS validates the
token against your WIF provider configuration and exchanges it for a short-lived
federated access token that impersonates your service account.

First, create a Workload Identity Pool to manage and group external identities
from GitHub Actions:

```bash
gcloud iam workload-identity-pools create "${POOL_ID}" \
  --project="${PROJECT_ID}" \
  --location="global" \
  --display-name="GitHub Actions Pool"
```

Next, create an OIDC provider inside the pool that trusts GitHub Actions as an
identity issuer:

- **`--issuer-uri`:** Specifies GitHub Actions
  (`https://token.actions.githubusercontent.com`) as the trusted OIDC token
  issuer.
- **`--attribute-mapping`:** Maps claims from the GitHub OIDC token (`sub`,
  `actor`, `repository`, and `repository_owner`) to Google Cloud attributes used
  in IAM policies.
- **`--attribute-condition`:** Restricts authentication to workflow runs
  originating from your specific repository (`${GITHUB_REPO}`), rejecting tokens
  from any other GitHub repository.

```bash
gcloud iam workload-identity-pools providers create-oidc "${PROVIDER_ID}" \
  --project="${PROJECT_ID}" \
  --location="global" \
  --workload-identity-pool="${POOL_ID}" \
  --display-name="GitHub Actions Provider" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
  --attribute-condition="assertion.repository == '${GITHUB_REPO}'"
```

### Allow GitHub repository to impersonate the service account

After STS validates the GitHub OIDC token and issues a federated token, the
workflow exchanges that federated token with the IAM Service Account Credentials
API (`iamcredentials.googleapis.com`) for a short-lived Google Cloud OAuth 2.0
access token belonging to the service account (`${SA_EMAIL}`). For this
impersonation step to succeed, you must grant the external federated identity
permission to act as the service account:

- **`--role="roles/iam.workloadIdentityUser"`:** Allows the federated identity
  to impersonate the service account and request short-lived credentials.
- **`--member="principalSet://..."`:** Restricts impersonation to federated
  principals in your Workload Identity Pool (`${POOL_ID}`) whose mapped
  `attribute.repository` claim matches `${GITHUB_REPO}`.

```bash
gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
  --project="${PROJECT_ID}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${GITHUB_REPO}"
```

## GitHub Actions setup

To configure GitHub Actions secrets and add workflow files under
`.github/workflows/`, you need **Admin** permissions on the target GitHub
repository. Forking the sample repository into your personal GitHub account
grants you admin access to your fork by default. If you use the GitHub CLI
(`gh`) to configure secrets from your terminal, authenticate `gh` with an
account that has repository admin access and the `workflow` token scope.

### Configure GitHub Actions secrets

Retrieve the configuration values and store them as GitHub repository secrets
under **Settings > Secrets and variables > Actions > New repository secret**, or
set them directly using the `gh` CLI:

```bash
export WIF_PROVIDER="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"

echo "GOOGLE_CLOUD_WORKLOAD_IDENTITY_PROVIDER=${WIF_PROVIDER}"
echo "GOOGLE_CLOUD_SERVICE_ACCOUNT=${SA_EMAIL}"
echo "GOOGLE_CLOUD_PROJECT=${PROJECT_ID}"
echo "GOOGLE_CLOUD_LOCATION=global"
echo "GEMINI_MODEL=Gemini 3.8 Flash (Low)"
```

Optional: set directly in GitHub if you have the `gh` CLI authenticated:

```bash
gh secret set GOOGLE_CLOUD_WORKLOAD_IDENTITY_PROVIDER --repo "${GITHUB_REPO}" --body "${WIF_PROVIDER}"
gh secret set GOOGLE_CLOUD_SERVICE_ACCOUNT --repo "${GITHUB_REPO}" --body "${SA_EMAIL}"
gh secret set GOOGLE_CLOUD_PROJECT --repo "${GITHUB_REPO}" --body "${PROJECT_ID}"
gh secret set GOOGLE_CLOUD_LOCATION --repo "${GITHUB_REPO}" --body "global"
gh secret set GEMINI_MODEL --repo "${GITHUB_REPO}" --body "Gemini 3.8 Flash (Low)"
```

> [!NOTE]
>
> Because WIF generates an `external_account` ADC credentials file that does not
> include a `quota_project_id` or `project_id` field, you must also set
> `GOOGLE_CLOUD_QUOTA_PROJECT: ${{ secrets.GOOGLE_CLOUD_PROJECT }}` in the
> workflow `env` so `agy` can resolve the Google Cloud project for model
> discovery.

## GitHub Actions workflow file configuration

The core of the GitHub Actions integration is the workflow file, which is a YAML
file located in the `.github/workflows/` directory of the repository, such as
`.github/workflows/review.yml`. This file defines the automated process,
including the trigger event, the environment, and the steps to execute the
Antigravity CLI.

## Antigravity CLI non-interactive mode

You can enable the Antigravity CLI non-interactive mode with the `-p`,
`--print`, or `--prompt` option for automated environments such as CI/CD
pipelines. In this mode, the CLI operates without requiring user input, making
it suitable for script-based execution within GitHub Actions workflows. It
processes commands and prompts directly, enabling automated tasks such as code
analysis, content generation, and structured output.

Sample non-interactive prompt to check for code documentation and quality:

```bash
agy -p 'Review the recent code changes and modified modules in this repository. Check that classes, functions, and APIs are properly documented, identify potential bugs or maintainability issues, and provide actionable suggestions for improvement in Markdown format.' >> $GITHUB_STEP_SUMMARY
```

### Command and tool permissions in non-interactive mode

In non-interactive mode (`-p`), `agy` grants read-only access to files inside
the active workspace directory. Because headless runs cannot prompt for user
confirmation, `agy` denies any action that requires approval, such as executing
shell commands, modifying files, fetching external URLs, or calling Model
Context Protocol (MCP) tools, unless you explicitly grant permission.

You can control which commands and tools `agy` can run using the following
options:

- **Pre-approve specific commands in `settings.json` (recommended):** Define
  granular allow and deny rules under `permissions` in
  `~/.gemini/antigravity-cli/settings.json`. Command rules match by prefix, so
  `command(git diff)` allows `git diff` with any arguments while blocking other
  shell commands:

    ```json
    {
      "permissions": {
        "allow": [
          "command(git diff)",
          "command(git log)",
          "command(mvn test)"
        ],
        "deny": [
          "command(git push)"
        ]
      }
    }
    ```

    Other supported rule types include `write_file(<path>)`,
    `read_url(<domain>)`, and `mcp(<server>/<tool>)`.

- **Set the agent execution mode (`--mode`):**
    - `--mode plan`: Restricts `agy` to read-only codebase analysis without
      modifying files.
    - `--mode accept-edits`: Approves file edits within the workspace while
      still requiring allow rules for shell commands.
    - `--mode auto`: Approves file edits and safe commands while blocking
      destructive actions.

## Essential components of the workflow

Review the following sample GitHub Actions workflow file:

```yaml
name: Antigravity Code Review

on:
  push:
    branches:
      - main
      - "feature/**"
      - "bugfix/**"

permissions: {}

jobs:
  agy-code-review:
    runs-on: ubuntu-latest
    name: Antigravity Code Review
    permissions:
      contents: read
      id-token: write
    env:
      AGY_ADC_AUTH: "1"
      GOOGLE_CLOUD_PROJECT: ${{ secrets.GOOGLE_CLOUD_PROJECT }}
      GOOGLE_CLOUD_QUOTA_PROJECT: ${{ secrets.GOOGLE_CLOUD_PROJECT }}
      GOOGLE_CLOUD_LOCATION: ${{ secrets.GOOGLE_CLOUD_LOCATION }}

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v5

      - name: Install Antigravity CLI
        run: |
          curl -fsSL https://antigravity.google/cli/install.sh | bash

      - name: Configure Antigravity CLI Settings
        run: |
          mkdir -p ~/.gemini/antigravity-cli
          cat <<EOF > ~/.gemini/antigravity-cli/settings.json
          {
            "gcp": {
              "project": "${{ secrets.GOOGLE_CLOUD_PROJECT }}",
              "location": "${{ secrets.GOOGLE_CLOUD_LOCATION }}"
            },
            "model": "${{ secrets.GEMINI_MODEL }}",
            "trustedWorkspaces": [
              "${GITHUB_WORKSPACE%/*}"
            ],
            "permissions": {
              "allow": [
                "read_file(*)",
                "command(git diff)",
                "command(git log)",
                "command(git status)",
                "command(git show)",
                "command(git branch)",
                "command(grep)",
                "command(find)"
              ],
              "deny": [
                "write_file(*)",
                "command(git push)",
                "command(git commit)",
                "command(rm)",
                "command(curl)"
              ]
            }
          }
          EOF

      - name: Authenticate to Google Cloud using WIF
        uses: google-github-actions/auth@v3
        with:
          workload_identity_provider: ${{ secrets.GOOGLE_CLOUD_WORKLOAD_IDENTITY_PROVIDER }}
          service_account: ${{ secrets.GOOGLE_CLOUD_SERVICE_ACCOUNT }}

      - name: Run Code Review
        run: |
          agy --mode plan -p "Review the recent code changes and modified modules in this repository. Check that classes, functions, and APIs are properly documented, identify potential bugs or maintainability issues, and provide actionable suggestions for improvement in Markdown format." >> $GITHUB_STEP_SUMMARY
```

> [!WARNING]
>
> Piping a remote installation script directly to `bash`
> (`curl -fsSL https://antigravity.google/cli/install.sh | bash`) is the
> standard installation procedure in the
> [Antigravity CLI documentation](https://antigravity.google/download?os=linux),
> but it introduces supply-chain and reproducibility risks in CI/CD pipelines:
>
> - **No integrity verification:** Executing a downloaded script without
>   checking a cryptographic digest or signature risks arbitrary code execution
>   or credential exfiltration if the remote script or host is compromised.
> - **No version pinning:** Installing the latest version on every workflow run
>   can introduce unexpected behavior changes or drift across runs.
>
> To mitigate these risks in production environments:
>
> - Pre-install a vetted, version-pinned `agy` binary into a custom runner
>   container image or internal artifact registry, and verify its SHA-256
>   checksum before execution.
> - Run the CLI installation step before the `google-github-actions/auth` step
>   so Google Cloud credentials are not present in the runner environment while
>   the installer executes.

1.  **Name and trigger:**
    - The `name` field provides a human-readable title for the workflow, visible
      in the GitHub Actions UI.
    - The `on` field specifies the GitHub events that run the workflow.
1.  **Permissions and environment:**
    - The root `permissions: {}` declaration revokes all default `GITHUB_TOKEN`
      permissions across the workflow.
    - The job-level `permissions` block grants only `contents: read` to check
      out the repository and `id-token: write` so the runner can request an OIDC
      token for WIF.
    - The `env` block sets `AGY_ADC_AUTH: "1"` along with
      `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_QUOTA_PROJECT`, and
      `GOOGLE_CLOUD_LOCATION`.
1.  **Jobs:**
    - A workflow consists of one or more jobs. Each job runs in a specified
      environment, such as `runs-on: ubuntu-latest`, and contains multiple
      steps.
1.  **Steps to execute Antigravity CLI:**
    - **Checkout:** Check out the repository code using the
      `actions/checkout@v5` action, making the project files available to the
      workflow runner.
    - **Install Antigravity CLI:** Install the `agy` CLI on the runner before
      authenticating to Google Cloud.
    - **Configure Antigravity CLI settings:** Create
      `~/.gemini/antigravity-cli/settings.json` with your Google Cloud project,
      location, model, trusted workspace, and tool permissions.
    - **Authenticate to Google Cloud:** Exchange the GitHub Actions OIDC token
      for short-lived Google Cloud ADC credentials using
      `google-github-actions/auth@v3`.
    - **Execute the command:** Call the Antigravity CLI in non-interactive mode
      (`-p`). Include the desired prompt and input context, and define the
      desired output behavior, such as writing the result to
      `$GITHUB_STEP_SUMMARY` or adding a comment to a pull request.

> [!NOTE]
>
> To keep this sample workflow self-contained in a single file, the **Configure
> Antigravity CLI Settings** step writes `settings.json` inline using a
> `heredoc` (`cat <<EOF`). Because maintaining inline JSON inside a YAML
> workflow is harder in larger projects, consider storing a template
> configuration file in your repository, such as
> `.github/antigravity/settings.json`, and copying or populating it with `jq` or
> `envsubst` during the workflow run.

## Test the workflow

To verify your GitHub Actions workflow with the Antigravity CLI:

1.  **Clone the repository:** In your terminal, replace `YOUR_GITHUB_USERNAME`
    with your GitHub username, clone the repository locally, and navigate into
    it.

    ```bash
    git clone git@github.com:YOUR_GITHUB_USERNAME/cymbal-eats.git
    cd cymbal-eats
    ```

1.  **Create a new branch:** From your repository, create a new branch to test
    your changes.

    ```bash
    git switch --create feature/test-agy-review
    ```

1.  **Update the workflow file:** Replace the contents of
    `.github/workflows/review.yml` with the sample workflow configuration from
    [Essential components of the workflow](#essential-components-of-the-workflow).

1.  **Make a code change:** Modify a file in your repository. For example, add a
    comment to a Java file under `menu-service`.

1.  **Commit and push:** Commit your changes and push the new branch to GitHub.

    ```bash
    git add .
    git commit -m "Test: Trigger Antigravity CLI code review workflow"
    git push origin feature/test-agy-review
    ```

1.  **Monitor GitHub Actions:**
    - Navigate to the **Actions** tab in your GitHub repository.
    - Find your workflow run triggered by your push or pull request.
    - Click on the workflow run to view its steps and logs.
    - Verify that the Antigravity CLI step executed and that the output, such as
      code review comments or a generated summary, appears as expected.

        The output is similar to the following:

        ```text
        # Documentation Review: menu-service
        ## Executive Summary
        A review of the Java source files in the menu-service module
        (org.google.demo) was conducted. The service consists of three core
        classes/enums:

        - Status (Status.java)
        - Menu (Menu.java)
        - MenuResource (MenuResource.java)

        ## Key Finding
        None of the classes, fields, or methods contain Javadoc or formal code
        documentation. Only file header license blocks and one inline comment
        (//"sweets delight", "super spicy" on Menu.tagLine) exist. Furthermore,
        REST API endpoints lack OpenAPI/Swagger documentation annotations.
        ```

1.  **Review output:** Check the `Summary` of your workflow run for the output
    generated by the Antigravity CLI.
