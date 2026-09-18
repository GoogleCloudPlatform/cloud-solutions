# Agentic Data Cloud & Knowledge Catalog Demo

This repository contains the code and configuration for the **Agentic Data Cloud
Demo**, demonstrating how to build an AI-ready data cloud infrastructure on
Google Cloud and perform advanced data analytics using Google Cloud Dataplex,
Gemini, and BigQuery.

## Repository Structure

The project organizes into the following structure:

```text
.
├── main.tf                   # Root Terraform configuration for Qwiklabs & standalone provisioning
├── variables.tf              # Terraform input variables (including Qwiklabs mandatory parameters)
├── outputs.tf                # Terraform outputs exposed to Qwiklabs student_visible_outputs
├── qwiklabs.yaml             # Qwiklabs V2 bundle specification
├── runtime.yaml              # Qwiklabs script runtime definition (Terraform 1.15.6)
├── QWIKLABS.md               # Student lab instruction manual (English)
├── QWIKLABS_ko.md            # Student lab instruction manual (Korean)
├── buildtest.dockerfile      # CI/CD presubmit container build & test configuration
│
├── analytics/                # Data analysis and AI playground using Python/Jupyter
│   ├── notebooks/            # Jupyter notebooks for data quality, catalog, graphs, and AI
│   ├── resources/            # Business glossary and schema mapping definitions
│   └── pyproject.toml        # Python dependency configuration (managed via uv)
│
└── scripts/                  # Automation scripts
    └── build_qwiklabs_bundle.sh # Packages git-tracked files into a deployable Qwiklabs zip archive
```

## Running as a Qwiklabs Lab

This repository natively supports the **Qwiklabs V2 Bundle Specification** using
the Terraform `1.15.6` runtime:

1.  **Automated Provisioning**: Upon clicking **Start Lab**, Qwiklabs executes
    `main.tf` to enable Google Cloud APIs, provision the VPC network,
    configure the `thelook_ecommerce` BigQuery dataset, replicate public tables
    via BigQuery Data Transfer Service, configure the Colab Enterprise Runtime
    Template, and stage all interactive notebooks in Cloud Storage.
1.  **Student Workflow**: Follow the step-by-step instructions in
    [QWIKLABS.md](QWIKLABS.md) (or [QWIKLABS_ko.md](QWIKLABS_ko.md)) to
    import notebooks from Cloud Storage into Colab Enterprise and execute
    analytics workflows.
1.  **Packaging the Lab Bundle**: Run the packaging utility to create a
    deployable archive:

```bash
./scripts/build_qwiklabs_bundle.sh
```

## Standalone Deployment via Terraform

To deploy the infrastructure manually without Qwiklabs:

1.  Authenticate with Google Cloud and select the active project:

```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

1.  Initialize and apply the Terraform configuration:

```bash
terraform init
terraform apply -var="gcp_project_id=$(gcloud config get-value project)"
```

1.  Review the outputs to obtain the Colab Enterprise Runtime Template ID and
    Cloud Storage notebook paths:

```bash
terraform output
```

## Running Interactive Notebooks in Colab Enterprise

1.  Open **Colab Enterprise** in the Google Cloud Console.
1.  Ensure the selected region matches the Terraform deployment region (default:
    `us-central1`).
1.  Import the notebooks directly from the Google Cloud Storage bucket path
    displayed in `terraform output notebooks_gcs_bucket`.
1.  Connect the imported notebook to the pre-configured Colab Enterprise Runtime
    Template.
1.  Execute the cells sequentially across notebooks `01` through `07`.

## License

This project is licensed under the Apache 2.0 License - see the LICENSE details.
