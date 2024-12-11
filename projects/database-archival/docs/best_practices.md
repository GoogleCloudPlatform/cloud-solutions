# Best Practices and Considerations of Database Archival and Pruning

## Use of read replicas

While Database Archival will use BigQuery for the archiving process to avoid
hitting the database, Datastream will add some additional workload to the
database. For this reason, we recommend to use Read Replica(s) for the
Datastream job since one of the main purposes is to improve database
performance.

## Why to snapshot the Main Data tables, in addition to Historical Data tables

The system provides a solution to archive both Historical Data and Main Data,
where a full copy is taken. While the live data in BigQuery brought by
Datastream would already allow joining Main Data with the archived data, this
may lead to inconsistent data.

For example, if we are querying archived Historical Data of a company_id on a
record from 5 years ago, the live data may not match the historical values. The
record may no longer exist (for example, if it was deleted) or the key values
(e.g. company_name) may have changed. All of this would lead to inconsistencies.

To allow for consistent data querying, the BigQuery live Main Data can (and
should) be snapshotted into a partitioned table at the same time as the
Historical Data.

## Data loss risk

When moving data between the database and BigQuery, or within BigQuery, there is
a risk of data loss or data corruption (such as interrupted transfers, data
type, encoding or localization compatibility).

*   Data loss could occur in cases where (1) the data is accidentally removed
    from BigQuery after it has been deleted from the source database, or (2)
    where the data was not successfully copied to BigQuery and it gets deleted
    from the source database.

*   Data corruption could occur in cases where (1) there is a misconfiguration
    in the Datastream, which leads to the wrong BigQuery data, or (2) where
    errors may occur in the copy of the data due to bugs or system issues.

The system is designed to be robust, but errors and accidents (e.g. someone
accidentally dropping the BigQuery tables or a partitiion) can still happen.
This is why this solution should not be considered as a source for Disaster
Recovery (DR).

If there are DR needs, consider alternative systems such as replicas, backups
and point in time recovery. Consider these practices also for the archived data
in BigQuery.

*   [AlloyDB DR](https://cloud.google.com/alloydb/docs/backup/overview)

*   [BigQuery DR](https://cloud.google.com/bigquery/docs/managed-disaster-recovery)

*   [Cloud SQL for MySQL DR](https://cloud.google.com/sql/docs/mysql/intro-to-cloud-sql-disaster-recovery)

*   [Cloud SQL for PostgreSQL DR](https://cloud.google.com/sql/docs/postgres/intro-to-cloud-sql-disaster-recovery)

*   [Cloud SQL for SQL Server DR](https://cloud.google.com/sql/docs/sqlserver/intro-to-cloud-sql-disaster-recovery)

*   [Spanner DR](https://cloud.google.com/spanner/docs/backup/disaster-recovery-overview)

If there are regulatory needs for which this data needs to be archived, consider
additional precautions to the aforementioned ones like archiving the data to
BigQuery and Cloud Storage.

## Data optimizations

If the main purpose is to optimize the performance of your database instances,
there are alternatives that you may want to consider before proceeding with data
archival. Some of these changes not only may lead to better gains in
performance, but also do not carry risks of data loss.

*   [Performance monitoring for AlloyDB](https://cloud.google.com/alloydb/docs/monitor-instance)

*   [Best practices](https://cloud.google.com/sql/docs/mysql/best-practices) and
    [performance optimization tips](https://cloud.google.com/mysql/optimization)
    for Cloud SQL for MySQL

*   [Best practices](https://cloud.google.com/sql/docs/postgres/best-practices)
    and
    [improve performance](https://cloud.google.com/sql/docs/postgres/recommender-enterprise-plus)
    for Cloud SQL for PostgreSQL.

*   [Best practices](https://cloud.google.com/sql/docs/sqlserver/best-practices)
    and
    [performance analysis and query tuning](https://cloud.google.com/blog/products/databases/sql-server-performance-analysis-and-query-tuning)
    for Cloud SQL for SQL Server

*   [SQL best practices for Spanner](https://cloud.google.com/spanner/docs/sql-best-practices)

## Schema evolution

This solution is not actively considering schema changes to the tables.

However, there are a few alternatives if the table schema ever changes:

### In place changes for new or removed columns

BigQuery table schemas support the addition of new columns. This type of changes
can be done in place by altering the schema of the existing table.

If a column is dropped, this can be treated as a no-op in BigQuery as long as
the column was marked as nullable. From that moment onward, the value will just
be null and will not be copied from your database to BigQuery.

However, this will not work for other changes of data types (i.e. the same
column changes from one type to another, renaming columns, or dropping
non-nullable columns). In those cases, we need to explore the following options:

### Keep old and new schema separate

The easiest way to handle this would be to create a new target empty table.
Historical data will remain the same with the old schema, while all future data
will be archived to the new tables with the new schema. Querying and unioning
data between tables could be complex as it may lack data or require casting of
fields. However, no high operational work is needed to keep the jobs and
pipeline running.

### Migrate the old schema

Alternatively, historical data would need to be migrated to the new schema. This
needs to be done on an ad hoc basis and dependent on the platform and changes.
This might be a relatively expensive operation depending on the data volume
stored.

For BigQuery, a new target table should be created. The table should be created
using a query that reads the originally archived data, adding the missing
fields, casting the changed fields or removing columns where necessary.
