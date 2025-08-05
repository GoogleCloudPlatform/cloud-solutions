# Deployment

<!-- markdownlint-disable MD046-->

This document describes how you can deploy the
[Confidential AI Model Serving](../README.md) in a Google Cloud project by using
Terraform.

## Cost

In this document, you use the following billable components of Google Cloud:

- [Compute Engine virtual machine (VM) instances](https://cloud.google.com/compute/all-pricing)
- [Cloud run](https://cloud.google.com/run/pricing)
- [Artifact Registry](https://cloud.google.com/artifact-registry/pricing)

## Before you begin

1.  In the Google Cloud console, on the project selector page, select or create
    a Google Cloud project.

    [Go to project selector](https://console.cloud.google.com/projectselector2/home/dashboard){.md-button}

1.  Make sure that
    [billing is enabled for your Google Cloud project](https://cloud.google.com/billing/docs/how-to/verify-billing-enabled#confirm_billing_is_enabled_on_a_project).

## Deploy the application

This section shows you how to deploy the example application by using Terraform.

1.  Open Cloud Shell.

    [Open Cloud Shell](https://console.cloud.google.com/?cloudshell=true){.md-button}

1.  Set an environment variable to contain your
    [project ID](https://cloud.google.com/resource-manager/docs/creating-managing-projects):

    ```sh
    export PROJECT_ID=project-id
    ```

    Replace `project-id` with the ID of your project.

1.  Set another environment variable to contain your preferred region:

    ```sh
    export REGION=region
    ```

    Replace `region` with a region that supports Cloud Run and Compute Engine,
    for example `us-central1`.

1.  Authorize `gcloud`:

    ```sh
    gcloud auth login
    ```

    You can skip this step if you're using Cloud Shell.

1.  Authorize `terraform`:

    ```sh
    gcloud auth application-default login &&
      gcloud auth application-default set-quota-project $PROJECT_ID
    ```

    You can skip this step if you're using Cloud Shell.

1.  Clone the Git repository containing the code to build the example
    architecture:

    ```sh
    git clone https://github.com/GoogleCloudPlatform/cloud-solutions.git &&
        cd cloud-solutions/projects/confidential-ai-model-serving/
    ```

1.  Initialize Terraform:

    ```sh
    terraform init
    ```

1.  Apply the configuration:

    ```sh
    terraform apply -var "project_id=$PROJECT_ID" -var "region=$REGION"
    ```

    When the command completes, it prints the URL of the Cloud Run service that
    runs the broker. The URL looks similar to the following:

    ```text
    https://broker-PROJECTNUMBER.REGION.run.app/
    ```

    Make note of this URL, you'll need it later.

    !!! note

        If you haven't used Artifact Registry before, the command might fail with the following error:

        ```text
        denied: Unauthenticated request. Unauthenticated requests do not have permission
        "artifactregistry.repositories.uploadArtifacts" on resource
        ```

        You can fix this error by running the following command:

        ```sh
        gcloud auth configure-docker $REGION-docker.pkg.dev
        ```

        Then re-run `terraform apply`.

## Test the deployment

To verify that the deployment was successful, run the test client application:

1.  Change to the `sources` directory:

    ```sh
    cd ../sources
    ```

1.  Run the test client:

    ```sh
    ./run.sh client --broker URL
    ```

    Replace `URL` with the URL of the Cloud Run service that you obtained
    previously.

    The command output looks similar to the following:

    ```sh
    [INFO] Running as client
    [INFO] Waiting for workload instances to become available...

    Your prompts will be served by one of the following workload instances:

    Instance   Zone               Prod  Hardware        OS                 Image
    ---------- ------------------ ----- --------------- ------------------ ------------
    workload-x1rf asia-southeast1-a  true  GCP_AMD_SEV     CONFIDENTIAL_SPACE bc84e0191c2e
    workload-r3lq asia-southeast1-a  true  GCP_AMD_SEV     CONFIDENTIAL_SPACE 904c6cbc5c56

    Enter a question>
    ```

    - The line `Waiting for workload instances to become available` indicates
      that the Confidential Space VM hasn't registered with the broker yet, and
      that the client is waiting for this process to complete.
    - The table shows the Confidential Space VM instances that are available to
      handle requests.
    - The `Prod` column indicates if the respective instance uses the
      [**Production** image](https://cloud.google.com/confidential-computing/confidential-space/docs/confidential-space-images#types_of_images).

        The client refuses to interact with instances that use the **Debug**
        image unless you specify the `--debug` command line flag.

1.  Enter an example prompt and press **Enter**.

    The client randomly selects one of the available workload instances,
    encrypts the prompt so that only this specific workload instance can read
    the prompt, and passes the encrypted message to the broker.

    The broker forwards the encrypted message to the workload instance, which
    generates an example response, which it encrypts so that only the client can
    read the response.

    The client then displays the response:

    ```text
    > Who are you?
    That's a good question.
    ```

## What's next

- Review Cloud Logging logs to follow the interaction between the client,
  broker, and workload instances.
- Learn more about
  [Confidential Space](https://cloud.google.com/confidential-computing/confidential-space/docs/confidential-space-overview).
