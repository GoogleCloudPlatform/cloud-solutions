# Gemini Powered Migrations To Google Cloud

This project provides a set of Gemini CLI custom commands to accelerate
assessments and migration of workloads and data from Amazon Web Services (AWS)
and Azure to Google Cloud. The Gemini CLI custom commands use Gemini to analyze
data, identifying suitable resources for migration, and augmenting traditional
assessments with AI.

## Prerequisites

To effectively utilize these instructions, ensure the following are set up:

- **Gemini CLI:** Installed and configured. For installation instructions, visit
  [geminicli.com](https://geminicli.com/docs/get-started/deployment/).
- **Source Cloud Provider Inventory Details:** Access to the inventory of
  objects to migrate (such as virtual machines, storage buckets, workloads,
  etc.) from your source environment for analysis. Sample inputs are available
  in the `test-data/` directory.

## Gemini CLI custom commands

This project provides Gemini CLI custom commands in the `.gemini/commands`
directory for doing the following:

- [Evaluate inventories](#evaluate-inventories)
- [Refactor and modernize applications](#refactor-and-modernize-applications)
- [Generate sample data](#generate-sample-data)

### Evaluate inventories

The custom commands in this section are aimed at helping you accelerate the
evaluation and inventory assessments.

- **aws-container-migration-analysis:** This command analyzes cluster and object
  inventory files from Amazon EKS workloads to generate a Google Kubernetes
  Engine (GKE) migration plan. The command expects a path to the directory
  containing the inventory output files. You must first generate these files
  using the
  [Kubernetes Cluster Discovery Tool](https://github.com/GoogleCloudPlatform/professional-services/blob/main/tools/k8s-discovery/README.md).

    **Usage:**

    ```sh
    /aws-container-migration-analysis [PATH/TO/KUBERNETES_INVENTORY/DIRECTORY]
    ```

    **Usage (Try with Sample Data):**

    ```sh
    /aws-container-migration-analysis test-data/aws-container-migration-analysis
    ```

- **/aws-lambda-to-cloud-run-poc-selection:** This command assists in reviewing
  AWS Lambda inventories to identify suitable functions for migration to Cloud
  Run. Example:

    ```sh
    /aws-lambda-to-cloud-run-poc-selection Review files in test-data/aws-lambda-assessment-results for migration to Cloud Run.
    ```

- **/aws-s3-bucket-poc-selection:** This command assists in reviewing Amazon S3
  buckets inventories to identify suitable buckets for migration to Google Cloud
  Storage. Example:

    ```sh
    /aws-s3-bucket-poc-selection review files in test-data/aws-s3-assessment-results for migration to US EAST region.
    ```

- **/aws-s3-migration-analysis:** This command analyzes an Amazon S3 inventory
  file to assess workload complexity and automatically generate tailored Google
  Cloud infrastructure code based on the specific data profile.

    To learn how to generate the required inventory file, see
    [Build an inventory of your Amazon S3 buckets](https://docs.cloud.google.com/architecture/migrate-amazon-s3-to-cloud-storage#build_an_inventory_of_your_amazon_s3_buckets).

    **Usage (Load your own file):**

    ```sh
    /aws-s3-migration-analysis [PATH/TO/YOUR/S3_INVENTORY_FILE.csv]
    ```

    **Usage (Try with Sample Data):**

    ```sh
    /aws-s3-migration-analysis test-data/aws-s3-migration-analysis/SAMPLE-S3_inventory.csv
    ```

    You can review the example output for this command at:
    `test-data/sample-selection/aws-s3-migration-analysis.md`

- **/azure-blob-storage-poc-selection:** This command helps analyze Azure Blob
  Storage inventories to suggest containers that are good candidates for
  migration to Google Cloud Storage.

    ```sh
    /azure-blob-storage-poc-selection review files in test-data/azure-blob-storage-assessment-results for migration to US EAST region.
    ```

### Refactor and modernize applications

The commands listed in this section are aimed at refactoring and modernizing the
source code of the applications to migrate:

- **/aws-lambda-refactor-python-app-to-cloud-run:** This command helps you
  refactor AWS Lambda functions and applications to run on Cloud Run:

    ```text
    /aws-lambda-refactor-python-app-to-cloud-run path/to/your/aws-lambda/function
    ```

    Where `path/to/your/aws-lambda/function` is the path to the source code of
    the AWS Lambda function or application to refactor.

- **/dotnet-sql-server-application-modernization:** This command helps you
  refactor legacy .NET applications to port them to a more modern .NET version
  that can run in a container. Also, it refactors SQL Server usage to
  PostgreSQL.

    ```text
    /dotnet-sql-server-application-modernization path/to/your/dotnet/app
    ```

    Where `path/to/your/dotnet/app` is the path to the source code of the .NET
    application to refactor.

### Generate sample data

The commands listed in this section are useful to generate sample data when you
don't have a source environment available, but you need data to evaluate other
commands:

- **/generate-sample-aws-lambda-list-functions:** This command helps you
  generate sample `aws lambda list-functions` command output:

    ```text
    /generate-sample-aws-lambda-list-functions test-data/aws-lambda-assessment-results/aws-lambda-list-functions-sample.json
    ```

- **/generate-sample-aws-lambda-get-function:** This command helps you generate
  sample `aws lambda get-function` command output:

    ```text
    /generate-sample-aws-lambda-get-function test-data/aws-lambda-assessment-results/aws-lambda-list-functions-sample.json
    ```

    The command takes the output of the `aws lambda list-functions` command as
    input.

- **/generate-sample-aws-lambda-get-function-configuration:** This command helps
  you generate sample `aws lambda get-function-configuration` command output:

    ```text
    /generate-sample-aws-lambda-get-function-configuration test-data/aws-lambda-assessment-results/aws-lambda-list-functions-sample.json
    ```

    The command takes the output of the `aws lambda list-functions` and
    `aws lambda get-function` commands as input.

- **/generate-sample-aws-lambda-get-policy-and-list-event-source-mappings:**
  This command helps you generate sample `aws lambda get-policy` and
  `aws lambda list-event-source-mappings` command output:

    ```text
    /generate-sample-aws-lambda-get-policy-and-list-event-source-mappings test-data/aws-lambda-assessment-results/aws-lambda-list-functions-sample.json
    ```

    The command takes the output of the `aws lambda list-functions`,
    `aws lambda get-function`, and `aws lambda get-function-configuration`
    commands as input.

The sample output in the `test-data` directory has been generated using these
commands.

## Setup and usage instructions

1.  Install Gemini CLI. For installation instructions, visit
    [geminicli.com](https://geminicli.com/docs/get-started/deployment/).

1.  Clone the repository:

    ```sh
    git clone https://github.com/GoogleCloudPlatform/cloud-solutions.git
    ```

1.  Configure the Gemini CLI custom commands in the
    `cloud-solutions/projects/gemini-powered-migrations-to-google-cloud`
    directory so that they are available as global user commands or project
    commands. For more information about configuring Gemini CLI custom commands,
    see [Custom commands](https://geminicli.com/docs/cli/custom-commands/).

1.  Change the working directory to the directory where you stored the files you
    want to assess with Gemini CLI, such as inventory files from other cloud
    providers.

1.  Start Gemini CLI:

    ```sh
    gemini
    ```

1.  Run the Gemini CLI authentication command, and follow instructions:

    ```sh
    /auth
    ```

1.  Run one of the [provided custom commands](#gemini-cli-custom-commands).

1.  Review generated report with recommendations.

## Test Data

The `test-data/` directory contains sample inventories from Amazon S3 and Azure
Blob Storage. These files are structured to mimic real-world cloud provider
outputs and are used by the custom Gemini CLI commands to demonstrate the
migration selection process without requiring actual cloud environments. This
data includes:

- **`aws-container-migration-analysis/`**: Contains mock Kubernetes clusters and
  objects inventory files for Amazon EKS workloads.
- **`aws-lambda-assessment-results/`**: Contains mock data for AWS Lambda
  functions.
- **`aws-s3-assessment-results/`**: Contains mock data for S3 bucket locations,
  policies, and bucket lists.
- **`aws-s3-migration-analysis/`**: Contains resources for the S3 migration
  analysis command.
- **`azure-blob-storage-assessment-results/`**: Contains mock data for Azure
  Blob Storage container locations, policies, and blob lists.
- **`sample-selection/`**: Stores example output files generated by the Gemini
  CLI custom commands, showing how a proof of concept migration selection might
  look.
