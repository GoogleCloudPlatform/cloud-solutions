# Frequently Asked Questions for Database Archival and Pruning

## How do you ensure the data sanctity in both the database and BigQuery? How to audit the actions?

The data gets moved from the database to BigQuery using Datastream continuous
replication first. This is an officially supported product, which offers
robustness in moving the data to BigQuery. Your are able to audit and validate
that the data is landing successfully before deploying this solution.

Datastream validation can be done using Cloud Monitoring tools like alerts in
Cloud Logging for errors or warnings that Datastream streams throws during the
Change Data Capture (CDC) or data movement processes.

From there, the data movements are only BigQuery to BigQuery, which reduces the
risk of any data corruption, using Composer.

Composer (Airflow) offers a UI which allows you to see all the tables and steps
that are taken and its status. This offers a first level of monitoring, and
retryability for failed actions. These views can be done at both pipeline and
individual actions level. Composer tasks also include their own details, logs
and Xcom to perform deeper analyses.

Additionally, for any data that will be pruned, we produce two tables: a
snapshots table, and a metadata table.

The snapshots table is identified with the date where the snapshot was taken
and the Composer run id. This allows linking the BigQuery data directly with a
specific run to allow for any auditing and administrative actions.

Similarly, the metadata table is also identified with the date and run id.
Additionally, it contains the status on whether the data was deleted - which
provides additional information and auditing mechanisms.

Finally, the data is deleted from the database using the primary key(s) from the
archival and metadata tables. This means that only data that has been confirmed
to land in BigQuery and has been archived is deleted.

## Is there a possibility that the data in the database instance gets deleted before getting archived in BigQuery when using this solution?

No, the data is deleted from the database using the primary key(s) from the
archival and metadata tables in BigQuery. This means that only data that has
been confirmed to land in BigQuery and has been archived will be deleted from
the database.

## How to ensure the archival and deletion process in database happens without burdening the primary instance performance?

When archiving the data, the solution does not query the database directly. The
archival process happens from BigQuery to BigQuery, which avoids putting
pressure when doing any heavy read and copy operations.

Do note, however, that Datastream will add some additional load for continuous
replication. This can be further mitigated by setting Datastream to replicate
data via a read replica.

Regarding the delete, there are a couple of precautions that are taken to
minimize the impact:

The data is only deleted in small batched rows using transactions and queries
with primary keys. This avoids the need for table scans and limits the impact on
the database. By default, the batch size is 1,000 but this number is
configurable.

To avoid problems with table locking, only one batch is deleted at a time from a
given table. Additionally, there is a waiting time in between the deletion of
each table batch to let other operations take place. The default waiting time is
2 minutes, but this is configurable.

## How to handle the child table (primary key -> foreign key) dependencies for data archiving?

This use case is not officially supported yet.

If you still need to handle it, there are additional considerations to respect
the referential integrity constraints.

Tables that form the group of parent and child relationship (e.g. parent is P,
child tables C1, C2) must be planned to be grouped together so that records with
foreign references from the child tables (C1, C2) are pruned first and finally
the parent table (P) undertakes the exercise for pruning the associated set of
Primary Key records.

There are plans to tackle theese dependencies natively in the solution in the
future.

## What happens if the Datastream job fails? What are the expected actions to ensure Archive & Pruning activities remain clean?

Datastream is a Native Change Data Capture (CDC) solution with mechanisms in
place for pausing, stopping, restarting the Datastream jobs and troubleshooting
the errors. See "How do you ensure the data sanctity in both the database and
BigQuery? How to audit the actions?" for more details.

Datastream job restarted in CDC phase continues from the last BINLOG/WAL
position and hence should not be a challenge in terms of data integrity. If the
job fails during initial backfill phase, it still shouldn't be a challenge since
re-running it will populate the mapped LIVE table in the dataset on BigQuery.
This takes support from the fact that BigQuery snapshots are created from the
live table in BigQuery.

Once the live data is on BigQuery, the solution takes measures to ensure the
data lands on each step.

### Overview

The first step is to copy the data from the BigQuery live table to a snapshot
table for archival. If and only if this step is successful, the metadata table
is created based on this table. Finally, if and only if the metadata table is
created, the table is deleted. This means that there is no risk of deleting the
data without having gone through the archival process for that table.

### Archival (Snapshot) Task

If the initial archival step fails, no data should be copied. Similarly, no data
would have been deleted, and therefore it can be re-run safely until it succeeds
and the data is copied. Note that Composer runs the dates based on the run date,
which is different from the day where it is run. For example, if you run
yesterday's failed run today, it will run with yesterday's date, as we would
like to do to keep consistency.

In the eventuality where only partial data is copied, the data is identified
with a snapshot date and/or run id. This would allow deleting the partial data,
and re-running this step - provided that the data was not deleted.
Alternatively, the data will be deleted in the next run.

### Metadata Task

If the metadata step fails, follow the same logic described in the Archival
step.

### Data Deletion Task

Assuming the archival and metadata steps are completed, data deletion is
idempotent. This means that you can re-run the deletion as many times as you
need without impacting the output.

If the batch failed and was not deleted, the re-run will trigger the deletion.

If the batch was deleted but it was not marked as deleted in the metadata, the
re-run will trigger the deletion. However, the records will not be found in the
database (as they are already deleted) and nothing will happen.

If the batch was deleted and marked as such in the metadata, the batch will be
ignored. If you need to force a re-run when the batch is marked as deleted in
the metadata, you would need to modify the metadata table to mark it as non
deleted (is_batch_deleted=FALSE).

## How is data integrity preserved if updates happen while the solution runs?

The data that is meant to be archived and deleted is old data that is no longer
operational (e.g. data older than 1 to 5 years). As such, there should not be
any changes to the in-transit data. This is because if the data is meant to be
archived it is because it is no longer operational and does not require edits
anymore.

If you require additional guarantees, you should coordinate a mechanism to lock
the tables before and after the archival process runs. This is not something
that the current solution offers, but we are actively considering it.
