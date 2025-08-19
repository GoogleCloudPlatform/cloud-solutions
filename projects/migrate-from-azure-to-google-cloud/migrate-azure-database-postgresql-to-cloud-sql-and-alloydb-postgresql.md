# Migrate from Azure to Google Cloud: Migrate Azure Database for PostgreSQL to Cloud SQL for PostgreSQL and AlloyDB for PostgreSQL

Google Cloud provides tools, products, guidance, and professional services to
migrate from Azure Database for PostgreSQL to Cloud SQL. This document discusses
how to design, implement, and validate a database migration from Azure Database
for PostgreSQL to Cloud SQL and AlloyDB for PostgreSQL.

This document is intended for cloud and database administrators who want details
about how to plan and implement a database migration project. It’s also intended
for decision-makers who are evaluating the opportunity to migrate and want an
example of what a migration might look like.

This document focuses on homogeneous migrations of Azure Database for PostgreSQL
to Cloud SQL for PostgreSQL and AlloyDB for PostgreSQL. A homogeneous database
migration is a migration between the source and target databases of the same
database technology, regardless of the database version. For example, you
migrate from a PostgreSQL based database instance in Azure to another PostgreSQL
based database in Google Cloud.

Google Cloud provides Cloud SQL for PostgreSQL and AlloyDB for PostgreSQL, two
fully managed relational database services that allows users to deploy, manage,
and scale PostgreSQL databases without the overhead of managing infrastructure.
In this document, we focus on Cloud SQL for PostgreSQL and AlloyDB for
PostgreSQL as the target environment to migrate the Azure Database for
PostgreSQL to.

| Source                        | Destination              |
| :---------------------------- | :----------------------- |
| Azure Database for PostgreSQL | Cloud SQL for PostgreSQL |
| Azure Database for PostgreSQL | AlloyDB for PostgreSQL   |

