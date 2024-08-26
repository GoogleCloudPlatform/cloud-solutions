# Configuration: Template Parameters

## Pipeline Flags

The Dataflow pipeline requires or accepts the following flags:

<!-- Disable MDLint as tables exceed 400 characters. -->
<!-- markdownlint-capture -->
<!-- markdownlint-disable MD013 -->

Flag                        | Required | Default Value | Description                                                                                                                                                                                                                                                                                                                          | Example
--------------------------- | -------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------
input_file_format           | **Yes**  | N/A           | Format of the files to load. Supported: `avro` and `csv`.                                                                                                                                                                                                                                                                            | `--input_file_format=csv`
input_file_pattern          | **Yes**  | N/A           | File pattern to the file(s). The path can contain glob characters (*, ?, and [...] sets).                                                                                                                                                                                                                                            | `--input_file_pattern=gs://my-bucket/data/*.csv`
input_schema                | **Yes**  | N/A           | The input schema using [dtype strings](https://pandas.pydata.org/docs/user_guide/basics.html#basics-dtypes). The format for each field is `field_name:dtype`. Example: `name:string`. The fields must follow the order of the file when in `csv` format. Each field must be separated with `;`. Example: `name:string;phone:number`. | `--input_schema=id:int64;first_name:string;last_name:string;salary:float`
input_csv_file_delimiter    | No       | `,`           | The column delimiter for the input CSV file(s). Only used for CSV files.                                                                                                                                                                                                                                                             | `--input_csv_file_delimiter=";"`
input_file_contains_headers | No       | `1`           | Whether the input CSV files contain a header record. Use 1 for true and 0 for false. Only used for CSV files.                                                                                                                                                                                                                        | `--input_file_contains_headers=1`
alloydb_ip                  | **Yes**  | N/A           | The IP (or hostname) of the AlloyDB (or PostgreSQL) database. The database must be accessible by the pipeline runner.                                                                                                                                                                                                                | `--alloydb_ip=10.1.1.25`
alloydb_port                | No       | `5432`        | Port of the AlloyDB instance.                                                                                                                                                                                                                                                                                                        | `--alloydb_port=5432`
alloydb_database            | No       | `postgres`    | Name of the AlloyDB database to which data will be written.                                                                                                                                                                                                                                                                          | `--alloydb_database=dbname`
alloydb_user                | No       | `postgres`    | User to login to Postgres database on AlloyDB.                                                                                                                                                                                                                                                                                       | `--alloydb_user=myuser`
alloydb_password            | **Yes**  | N/A           | Password to login to Postgres database on AlloyDB using the provided user.                                                                                                                                                                                                                                                           | `--alloydb_password=mySafePassword123!`
alloydb_table               | **Yes**  | N/A           | Name of the table within the Postgres database on AlloyDB to which data will be written.                                                                                                                                                                                                                                             | `--alloydb_table=customers`

<!-- markdownlint-restore -->

## DataFlow Template Flags

Dataflow requires some additional parameter to deploy the pipeline as a Dataflow
job. For information about pipeline options that are directly required and
supported by Flex Templates, see
[Pipeline options](https://cloud.google.com/dataflow/docs/reference/pipeline-options#python).

Flag             | Required | Description                                                                                                | Example
---------------- | -------- | ---------------------------------------------------------------------------------------------------------- | -------
region           | **Yes**  | The region where you want to deploy the Dataflow job.                                                      | `--region=asia-southeast-1`
project          | **Yes**  | The project id where you want to deploy the Dataflow job.                                                  | `--project=my-gcp-project`
job_name         | **Yes**  | Name of the Dataflow job name.                                                                             | `--job_name=gcs_to_alloydb`
temp_location    | **Yes**  | Cloud Storage path for Dataflow to stage temporary job files created during the execution of the pipeline. | `--temp_location=gs://bucket/path/dataflow/temp/`
staging_location | **Yes**  | Cloud Storage path for Dataflow to stage staging job files created during the execution of the pipeline.   | `--staging_location=gs://bucket/path/dataflow/staging/`
