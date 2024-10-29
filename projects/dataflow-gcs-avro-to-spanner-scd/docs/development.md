# Development Instructions for the Dataflow Flex Template for Avro to Cloud Spanner with Slowly Changing Dimensions (SCD)

The following instructions are for developers only.

## Pre-requirements

In order to work with this repository, you would need to have the following
environment installed:

*   Java 21
*   Gradle 8.10.2

## Steps to test the template

1.  Access this project folder.

    ```bash
    git clone https://github.com/GoogleCloudPlatform/cloud-solutions.git
    cd cloud-solutions/projects/dataflow-gcs-avro-to-spanner/
    ```

1.  Run unit and local integration tests.

    ```bash
    gradle clean test
    ```