For a comprehensive mapping between Azure and Google Cloud services, see
[compare AWS and Azure services to Google Cloud services](https://cloud.google.com/free/docs/aws-azure-gcp-service-comparison).

For this migration to Google Cloud, we recommend that you follow the migration
framework described in
[Migrate to Google Cloud: Get started](https://cloud.google.com/architecture/migration-to-gcp-getting-started).

The following diagram illustrates the path of your migration journey. For
migration scenarios, the Deploy phase is equivalent to performing a migration
process.

![Migration path with four phases.](https://cloud.google.com//architecture/images/migration-to-gcp-getting-started-migration-path.svg)

You might migrate from Azure Database for PostgreSQL to Cloud SQL for PostgreSQL
and AlloyDB for PostgreSQL in a series of iterations—for example, you might
migrate some instances first and others later. For each separate migration
iteration, you follow the phases of the general migration framework:

1.  Assess and discover your workloads and data.
1.  Plan and build a foundation on Google Cloud.
1.  Migrate your workloads and data to Google Cloud.
1.  Optimize your Google Cloud environment.

For more information about the phases of this framework, see
[Migrate to Google Cloud: Get started](https://cloud.google.com/architecture/migration-to-gcp-getting-started).

To design an effective migration plan, we recommend that you validate each step
of the plan, and ensure that you have a rollback strategy. To help you validate
your migration plan, see
[Migrate to Google Cloud: Best practices for validating a migration plan](https://cloud.google.com/architecture/migration-to-google-cloud-best-practices).

The workloads to migrate may be composed of resources of several kinds, such as:

- Compute resources
- Data and object storage
- Databases
- Messaging and streaming
- Identity management
- Operations
- Continuous integration and continuous deployment

This document focuses on migrating Azure Database for PostgreSQL to Cloud SQL
for PostgreSQL. For more information about migrating other kinds of resources,
such as compute resources and objects storage from Azure to Google Cloud, see
the [Migrate from Azure to Google Cloud document series](./README.md).

## Assess the source environment

In the assessment phase, you determine the requirements and dependencies of the
resources that you want to migrate from Azure Database for PostgreSQL to Cloud
SQL for PostgreSQL and AlloyDB for PostgreSQL.

The assessment phase consists of the following tasks:

1.  Build a comprehensive inventory of your workloads.
1.  Catalog your workloads according to their properties and dependencies.
1.  Train and educate your teams about Google Cloud, including database best
    practices.
1.  Build experiments and proofs of concept on Google Cloud.
1.  Calculate the total cost of ownership (TCO) of the target environment.
1.  Decide on the order and priority of the workloads that you want to migrate.

The database assessment phase helps you answer questions regarding your database
version, size, platform, edition, dependencies and many more. It helps choose
the size and specifications of your target Cloud SQL instance that match the
source for similar performance needs. Pay special attention to disk size and
throughput, IOPS and number of vCPUs. Migrations might struggle or fail due to
incorrect target instance sizing. Incorrect sizing can lead to long migration
times, database performance problems, database errors and application
performance problems. When deciding on the Cloud SQL instance, keep in mind that
disk performance is based on the disk size and the number of vCPUs.

For more information about the assessment phase and these tasks, see
[Migrate to Google Cloud: Assess and discover your workloads](https://cloud.google.com/solutions/migration-to-gcp-assessing-and-discovering-your-workloads).
The following sections are based on information in that document.

### Build an inventory of your Azure Database for PostgreSQL databases

To define the scope of your migration, you create an inventory and collect
information about your Azure Database for PostgreSQL databases. Ideally, this
should be an automated process, because manual approaches are prone to error and
can lead to incorrect assumptions.

Azure Database for PostgreSQL, Cloud SQL for PostgreSQL and AlloyDB for
PostgreSQL might not have similar features, instance specifications, or
operation. Some functionalities might be implemented differently or be
unavailable. Some features are specific only to Azure Database for PostgreSQL.
For example, Azure Database for PostgreSQL Flexible Server has burstable compute
configurations, designed to handle workloads with variable CPU demands.

In other areas, Cloud SQL for PostgreSQL employs features that are not available
in Azure Database for PostgreSQL like the 64 TB maximum storage size or 3-year
extended support for End-Of-Life (EOL) versions of PostgreSQL in the Enterprise
edition. Other areas of differences might include underlying infrastructure,
authentication and security, replication and backup.

AlloyDB for PostgreSQL is designed to offer higher throughput for transactional
workloads and it uses a columnar engine for analytical queries that can improve
performance on large-scale datasets, similar to dedicated analytics databases.

Benchmarking can help you to better understand the workloads that are to be
migrated and contributes to defining the right architecture of the migration
target environment. Collecting information about performance is important to
help estimate the performance needs of the Google Cloud target environment.
Benchmarking concepts and tools are detailed in the
[Perform testing and validation of the migration process](#perform-testing-and-validation),
but they also apply to the inventory building stage.

For more information about Azure Database for PostgreSQL, see
[What is Azure Database for PostgreSQL flexible server?](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/service-overview)

#### Performance assessment

Take baseline measurements on your source environment in production use.
Consider employing tools such as pgbench and DBT2 Benchmark Tool.

- Measure the size of your data, as well as your workload’s performance. How
  long do important queries or transactions take, on average? How long during
  peak times? This includes metrics such as:

    - Query response times: For common and critical queries.
    - Transactions per second (TPS): A measure of how many transactions your
      database can handle.
    - Resource utilization: CPU, memory, and disk I/O usage.
    - Latency: The time it takes for data to travel between points.

- Load testing: Simulate realistic user loads to assess how the database
  performs under stress.
- You document the benchmarking results for later comparison in the validate the
  migration before the cut-over step. The comparison helps you decide if the
  fidelity of your database migration is satisfactory and if you can switch your
  production workloads.

For more information about benchmarking in PostgreSQL, see
[pgbench](https://www.postgresql.org/docs/current/pgbench.html).

#### Tools for assessments

We recommend Google Cloud
[Migration Center](https://cloud.google.com/migration-center/docs/migration-center-overview)
for an initial full assessment of your current infrastructure and database
estate. With Migration Center you can perform a complete assessment of your
application and database landscape, including the technical fit of your database
for a Cloud SQL database migration. You receive Cloud SQL shape recommendations,
create a TCO report composed of servers and databases, and you can also set
preferred target Google Cloud configurations.

The database assessment with Migration Center is comprised of three main steps:

- Collect databases configuration via open source scripts or exports
- Assess database Technical Fit to Cloud SQL
- Generate a TCO report, including server grouping and migration preferences

For more information about assessing your Azure environment by using Migration
Center, see
[Import data from other cloud providers](https://cloud.google.com/migration-center/docs/import-data-cloud-providers).

Additionally, you can also use other tools that are more specialized database
assessments. For example, Database Migration Assessment tool (DMA) is an open
source data collector tool, backed by Google’s engineers, Professional Services,
and partners. It offers a complete and accurate database assessment, including
features in use, database code and database objects, for example: schemas,
tables, views, functions, triggers and stored procedures.

While DMA focuses specifically on database instances and is specialized on
assessments where the purpose is database modernization, having the target
database engine different than the source database engine, it can also be used
for homogeneous database migrations, within Google Cloud Migration Center.

For guidance about using the open-source data collector and assessment scripts,
see
[Google Cloud Database Migration Assessment](https://cloud.google.com/migration-center/docs/discover-and-import-databases).

Alternatively, you can also use other open-source data collectors and diagnostic
scripts. These scripts can help you collect information about your database
workloads, features, and database diagnostic information, helping you build your
database inventory.

### Assess your deployment and administration process

After you build the inventories, we recommend that you assess your database
operational and deployment processes to determine how they need to be adapted to
facilitate your migration. These are a fundamental part of the practices that
prepare and maintain your production environment.

Consider how you complete the following tasks:

- **Define and enforce security policies for your instances:** For example, you
  might need to replace
  [Private Network Access with Virtual Network](https://learn.microsoft.com/en-us/azure/mysql/flexible-server/concepts-networking-vnet)
  and
  [Microsoft Entra authentication](https://learn.microsoft.com/en-us/azure/mysql/flexible-server/concepts-azure-ad-authentication).
  You can use Google IAM roles, VPC firewall rules, VPC Service Controls,
  Private Service Connect, and Cloud SQL Auth Proxy to control access to your
  Cloud SQL instances and constrain the data within a VPC or a group of VPCs.

- **Set up your network infrastructure.** Document how users and applications
  connect to your database instances. Build an inventory of existing subnets, IP
  ranges and types, firewall rules, private DNS names. Consider having similar
  or complementary network configurations of your Azure Virtual Network in
  Google Cloud. For more information about connecting to a Cloud SQL for
  PostgreSQL instance, see:

    - [About connection options in Cloud SQL for PostgreSQL](https://cloud.google.com/sql/docs/postgres/connect-overview)
    - [Connection overview in AlloyDB for PostgreSQL](https://cloud.google.com/alloydb/docs/connection-overview)

- **Define access control to your instances.** Consider configuring access to
  define who or what can access the instance. For more information about access
  control in Cloud SQL for PostgreSQL and AlloyDB for PostgreSQL, see:

    - [About access control in Cloud SQL for PostgreSQL](https://cloud.google.com/sql/docs/postgres/instance-access-control)
    - [Grant access to other users in AlloyDB for PostgreSQL](https://cloud.google.com/alloydb/docs/user-grant-access)

- **Define backup plans.** Create a reliable backup strategy on Cloud SQL that
  aligns with Azure’s backup capabilities. For more information about backup
  plans, see:

    - [Schedule Cloud SQL database backups](https://cloud.google.com/sql/docs/postgres/backup-recovery/scheduling-backups)
    - [Configure backup plans for AlloyDB](https://cloud.google.com/alloydb/docs/backup/configure)

- **Define HA and business continuity plans.** We recommend using regional
  instances with zonal availability and cross-regional replicas for DR and read
  scaling purposes with Cloud SQL and considering using
  [Cloud SQL Enterprise Plus](https://cloud.google.com/sql/docs/editions-intro)
  edition to avoid unexpected failover delays.

- **Patch and configure your instances.** Your existing deployment tools might
  need to be updated. For example, you might be using Azure CLI to configure
  your instances. Your provisioning tools might need to be adapted to work with
  the gcloud command tool and the
  [Google Cloud Client Libraries](https://cloud.google.com/apis/docs/cloud-client-libraries).

- **Manage monitoring and alerting infrastructure.** Metric categories for your
  Azure source database instances provide observability during the migration
  process. Metric categories might include Azure Monitor and Azure Monitor
  workbooks.

### Complete the assessment

After you build the inventory of your Azure databases, complete the rest of the
activities of the assessment phase as described in
[Migrate to Google Cloud: Assess and discover your workloads](https://cloud.google.com/solutions/migration-to-gcp-assessing-and-discovering-your-workloads).

## Plan and build your foundation

In the plan and build phase, you provision and configure the infrastructure to
do the following:

- Support your workloads in your Google Cloud environment.
- Connect your Azure environment and your Google Cloud environment to complete
  the migration.

### Build your foundation on Google Cloud

The plan and build phase is composed of the following tasks:

1.  Build a resource hierarchy.
1.  Configure identity and access management.
1.  Set up billing.
1.  Set up network connectivity.
1.  Harden your security.
1.  Set up logging, monitoring, and alerting.

For more information about each of these tasks, see
[Migrate to Google Cloud: Build your foundation](https://cloud.google.com/architecture/migration-to-google-cloud-building-your-foundation).

### Monitoring and alerting

Use Google [Cloud Monitoring](https://cloud.google.com/monitoring), which
includes predefined dashboards for several Google Cloud products, including a
Cloud SQL monitoring dashboard. Alternatively, you can consider using
third-party monitoring solutions that are integrated with Google Cloud, like
Datadog and Splunk. For more information about monitoring and altering, see
[About database observability](https://cloud.google.com/sql/docs/sqlserver/observability)
and [Monitor instances](https://cloud.google.com/alloydb/docs/monitor-instance).

###

## Migrate Azure Database for PostgreSQL to Cloud SQL for PostgreSQL and AlloyDB for PostgreSQL

To migrate your instances, you do the following:

1.  [Choose the migration strategy: continuous replication or scheduled maintenance](#choose-the-migration-strategy).

1.  [Choose the migration tools](#choose-the-migration-tools), depending on your
    chosen strategy and requirements.

1.  [Define the migration plan and timeline](#define-the-migration-timeline) for
    each database migration, including preparation and execution tasks.

1.  [Define the preparation tasks](#define-the-preparation-tasks) that must be
    done to ensure the migration tool can work properly.

1.  [Define the execution tasks](#define-the-execution-tasks), which include
    work activities that implement the migration.

1.  [Define fallback scenarios](#define-fallback-scenarios) for each execution
    task.

1.  [Perform testing and validation](#perform-testing-and-validation), which can
    be done in a separate staging environment.

1.  [Perform the migration](#perform-the-migration).

1.  [Validate the migration before cut-over](#validate-the-migration-before-cut-over).
    This step involves validation of critical business transactions, including
    verifying that their performance respects your SLAs.

1.  [Perform the production cut-over](#perform-the-production-cut-over).

1.  [Clean up the source environment and configure the Cloud SQL and AlloyDB instance](#cleanup-the-source-environment-and-configure-the-cloud-sql-and-alloydb-instance).

1.  [Optimize your environment after migration](#optimize-your-environment-after-migration).

1.  [Update database production operations runbooks and support documentation](#update-database-production-operations-runbooks-and-support-documentation-to-align-with-the-cloud-sql-database-platform)
    to align with the Cloud SQL and AlloyDB database platform.

Each phase is described in the following sections.

### Choose the migration strategy

At this step, you have enough information to evaluate and decide on one of the
following migration strategies that best suits your use case for each database:

- **Scheduled maintenance** (also called one-time migration or big-bang
  migration): Ideal if you can afford downtime. This option is relatively low in
  cost and complexity, because your workloads and services won’t require much
  refactoring. However, if the migration fails before completion, you have to
  restart the process, which prolongs the downtime. For more details, see
  [Scheduled maintenance.](https://cloud.google.com/architecture/migration-to-google-cloud-transferring-your-large-datasets#scheduled_maintenance)

- **Continuous replication** (also called online migration or trickle
  migration): For mission-critical databases that can't undergo any scheduled
  downtime, choose this option, which offers a lower risk of data loss and
  near-zero downtime. Because the efforts are split into several chunks, if a
  failure occurs, rollback and repeat takes less time. However, a relatively
  complex setup is required and takes more planning and time. For more details,
  see
  [Continuous replication](https://cloud.google.com/architecture/migration-to-google-cloud-transferring-your-large-datasets#continuous_replication).

Two variations of the continuous replication strategy are represented by Y
(writing and reading) and the Data-access microservice migration pattern. They
both are a form of continuous replication migration, duplicating data in both
source and destination instances. While they can offer zero downtime and high
flexibility when it comes to migration, they come with an additional complexity
given by the efforts to refactor the applications that connect to your database
instances. For more information about data migration strategies, see
[Migration to Google Cloud: Transferring your large datasets \- Evaluating data migration approaches.](https://cloud.google.com/architecture/migration-to-google-cloud-transferring-your-large-datasets#data_migration_approaches)

The following diagram shows a flowchart based on example questions that you
might have when deciding the migration strategy for a single database:

![view of the path to decide the migration strategy for a single database from Azure Database for PostgreSQL to Cloud SQL for PostgreSQL and AlloyDB for PostgreSQL](docs/azuremysql_mig_strategy_homogeneous.svg "Path to decide the migration strategy for a single database from Azure Database for PostgreSQL to Cloud SQL for PostgreSQL and AlloyDB for PostgreSQL")

The diagram can be summarized as follows:

**Migrate from Azure Database for PostgreSQL to Cloud SQL for PostgreSQL and
AlloyDB for PostgreSQL path**

**Can you afford the downtime represented by the cut-over window while migrating
data?** The cut-over window represents the time to take a backup of the
database, transfer it to Cloud SQL, restore it \- manually or using tools like
Database Migration Service, and then switch over your applications.

- If yes, adopt the **Scheduled Maintenance migration strategy**.
- If no, adopt the **Continuous Replication migration strategy**.

Strategies may vary for different databases located on the same instance and
usually a mix of them can produce optimal results. Small and infrequently used
databases can usually be migrated using the scheduled maintenance approach,
while for the mission-critical ones where having downtime is expensive, the best
fitting strategies usually involve continuous replication.

Usually, a migration is considered completed when the switch between the initial
source and the target instances takes place. Any replication (if used) is
stopped and all reads and writes are done on the target instance. Switching when
both instances are in sync means no data loss and minimal downtime.

When the decision is made to migrate all applications from one replica to
another, applications (and therefore customers) might have to wait (incurring
application downtime) at least as long as the replication lag lasts before using
the new database. In practice, the downtime might be higher because:

#### Database Instance

- Database queries can take a few seconds to complete. At the time of migration,
  in-flight queries might be aborted.
- The database has to be “warmed up” by filling up the cache if it has
  substantial buffer memory, especially in large databases.

#### TCP reconnections

- When applications establish a connection to the Google Cloud target database
  instance, they need to go through the process of connection initialization.
  This includes authentication, session setup, and possibly the negotiation of
  secure connections such as SSL and TLS handshakes.

#### Applications

- Applications might need to reinitialize internal resources, such as connection
  pools, caches, and other components, before they can fully connect to the
  database. This warm-up time can contribute to the initial lag.
- If an application was in the middle of processing transactions when it was
  stopped, it might need to recover or reestablish those sessions when it
  reconnects. Depending on how the application handles state and session
  recovery, this process can take some additional time.

#### Network Latency

- Applications stopped at source and restarted in Google Cloud might have a
  small lag until the connection to the Google Cloud database instance is
  established, depending on the network conditions, especially if the network
  paths need to be recalculated or if there is high network traffic.
- If the Google Cloud database is behind a load balancer, the load balancer
  might take a moment to route the incoming connection to the appropriate
  database instance.

#### DNS

- Network routes to the applications must be rerouted. Based on how DNS entries
  are set up this can take some time (tip: reduce TTL before migrations when
  updating DNS records).

For more information about data migration strategies and deployments, see
[Classification of database migrations](https://cloud.google.com/architecture/database-migration-concepts-principles-part-1#classification_of_database_migrations).

#### Minimize downtime and impact due to migration

Migration configurations that provide no application downtime require the most
complex setup. One has to balance the efforts needed for a complex migration
setup and deployment orchestrations against the perspective of having a
scheduled downtime, planned when its business impact is minimal. Have in mind
that there is always some impact associated with the migration process. For
example, replication processes involve some additional load on your source
instances and your applications might be affected by replication lag.

While managed migration services try to encapsulate that complexity, application
deployment patterns, infrastructure orchestration and custom migration
applications might also be involved to ensure a seamless migration and cut-over
of your applications.

Some common practices to minimize downtime impact:

- Find a time period for when downtime impacts minimally your workloads. For
  example: outside normal business hours, during weekends, or other scheduled
  maintenance windows.
- Find modules of your workloads for which the migration and production cut-over
  can be executed at different stages. Your applications might have different
  components that can be isolated, adapted and migrated earlier. For example:
  Frontends, CRM modules, backend services, reporting platforms. Such modules
  could have their own databases that can be scheduled for migration earlier in
  the process.
- Consider implementing a gradual, slower paced migration, having both the
  source and target instances as integral parts of your workloads. You might
  mitigate your migration impact if you can afford to have some latency on the
  target database by using incremental, batched data transfers and adapting part
  of your workloads to work with the stale data on the target instance.
- Consider refactoring your applications to support minimal migration impact.
  For example: adapt your applications to write to both source and target
  databases and therefore implement an application-level replication.

### Choose the migration tools

For a successful migration of your Azure Database for PostgreSQL to Cloud SQL
and AlloyDB for PostgreSQL, choosing the right tool for the migration is the
most important aspect. Once the migration strategy has been decided, it is time
to review and decide.

There are many tools to migrate a database, each of them being optimized for
certain migration use cases. These usually depend on:

- migration strategy. For example: scheduled maintenance, continuous
  replication.
- source and target database engines and engine versions \- some tools may be
  specialized in same database engine migrations, while others can also handle
  migrations of different database engines.
- environments where the source and target instances are located \- you might
  choose different tools for dev/test, staging and production environments.
- database size \- the larger the database, the more time it takes to migrate
  the initial backup.
- special migration requirements like data transformations or database schema
  consolidation.
- database change frequency.
- migration scope \- tools specialized in migrating schema, data and users and
  logins.
- licensing and cost.
- availability to use managed services for migration.

Database migration systems encapsulate the complex logic of migration and offer
monitoring capabilities. They execute the data extraction from the source
databases, securely transport it from the source to the target databases and can
optionally modify the data during transit. We can list the advantages of using
database migration systems as follows:

- **Minimize downtime.** Downtime can be minimized by using the built-in
  replication capabilities of the migrated storage engines in an easy to manage,
  centralized way.

- **Ensure data integrity and security.** Migration systems can ensure that all
  data is securely and reliably transferred from the source to the destination
  database.

- **Provide uniform and consistent migration experience.** Different migration
  techniques and patterns can be abstracted in a consistent, common one-stop
  interface by using database migration executables that can be managed and
  monitored.

- **Offer resilient and proven migration models.** Database migrations are not
  happening often so chances are that using a tool developed by experts in this
  area brings huge benefits rather than trying to implement something custom
  made. Moreover, a cloud based migration system also comes with increased
  resiliency.

In the next sections, we explore the migration tools recommended depending on
the chosen migration strategy.

#### Tools for scheduled maintenance migrations

The following subsections describe the tools that can be used for one-time
migrations, along with their limitations and best practices.

For one-time migrations to Cloud SQL for PostgreSQL and AlloyDB for PostgreSQL,
we recommend using built-in database engine backups.

##### Built-in database engine backups

When significant downtime is acceptable, and your source databases are
relatively static, you can use the database engine's built-in dump and load
(also sometimes called backup and restore) capabilities. Database engine backups
are usually readily available and straightforward to use.

Database engine backups have the following general limitations:

- Data is unsecured if the backups are not properly managed.
- Built-in backups usually have limited monitoring capabilities.
- Effort is required to scale, if many databases are being migrated by using
  this tool.

You can perform database engine backups on your Azure Database for PostgreSQL
databases by using the pg_dump utility on a running server. With pg_dump you can
have consistent backups even if the database is being used, as it doesn't block
users from accessing and reading the database. However, it requires some
additional CPU, memory, and IO resources. This is why the best candidates for
pg_dump are relatively small sized, non-mission critical databases. For large,
write-intensive databases, we recommend stopping database writes before running
pg_dump or performing pg_dump on a point-in-time replica.

Consider using the best practices from
[Best practices for pg_dump and pg_restore for Azure Database for PostgreSQL \- Flexible Server](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/how-to-pgdump-restore)
to speed up the backup and restore of large databases.

- Consider excluding large static tables that you might import via flat files.

- Perform the restore from a dump file stored on a Cloud Storage bucket that is
  in the same region to your Cloud SQL instance.

- Regional buckets have lower availability guarantees compared to multi-regional
  or dual-regional buckets. However, for one-time imports, regional buckets
  should suffice.
- If you are migrating to a different region, consider using compressed dumps as
  this involves faster uploads and downloads to Cloud Storage. However,
  compressed backups take longer to restore.

The dump file does not contain the statistics used by the optimizer to make
query planning decisions. To ensure optimal database performance after the
restore of a pg_dump file we recommend running
[ANALYZE](https://www.postgresql.org/docs/current/sql-analyze.html). Note that
you can run ANALYZE while restoring as part of the pg_restore command.

The pg_dump utility doesn't include users and roles. To migrate these user
accounts and roles, you can use the
[pg_dumpall](https://www.postgresql.org/docs/current/app-pg-dumpall.html)
utility. pg_dumpall exports all PostgreSQL databases of a cluster into one
script file, but you can also use it to export only global objects such as roles
and tablespaces by providing the **\--globals-only** command-line option.

For further reading about limitations and best practices for importing and
exporting data with Cloud SQL for PostgreSQL and AlloyDB for PostgreSQL, see the
following:

- [Best practices for importing and exporting data with Cloud SQL for PostgreSQL](https://cloud.google.com/sql/docs/postgres/import-export)
- [Import a DMP file into an AlloyDB database](https://cloud.google.com/alloydb/docs/import-dmp-file)

##### File export and import

You can consider exporting the tables from your source PostgreSQL database to
flat files, which can then be imported into the target Cloud SQL for PostgreSQL
and AlloyDB for PostgreSQL.

To export data from your Azure Database for PostgreSQL source instance, use the
**azure_storage** extension. You execute the COPY statement or the blob_put
function to export data from a table to Azure Blob Storage. You then copy the
files to a Google Cloud Storage bucket and import it to Cloud SQL for PostgreSQL
and AlloyDB for PostgreSQL.

Alternatively, you can use
[Azure Data Factory with your PostgreSql database as a source](https://learn.microsoft.com/en-us/azure/data-factory/connector-azure-database-for-postgresql?tabs=data-factory#azure-database-for-postgresql-as-source)
and a Google Cloud Storage bucket as the target. Once the data is in flat files,
you can import it to Cloud SQL for PostgreSql and AlloyDB for PostgreSQL.

For more information on importing data from files to Cloud SQL for PostgreSQL
and AlloyDB for PostgreSQL, see:

- [Export data from Azure Database for PostgreSQL flexible server to Azure Blob Storage](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-storage-extension#export-data-from-azure-database-for-postgresql-flexible-server-to-azure-blob-storage)
- [Import data from a CSV file to Cloud SQL for PostgreSQL](https://cloud.google.com/sql/docs/mysql/import-export/import-export-csv)
- [Import a CSV file into an AlloyDB database](https://cloud.google.com/alloydb/docs/import-csv-file)

#### Tools for continuous replication migrations

The following sections describe the tools that can be used for continuous
replication migrations, along with their limitations and common issues.

##### Database Migration Service for continuous replication migration to Cloud SQL

Cloud SQL for PostgreSQL supports replication from a PostgreSQL source instance,
including Azure Database for PostgreSQL. Continuous Database Migration Service
migration jobs can be promoted, which signals the replication to stop.

If you choose this tool, consider the following best practices and restrictions:

- Consider migrating from a read replica.
- Users need to be migrated manually.
- You must install the pglogical extension on both source and target databases.
- There might be brief write downtime, depending on the number of tables in your
  source database.
- When migrating from Azure Database for PostgreSQL, some specific unsupported
  extensions will not be migrated, such as: azure and pgaadauth.

For a full list of limitations, see
[Known limitations](https://cloud.google.com/database-migration/docs/postgres/known-limitations).

At the moment of writing this document, Database Migration Service does not yet
support migrating from Azure Database for PostgreSQL to AlloyDB for PostgreSQL.
Alternatively, you can migrate to an intermediary Cloud SQL for PostgreSQL
instance and then perform a migration to AlloyDB for PostgreSQL.

##### Database replication

Cloud SQL for PostgreSQL and AlloyDB for PostgreSQL support
[logical replication](https://www.postgresql.org/docs/current/logical-replication.html)
from Azure Database for PostgreSQL. Database replication represents the ongoing
process of copying and streaming data from a database called the primary
database to other databases called replicas.

Data changes are extracted from the WAL logs using logical decoding and are
represented in SQL statements such as INSERTs, UPDATEs, and DELETEs. In this
way, logical replication enables replication across different PostgreSQL major
versions.

Logical replication in Cloud SQL is supported in two ways:

- Built-in
  [logical replication](https://www.postgresql.org/docs/current/logical-replication.html),
  added in PostgreSQL 10\.
- Logical replication through
  [pglogical](https://github.com/2ndQuadrant/pglogical) extension, available in
  all PostgreSQL versions.

For built-in replication migrations to Cloud SQL for PostgreSQL and AlloyDB for
PostgreSQL, we recommend using the pglogical extension for replication because
it offers broader compatibility and it is a mature solution for migrations, used
by many customers and by Database Migration Service.

For most replication setups, when you need a simple, reliable, and
low-maintenance solution for single-directional replication, PostgreSQL’s
built-in logical replication provides a solid, integrated solution. For
PostgreSQL versions starting with v15, built-in logical replication offers
improved flexibility in filtering rows, columns and performing transformations.

Consider the pglogical extension if you need multi-master replication, advanced
filtering especially for PostgreSQL versions lower than 15, and conflict
resolution, especially for complex distributed systems, sharded databases, or
when operating in environments with PostgreSQL 9.4-9.6. If any of your sources
or targets are using a PostgreSQL version lower than 10, you must use pglogical.

Limitations of logical replication include:

- Schema and DDL commands are not replicated. The two schemas of the source and
  target must be kept in sync manually.
- Sequence data is not replicated.
- TRUNCATE commands are not replicated.
- Large objects are not replicated

For more information on the limitations of logical replication, see
[Restrictions in the PostgreSQL Logical Replication documentation](https://www.postgresql.org/docs/current/logical-replication-restrictions.html).

For further reading about best practices for replicating data from Azure
Database for PostgreSQL to Cloud SQL for PostgreSQL, see the following:

- [Configure Cloud SQL and the external server for replication](https://cloud.google.com/sql/docs/postgres/replication/configure-replication-from-external)
- [Set up logical replication and decoding](https://cloud.google.com/sql/docs/postgres/replication/configure-logical-replication)
- [Logical replication and logical decoding in Azure Database for PostgreSQL \- Flexible Server](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-logical)

##### Third-party tools for continuous migration

You can decide to use a third-party tool to execute your database migration.
Choose one of the following recommendations, which you can use for most database
engines:

[Striim](https://www.striim.com/striim-for-google-cloud-sql/) is an end-to-end,
in-memory platform for collecting, filtering, transforming, enriching,
aggregating, analyzing, and delivering data in real time. It can handle large
data volumes, complex migrations.

- Advantages:

- Handles large data volumes and complex migrations.
- Preconfigured connection templates and no-code pipelines.
- Able to handle mission-critical, large databases that operate under heavy
  transactional load.
- Exactly-once delivery.

- Disadvantages:

- Not open source.
- Can become expensive, especially for long migrations.
- Some limitations in data definition language (DDL) operations propagation. For
  more information, see
  [Supported DDL operations](https://www.striim.com/docs/en/handling-schema-evolution.html#supported-ddl-operations)
  and
  [Schema evolution notes and limitations](https://www.striim.com/docs/en/handling-schema-evolution.html#schema-evolution-notes-and-limitations).

For more information about Striim, see:

- [Running Striim in the Google Cloud Platform](https://www.striim.com/docs/platform/en/running-striim-in-the-google-cloud-platform.html).
- [Striim Migration Service to Google Cloud Tutorials](https://www.striim.com/videos/striim-migration-service-to-google-cloud-tutorials/)
- [How to Migrate Transactional Databases to AlloyDB for PostgreSQL](https://www.striim.com/videos/how-to-migrate-transactional-databases-to-alloydb/)

[Debezium](https://debezium.io/) is an open source distributed platform for CDC,
and can stream data changes to external subscribers:

- Advantages:

- Open source.
- Strong community support.
- Cost effective.
- Fine grained control on rows, tables or databases.
- Specialized for change capture in real time from database transaction logs.

- Challenges:

- Require specific experience with Kafka and ZooKeeper.
- At-least-once delivery of data changes, which means that you need duplicates
  handling.
- Manual monitoring setup using Grafana and Prometheus.
- No support for incremental batch replication.

For more information about using Debezium with Azure Database for PostgreSQL,
see
[Debezium for Change Data Capture](https://learn.microsoft.com/en-us/azure/event-hubs/event-hubs-kafka-connect-debezium).

[Fivetran](https://www.fivetran.com/) is an automated data movement platform for
moving data out of and across cloud data platforms.

- Advantages:
- Preconfigured connection templates and no-code pipelines.
- Propagates any schema changes from your source to the target database.
- Exactly-once delivery.

- Disadvantages:
- Not open source.
- Support for complex data transformation is limited.

For more information about Azure Database for PostgreSQL migrations with
Fivetran, see
[Azure PostgreSQL Database Setup Guide](https://fivetran.com/docs/connectors/databases/postgresql/azure-setup-guide).

| Product  | Strengths                                                                                                                                                                                                                         | Constraints                                                                                                                                                                                                                                       |
| :------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Striim   | Handles large data volumes and complex migrations. Preconfigured connection templates and no-code pipelines. Able to handle mission-critical, large databases that operate under heavy transactional load. Exactly-once delivery. | Not open source. Can become expensive, especially for long migrations. Some limitations in data definition language (DDL) operations propagation.                                                                                                 |
| Debezium | Open source. Strong community support. Cost effective. Fine grained control on rows, tables or databases. Specialized for change capture in real time from database transaction logs.                                             | Requires specific experience with Kafka and ZooKeeper. At-least-once delivery of data changes, which means that you need duplicates handling. Manual monitoring setup using Grafana and Prometheus. No support for incremental batch replication. |
| Fivetran | Preconfigured connection templates and no-code pipelines. Propagates any schema changes from your source to the target database. Exactly-once delivery.                                                                           | Not open source. Support for complex data transformation is limited.                                                                                                                                                                              |

### Define the migration timeline

During this step, you prepare a timeline for each database that is to be
migrated, with defined start and estimated end dates that contains all work
items that have to be performed to achieve a successful migration.

We recommend constructing a T-Minus plan per migration environment. This is a
plan that contains the tasks required to complete the migration project,
structured as a countdown schedule, along with the responsible groups and
estimated duration.

For more information about defining the migration timeline, see
[Define the migration timeline](https://cloud.google.com/architecture/migrate-aws-rds-to-cloudsql-for-sqlserver#define_the_migration_plan_and_timeline)**.**

### Define the preparation tasks

The preparation tasks refer to all the activities that you need to complete so
that a database fulfills the migration prerequisites. Without these, migration
can't take place or the database once migrated can be in an unusable state.

Consider the following prerequisite tasks depending on the migration tool you
choose:

#### Built-in database engine backups preparation

- Ensure enough disk space on the machine where you are exporting the PostgreSQL
  dump file.
- You might need to create a Cloud Storage bucket for the DMP file and
  potentially a client host to perform the import operation. For more
  information, see
  [Export and import using SQL dump files for CloudSQL](https://cloud.google.com/sql/docs/postgres/import-export/import-export-sql)
  and
  [Import a DMP file for AlloyDB](https://cloud.google.com/alloydb/docs/import-dmp-file).

#### File export and import preparation

- Provision a Google Cloud Storage bucket in which you store the flat files. For
  more information, see
  [Export and import using CSV files](https://cloud.google.com/sql/docs/postgres/import-export/import-export-csv)
  and
  [Import a CSV file for AlloyDB](https://cloud.google.com/alloydb/docs/import-csv-file).
- If you intend to use Azure Data Factory, you might need to create a linked
  service and define a dataset in Azure Data Factory.

#### Database Migration Service for continuous replication migration to Cloud SQL preparation

- Follow the guidance from Database Migration Service documentation
  [Configure your source: Microsoft Azure Database for PostgreSQL](https://cloud.google.com/database-migration/docs/postgres/configure-source-database#azure-postgres).
- Depending on the type of connection you establish between your source and
  target database instances, you might need to disable the
  **require_secure_transport** setting on your source instance.

#### Database replication preparation

- Create a replication user account on the source instance and make sure it has
  replication privileges:

    ```sql
    CREATE ROLE repuser WITH REPLICATION LOGIN PASSWORD 'password';
    ```

- Set up your source instance for replication for PostgreSQL. Built-in
  replication or tools that use built-in replication need logical replication
  for PostgreSQL. If you plan on using logical replication with pglogical, you
  must allowlist and install the pglogical extension. Follow the guidance from
  Database Migration Service documentation
  [Configure your source: Microsoft Azure Database for PostgreSQL](https://cloud.google.com/database-migration/docs/postgres/configure-source-database#azure-postgres).
- Check that the target Cloud SQL and AlloyDB instances have network
  connectivity to your Azure source instance.
  [Get the Cloud SQL replica's outgoing IP address](https://cloud.google.com/sql/docs/mysql/replication/configure-replication-from-external#outgoing-ip)
  and set up
  [firewall rules to allow incoming connections](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-firewall-rules)
  from the Cloud SQL for PostgreSQL replica. After the migration completes
  successfully, remove the firewall permissions that you’ve set.
- Create a source representation instance that references the source Azure
  Database for PostgreSQL server. It contains only the request data from the
  external server. For more information about the source representation
  instance, see
  [Set up a source representation instance](https://cloud.google.com/sql/docs/postgres/replication/configure-replication-from-external#setup-source-instance).
- Define the set of tables for which you want to set up replication.
- Set up your target Cloud SQL instance as a replica. The Cloud SQL replica
  eventually contains the data from the external server. For more information
  about setting up Cloud SQL for PostgreSQL as a replica, see
  [Set up a Cloud SQL replica](https://cloud.google.com/sql/docs/postgres/replication/configure-replication-from-external#setup-replica-instance).
- For AlloyDB, you need to enable logical replication on the source instance by
  setting alloydb.logical_decoding to on. For using pglogical, you need to set
  alloydb.[enable_pglogical](https://cloud.google.com/alloydb/docs/reference/alloydb-flags#alloydb.enable_pglogical)
  to on.

For more information about Cloud SQL setup, see
[General best practices for Cloud SQL for PostgreSQL](https://cloud.google.com/sql/docs/postgres/best-practices).

#### Third-party tools for continuous migration preparation

For most third-party tools, you need to provision migration specific resources.
Upfront settings and configurations are usually required before using the tool.
Check the documentation from the third-party tool. For example, for Striim, you
need to use the Google Cloud Marketplace to begin. Then, to set up your
migration environment in Striim, you can use the Flow Designer to create and
change applications, or you can select a pre-existing template.

#### General preparation tasks

- Document the
  [server parameters](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-server-parameters)
  of your Azure Database for PostgreSQL source instance as you might need to
  apply them on your target instance before doing migration testing and
  validation.
- Choose the project and region of your target Cloud SQL and AlloyDB instances
  carefully. Cloud SQL and AlloyDB instances can't be migrated between Google
  Cloud projects and regions without data transfer.
- Migrate user information separately. Cloud SQL and AlloyDB manages users using
  the built-in PostgreSQL users and groups and Google IAM. Tools such as
  Database Migration Service do not migrate information about users and user
  roles. For more details about authentication, see
  [Cloud SQL AM authentication](https://cloud.google.com/sql/docs/postgres/iam-authentication)
  and
  [AlloyDB for PostgreSQL Manage IAM authentication](https://cloud.google.com/alloydb/docs/database-users/manage-iam-auth).

### Define the execution tasks

Execution tasks implement the migration work itself. The tasks depend on your
chosen migration tool, as described in the following subsections.

#### Built-in database engine backups execution

You can perform a database migration from Azure Database for PostgreSQL to Cloud
SQL for PostgreSQL using the pg_dump, pg_dumpall, and pg_restore utilities by
performing the following steps:

1.  Create a VM in Azure that can connect to your source Azure Database for
    PostgreSQL, ideally in the same region of both your source and target
    instances, or at least closer to one of them.
1.  Provision a Google Cloud Storage bucket in the same region as your target
    Cloud SQL instance.
1.  Stop writing to your source databases.
1.  Run pg_dump to backup your database and to extract the database into a
    script file or archive file. Consider using the flags suggested in the
    [Export data from an on-premises PostgreSQL server using pg_dump](https://cloud.google.com/sql/docs/postgres/import-export/import-export-dmp#external-server)
    section. Some options to reduce the overall dump time and impact are:

- Consider table vacuuming before running pg_dump. Having a high number of dead
  tuples might increase pg_dump duration.
- Consider running pg_dump on a replica to avoid the extra load on your primary.
  However, if data consistency and freshness are crucial for your backup, make
  sure that the replica is caught up with the primary before performing the
  dump.
- Consider the compression level to use. Having no compression might help with
  performance.
- Run dump jobs concurrently by using the parallel jobs option. However, this
  can lead to additional load on the database server.

    Optionally, you can consider running pg_dumpall. pg_dumpall is a utility
    that allows you to extract all PostgreSQL databases of a cluster into a
    single script file.

1.  Transfer the dump file to the Google Cloud Storage bucket you provisioned
    earlier.
1.  Import the dump file to the Cloud SQL for PostgreSQL instance. Follow the
    guidance from the
    [Import a SQL dump file to Cloud SQL for PostgreSQL](https://cloud.google.com/sql/docs/postgres/import-export/import-export-sql#import_a_sql_dump_file_to)
    and
    [Import](https://cloud.google.com/sql/docs/postgres/import-export/import-export-dmp#import)
    documentation section.
1.  Connect your applications to the target Cloud SQL Instance and start writing
    to your new database instance.

#### File export and import execution

You can perform a database migration from Azure Database for PostgreSQL to Cloud
SQL by exporting table data to flat files using various utilities such as
[pgAdmin](https://www.pgadmin.org/),
[psql](https://www.postgresql.org/docs/current/app-psql.html), the azure_storage
extension and Azure Data Factory.

You can export data to files using pgAdmin by performing the following steps:

1.  Provision a Google Cloud Storage bucket in the same region as your target
    Cloud SQL for PostgreSQL instance.
1.  Create a VM in Azure that can connect to your source Azure Database for
    PostgreSQL, ideally in the same region of your source database.
1.  On the VM, connect to the Azure Database for PostgreSQL using pgAdmin.
1.  Stop writing to your source databases.
1.  Navigate to the tables you want to export in the Object Explorer on the
    left.
1.  Right-click the table, and select "Import/Export Data".
1.  In the Export dialog, choose the CSV format and specify the output file path
    on your local system.
1.  Click OK to export the data.
1.  Transfer the files to the Google Cloud Storage bucket.
1.  Import data from the flat files. For more information on importing CSV files
    to Cloud SQL for PostgreSQL, see
    [Import data from a CSV file to Cloud SQL for PostgreSQL](https://cloud.google.com/sql/docs/postgres/import-export/import-export-csv#import_data_from_a_csv_file_to).
1.  Connect your applications to the target Cloud SQL Instance and start writing
    to your new database instance.

You can export data to files using the azure_storage extension by performing the
steps defined in the
[Export data from Azure Database for PostgreSQL flexible server to Azure Blob Storage](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-storage-extension#export-data-from-azure-database-for-postgresql-flexible-server-to-azure-blob-storage)
document.

If your tables are large or you need to automate the process, we recommend using
Azure Data Factory. For guidance on how to export data from an Azure Database
for PostgreSQL instance with Azure Data Factory, see
[Copy and transform data in Azure Database for PostgreSQL](https://learn.microsoft.com/en-us/azure/data-factory/connector-azure-database-for-postgresql?tabs=data-factory).

#### Database Migration Service for continuous replication migration to Cloud SQL execution

Define and configure migration jobs in Database Migration Service to migrate
data from a source instance to the destination database. Migration jobs connect
to the source database instance through user-defined connection profiles. Choose
a time when your workloads can afford a short downtime for the migration and
production cut-over.

Choose PostgreSQL for source and Cloud SQL for PostgreSQL for destination. At
the moment of writing this document, Database Migration Service does not yet
support migrating directly from Azure Database for PostgreSQL to AlloyDB for
PostgreSQL. However, you can migrate to a CloudSQL for PostgreSQL instance
first, and then you
[migrate to AlloyDB through Database Migration Service](https://cloud.google.com/database-migration/docs/postgresql-to-alloydb/quickstart).
Database Migration Service performs both migrations through continuous
replication and you can fallback to the migration source at any time.

Test all the prerequisites to ensure the job can run successfully. You might get
a warning telling you that unsupported extensions will not be migrated, such as
azure and pgaadauth.

In Database Migration Service, the migration begins with the initial full dump,
followed by a continuous flow of changes from the source to the destination
database instance, called CDC.

Database Migration Service uses the pglogical extension for replication from
your source to the target database instance. At the beginning of migration, this
extension sets up replication by requiring exclusive short-term locks on all the
tables in your source instance. For this reason, we recommend starting the
migration when the database is least busy, and avoiding statements on the source
during the dump and replication phase, as DDL statements are not replicated. If
you must perform DDL operations, use the 'pglogical' functions to run DDL
statements on your source instance or manually run the same DDL statements on
the migration target instance, but only after the initial dump stage finishes.

The migration process with Database Migration Service ends with the promotion
operation. Promoting a database instance disconnects the destination database
from the flow of changes coming from the source database, and then the now
standalone destination instance is promoted to a primary instance. This approach
is also called a production switch.

For more information about migration jobs in Database Migration Service, see the
[Manage migration jobs](https://cloud.google.com/database-migration/docs/postgres/migration-job-actions)
section.

For a detailed migration setup process, see
[Migrate a database to Cloud SQL for PostgreSQL by using Database Migration Service](https://cloud.google.com/database-migration/docs/postgres/quickstart),
[Known limitations for Cloud SQL](https://cloud.google.com/database-migration/docs/postgres/known-limitations)
and
[Known limitations for AlloyDB](https://cloud.google.com/database-migration/docs/postgresql-to-alloydb/known-limitations).

#### Database replication execution

Cloud SQL supports two types of logical replication: the built-in logical
replication of PostgreSQL and logical replication through the pglogical
extension. For AlloyDB for PostgreSQL we recommend using the pglogical extension
for replication. Each type of logical replication has its own features and
limitations.

To perform a database migration using PostgreSQL built-in replication, you can
replicate directly to your target Cloud SQL for PostgreSQL or you can set up a
source representation instance which references the external server. The end
target Cloud SQL instance starts as a replica of this representation instance,
is updated with the latest changes and it then gets promoted to a stand-alone
primary instance.

Prepare your source Azure PostgreSQL Database instance for logical replication:

To prepare your Azure PostgreSQL Database instance for logical replication,
follow the steps from the Azure official documentation
[Prerequisites for logical replication and logical decoding](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-logical#prerequisites-for-logical-replication-and-logical-decoding).

To perform a database migration using PostgreSQL built-in replication through a
source representation instance:

1.  On Google Cloud,
    [Set up a source representation instance](https://cloud.google.com/sql/docs/postgres/replication/configure-replication-from-external#setup-source-instance).
    The source representation instance references the external server and
    contains only the request data from the external server:
1.  Using Google Cloud Shell, create a source.json file providing information
    about your source Azure Database for PostgreSQLinstance. For more
    information, see
    [Create the request data](https://cloud.google.com/sql/docs/postgres/replication/configure-replication-from-external#create-source-request).
1.  Execute a **curl** command to create the source representation instance in
    Cloud SQL, providing the path to the json file that you created in the
    previous step.

1.  Set up a Cloud SQL replica:
1.  Using Google Cloud Shell, create a replica.json file providing information
    about your source Cloud SQL for PostgreSQL instance that acts as a replica
    for the source database instance. For more information, see
    [Create the request data](https://cloud.google.com/sql/docs/postgres/replication/configure-replication-from-external#create-replica-request).
1.  Execute a **curl** command to create the Cloud SQL replica, providing the
    path to the json file that you created in the previous step.

1.  Write down the Cloud SQL replica's outgoing IP address. See
    [Get the Cloud SQL replica's outgoing IP address](https://cloud.google.com/sql/docs/postgres/replication/configure-replication-from-external#outgoing-ip).
1.  Ensure that you have network connectivity between your source Azure Database
    for PostgreSQL and target Cloud SQL for PostgreSQL replica instance:
1.  Ensure the necessary ports (PostgreSQL default is 5432\) are open on your
    VPC and Azure Virtual Network.
1.  Configure the source Azure Database instance to Allow incoming connections
    from the replica’s outgoing IP address from the previous step. Ensure that
    firewall rules allow the replica server IP address.
1.  Configure your source Azure Database instance:
1.  Install the pglogical extension
1.  Create a new replication role and set up permissions.

For more information about configuring your Azure Database instance as a
replication source, see
[Configure your source databases](https://cloud.google.com/sql/docs/postgres/replication/configure-replication-from-external#configure-your-source-databases-postgres)
and
[Logical replication and logical decoding in Azure Database for PostgreSQL](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-logical).

1.  Seed the Cloud SQL replica. Follow the guidance from
    [Seed the Cloud SQL replica](https://cloud.google.com/sql/docs/postgres/replication/configure-replication-from-external#seed_the_replica).
1.  Connect to the Cloud SQL for PostgreSQL replica and start the replication by
    following the guidance from
    [Logical replication and logical decoding in Azure Database for PostgreSQL](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-logical#pglogical-extension).
1.  Monitor the replication. Use the guidance from
    [Configure Cloud SQL and the external server for replication: Monitor Replication](https://cloud.google.com/sql/docs/postgres/replication/configure-replication-from-external#monitor_replication).
1.  Once the cut-over decision is made, stop writing on your source database
    instance, wait for all the changes to be replicated to the replica Cloud SQL
    Instances. This step is called the draining phase.
1.  Perform the switchover by
    [promoting the Cloud SQL for PostgreSQL replica](https://cloud.google.com/sql/docs/postgres/replication/configure-replication-from-external#promote_the_replica).
1.  Connect your applications to the target Cloud SQL Instance.

To replicate directly to your target Cloud SQL for PostgreSQL, you first need to
decide on the type of logical replication you want to use: built-in logical
replication or the pglogical replication.

For more information about logical replication and pglogical limitations, see:

- [Logical replication restrictions](https://www.postgresql.org/docs/current/logical-replication-restrictions.html)
- [pglogical Limitations and restrictions](https://github.com/2ndQuadrant/pglogical#limitations-and-restrictions)

To perform a database migration using PostgreSQL **built-in logical
replication** follow these steps:

1.  Create a publication on the Azure PostgreSQL instance that sends changes to
    the target instance:

```sql
CREATE PUBLICATION pub FOR ALL TABLES;
```

A publication is a group of tables whose data changes are intended to be
replicated through logical replication. You can create a publication for a set
of tables or for all the tables in your database. For more details about
publications in PostgreSQL, see
[CREATE PUBLICATION](https://www.postgresql.org/docs/current/sql-createpublication.html).

1.  On the target Cloud SQL for Postgres instance, check that the value of the
    wal_level is set to logical. Set max_replication_slots and max_wal_senders
    and. Consider that Cloud SQL requires one slot for each database that's
    migrated.
1.  On the target Cloud SQL for Postgres instance, check that the value of the
    wal_level is set to logical. Set max_replication_slots and max_wal_senders
    and. Consider that Cloud SQL requires one slot for each database that's
    migrated.
1.  Create the tables that you want to replicate on the target Cloud SQL
    instance.
1.  Create a subscription on the Cloud SQL for PostgreSQL instance that receives
    changes:

    ```sql
    CREATE SUBSCRIPTION sub CONNECTION
    'host=`source_server_name`.postgres.database.azure.com port=5432
    dbname=`source_database` user=`replication_user` password=`password`'
    PUBLICATION pub;
    ```

Replace `source_server_name`, `source_database`, `replication_user` and
`password` with appropriate connection details to the source Azure PostgreSQL
server. Make sure that the user you are using for the connection has the
appropriate replication privileges.

For more details about publications in PostgreSQL, see
[CREATE SUBSCRIPTION](https://www.postgresql.org/docs/current/sql-createsubscription.html).

1.  Monitor the replication. Query the
    [pg_stat_subscription](https://www.postgresql.org/docs/current/monitoring-stats.html#MONITORING-PG-STAT-SUBSCRIPTION)
    and
    [pg_replication_slots](https://www.postgresql.org/docs/current/view-pg-replication-slots.html)
    system views to observe real-time statistics about logical replication
    subscriptions such as active subscriptions, the status of your replication
    slots and the general overview of replication performance.
1.  Stop writing to your source database. Allow changes to be drained until
    there are no more publications to be transferred to the target database
    server.
1.  Stop replication. On the subscriber, run the following command to drop the
    subscription:

    ```sql
    DROP SUBSCRIPTION sub;
    ```

1.  Connect your applications to the target Cloud SQL Instance and start writing
    to your new database instance.

To perform a database migration to **CloudSQL** using the **pglogical extension
for logical replication** follow these steps:

1.  In the Azure Portal, navigate to your Azure Database for PostgreSQL, open
    the Server parameters page under the Settings section.
1.  Search the shared_preload_libraries and azure.extensions parameters and
    select the **pglogical** extension.
1.  Restart the instance to apply the settings.
1.  In the Cloud SQL for PostgreSQL target instance, set
    cloudsql.logical_decoding=on and cloudsql.enable_pglogical=on.
1.  Restart the instance to apply the settings.
1.  For setting up replication between your source and target databases through
    pglogical, follow the guidance from the
    [Set up logical replication and decoding: Set up logical replication with pglogical](https://cloud.google.com/sql/docs/postgres/replication/configure-logical-replication#set-up-logical-replication-with-pglogical).
1.  Monitor the replication status and performance. You can verify the
    subscription status by running the **pglogical.show_subscription_status**.
    Once your replication is up and running, decide when to stop writing to your
    source database. This involves a short moment of downtime.
1.  Stop writing to your source database. Allow changes on the source to be
    drained.
1.  Connect your applications to the target Cloud SQL Instance and start writing
    to your new database instance.
1.  Stop replication. On the subscriber, run the following command to stop the
    pglogical subscription:

    ```sql
    SELECT pg_drop_subscription('pglogical_sub');
    ```

To perform a database migration to **AlloyDB** using the **pglogical extension
for logical replication** follow the same steps as described above for the
migration to CloudSQL. Make sure the value of the
[enable_pglogical](https://cloud.google.com/alloydb/docs/reference/alloydb-flags#alloydb.enable_pglogical)
is set to on.

For more details about logical replication from Azure Database for PostgreSQL to
Cloud SQL for PostgreSQL, see:

- [Set up logical replication and decoding](https://cloud.google.com/sql/docs/postgres/replication/configure-logical-replication)
- [Logical replication and logical decoding in Azure Database for PostgreSQL \- Flexible Server](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-logical)
- [Configure Cloud SQL and the external server for replication](https://cloud.google.com/sql/docs/postgres/replication/configure-replication-from-external)

#### Third-party tools for continuous migration execution

Define execution tasks for the third-party tool you've chosen.

### Define fallback scenarios

In case you are using database replication, you can set up reverse replication
after you perform the cut-over to transfer new data that is written on your new
primary Cloud SQL for PostgreSQL or AlloyDB instance back to your Azure Database
for PostgreSQL instance. In this way, you can keep your Azure Database for
PostgreSQL up to date while you perform writes on the Cloud SQL instance.

### Perform testing and validation

#### Data Validation Tool

For performing data validation, we recommend the
[Data Validation Tool](https://github.com/GoogleCloudPlatform/professional-services-data-validator).
Data Validation Tool is an open sourced Python CLI tool, backed by Google, that
provides an automated and repeatable solution for validation across different
environments.

DVT can help streamline the data validation process by offering customized,
multi-level validation functions to compare source and target databases on the
table, column, and row level. You can also add validation rules.

DVT covers many Google Cloud data sources, including AlloyDB, BigQuery,
PostgreSQL, PostgreSQL, SQL Server, Cloud Spanner, JSON, and CSV files on Cloud
Storage. It can also be integrated with Cloud Functions and Cloud Run for event
based triggering and orchestration.

DVT supports the following types of validations:

- Schema level comparisons
- Column (including count, sum, avg, min, max, group by, and string length
  aggregations)
- Row (including hash and exact match in field comparisons)
- Custom query results comparison

For more information about the Data Validation Tool, see the
[Data Validation Tool repository](https://github.com/GoogleCloudPlatform/professional-services-data-validator).

### Perform the migration

The migration tasks include the activities to support the transfer from one
system to another. Migrations that follow a detailed step-by-step runbook
authored during development and testing phases are successful migrations.

Consider the following best practices for your data migration:

- Inform the involved teams whenever a plan step begins and finishes.
- If any of the steps take longer than expected, compare the time elapsed with
  the maximum amount of time allotted for that step. Issue regular intermediary
  updates to involved teams when this happens.
- If the time span is greater than the maximal amount of time reserved for each
  step in the plan, consider rolling back.
- Make “go or no-go” decisions for every step of the migration and cut-over
  plan.
- Consider rollback actions or alternative scenarios for each of the steps.

Perform the migration by following your
[defined execution tasks](#define-the-execution-tasks), and refer to the
documentation for your selected migration tool.

### Validate the migration before cut-over

This step represents the final testing and validation before the production
cut-over and it is usually performed in the production environment. In this
step, you might perform tasks such as:

**Database related final testing**: You execute data consistency checks and
schema verifications. You might use the same tools or automated tests from the
testing and validation step. You can also perform data sampling or random spot
checks to verify the consistency of complex data sets and business-critical
information. **Application functionality testing**: You perform isolated smoke
tests on critical applications to validate that they interact with the migrated
application. You can also simulate real-world scenarios by testing end-to-end
application workflows to ensure that all features behave as expected. **Security
and Access Control Validation**: You perform tests to confirm that user roles
and permissions have been correctly migrated to maintain appropriate access
controls. You validate that the correct group of users can access the target
databases and that various applications can connect to the database.
**Performance Benchmarking**: You measure query performance in the target
database and compare it against the baseline performance of the source database.
In this step, you can also execute custom load tests to verify that the target
database can handle peak traffic without issues.
[Standardized benchmark suites](https://benchant.com/blog/benchmarking-suites)
give you an objective perspective of your source and target database’s
performance. However, the expected success factors are subjective to your
migration.

If the database migration validation tests fail your set migration criteria,
consider the defined fallback scenarios. When considering a fallback scenario,
measure the impact of falling back against the effort of solving the discovered
migration issues such as prolonging the write downtime to investigate data
inconsistencies or trying different configurations of your target instance.

### Perform the production cut-over

The high-level production cut-over process can differ depending on your chosen
migration strategy. If you can have downtime on your workloads, then your
migration cut-over begins by stopping writes to your source database.

For continuous replication migrations, at a high level, production cut-over
includes the following:

- Stop writing to the source database.
- Drain the source.
- Stop the replication process.
- Deploy the applications that point to the new target database.

After the data has been migrated by using the chosen migration tool, you
validate the data in the target database. You confirm that the source database
and the target databases are in sync and the data in the target instance adheres
to your chosen migration success standards.

Once the data validation passes your criteria, you deploy the workloads that
have been refactored to use the new target instance. This is your application
level cut-over. You deploy the versions of your applications that point to the
new target database instance. The deployments can be performed through various
deployment strategies such as rolling updates,
[canary deployment](https://cloud.google.com/deploy/docs/deployment-strategies/canary),
or by using a blue-green deployment pattern. Some application downtime might be
incurred. For more information about deploying and testing your workloads, see
[Deploy to Compute Engine](https://cloud.google.com/build/docs/deploying-builds/deploy-compute-engine)
and
[Deploying to GKE](https://cloud.google.com/build/docs/deploying-builds/deploy-gke).

Follow the best practices for your production cut-over:

- Monitor your applications that work with the target database after the
  cut-over.
- Define a time period of monitoring to consider whether or not you need to
  implement your fallback plan.
- Note that your Cloud SQL instance might need a restart if you change some
  database flags.
- Consider that the effort of rolling back the migration might be greater than
  fixing issues that appear on the target environment.

### Cleanup the source environment and configure the Cloud SQL and AlloyDB instance

After the cut-over is completed, you can delete the source databases. We
recommend performing the following important actions before the cleanup of your
source instance:

- Create a final backup of each source database. This provides you with an end
  state of the source databases, and it also might be required by data
  regulations.

- Collect the database parameter settings of your source instance.
  Alternatively, check that they match the ones you’ve gathered in the inventory
  building phase. Adjust the target instance parameters to match the ones from
  the source instance.

- Collect database statistics from the source instance and compare them to the
  ones in the target instance. If the statistics are not similar, it’s hard to
  compare the performance of the source instance and target instance.

In a fallback scenario, you might want to implement the replication of your
writes on the Cloud SQL instance back to your original source database. The
setup resembles the migration process but would run in reverse: the initial
source database would become the new target.

As a best practice to keep the source instances up to date after the cut-over,
replicate the writes performed on the target Cloud SQL instances back to the
source database. If you need to roll back, you can fall back to your old source
instances with minimal data loss.

Alternatively, you can use another instance and replicate your changes to that
instance. For example, when AlloyDB for PostgreSQL is a migration destination,
consider setting up replication to a Cloud SQL for PostgreSQL instance for
fallback scenarios.

In addition to the source environment cleanup, the following critical
configurations for your Cloud SQL for PostgreSQL instances must be done:

- Configure a maintenance window for your primary instance to control when
  disruptive updates can occur.
- Configure the storage on the instance so that you have at least 20% available
  space to accommodate any critical database maintenance operations that Cloud
  SQL may perform. To receive an alert if available disk space gets lower than
  20%, create a metrics-based alerting policy for the disk utilization metric.

Don't start an administrative operation before the previous operation has
completed.

For more information about maintenance and best practices on Cloud SQL for
PostgreSQL and AlloyDB for PostgreSQL instances, see the following resources:

- [About maintenance on Cloud SQL for PostgreSQL instances](https://cloud.google.com/sql/docs/postgres/maintenance#management)
- [About instance settings on Cloud SQL for PostgreSQL instances](https://cloud.google.com/sql/docs/postgres/instance-settings)
- [About maintenance on AlloyDB for PostgreSQL](https://cloud.google.com/alloydb/docs/maintenance)
- [Configure an AlloyDB for PostgreSQL instance's database flags](https://cloud.google.com/alloydb/docs/instance-configure-database-flags)

## Optimize your environment after migration

Optimization is the last phase of your migration. In this phase, you iterate on
optimization tasks until your target environment meets your optimization
requirements. The steps of each iteration are as follows:

1.  Assess your current environment, teams, and optimization loop.
1.  Establish your optimization requirements and goals.
1.  Optimize your environment and your teams.
1.  Tune the optimization loop.

You repeat this sequence until you've achieved your optimization goals.

For more information about optimizing your Google Cloud environment, see
[Migrate to Google Cloud: Optimize your environment](https://cloud.google.com/architecture/migration-to-google-cloud-optimizing-your-environment)
and
[Google Cloud Well-Architected Framework: Performance optimization](https://cloud.google.com/architecture/framework/performance-optimization).

### Establish your optimization requirements

Review the following optimization requirements for your Google Cloud environment
and choose the ones that best fit your workloads.

#### Increase reliability and availability of your database

With Cloud SQL, you can implement a high availability and disaster recovery
strategy that aligns with your recovery time objective (RTO) and recovery point
objective (RPO). To increase reliability and availability, consider the
following:

- In cases of read-heavy workloads, add read replicas to offload traffic from
  the primary instance.
- For mission critical workloads, use the high-availability configuration,
  replicas for regional failover, and a robust disaster recovery configuration.
- For less critical workloads, a mix of automated and on-demand backups can be
  sufficient.
- To prevent accidental removal of instances, use instance deletion protection.
- When migrating to Cloud SQL for PostgreSQL, consider using Cloud SQL
  Enterprise Plus edition to benefit from increased availability, log retention,
  and near-zero downtime planned maintenance. For more information about Cloud
  SQL Enterprise Plus, see
  [Introduction to Cloud SQL editions](https://cloud.google.com/sql/docs/editions-intro#edition-features)
  and
  [Near-zero downtime planned maintenance](https://cloud.google.com/sql/docs/postgres/maintenance#nearzero).

For more information on increasing the reliability and availability of your
Cloud SQL for PostgreSQL database, see the following documents:

- [Promote replicas for regional migration or disaster recovery](https://cloud.google.com/sql/docs/postgres/replication/cross-region-replicas)
    - [Cloud SQL database disaster recovery](https://cloud.google.com/sql/docs/postgres/intro-to-cloud-sql-disaster-recovery)
    - [About Cloud SQL backups](https://cloud.google.com/sql/docs/postgres/backup-recovery/backups)
    - [Prevent deletion of an instance documentation](https://cloud.google.com/sql/docs/postgres/deletion-protection)

When migrating to
[AlloyDB for PostgreSQL](https://cloud.google.com/alloydb/docs/maintenance),
consider the following:

- Configure backup plans.
- Create read pools and consider scaling instances.
- Create secondary clusters for cross-region replication.
- Consider using the AlloyDB for PostgreSQL Auth Proxy.
- Consider using AlloyDB language connectors.

For more information on increasing the reliability and availability of your
[AlloyDB for PostgreSQL](https://cloud.google.com/alloydb/docs/maintenance)
database, see the following documents:

- [AlloyDB for PostgreSQL under the hood: Business continuity](https://cloud.google.com/alloydb/docs/maintenance)
    - [About the AlloyDB for PostgreSQL Auth proxy](https://cloud.google.com/alloydb/docs/auth-proxy/overview)
    - [Work with cross-region replication](https://cloud.google.com/alloydb/docs/cross-region-replication/work-with-cross-region-replication)
    - [Create a read pool instance in an AlloyDB cluster](https://cloud.google.com/alloydb/docs/instance-read-pool-create)
    - [Scale an instance](https://cloud.google.com/alloydb/docs/instance-read-pool-scale)
    - [AlloyDB Language Connectors overview](https://cloud.google.com/alloydb/docs/language-connectors-overview)

#### Increase the cost effectiveness of your database infrastructure

To have a positive economic impact, your workloads must use the available
resources and services efficiently. Consider the following options:

- Provide the database with the minimum required storage capacity by doing the
  following:
    - To scale storage capacity automatically as your data grows,
      [enable automatic storage increases](https://cloud.google.com/sql/docs/postgres/instance-settings#automatic-storage-increase-2ndgen).
      However, ensure that you configure your instances to have some buffer in
      peak workloads. Remember that database workloads tend to increase over
      time.
- Identify possible underutilized resources:
    - Rightsizing your Cloud SQL instances can reduce the infrastructure cost
      without adding additional risks to the capacity management strategy.
    - Cloud Monitoring provides predefined dashboards that help identify the
      health and capacity utilization of many Google Cloud components, including
      Cloud SQL. For details, see
      [Create and manage custom dashboards](https://cloud.google.com/monitoring/charts/dashboards#listing_all_dashboards).
- Identify instances that don't require high availability or disaster recovery
  configurations, and remove them from your infrastructure.
- Remove tables and objects that are no longer needed. You can store them in a
  full backup or an archival Cloud Storage bucket.
- Evaluate the most cost-effective storage type (SSD or HDD) for your use case.
    - For most use cases, SSD is the most efficient and cost-effective choice.
    - If your datasets are large (10 TB or more), latency-insensitive, or
      infrequently accessed, HDD might be more appropriate.
    - For details, see
      [Choose between SSD and HDD storage](https://cloud.google.com/sql/docs/postgres/choosing-ssd-hdd).
- Purchase [committed use discounts](https://cloud.google.com/sql/cud#pricing)
  for workloads with predictable resource needs.
- Use [Active Assist](https://cloud.google.com/solutions/active-assist) to get
  cost insights and recommendations. For more information and options, see
  [loud SQL cost optimization recommendations with Active Assist](https://cloud.google.com/blog/products/databases/reduce-cloud-sql-costs-with-optimizations-by-active-assist).
- When migrating to Cloud SQL for PostgreSQL, you can reduce overprovisioned
  instances and identify idle Cloud SQL for PostgreSQL instances. For more
  information on increasing the cost effectiveness of your Cloud SQL for
  PostgreSQL database instance, see the following documents:
    - [Enable automatic storage increases for Cloud SQL](https://cloud.google.com/sql/docs/postgres/instance-settings#automatic-storage-increase-2ndgen)
    - [Identify idle Cloud SQL instances](https://cloud.google.com/sql/docs/postgres/recommender-sql-idle)
    - [Reduce overprovisioned Cloud SQL instances](https://cloud.google.com/sql/docs/postgres/recommender-sql-overprovisioned)
    - [Optimize queries with high memory usage](https://cloud.google.com/sql/docs/postgres/recommender-optimize-high-memory-queries)
    - [Create and manage custom dashboards](https://cloud.google.com/monitoring/charts/dashboards#listing_all_dashboards)
    - [Choose between SSD and HDD storage](https://cloud.google.com/sql/docs/postgres/choosing-ssd-hdd)
    - [Committed use discounts](https://cloud.google.com/sql/cud#pricing)
    - [Active Assist](https://cloud.google.com/solutions/active-assist)
- When using
  [AlloyDB for PostgreSQL](https://cloud.google.com/alloydb/docs/maintenance),
  you can do the following to increase cost effectiveness:
    - Use the columnar engine to efficiently perform certain analytical queries
      such as aggregation functions or table scans.
    - Use cluster storage quota
      [recommender](https://cloud.google.com/recommender/docs/whatis-activeassist)
      for AlloyDB for PostgreSQL to detect clusters which are at risk of hitting
      the storage quota.
- For more information on increasing the cost effectiveness of your
  [AlloyDB for PostgreSQL](https://cloud.google.com/alloydb/docs/maintenance)
  database infrastructure, see the following documentation sections:
    - [About the AlloyDB for PostgreSQL columnar engine](https://cloud.google.com/alloydb/docs/columnar-engine/about)
    - [Optimize underprovisioned AlloyDB for PostgreSQL clusters](https://cloud.google.com/alloydb/docs/recommender-optimize-underprovisioned-cluster)
    - [Increase cluster storage quota for AlloyDB for PostgreSQL](https://cloud.google.com/alloydb/docs/recommender-increase-cluster-storage-quota)
    - [Monitor active queries](https://cloud.google.com/alloydb/docs/monitor-active-queries)

#### Increase the performance of your database infrastructure

Minor database-related performance issues frequently have the potential to
impact the entire operation. To maintain and increase your Cloud SQL instance
performance, consider the following guidelines:

- If you have a large number of database tables, they can affect instance
  performance and availability, and cause the instance to lose its SLA coverage.
- Ensure that your instance isn't constrained on memory or CPU.
    - For performance-intensive workloads, ensure that your instance has at
      least 60 GB of memory.
    - For slow database inserts, updates, or deletes, check the locations of the
      writer and database; sending data over long distances introduces latency.
- Improve query performance by using the predefined Query Insights dashboard in
  Cloud Monitoring (or similar database engine built-in features). Identify the
  most expensive commands and try to optimize them.
- Prevent database files from becoming unnecessarily large. Set
  [autogrow](https://docs.microsoft.com/en-us/troubleshoot/sql/admin/considerations-autogrow-autoshrink)
  in MBs rather than as a percentage, using increments appropriate to the
  requirement.

##### When migrating to Cloud SQL for PostgreSQL, consider the following guidelines

- Use caching to improve read performance. Inspect the various statistics from
  the
  [pg_stat_database](https://www.postgresql.org/docs/current/monitoring-stats.html#MONITORING-PG-STAT-DATABASE-VIEW)
  view. For example, the blks_hit / (blks_hit \+ blks_read) ratio should be
  greater than 99%. If this ratio isn't greater than 99%, consider increasing
  the size of your instance's RAM. For more information, see
  [PostgreSQL statistics collector](https://www.postgresql.org/docs/current/static/monitoring-stats.html).
- Reclaim space and prevent poor index performance. Depending on how often your
  data is changing, either set a schedule to run the VACUUM command on your
  Cloud SQL for PostgreSQL.
- Use Cloud SQL Enterprise Plus edition for increased machine configuration
  limits and data cache. For more information about Cloud SQL Enterprise Plus,
  see
  [Introduction to](https://cloud.google.com/sql/docs/editions-intro#edition-features)
  Cloud SQL
  [editions](https://cloud.google.com/sql/docs/editions-intro#edition-features).
- Switch to
  [AlloyDB for PostgreSQL](https://cloud.google.com/alloydb/docs/maintenance).
  If you switch, you can have full PostgreSQL compatibility, better
  transactional processing, and fast transactional analytics workloads supported
  on your processing database. You also get a recommendation for new indexes
  through the use of the index advisor feature.

For more information about increasing the performance of your Cloud SQL for
PostgreSQL database infrastructure, see Cloud SQL performance improvement
documentation for
[PostgreSQL](https://cloud.google.com/sql/docs/postgres/diagnose-issues#performance).

##### When migrating to AlloyDB for PostgreSQL, consider the following guidelines to increase the performance of your AlloyDB for PostgreSQL database instance

- Use the
  [AlloyDB for PostgreSQL columnar engine](https://cloud.google.com/alloydb/docs/columnar-engine/about)
  to accelerate your analytical queries.
- Use the
  [index advisor](https://cloud.google.com/alloydb/docs/use-index-advisor) in
  [AlloyDB for PostgreSQL](https://cloud.google.com/alloydb/docs/maintenance).
  The index advisor tracks the queries that are regularly run against your
  database and it analyzes them periodically to recommend new indexes that can
  increase their performance.
- [Improve query performance by using Query Insights in AlloyDB for PostgreSQL](https://cloud.google.com/alloydb/docs/using-query-insights).

#### Increase database observability capabilities

Diagnosing and troubleshooting issues in applications that connect to database
instances can be challenging and time-consuming. For this reason, a centralized
place where all team members can see what's happening at the database and
instance level is essential. You can monitor Cloud SQL instances in the
following ways:

- Cloud SQL uses built-in memory custom agents to collect query telemetry.
    - Use
      [Cloud Monitoring](https://cloud.google.com/monitoring/docs/monitoring-overview)
      to collect measurements of your service and the Google Cloud resources
      that you use. [Cloud Monitoring](https://cloud.google.com/monitoring)
      includes predefined dashboards for several Google Cloud products,
      including a Cloud SQL monitoring dashboard.
    - You can create custom dashboards that help you monitor metrics and set up
      alert policies so that you can receive timely notifications.
    - Alternatively, you can consider using third-party monitoring solutions
      that are integrated with Google Cloud, such as Datadog and Splunk.
- [Cloud Logging](https://cloud.google.com/logging/docs/overview) collects
  logging data from common application components.
- [Cloud Trace](https://cloud.google.com/trace/docs/overview) collects latency
  data and executed query plans from applications to help you track how requests
  propagate through your application.
- [Database Center](https://cloud.google.com/database-center/docs/overview)
  provides an AI-assisted, centralized database fleet overview. You can monitor
  the health of your databases, availability configuration, data protection,
  security, and industry compliance.

For more information about increasing the observability of your database
infrastructure, see the following documentation sections:

- [Monitor Cloud SQL for PostgreSQL instances](https://cloud.google.com/sql/docs/postgres/monitor-instance)
- [Monitor instances with AlloyDB for PostgreSQL](https://cloud.google.com/alloydb/docs/monitor-instance)

### General Cloud SQL best practices and operational guidelines

Apply the best practices for Cloud SQL to configure and tune the database.

Some important Cloud SQL general recommendations are as follows:

- If you have large instances, we recommend that you split them into smaller
  instances, when possible.
- Configure storage to accommodate critical database maintenance. Ensure you
  have at least 20% available space to accommodate any critical database
  maintenance operations that Cloud SQL might perform.
- Having too many database tables can affect database upgrade time. Ideally, aim
  to have under 10,000 tables per instance.
- Choose the appropriate size for your instances to account for transaction
  (binary) log retention, especially for high write activity instances.

To be able to efficiently handle any database performance issues that you might
encounter, use the following guidelines until your issue is resolved:

**Scale up infrastructure**: Increase resources (such as disk throughput, vCPU,
and RAM). Depending on the urgency and your team's availability and experience,
vertically scaling your instance can resolve most performance issues. Later, you
can further investigate the root cause of the issue in a test environment and
consider options to eliminate it.

**Perform and schedule database maintenance operations**: Index defragmentation,
statistics updates, vacuum analyze, and reindex heavily updated tables. Check if
and when these maintenance operations were last performed, especially on the
affected objects (tables, indexes). Find out if there was a change from normal
database activities. For example, recently adding a new column or having lots of
updates on a table.

**Perform database tuning and optimization**: Are the tables in your database
properly structured? Do the columns have the correct data types? Is your data
model right for the type of workload? Investigate your
[slow queries](https://dev.mysql.com/doc/refman/8.0/en/slow-query-log.html) and
their execution plans. Are they using the available indexes? Check for index
scans, locks, and waits on other resources. Consider adding indexes to support
your critical queries. Eliminate non-critical indexes and foreign keys. Consider
rewriting complex queries and joins. The time it takes to resolve your issue
depends on the experience and availability of your team and can range from hours
to days.

**Scale out your reads**: Consider having read replicas. When scaling vertically
isn't sufficient for your needs, and database tuning and optimization measures
aren't helping, consider scaling horizontally. Routing read queries from your
applications to a read replica improves the overall performance of your database
workload. However, it might require additional effort to change your
applications to connect to the read replica.

**Database re-architecture**: Consider partitioning and indexing the database.
This operation requires significantly more effort than database tuning and
optimization, and it might involve a data migration, but it can be a long-term
fix. Sometimes, poor data model design can lead to performance issues, which can
be partially compensated by vertical scale-up. However, a proper data model is a
long-term fix. Consider partitioning your tables. Archive data that isn't needed
anymore, if possible. Normalize your database structure, but remember that
denormalizing can also improve performance.

**Database sharding**: You can scale out your writes by sharding your database.
Sharding is a complicated operation and involves re-architecting your database
and applications in a specific way and performing data migration. You split your
database instance in multiple smaller instances by using a specific partitioning
criteria. The criteria can be based on customer or subject. This option lets you
horizontally scale both your writes and reads. However, it increases the
complexity of your database and application workloads. It might also lead to
unbalanced shards called hotspots, which would outweigh the benefit of sharding.

For Cloud SQL for PostgreSQL and AlloyDB for PostgreSQL, consider the following
best practices:

- To offload traffic from the primary instance, add read replicas. You can also
  use a load balancer such as HAProxy to manage traffic to the replicas.
  However, avoid too many replicas as this hinders the VACUUM operation. For
  more information on using HAProxy, see the official
  [HAProxy](http://www.haproxy.org/) website.
- Optimize the VACUUM operation by increasing system memory and the
  maintenance_work_mem parameter. Increasing system memory means that more
  tuples can be batched in each iteration.
- Because larger indexes consume a significant amount of time for the index
  scan, set the INDEX_CLEANUP parameter to OFF to quickly clean up and freeze
  the table data.
- When using
  [AlloyDB for PostgreSQL](https://cloud.google.com/alloydb/docs/maintenance),
  use the AlloyDB for PostgreSQL System Insights dashboard and audit logs. The
  AlloyDB for PostgreSQL System Insights dashboard displays metrics of the
  resources that you use, and lets you monitor them. For more details, see the
  guidelines from the
  [Monitor instances](https://cloud.google.com/alloydb/docs/monitor-instance)
  topic in the
  [AlloyDB for PostgreSQL](https://cloud.google.com/alloydb/docs/maintenance)
  documentation.

For more details, see the following resources:

- [General best practices section](https://cloud.google.com/sql/docs/postgres/best-practices)
  and
  [Operational Guidelines](https://cloud.google.com/sql/docs/postgres/operational-guidelines)
  for Cloud SQL for PostgreSQL
- [About maintenance](https://cloud.google.com/alloydb/docs/maintenance) and
  [Overview](https://cloud.google.com/alloydb/docs/overview) for AlloyDB for
  PostgreSQL

## Update database production operations runbooks and support documentation to align with the Cloud SQL database platform

After migrating from Azure to Google Cloud, update production runbooks,
administration guides and support documentation to reflect Cloud SQL platform
specifics.

- **Connection Settings:** Document new connection strings, authentication, and
  network configurations.
- **Maintenance & Backups:** Include steps for automated backups, recovery, and
  maintenance windows in Cloud SQL.
- **Monitoring:** Update alert thresholds and monitoring to use Google Cloud’s
  Operations Suite.
- **Security:** Align policies with Cloud SQL's IAM roles and encryption
  options.
- **Incident Response:** Adapt troubleshooting and escalation protocols for
  Cloud SQL scenarios.
- **Integrations:** Document workflows for integrations with tools such as
  Dataflow or BigQuery.
- **Training:** Train teams on Cloud SQL features, tools, and APIs. Regular
  updates ensure efficiency, reliability, and team readiness post-migration.

## What’s next

- Learn when to
  [find help for your migrations](https://cloud.google.com/architecture/migration-to-gcp-getting-started#finding_help).
- Read about
  [migrating and modernizing Microsoft workloads on Google Cloud](https://cloud.google.com/windows).
- Learn how to
  [compare AWS and Azure services to Google Cloud](https://cloud.google.com/free/docs/aws-azure-gcp-service-comparison).
- Read about
  [other migration journeys to Google Cloud](https://cloud.google.com/architecture/migration-to-gcp-getting-started).

## Contributors

Author: [Alex Carciu](https://www.linkedin.com/in/alex-carciu) | Cloud Solutions
Architect

Other contributors:

- [Marco Ferrari](https://www.linkedin.com/in/ferrarimark) | Cloud Solutions
  Architect
- Ido Flatow | Cloud Solutions Architect
