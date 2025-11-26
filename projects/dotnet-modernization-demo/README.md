# Gemini-powered .NET modernization

In this demo, you modernize a .NET Framework application to a Linux-ready .NET
application.

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
- The [gcloud CLI](https://docs.cloud.google.com/sdk/docs/install)
- [Gemini CLI](https://geminicli.com/docs/get-started/deployment/)
- The
  [codmod CLI](https://docs.cloud.google.com/migration-center/docs/app-modernization-assessment)
- [Docker Engine](https://docs.docker.com/engine/install/) (to test locally on
  your host). This guide assumes that you can
  [manage Docker as a non-root user](https://docs.docker.com/engine/install/linux-postinstall/#manage-docker-as-a-non-root-user),
  so you can run Docker commands without `sudo`.
- [Chrome DevTools MCP](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/main/README.md)

## Prepare the environment

1.  Open
    [Cloud Shell](https://cloud.google.com/shell/docs/launching-cloud-shell).

1.  Install the
    [codmod CLI](https://docs.cloud.google.com/migration-center/docs/app-modernization-assessment#set_up_codmod)

1.  Install the Chrome DevTools MCP in Gemini CLI:

    ```bash
    gemini mcp add chrome-devtools npx chrome-devtools-mcp@latest
    ```

    For more information, see the
    [Chrome DevTools MCP README](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/main/README.md):

1.  Clone the repository and set the working directory:

    ```bash
    git clone https://github.com/GoogleCloudPlatform/cloud-solutions && \
    cd cloud-solutions/projects/dotnet-modernization-demo
    ```

## Run the Migration Center App Modernization Assessment

To generate a Migration Center App Modernization Assessment report, you do the
following:

1.  Generate the report:

    ```bash
    codmod create full \
      --codebase ./dotnet-migration-sample \
      --output-path ./codmod-full-report-dotnet-mod.html \
      --experiments=enable_pdf,enable_images \
      --improve-fidelity \
      --intent=MICROSOFT_MODERNIZATION \
      --optional-sections "files,classes"
    ```

    This command takes about 15 minutes to run.

1.  Open the generated report with a web browser, such as Google Chrome.

To review how the output looks like, see the sample report:
`modernization-report-sample/third_party/codmod-full-report-dotnet-mod.html`.

## Modernize the .NET application using Gemini CLI

1.  Change the working directory to the .NET application directory:

    ```bash
    cd dotnet-migration-sample
    ```

1.  Run Gemini CLI:

    ```bash
    gemini
    ```

1.  Copy the prompt defined in `modernization-prompt.md`, and paste the prompt
    in the Gemini CLI user interface, and press the Enter key.

To complete the execution, Gemini CLI takes about 25 minutes.

### Sample modernized application

The `dotnet-migration-sample-modernized` directory contains an example of the
modernized .NET application resulting in running Gemini CLI with the above
prompt.

To run the example modernized application locally, you do the following:

1.  Change the working directory to the .NET application directory:

    ```bash
    cd dotnet-migration-sample-modernized
    ```

1.  Run the application using Docker Compose:

    ```bash
    docker compose up --build
    ```

1.  Wait for the application to accept connections. When the application is
    ready to accept connections, the output is similar to the following:

    ```text
    app-1  | {"EventId":14,"LogLevel":"Information","Category":"Microsoft.Hosting.Lifetime","Message":"Now listening on: http://0.0.0.0:8080","State":{"Message":"Now listening on: http://0.0.0.0:8080","address":"http://0.0.0.0:8080","{OriginalFormat}":"Now listening on: {address}"}}
    ```

1.  Open `http://localhost:8080/` with a web browser, such as Google Chrome.

1.  Navigate the application using the web browser.

After completing your test, stop the application by sending the `CTRL+C` key
combination.

## Deploy the application to Google Cloud

To deploy the the example modernized application to Google Cloud using Cloud
Run, Artifact Registry, and Cloud SQL for PostgreSQL, follow the guidance in
this section.

You can follow similar steps to deploy your own modernized .NET application.

### 1. Set up your Google Cloud environment

Set your project ID and region as environment variables in your shell.

```bash
export PROJECT_ID="[YOUR_PROJECT_ID]"
export REGION="[YOUR_REGION]" # e.g., us-central1
gcloud config set project $PROJECT_ID
gcloud config set run/region $REGION
```

### 2. Enable necessary Google Cloud APIs

Enable the APIs for Artifact Registry, Cloud SQL, Cloud Build, and Cloud Run.
This allows the services to work together.

```bash
gcloud services enable \
    iam.googleapis.com \
    artifactregistry.googleapis.com \
    sqladmin.googleapis.com \
    run.googleapis.com \
    cloudbuild.googleapis.com
```

### 3. Create an Artifact Registry repository

Create a Docker repository in Artifact Registry to store the container images
for your application.

```bash
export REPO_NAME="contoso-university-repo"
gcloud artifacts repositories create $REPO_NAME \
    --repository-format=docker \
    --location=$REGION \
    --description="Docker repository for Contoso University"
```

### 4. Create a Cloud SQL for PostgreSQL instance

Create a PostgreSQL instance to host the application's database. This may take a
few minutes.

```bash
export INSTANCE_NAME="contoso-university-db"
export DB_PASSWORD="[YOUR_DB_PASSWORD]" # Choose a strong password
gcloud sql instances create $INSTANCE_NAME \
    --database-version=POSTGRES_13 \
    --tier=db-g1-small \
    --region=$REGION \
    --root-password=$DB_PASSWORD
```

After the instance is created, create a database for the application.

```bash
gcloud sql databases create contosouniversity --instance=$INSTANCE_NAME
```

### 5. Build and push the container image

Use Google Cloud Build to build your container image and push it to the Artifact
Registry repository you created. Cloud Build uses the `Dockerfile` in your
project root.

```bash
cd dotnet-migration-sample-modernized
gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/contoso-university:latest .
```

### 6. Deploy the application to Cloud Run

Deploy the container image from Artifact Registry to Cloud Run. This command
creates a new Cloud Run service and connects it to your Cloud SQL instance.

First, get your Cloud SQL instance connection name:

```bash
export INSTANCE_CONNECTION_NAME=$(gcloud sql instances describe $INSTANCE_NAME --format='value(connectionName)')
```

Now, deploy the service to Cloud Run:

```bash
gcloud run deploy contoso-university \
    --image=$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/contoso-university:latest \
    --platform managed \
    --allow-unauthenticated \
    --add-cloudsql-instances=$INSTANCE_CONNECTION_NAME \
    --region "${REGION}" \
    --set-env-vars "ConnectionStrings__SchoolContext=Host=/cloudsql/${INSTANCE_CONNECTION_NAME};Database=contosouniversity;Username=postgres;Password=${DB_PASSWORD}"
```

This command will prompt you to confirm the deployment. After it completes, it
will output the URL for your deployed service.

### 7. Test the application

Once the deployment is complete, you can test the application:

1.  Copy the URL provided in the output of the `gcloud run deploy` command.
1.  Open the URL in a web browser.
1.  You should see the Contoso University application homepage. You can navigate
    through the site to view students, courses, instructors, and departments.
    The application is now running live on Cloud Run and connected to your Cloud
    SQL database.
1.  Optionally, you can go back to the Gemini CLI and ask it to run the
    automated UI tests again, this time against the deployed application's URL.

## Clean up your Google Cloud environment

To avoid incurring unwanted charges, follow these steps to remove all the
resources provisioned for this demo.

1.  Delete the Cloud Run service

    ```bash
    gcloud run services delete contoso-university --platform managed --region=$REGION --quiet
    ```

1.  Delete the Artifact Registry repository

    ```bash
    gcloud artifacts repositories delete $REPO_NAME --location=$REGION --quiet
    ```

1.  Delete the Cloud SQL for PostgreSQL instance

    ```bash
    gcloud sql instances delete $INSTANCE_NAME --quiet
    ```
