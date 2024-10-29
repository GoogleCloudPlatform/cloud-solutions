# Load Apache Avro files to Cloud Spanner with Slowly Changing Dimensions (SCD) using Dataflow Flex template

Customers have large volumes of transactional data with
[Slowly Changing Dimensions (SCD)](https://en.wikipedia.org/wiki/Slowly_changing_dimension),
which may need to be loaded to [Cloud Spanner](https://cloud.google.com/spanner)
during migrations.

The Dataflow pipeline template in this solution allows customers to load exports
(in Apache Avro format) from their current database or data warehouse to Cloud
Spanner from a staged
[Cloud Storage Bucket](https://cloud.google.com/storage/docs/buckets).

The Dataflow pipeline supports the following SCD Types:

*   **SCD Type 1**: updates existing row if the primary key exists, or inserts a
    new row otherwise.

*   **SCD Type 2**: updates existing row's end date to the current timestamp if
    the primary key exists, and inserts a new row with null end date and start
    date with the current timestamp if the column is passed.

Follow the [deployment guide](deployment.md) to build, run and test the Dataflow
pipeline.

## Background and motivation

There are other Dataflow templates for loading data from Avro to Cloud
Spanner like
[this Google-provided template](https://cloud.google.com/dataflow/docs/guides/templates/provided/avro-to-cloud-spanner).

This pipeline differs from the existing Dataflow templates in the following way:

1.  The Google-provided template requires the database to be empty, and it
    creates the tables and schema before inserting the data. This template
    expects the tables and schema to be created, but allows inserting and
    updating to it.

1.  The Google-provided template only supports the initial upload. It will not
    load the data if the schema has been created. This template allows data to
    be inserted and updated, allowing for changes in data over time. More
    importantly, those updates can be done following
    [SCD Types](https://en.wikipedia.org/wiki/Slowly_changing_dimension).

In other words, the Google-provided template is most useful for an initial
database migration where only one data insertion is required and the schema must
be created. On the other hand, this template is most useful in insertions and
updates after the initial data load following different SCD Type, whether done
as one time ad-hoc update or continuous upserts.
