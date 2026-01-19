# Load Apache Avro files to Cloud Spanner with Slowly Changing Dimensions (SCD) using Dataflow Flex template

Update **2026-01-19**:

This project has been archived. You can still access the code by browsing the
repository at
[commit 79ceca9](https://github.com/GoogleCloudPlatform/cloud-solutions/tree/79ceca9b9ff498d2af6101f264b1c731c8911aee/projects/dataflow-gcs-avro-to-spanner-scd)

Customers have large volumes of transactional data with
[Slowly Changing Dimensions (SCD)](https://en.wikipedia.org/wiki/Slowly_changing_dimension),
which may need to be loaded to [Cloud Spanner](https://cloud.google.com/spanner)
during migrations.

The Dataflow pipeline template in this solution allows customers to load exports
(in Apache Avro format) from their current database or data warehouse to Cloud
Spanner from a staged
[Cloud Storage Bucket](https://cloud.google.com/storage/docs/buckets).

The Dataflow pipeline supports the following SCD Types:

- **SCD Type 1**: updates existing row if the primary key exists, or inserts a
  new row otherwise.

- **SCD Type 2**: updates existing row's end date to the current timestamp if
  the primary key exists, and inserts a new row with null end date and start
  date with the current timestamp if the column is passed.
