# Antigravity-powered .NET modernization

In this demo, you modernize a legacy .NET application to a Linux-ready .NET
application that runs on Cloud Run with Cloud SQL for PostgreSQL.

This demo guide walks you through the following steps:

1.  Prepare the environment
1.  Generate a modernization assessment
1.  Modernize the application
1.  Generate deployment descriptors
1.  Deploy on Google Cloud

## Requirements

To deploy this demo, you need:

- A Google Cloud project.
- An account that has the `owner` role on that Google Cloud project.
- The [gcloud CLI](https://docs.cloud.google.com/sdk/docs/install) version
  590.0.0 or higher
- The [Antigravity CLI](https://antigravity.google/docs/getting-started/)
  version 1.4.3 or higher
- The
  [codmod CLI](https://docs.cloud.google.com/migration-center/docs/app-modernization-assessment)
  version 1.1.0 or higher
- [Docker Engine](https://docs.docker.com/engine/install/) version 29.8.0 or
  higher (to test locally on your host). This guide assumes that you can
  [manage Docker as a non-root user](https://docs.docker.com/engine/install/linux-postinstall/#manage-docker-as-a-non-root-user),
  so you can run Docker commands without `sudo`.
- [Chrome DevTools](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/main/README.md)
  version 1.11.0 or higher

## Prepare the environment

Run all the steps in the same Cloud Shell session. If the session resets, run
the `export` commands again.

1.  Open
    [Cloud Shell](https://cloud.google.com/shell/docs/launching-cloud-shell).

1.  Set up your Google Cloud environment:

    ```bash
    export PROJECT_ID="[YOUR_PROJECT_ID]"
    export REGION="[YOUR_REGION]" # e.g., us-central1
    gcloud config set project $PROJECT_ID
    gcloud config set run/region $REGION
    ```

1.  Enable the APIs that this demo requires: Identity and Access Management
    (IAM), Artifact Registry, Cloud SQL Admin, Cloud Run, Cloud Build,
    [Gemini platform](https://cloud.google.com/products/gemini-enterprise-agent-platform),
    and Cloud Resource Manager:

    ```bash
    gcloud services enable \
        iam.googleapis.com \
        artifactregistry.googleapis.com \
        sqladmin.googleapis.com \
        run.googleapis.com \
        cloudbuild.googleapis.com \
        aiplatform.googleapis.com \
        cloudresourcemanager.googleapis.com
    ```

1.  Install the
    [Antigravity CLI](https://antigravity.google/docs/getting-started/), add it
    to your `PATH`, and verify the installation:

    ```bash
    curl -fsSL https://antigravity.google/cli/install.sh | bash
    export PATH="${HOME}/.local/bin:${PATH}"
    agy --version
    ```

1.  Authenticate the Antigravity CLI using
    [Application Default Credentials (ADC)](https://antigravity.google/docs/install/?tab=cli):

    ```bash
    gcloud auth application-default login --project $PROJECT_ID
    export AGY_ADC_AUTH=true
    export GOOGLE_CLOUD_QUOTA_PROJECT="${PROJECT_ID}"
    ```

1.  Install the Chrome DevTools MCP in Antigravity CLI. The `--headless` option
    lets the MCP server run on hosts without a display:

    ```bash
    agy mcp add chrome-devtools npx -y chrome-devtools-mcp@1.11.0 --headless --isolated
    agy mcp list
    ```

    The MCP server requires Chrome on the host. If Chrome isn't available, the
    modernization skill reports that it skipped the browser test. For more
    information, see the
    [Chrome DevTools MCP README](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/main/README.md).

1.  Download the codmod CLI for Linux and verify the installation. For other
    platforms, see the
    [codmod setup instructions](https://docs.cloud.google.com/migration-center/docs/app-modernization-assessment#set_up_codmod):

    ```bash
    CODMOD_VERSION="1.1.0"
    curl -fsSL -o "${HOME}/codmod" \
      "https://codmod-release.storage.googleapis.com/${CODMOD_VERSION}/linux/amd64/codmod"
    chmod +x "${HOME}/codmod"
    export CODMOD="${HOME}/codmod"
    "${CODMOD}" --version
    ```

1.  Clone the sample applications and the modernization skill, and set the demo
    directory. The sparse checkout downloads only the
    `applications/dotnet-modernize-demo` directory:

    ```bash
    git clone --depth 1 --filter=blob:none --sparse \
      https://github.com/GoogleCloudPlatform/dotnet-docs-samples
    git -C dotnet-docs-samples sparse-checkout set applications/dotnet-modernize-demo
    export DEMO_DIR="${PWD}/dotnet-docs-samples/applications/dotnet-modernize-demo"
    ls -A "${DEMO_DIR}"
    ```

## Run the Migration Center App Modernization Assessment

To generate a Migration Center App Modernization Assessment report, you do the
following:

1.  Set the working directory:

    ```bash
    cd "${DEMO_DIR}"
    ```

1.  Generate the report:

    ```bash
    "${CODMOD}" create full \
      --codebase ./dotnet-migration-sample \
      --output-path ./codmod-full-report-dotnet-mod.html \
      --project "${PROJECT_ID}" \
      --region global \
      --improve-fidelity \
      --intent=MICROSOFT_MODERNIZATION \
      --optional-sections "files,classes"
    ```

    This command takes about 16 minutes to run.

1.  Download the generated report from Cloud Shell and open it with a web
    browser, such as Google Chrome:

    ```bash
    cloudshell download codmod-full-report-dotnet-mod.html
    ```

## Modernize the .NET application using Antigravity CLI

1.  Change the working directory to the .NET application directory:

    ```bash
    cd "${DEMO_DIR}/dotnet-migration-sample"
    ```

1.  Start the Antigravity CLI:

    ```bash
    agy
    ```

    The Antigravity CLI prompts you to choose a color scheme, to accept the
    terms of service, and to trust the workspace. Press `Enter` to accept the
    defaults.

1.  At the Antigravity CLI prompt, run the
    [`modernize-dotnet-cloudrun` skill](https://github.com/GoogleCloudPlatform/dotnet-docs-samples/blob/main/applications/dotnet-modernize-demo/.agents/skills/modernize-dotnet-cloudrun/SKILL.md),
    which the Antigravity CLI discovers in the parent directory:

    ```text
    Use the modernize-dotnet-cloudrun skill to modernize the application in the current working directory.
    ```

    When the Antigravity CLI presents the implementation plan or asks for
    permission to run tools, such as `docker` commands and Chrome DevTools MCP
    tools, review and approve the requests. To complete the execution, the
    Antigravity CLI takes between 15 and 25 minutes.

1.  After execution completes, exit the Antigravity CLI by entering `/exit` or
    by pressing `CTRL+C`.

### Sample modernized application

The `dotnet-migration-sample-modernized` directory contains an example of the
modernized .NET application resulting from running the Antigravity CLI with the
modernization skill. For a summary of the changes, see the
[modernization report](https://github.com/GoogleCloudPlatform/dotnet-docs-samples/blob/main/applications/dotnet-modernize-demo/dotnet-migration-sample-modernized/MODERNIZATION.md).

To run the example modernized application locally, you do the following:

1.  Change the working directory to the .NET application directory:

    ```bash
    cd "${DEMO_DIR}/dotnet-migration-sample-modernized"
    ```

1.  Run the application using Docker Compose:

    ```bash
    docker compose up --build
    ```

1.  Wait for the application to accept connections. When the application is
    ready to accept connections, the output is similar to the following:

    ```text
    web-1  | {
    web-1  |   "Timestamp": "2026-10-20T18:15:25Z ",
    web-1  |   "EventId": 14,
    web-1  |   "LogLevel": "Information",
    web-1  |   "Category": "Microsoft.Hosting.Lifetime",
    web-1  |   "Message": "Now listening on: http://0.0.0.0:8080",
    web-1  |   "State": {
    web-1  |     "Message": "Now listening on: http://0.0.0.0:8080",
    web-1  |     "address": "http://0.0.0.0:8080",
    web-1  |     "{OriginalFormat}": "Now listening on: {address}"
    web-1  |   }
    web-1  | }
    ```

1.  Open `http://localhost:8080/` with a web browser, such as Google Chrome, or
    open [Web Preview](https://cloud.google.com/shell/docs/using-web-preview) on
    port `8080` if you are running in Cloud Shell.

1.  Navigate the application using the web browser.

After completing your test, stop the application by sending the `CTRL+C` key
combination.

## Deploy the application to Google Cloud

To deploy the example modernized application to Google Cloud using Cloud Run,
Artifact Registry, and Cloud SQL for PostgreSQL, follow the guidance in this
section.

You can follow similar steps to deploy your own modernized .NET application.

### 1. Create and configure a dedicated service account

1.  Create the service account:

    ```bash
    export SA_NAME="dotnet-demo-sa"
    gcloud iam service-accounts create $SA_NAME \
        --display-name "Dotnet Modernization Demo Service Account"

    export SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
    ```

1.  Grant the necessary roles to the service account:

    ```bash
    # For Cloud Run to connect to Cloud SQL
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="roles/cloudsql.client" \
        --condition=None

    # For Cloud Build to write logs
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="roles/logging.logWriter" \
        --condition=None

    # For Cloud Build to push images to Artifact Registry
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="roles/artifactregistry.writer" \
        --condition=None

    # For Cloud Build to manage storage buckets for artifacts
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="roles/storage.admin" \
        --condition=None
    ```

### 2. Create an Artifact Registry repository

Create a Docker repository in Artifact Registry to store the container images
for your application.

```bash
export REPO_NAME="contoso-university-repo"
gcloud artifacts repositories create $REPO_NAME \
    --repository-format=docker \
    --location=$REGION \
    --description="Docker repository for Contoso University"
```

### 3. Create a Cloud SQL for PostgreSQL instance

Create a PostgreSQL instance to host the application's database. This takes a
few minutes. The `db-g1-small` tier requires the `--edition=enterprise` option.

> [!NOTE]
>
> By default, `gcloud sql instances create` assigns a public IP address to the
> instance. In production environments, block public IP assignment by passing
> `--no-assign-ip` and configure private connectivity.

```bash
export INSTANCE_NAME="contoso-university-db"
export DB_PASSWORD="[YOUR_DB_PASSWORD]" # Choose a strong password
gcloud sql instances create $INSTANCE_NAME \
    --database-version=POSTGRES_18 \
    --edition=enterprise \
    --tier=db-g1-small \
    --region=$REGION \
    --root-password=$DB_PASSWORD
```

After Cloud SQL creates the instance, create a database for the application.

```bash
gcloud sql databases create contosouniversity --instance=$INSTANCE_NAME
```

### 4. Build and push the container image

Use Cloud Build to build your container image and push it to the Artifact
Registry repository you created. Cloud Build uses the `Dockerfile` in your
project root.

```bash
cd "${DEMO_DIR}/dotnet-migration-sample-modernized"
gcloud builds submit \
    --tag $REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/contoso-university:latest \
    --service-account="projects/${PROJECT_ID}/serviceAccounts/${SA_EMAIL}" \
    --default-buckets-behavior=regional-user-owned-bucket .
```

### 5. Deploy the application to Cloud Run

Deploy the container image from Artifact Registry to Cloud Run. This command
creates a new Cloud Run service and connects it to your Cloud SQL instance.

First, get your Cloud SQL instance connection name:

```bash
export INSTANCE_CONNECTION_NAME=$(gcloud sql instances describe $INSTANCE_NAME --format='value(connectionName)')
```

Now, deploy the service to Cloud Run. The `--no-invoker-iam-check` option makes
the service publicly reachable without an `allUsers` IAM binding:

```bash
gcloud run deploy contoso-university \
    --image=$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/contoso-university:latest \
    --no-allow-unauthenticated \
    --add-cloudsql-instances=$INSTANCE_CONNECTION_NAME \
    --region "${REGION}" \
    --no-invoker-iam-check \
    --service-account="${SA_EMAIL}" \
    --set-env-vars "ConnectionStrings__SchoolContext=Host=/cloudsql/${INSTANCE_CONNECTION_NAME};Database=contosouniversity;Username=postgres;Password=${DB_PASSWORD}"
```

After the deployment completes, the command outputs the URL for your deployed
service.

### 6. Test the application

Once the deployment is complete, you can test the application:

1.  Copy the URL provided in the output of the `gcloud run deploy` command.
1.  Open the URL in a web browser.
1.  The browser displays the Contoso University Students page, where you can
    view students, add new students, and view the enrollment date summary. The
    application is now running live on Cloud Run and connected to your Cloud SQL
    database.

## Clean up your Google Cloud environment

To avoid incurring unwanted charges, follow these steps to remove all the
resources provisioned for this demo.

1.  Delete the Cloud Run service

    ```bash
    gcloud run services delete contoso-university --region=$REGION --quiet
    ```

1.  Delete the Artifact Registry repository

    ```bash
    gcloud artifacts repositories delete $REPO_NAME --location=$REGION --quiet
    ```

1.  Delete the Cloud SQL for PostgreSQL instance

    ```bash
    gcloud sql instances delete $INSTANCE_NAME --quiet
    ```

1.  Remove the IAM role bindings of the custom service account, and delete the
    service account

    ```bash
    for ROLE in roles/cloudsql.client roles/logging.logWriter roles/artifactregistry.writer roles/storage.admin; do
      gcloud projects remove-iam-policy-binding $PROJECT_ID \
          --member="serviceAccount:${SA_EMAIL}" \
          --role="${ROLE}" \
          --condition=None
    done
    gcloud iam service-accounts delete $SA_EMAIL --quiet
    ```

1.  Revoke the Application Default Credentials and disable ADC authentication
    for the Antigravity CLI

    ```bash
    gcloud auth application-default revoke --quiet
    unset AGY_ADC_AUTH GOOGLE_CLOUD_QUOTA_PROJECT
    ```
