# Database Archival and Pruning

Database Archival and Pruning (or "Database Archival" for short) is a solution
which allows you to archive and prune data from Google Cloud database products
(such as Cloud SQL, AlloyDB, Spanner) into BigQuery. This solution archives and
prunes data from Historical Data tables.

Historical Data tables are usually large tables, with a date or timestamp
column, which stores transactions, facts, log or raw data which are useful for
various long-term storage and analytics needs. These tables are copied from the
operational Database to BigQuery - after which, the data can be removed from the
database.

The solution supports multiple tables - across multiple databases and
instances - with customizable configuration and retention periods for each
table.

This concept is similar to BigTable's age-based
[Garbage Collection](https://cloud.google.com/bigtable/docs/garbage-collection).

Refer to detailed documentation in [docs/index.md](/docs/index.md).

Disclaimer: This is not an official Google product.
