# Custom PerfKit Benchmarks

Consists of 3 modules:

1. API Server:
   Java SpringBoot based server providing RESTful API for creating, monitoring and cancelling
   BenchmarkJobs using the Benchmark Runner.

2. Benchmark Runner:
   Templated launch scripts on fork of Google's Perfkit benchmark maintained by @prakhargautam at
   https://github.com/prakhag2/PerfKitBenchmarker
   The runner executes a parameterized Cloud Build jobs with job specific parameters passed as input and writes the
    results to Google BigQuery table.

3. Daily Perfkit benchmarks runner
   cron-based runner for standard shapes.

## Prerequisites
   terraform >= 1.3.9
   kubectl >= 1.25
   Docker >= 20.10
   Google Cloud SDK >= 423.0.0 with credentials
   yarn >= 1.22
   nodejs >= 16.0

## Create or Use Existing Google Cloud Project
   Use the Console UI to create new GCP project or select existing project. To do this the user needs Project Editor or Owner role.
   ```shell
   PROJECT_ID="<replace_with_project_id>"
   ```
## Download the Repository of sa-tools
   From terminal, clone the repository:
   ```shell
   git clone https://github.com/GoogleCloudPlatform/cloud-solutions
   cd cloud-solutions/projects/sa-tools/perfkit-benchmark/tf
   ```

### Create OAuth Consent Screen
   Follow the steps as per https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid to generate a Client ID.

   ```shell
   CLIENT_ID="<replace_with_generated_client_id>"
   ```

## Permission for gcloud command Issuer User
   These roles are required for the person who is deploying this tool:
   * `roles/editor` (Editor)
   * `roles/iam.securityAdmin` (Security Admin)
   * `roles/datastore.owner` (Datastore Owner)

## Deploy on Google Cloud

   Make sure the terminal session has Application Default Credential connected to the target GCP Project deployment.
   ```shell
   gcloud auth login
   gcloud auth configure-docker asia-southeast1-docker.pkg.dev
   ```
   To verify, the result of the following command should be the account that going to deploy this tool:
   ```shell
   gcloud auth list
   ```
### Setup Initial Datastore Database
   ```shell
   gcloud firestore databases create --type=datastore-mode --project "${PROJECT_ID}" --location "nam5"
   ```

### Enable GCP Resources Creation
   ```shell
   gcloud services enable cloudresourcemanager.googleapis.com
   ```

### Create GCP Infra using Terraform
   Issue the below command from `sa-tools/perf-benchmark` root folder repo. ex: sa-tools/perf-benchmark.
   Please supply variable values to Terraform command by replacing the values inside `terraform.tfvars` file:
   - `client_id`, from Create OAuth Consent Screen step above
   - `project_id`, the GCP Project ID where the tool going to be installed
   - `region`, the GCP region where the tool will be deployed
   - `tool_user_or_group_email`, The group or user's email address that will be using the tool. Ex: johndoe@example.com
   - `tool_user_or_group_email_type`, The type of email provided that will be using the tool ('group' or 'user')

   ```shell
   terraform init
   terraform apply
   ```

   Copy the final generated perfkit-benchmark Cloud Run's URL from Cloud Run Page and paste the URL to the *Authorized Javascript Origins* and *Authorized redirect URIs* in Client ID Configuration Page:

   `https://console.cloud.google.com/apis/credentials/oauthclient/<REPLACE_WITH_CLIENT_ID>?project=<REPLACE_WITH_PROJECT_ID>`

   Copy paste the generated URL above to your browser to directly open *Client ID for Web Application* Page

   Additionally, also add allow Authorized Domains section under Edit App Registration Page under OAuth Consent Screen with the Cloud Run's generated URL minus the `http://` part. Example value: `test-cpwwsohaga-uc.a.run.app`

### Running Perfkit-Benchmark Tool

   After the deployment, find the Cloud Run's perfkit-benchmark URL that being generated and open it in the browser:
   https://console.cloud.google.com/run/detail/asia-southeast1/perfkit-benchmark/metrics?cloudshell=false&project=<REPLACE_WITH_PROJECT_ID>
## Troubleshooting

1. If facing this error: "Firestore database with name perfkit already exist."
   Run this command manually:
   ```shell
   gcloud firestore databases create --type=datastore-mode --project "${PROJECT_ID}" --location "nam5"
   ```

2. If facing this error: "Unable to Sign-In using Google Sign-In. An Error has occured. Only accounts from the organization can access this site."
   Make sure the Authorized Domains section under OAuth Screen https://console.cloud.google.com/apis/credentials/consent/edit?project=<replace_with_PROJECT_ID>
   having domain name of user's Identiy Platform, ex: example.com
   Which means johndoe@example.com login will be allowed.

3. If facing this error: "Storage object. Permission 'storage.objects.get' denied on resource (or it may not exist)., forbidden" or "denied: Permission "artifactregistry.repositories.uploadArtifacts" denied on resource"
   Make sure that <project_number>@cloudbuild.gserviceaccount.com exist, and having Artifact Registry Writer and Storage Object Creator permissions.

4. If facing this error: "message":"Failed to open popup window","stack":"Error: Failed to open popup window\n at new ..."
   Make sure the allow pop-up from the Cloud Run's URL domain is allowed from Browser's address bar.


5. Error: Members belonging to the external domain cannot be added as domain restricted sharing is enforced by the organization policy
   Depending on organization policy being used, some organization will have constraints/iam.allowedPolicyMemberDomains to be restricted to be on the same domain. This means, not allowing non-authenticated Cloud Run is not allowed from Organization Policy perspective.
   Replace allUsers with "group:your_group@example.com" inside main.tf and re-run terraform apply.
## Local Testing Launch:

1. Run local datastore emulator ([install instructions](https://cloud.google.com/datastore/docs/tools/datastore-emulator))
   ```shell
   gcloud beta emulators datastore start --no-store-on-disk &
   ```

2. Set Environment variables
   ```shell
   $(gcloud beta emulators datastore env-init)
   ```

3. Run Local server
   ```shell
   cd api/
   ./gradlew clean bootRun
   ```
