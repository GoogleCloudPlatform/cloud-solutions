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

Update **2025-12-10**:

This project has been archived. You can still access the code by browsing the
repository at
[commit 128f980](https://github.com/GoogleCloudPlatform/cloud-solutions/tree/c68f74144cd399fed2493a8b2776cc876bf8711a/projects/database-archival)
