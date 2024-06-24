# Hive-BigQuery-Connector Demo Setup

## Introduction

This repository is meant to enable fast setup of a demo environment that can walk you through a demo of the
[Hive-BigQuery-Connector](https://github.com/GoogleCloudDataproc/hive-bigquery-connector).

The demo walks us through the scenario of trying to use several different datasets from different data sources, and how
you can accomplish that and running all our queries through hive, even if some of the data is in HDFS/GCS, some of it is
on native tables on BigQuery, or even external tables in BigQuery.
To showcase this, we will use data from
the [`thelook_ecommerce` public dataset](https://console.cloud.google.com/bigquery(cameo:product/bigquery-public-data/thelook-ecommerce)),

The repo is a setup to run against a clean newly created GCP project, with an associated billing account.

## Dependencies

- [Terraform](https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli) (tested on 1.6, but should work with any recent release)
- Python >= 3.7

## Initial setup

To set up the demo, please follow the steps mentioned below:

1. Clone this repo
2. Change your working directory to the `terraform` folder
3. Make sure to log in with your credentials to the [gcloud CLI utility](https://cloud.google.com/sdk/docs/install-sdk#initializing_the)
4. Choose the correct GCP project for your CLI session:

    ```bash
   gcloud config set project <YOUR_PROJECT>
   ```

5. Set the application default credentials:

   ```bash
   gcloud auth application-default login
   ```

6. Create a copy of the `terraform.tfvars.template` file, and remove the `.template` suffix
7. Edit the copied file `terraform.tfvars` and put in your GCP project as a variable value.
8. Initialize the terraform dependencies:

    ```bash
    terraform init
    ```

9. (Optional) See the terraform plan to review what will terraform create for you.

    ```bash
   terraform plan
    ```

10. Apply the plan. When prompted, reply "y" to the confirmation prompt. This process will set up all
    required infrastructure on your GCP project. Please review the section on [Terraform Setup](#terraform-setup) for
    more details on what is
    exactly being created for you on your GCP project. The terraform script will run for about 10-15 minutes.

    ```bash
    terraform apply
    ```

11. After the successful completion of the terraform script, change your working directory to the `scripts` folder.
12. (Recommended) Create a virtual environment to isolate the dependencies:

    ```bash
    python3 -m virtualenv
    source venv/bin/activate
    ```

13. Install the runtime dependencies

    ```bash
    pip install -r requirements.txt
    ```

14. Run the python script - this will again, take some time. To read more about the action preformed by this script read
    more at the [Python Setup](#python-setup) section.

    ```bash
    python main.py
    ```

    At the end of the script, there will be a link presented that will lead you to a Jupyter Notebook, with the demo
    scenario - open it in your browser, and follow along with the instructions in the Jupyter Notebook

## Setup information

This repo contains 2 parts to the setup. The first, __Terraform__, that sets up the infrastructure needed for this demo.
The standard output of the terraform output is saved into the `terraform.tfstate` file, which will contain all the
information about the infrastructure created.
The second part of this setup is a python script, that will prepare the data to be used in this demo, and compile a
notebook that contains the actual demo code.

To create the tables in BQ and the notebook code, the python script will read the `terraform.tfstate` file to read the
right values for the GCP project, GCS buckets and Dataproc cluster that were created.

### Terraform Setup

- `bq.tf` sets up the BigQuery Dataset, and the BigQuery-Cloud Storage connection to allow for external tables from
  files in GCS.
- `dataproc.tf` sets up the dataproc cluster, which includes 2 initialization actions. One for the
  Hive-BigQuery-Connector and one to install some missing packages that are required to support
  the [PyHive](https://pypi.org/project/PyHive/) library.
- `gcp.tf` sets up basic Google Cloud Platform data, like the project details and enable APIs
- `gcs.tf` sets up 2 GCS buckets, one for Dataproc (staging) and one for BigQuery external data (warehouse). This will
  also upload a bash script to the staging bucket, to be used as an initialization action.
- `iam.tf` sets up a service account with permissions for the Dataproc cluster and BigQuery to run all the queries
  necessary for the demo. In a real-world scenario the roles might be split to different service accounts, so mind
  the specific roles required for your users and services when deploying in a production environment.
- `locals.tf` sets up a local variable for region. In this demo, since we are using the `thelook_ecommerce` public
  dataset, which is hosted in the US region, we have to use that region, but that is might not be required for your
  use-case.
- `network.tf` sets up a default VPC for deploying the different assets in this demo.
- `outputs.tf` defines the output variables that will be saved in this script. These variables are picked up by the
  python script to handle the next steps required in this demo.
- `variables.tf` defines the input variables required for the terraform script to run.

### Python Setup

There are 2 python scripts. The `main.py` which is used to set up the data and notebook for the demo and
the `deconstruct-jupyter-notebook.py` script.

#### The `main.py` script

##### Jupyter Notebook phase

The code for the Jupyter Notebook is split up inside the `paragraphs` folder, where each file in that folder is
either a markdown file (with `.md` suffix) or an executable code file (with a `.code` suffix). These suffixes are
aligned to the underlying representation of paragraphs in a Jupyter Notebook file (which is a glorified JSON file).

Each "paragraph" file is being read by the python script, making the variable replacement where needed, and outputting
a JSON file with the name `notebook.ipynb`, that is then uploaded to the correct GCS bucket to be used by Dataproc
JupyterLab.

##### Data Copy phase

To represent the imaginary data for this ecommerce company, we are using
the [`thelook_ecommerce` public dataset](https://console.cloud.google.com/bigquery(cameo:product/bigquery-public-data/thelook-ecommerce)).

Since we want to demonstrate how hive can work with data coming in from different data sources, like a local Hive
tables, both internal and external and BigQuery tables, the script will copy all tables but spread them across several
different data storages, to simulate these scenarios.
The tables are copied and distributed in the following manner:

- `users` is copied directly into BigQuery as a native internal BigQuery table. During the demo, it will be mounted on
  Hive as an external table.
- `products` is extracted as Parquet files into the `staging` GCS bucket (which supports the Dataproc cluster,
  representing the HDFS layer in on-prem deployments). During the demo, it will be mounted as an external table in Hive,
  as an "HDFS" backed external table in hive. We will demonstrate that table of this kind can be joined with BigQuery
  backed tables.
- `orders` is mounted in BigQuery as an internal __partitioned__ table, to demonstrate how the Hive-BigQuery-Connector
  works with BigQuery partitioned tables. The partition field is `created_at` DateTime column.
- `order_items` is extracted as Parquet files into the `warehouse` GCS bucket (that is connected to BigQuery in a
  BigLake connection) and is mounted as an external BigLake table in BigQuery. During the demo it will be used from
  Hive, after mounting the table in Hive as an external table.
- `events` is extracted as Parquet files into the `warehouse` GCS bucket  (that is connected to BigQuery in a BigLake
  connection), but with Hive-style partitioning schema, by a `created_date` Date column. The extracted paths contain
  the `crated_date` as part of the GCS path. E.G: `gs://<WAREHOUSE_BUCKET>/data/events/created_date=2022-12-23`. The
  data is mounted as an external BigLake partitioned table in BigQuery. During the demo it will be used from Hive, after
  mounting the table in Hive as an external table.
- `distribution_centers` is extracted as Parquet files to the `staging` GCS bucket. The data will be used to insert to a
  Hive internal table backed by BigQuery to demonstrate how internal tables work in the context of the
  Hive-BigQuery-Connector.
- `inventory_items` is copied directly into BigQuery as a native internal BigQuery table. During the demo, it will be
  mounted on Hive as an external table.

__NOTE:__ All `TIMESTAMP` column in the original datasets are converted to `DATETIME` before any operation. The reason
for that is that `PyHive` has an outstanding bug trying to deserialize the `TIMESTAMP` representation from BigQuery.

#### The `deconstruct-jupyter-notebhook.py` script

There is another python script named `deconstrct-jupyter-notebook.py` which is only intended for development purposes.
It is used to take an existing notebook, and convert it back to files, each representing a paragraph in the notebook.
Use with care, as it will override the paragraphs folder and rewrite the entire content.
