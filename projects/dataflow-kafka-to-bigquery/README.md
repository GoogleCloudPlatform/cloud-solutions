# Dataflow flex template for Kafka Protobuf messages to BigQuery

This project demonstrates a Dataflow pipeline that reads messages in Protobuf
binary format from Kafka and writes them into a BigQuery table with the same
schema.

If the schema for the protobuf has evolved, it will also generate a new entry in
a separate BigQuery table with raw bytes.
