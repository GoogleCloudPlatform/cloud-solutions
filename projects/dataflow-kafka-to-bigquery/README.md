# Dataflow flex template for Kafka Protobuf messages to BigQuery

This project demonstrates a Dataflow pipeline that reads messages in Protobuf
binary format from Kafka and writes them into a BigQuery table with the same
schema.

If the schema for the protobuf has evolved, it will also generate a new entry in
separate BigQuery table with raw bytes.

Update **2025-12-19**:

This project has been archived. You can still access the code by browsing the
repository at
[commit ea7cba2](https://github.com/GoogleCloudPlatform/cloud-solutions/tree/ea7cba2313c2d5048a97e2d0a8a105290a37e110/projects/dataflow-kafka-to-bigquery)
