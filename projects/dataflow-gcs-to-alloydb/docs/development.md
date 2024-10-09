# Development Documentation

The documentation is targeted to developers. The guide below will help you to
run certain tasks focused on contributors and project maintainers.

## Run Unit Tests

When making any changes, run Unit Tests to ensure the pipeline is working as
intended. You may want to extend these tests if the changes impact the
underlying pipeline logic and use cases.

### Run Tests Directly via Python

#### Pre-Requirements to Run Tests

1.  [Python](https://www.python.org/downloads/) 3.7 or higher, with
    [pip](https://pip.pypa.io/en/stable/installation/) installed.

1.  [JDK](https://cloud.google.com/java/docs/setup) 17 or higher.

#### Run Tests with Python

1.  Clone this repository.

    ```bash
    git clone https://github.com/GoogleCloudPlatform/cloud-solutions.git
    ```

1.  Access this project folder.

    ```bash
    cd cloud-solutions/projects/dataflow-gcs-to-alloydb/
    ```

1.  Install the `requirements-dev.txt`. (Optional) Consider using a virtual
    environment.

    ```bash
    python3 -m pip install --upgrade pip && \
    python3 -m pip install --require-hashes -r ./requirements-dev.txt
    ```

1.  Run the unit tests.

    ```bash
    python3 ./src/dataflow_gcs_to_alloydb_test.py
    ```

### Run Tests via Container

#### Pre-Requirements to run the test container

1.  [Docker Engine](https://docs.docker.com/engine/install/) or equivalent
    installed.

1.  [Docker Compose](https://docs.docker.com/compose/install/) or equivalent
    installed.

#### Build and run the test container

1.  Clone this repository.

    ```bash
    git clone https://github.com/GoogleCloudPlatform/cloud-solutions.git
    ```

1.  Access this project folder.

    ```bash
    cd cloud-solutions/projects/dataflow-gcs-to-alloydb/
    ```

1.  Build the test container image.

    ```bash
    docker build -f Dockerfile.dev . -t test_container
    ```

1.  Run the test container.

    ```bash
    docker run --net host -v /var/run/docker.sock:/var/run/docker.sock test_container
    ```

## Run Pipeline Locally

For development purposes, you may want to run the pipeline locally using Apache
Beam's Direct Runner.

### Pre-Requirements

1.  [Python](https://www.python.org/downloads/) 3.7 or higher, with
    [pip](https://pip.pypa.io/en/stable/installation/) installed.

1.  [JDK](https://cloud.google.com/java/docs/setup) 17 or higher.

1.  An AlloyDB (or PostgreSQL compatible) database and a data file to upload it.
    If you do not have one, follow the steps under
    [Run Dataflow Template](./build_and_run_pipeline.md) first.

### Run the Dataflow pipeline locally

1.  Clone this repository.

    ```bash
    git clone https://github.com/GoogleCloudPlatform/cloud-solutions.git
    ```

1.  Access this project folder.

    ```bash
    cd cloud-solutions/projects/dataflow-gcs-to-alloydb/
    ```

1.  Set up the following variables to your project values.

    ```bash
    BUCKET_NAME=""
    ALLOYDB_IP=""
    ALLOYDB_PASSWORD=""
    ```

    The variables mean the following:

*   `BUCKET_NAME` is the name of the Google Cloud Storage bucket that will be
    used to read the data files.

*   `ALLOYDB_IP` is the IP or hostname for the AlloyDB instance. Your machine
    needs to be able to access this IP. You may need to use a
    [Public IP](https://cloud.google.com/alloydb/docs/connect-public-ip) for
    this.

*   `ALLOYDB_PASSWORD` is password for the AlloyDB instance.

1.  Install the `requirements.txt`. (Optional) Consider using a virtual
    environment.

    ```bash
    python3 -m pip install --upgrade pip && \
    python3 -m pip install --require-hashes -r ./requirements.txt
    ```

1.  Run the pipeline locally.

    ```bash
    python3 ./src/dataflow_gcs_to_alloydb.py \
      --input_file_format=csv \
      --input_file_pattern "gs://$BUCKET_NAME/dataflow-template/*.csv" \
      --input_schema "id:int64;first_name:string;last_name:string;department:string;salary:float;hire_date:string" \
      --alloydb_ip "$ALLOYDB_IP" \
      --alloydb_password "$ALLOYDB_PASSWORD" \
      --alloydb_table "employees"
    ```

    To learn how to customize these flags, read the
    [Configuration](./configuration.md) section.
