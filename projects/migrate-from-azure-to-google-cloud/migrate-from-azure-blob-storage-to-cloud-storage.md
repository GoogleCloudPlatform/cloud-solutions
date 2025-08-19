# Migrate from Azure to Google Cloud: Migrate from Azure Blob Storage to Cloud Storage

Google Cloud provides tools, products, guidance, and professional services to
help you migrate data from
[Azure Blob Storage](https://azure.microsoft.com/products/storage/blobs) to
[Cloud Storage](https://cloud.google.com/storage). This document discusses how
to design, implement, and validate a plan to migrate from Azure Blob Storage to
Cloud Storage. The document describes a portion of the overall migration process
in which you create an inventory of Azure Blob Storage artifacts and create a
plan for how to handle the migration process.

The discussion in this document is intended for cloud administrators who want
details about how to plan and implement a migration process. It's also intended
for decision-makers who are evaluating the opportunity to migrate and who want
to explore what migration might look like.

For this migration to Google Cloud, we recommend that you follow the migration
framework described in
[Migrate to Google Cloud: Get started](https://cloud.google.com/architecture/migration-to-gcp-getting-started#the_migration_path).

The following diagram illustrates the path of your migration journey.

![Migration path with four phases.](https://cloud.google.com//architecture/images/migration-to-gcp-getting-started-migration-path.svg)

You might migrate from your source environment to Google Cloud in a series of
iterations—for example, you might migrate some workloads first and others later.
For each separate migration iteration, you follow the phases of the general
migration framework:

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

This document focuses on migrating from Azure Blob Storage to Cloud Storage. For
more information about migrating other kinds of resources, such as objects
storage, and databases from Azure to Google Cloud, see the
[Migrate from Azure to Google Cloud document series](./README.md).

## **Assess the source environment**

In the assessment phase, you determine the requirements and dependencies to
migrate your source environment to Google Cloud.

The assessment phase is crucial for the success of your migration. You need to
gain deep knowledge about the workloads you want to migrate, their requirements,
their dependencies, and about your current environment. You need to understand
your starting point to successfully plan and execute a Google Cloud migration.

The assessment phase consists of the following tasks:

1.  Build a comprehensive inventory of your workloads.
1.  Catalog your workloads according to their properties and dependencies.
1.  Train and educate your teams on Google Cloud.
1.  Build experiments and proofs of concept on Google Cloud.
1.  Calculate the total cost of ownership (TCO) of the target environment.
1.  Choose the migration strategy for your workloads.
1.  Choose your migration tools.
1.  Define the migration plan and timeline.
1.  Validate your migration plan.

For more information about the assessment phase and about these tasks, see
[Migrate to Google Cloud: Assess and discover your workloads](https://cloud.google.com/solutions/migration-to-gcp-assessing-and-discovering-your-workloads).
The following sections are based on information in that document.

### Build your inventories

To scope your migration, you create two inventories: an inventory of your Azure
Blob Storage accounts, and an inventory of the objects that are stored in the
accounts.

#### Build the inventory of your Azure Blob Storage accounts

To build the inventory of your Azure Blob Storage accounts, you can use Azure
tools, such as the Azure command-line interface, or the
[Azure Resource Inventory](https://github.com/microsoft/ARI).

After you build the inventory of your Azure Blob Storage accounts, refine the
inventory by considering the following data points about each Azure Blob Storage
account:

- How you've configured Azure Storage service-side encryption.
- Your settings for Azure Storage authorization (identity and access
  management).
- The configuration for Azure Storage account public endpoint.
- The configuration for Azure Blob Storage immutability policy.
- How you're accessing the Azure Blob Storage container.
- The settings for Azure Blob storage versioning.
- The configuration for Azure Backup policies for Azure Blobs (Azure Storage).
- How you've configured for Azure Blob Storage object replication.
- The Azure Blob Storage object lifecycle.

We also recommend that you gather data about your Azure Blob Storage accounts
that lets you compute aggregate statistics about the objects that each bucket
contains. For example, if you gather the total object size, average object size,
and object count, it can help you
[estimate the time and cost that's needed](https://cloud.google.com/architecture/migration-to-google-cloud-transferring-your-large-datasets#step_3_evaluating_your_transfer_options)
to migrate from an Azure Blob Storage account to a Cloud Storage bucket.

To gather these data points about your Azure Blob Storage account, you can
implement data-collection mechanisms and processes that rely on Azure tools,
such as the following:

- [Azure Storage blob inventory](https://learn.microsoft.com/azure/storage/blobs/blob-inventory)
- [Azure Storage Insights](https://learn.microsoft.com/azure/storage/common/storage-insights-overview)
- Azure APIs
- Azure developer tools
- The Azure command-line interface

To help you avoid issues during the migration, and to help estimate the effort
needed for the migration, we recommend that you evaluate how Azure Blob Storage
account features map to similar Cloud Storage bucket features. The following
table summarizes this mapping.

| Azure Blob Storage feature                                                                                                                                                                                              | Cloud Storage feature                                                                                                                                                                                                                                                                  |
| :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [Naming and Referencing Containers, Blobs, and Metadata](https://learn.microsoft.com/rest/api/storageservices/naming-and-referencing-containers--blobs--and-metadata)                                                   | [Bucket name requirements](https://cloud.google.com/storage/docs/buckets#naming)                                                                                                                                                                                                       |
| [Azure Storage redundancy](https://learn.microsoft.com/azure/storage/common/storage-redundancy)                                                                                                                         | [Bucket location](https://cloud.google.com/storage/docs/locations)                                                                                                                                                                                                                     |
| [Service-side encryption](https://learn.microsoft.com/azure/storage/common/storage-service-encryption)                                                                                                                  | [Encryption options](https://cloud.google.com/storage/docs/encryption)                                                                                                                                                                                                                 |
| [Authorize data operations](https://learn.microsoft.com/azure/storage/common/authorize-data-access) [Authorize management operations](https://learn.microsoft.com/azure/storage/common/authorization-resource-provider) | [Identity and Access Management (IAM)](https://cloud.google.com/storage/docs/access-control/iam) [Managed folders](https://cloud.google.com/storage/docs/managed-folders)                                                                                                              |
| [Private endpoints for Azure Storage](https://learn.microsoft.com/azure/storage/common/storage-private-endpoints)                                                                                                       | [Public data access](https://cloud.google.com/storage/docs/access-control/making-data-public) [Public access prevention](https://cloud.google.com/storage/docs/public-access-prevention)                                                                                               |
| [Data protection](https://learn.microsoft.com/azure/storage/blobs/data-protection-overview)                                                                                                                             | [Retention policies and retention policy lock](https://cloud.google.com/storage/docs/bucket-lock)                                                                                                                                                                                      |
| [Upload, download, and list blobs](https://learn.microsoft.com/azure/storage/blobs/storage-quickstart-blobs-portal)                                                                                                     | [Uploads and downloads](https://cloud.google.com/storage/docs/uploads-downloads) [Hierarchical Namespace](https://cloud.google.com/storage/docs/hns-overview)                                                                                                                          |
| [Blob versioning](https://learn.microsoft.com/azure/storage/blobs/versioning-overview)                                                                                                                                  | [Object versioning](https://cloud.google.com/storage/docs/object-versioning)                                                                                                                                                                                                           |
| [Azure Blob backup](https://learn.microsoft.com/azure/backup/blob-backup-configure-manage)                                                                                                                              | [Transfer jobs](https://cloud.google.com/storage-transfer/docs/create-transfers#microsoft-azure-blob-storage) [Object Lifecycle Management](https://cloud.google.com/storage/docs/lifecycle)                                                                                           |
| [Object replication](https://learn.microsoft.com/azure/storage/blobs/object-replication-overview)                                                                                                                       | [Dual-region replication](https://cloud.google.com/storage/docs/dual-regions) [Turbo replication](https://cloud.google.com/storage/docs/availability-durability#turbo-replication) [Event-driven transfer jobs](https://cloud.google.com/storage-transfer/docs/event-driven-transfers) |
| [Lifecycle management policies](https://learn.microsoft.com/azure/storage/blobs/lifecycle-management-overview)                                                                                                          | [Object Lifecycle Management](https://cloud.google.com/storage/docs/lifecycle)                                                                                                                                                                                                         |

As noted earlier, the features listed in the preceding table might look similar
when you compare them. However, differences in the design and implementation of
the features in the two cloud providers can have significant effects on your
migration from Azure Blob Storage to Cloud Storage.

#### Build the inventory of the objects stored in your Azure Blob Storage accounts

After you build the inventory of your Azure Blob Storage accounts, we recommend
that you build an inventory of the objects stored in these accounts by using the
[Azure Storage blob inventory](https://learn.microsoft.com/azure/storage/blobs/blob-inventory)
tool.

To build the inventory of your Azure Blob Storage objects, consider the
following for each object:

- Blob object name
- Blob object size
- Blob object metadata
- Blob object versions, and if you need to migrate these versions
- Blob object shared access signatures
- Blob object index tags
- Blob object storage classes
- Blob object archiving

We also recommend that you gather data about your Azure Blob Storage objects to
understand how often you and your workloads create, update, and delete Azure
Blob Storage objects.

To help you avoid issues during the migration, and to help estimate the effort
needed for the migration, we recommend that you evaluate how Azure Blob Storage
object features map to similar Cloud Storage object features. The following
table summarizes this mapping.

| Azure Blob Storage feature                                                                                                                                                                                                           | Cloud Storage feature                                                                                                                                                                                                                              |
| :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [Object naming rules](https://learn.microsoft.com/rest/api/storageservices/naming-and-referencing-containers--blobs--and-metadata#blob-names)                                                                                        | [Object name requirements](https://cloud.google.com/storage/docs/objects#naming)                                                                                                                                                                   |
| [Blob metadata](https://learn.microsoft.com/rest/api/storageservices/setting-and-retrieving-properties-and-metadata-for-blob-resources) [Blob index tags](https://learn.microsoft.com/azure/storage/blobs/storage-manage-find-blobs) | [Object metadata](https://cloud.google.com/storage/docs/metadata)                                                                                                                                                                                  |
| [Shared access signatures](https://learn.microsoft.com/azure/storage/common/storage-sas-overview)                                                                                                                                    | [Signed URLs](https://cloud.google.com/storage/docs/access-control/signed-urls)                                                                                                                                                                    |
| [Access tiers](https://learn.microsoft.com/azure/storage/blobs/access-tiers-overview) [Blob rehydration](https://learn.microsoft.com/azure/storage/blobs/archive-rehydrate-overview)                                                 | [Storage classes](https://cloud.google.com/storage/docs/storage-classes)                                                                                                                                                                           |
| [Data Lake Storage Gen2](https://learn.microsoft.com/azure/storage/blobs/data-lake-storage-introduction)                                                                                                                             | [Hierarchical namespace](https://cloud.google.com/storage/docs/hns-overview) [Managed folders](https://cloud.google.com/storage/docs/managed-folders) [Connect to Cloud Storage using gRPC](https://cloud.google.com/storage/docs/enable-grpc-api) |

As noted earlier, the features listed in the preceding table might look similar
when you compare them. However, differences in the design and implementation of
the features in the two cloud providers can have significant effects on your
migration from Azure Blob Storage to Cloud Storage. For example, you can use a
[stored access policy](https://learn.microsoft.com/en-us/azure/storage/common/storage-stored-access-policy-define-dotnet)
to change the permissions and expiration of shared access signatures (SAS) In
Azure Blob Storage. In Google Cloud, you cannot change a signed URL after it is
created.

### Assess your deployment and operational processes

It's important to have a clear understanding of how your deployment and
operational processes work. These processes are a fundamental part of the
practices that prepare and maintain your production environment and the
workloads that run there.

Your deployment and operational processes might build the artifacts that your
workloads need to function. Therefore, you should gather information about each
artifact type. For example, an artifact can be an operating system package, an
application deployment package, an operating system image, a container image, or
something else.

In addition to the artifact type, consider how you complete the following tasks:

- **Develop your workloads**. Assess the processes that development teams have
  in place to build your workloads. For example, how are your development teams
  designing, coding, and testing your workloads?
- **Generate the artifacts that you deploy in your source environment**. To
  deploy your workloads in your source environment, you might be generating
  deployable artifacts, such as container images or operating system images, or
  you might be customizing existing artifacts, such as third-party operating
  system images by installing and configuring software. Gathering information
  about how you're generating these artifacts helps you to ensure that the
  generated artifacts are suitable for deployment in Google Cloud.
- **Store the artifacts**. If you produce artifacts that you store in an
  artifact registry in your source environment, you need to make the artifacts
  available in your Google Cloud environment. You can do so by employing
  strategies like the following:

    - **Establish a communication channel between the environments**: Make the
      artifacts in your source environment reachable from the target Google
      Cloud environment.
    - **Refactor the artifact build process**: Complete a minor refactor of your
      source environment so that you can store artifacts in both the source
      environment and the target environment. This approach supports your
      migration by building infrastructure like an artifact repository before
      you have to implement artifact build processes in the target Google Cloud
      environment. You can implement this approach directly, or you can build on
      the previous approach of establishing a communication channel first.

    Having artifacts available in both the source and target environments lets
    you focus on the migration without having to implement artifact build
    processes in the target Google Cloud environment as part of the migration.

- **Scan and sign code**. As part of your artifact build processes, you might be
  using code scanning to help you guard against common vulnerabilities and
  unintended network exposure, and code signing to help you ensure that only
  trusted code runs in your environments.
- **Deploy artifacts in your source environment**. After you generate deployable
  artifacts, you might be deploying them in your source environment. We
  recommend that you assess each deployment process. The assessment helps ensure
  that your deployment processes are compatible with Google Cloud. It also helps
  you to understand the effort that will be necessary to eventually refactor the
  processes. For example, if your deployment processes work with your source
  environment only, you might need to refactor them to target your Google Cloud
  environment.
- **Inject runtime configuration**. You might be injecting runtime configuration
  for specific clusters, runtime environments, or workload deployments. The
  configuration might initialize environment variables and other configuration
  values such as secrets, credentials, and keys. To help ensure that your
  runtime configuration injection processes work on Google Cloud, we recommend
  that you assess how you're configuring the workloads that run in your source
  environment.
- **Logging, monitoring, and profiling**. Assess the logging, monitoring, and
  profiling processes that you have in place to monitor the health of your
  source environment, the metrics of interest, and how you're consuming data
  provided by these processes.
- **Authentication**. Assess how you're authenticating against your source
  environment.
- **Provision and configure your resources**. To prepare your source
  environment, you might have designed and implemented processes that provision
  and configure resources. For example, you might be using
  [Terraform](https://www.terraform.io/) along with configuration management
  tools to provision and configure resources in your source environment.

### **Complete the assessment**

After you build the inventories from your Azure Blob Storage environment,
complete the rest of the activities of the assessment phase as described in
[Migrate to Google Cloud: Assess and discover your workloads](https://cloud.google.com/solutions/migration-to-gcp-assessing-and-discovering-your-workloads).

## **Plan and build your foundation**

In the plan and build phase, you provision and configure the infrastructure to
do the following:

- Support your workloads in your Google Cloud environment.
- Connect your source environment and your Google Cloud environment to complete
  the migration.

The plan and build phase is composed of the following tasks:

1.  Build a resource hierarchy.
1.  Configure Google Cloud's Identity and Access Management (IAM).
1.  Set up billing.
1.  Set up network connectivity.
1.  Harden your security.
1.  Set up logging, monitoring, and alerting.

For more information about each of these tasks, see the
[Migrate to Google Cloud: Plan and build your foundation](https://cloud.google.com/architecture/migration-to-google-cloud-building-your-foundation).

## **Migrate data and workloads from Azure Blob Storage to Cloud Storage**

To migrate data from Azure Blob Storage to Cloud Storage, we recommend that you
design a data migration plan by following the guidance in
[Migrate to Google Cloud: Transfer your large datasets](https://cloud.google.com/architecture/migration-to-google-cloud-transferring-your-large-datasets).
That document recommends using
[Storage Transfer Service](https://cloud.google.com/storage-transfer/docs/overview),
a Google Cloud product that lets you migrate data from several sources to Cloud
Storage, such as from on-premises environments or from other cloud storage
providers. Storage Transfer Service supports several types of data transfer
jobs, such as the following:

- [Run-once transfer jobs](https://cloud.google.com/storage-transfer/docs/create-transfers),
  which transfer data from Azure Blob Storage or other supported sources to
  Cloud Storage on demand.
- [Scheduled transfer jobs](https://cloud.google.com/storage-transfer/docs/schedule-transfer-jobs),
  which transfer data from Azure Blob Storage or other supported sources to
  Cloud Storage on a schedule.

To implement a data migration plan, you can configure one or more data transfer
jobs. For example, to reduce the length of cut-over windows during the
migration, you can implement a
[continuous replication](https://cloud.google.com/architecture/migration-to-google-cloud-transferring-your-large-datasets#continuous_replication)
data migration strategy as follows:

1.  Configure a run-once transfer job to copy the data from an Azure Blob
    Storage account and container to the Cloud Storage bucket.
1.  Perform data validation and consistency checks to compare data in the Azure
    Blob Storage against the copied data in the Cloud Storage bucket.
1.  Refactor workloads to use Cloud Storage instead of Azure Blob Storage.

    - For workloads that support both Azure Blob Storage and Cloud Storage as
      inputs and/or outputs \- Change the data source to Cloud Storage, and
      apply any required changes, such as how the workload authenticates to
      Cloud Storage, and which bucket to use.
    - For workloads that access Azure Blob Storage using the Azure Blob Storage
      client library \- Refactor your workloads to use the
      [Cloud Storage client library](https://cloud.google.com/storage/docs/reference/libraries)
      instead.

1.  Stop the workloads and services that have access to the data that's being
    migrated (that is, to the data that's involved in the previous steps).
1.  Configure a run-once transfer job to copy the remaining data that was added
    or updated after the first sync, and wait for the replication to fully
    synchronize Cloud Storage with Azure Blob Storage.
1.  Start your workloads.
1.  When you no longer need your Azure Blob Storage environment as a fallback
    option, retire it.

Storage Transfer Service can preserve
[certain metadata when you migrate objects from a supported source to Cloud Storage](https://cloud.google.com/storage-transfer/docs/metadata-preservation).
We recommend that you assess whether Storage Transfer Service can migrate
[the Azure Storage metadata](https://cloud.google.com/storage-transfer/docs/metadata-preservation#azure-to-cloud)
that you're interested in.

When you design your data migration plan, we recommend that you also assess
Azure network egress costs and your Azure Blob Storage costs. For example,
consider the following options to transfer data:

- Across the public internet.
- By using an interconnect link.
- By using
  [Azure CDN](https://learn.microsoft.com/en-us/azure/cdn/cdn-storage-custom-domain-https).
- By using
  [Azure Front Door](https://learn.microsoft.com/azure/frontdoor/scenario-storage-blobs).

The option that you choose can have an impact on your Azure network egress costs
and your Azure Blob Storage costs. The option can also affect the amount of
effort and resources that you need in order to provision and configure the
infrastructure. For example, transferring data over Azure CDN with Azure Blob
Storage as origin can reduce Azure network egress costs. However, choosing this
path requires
[configuring Storage Transfer Service with a list of CDN URLs with SAS](https://cloud.google.com/storage-transfer/docs/source-url-list)
for all the blobs you plan on migrating from Azure Blob Storage. For more
information about costs, see the following:

- [Compare data transfer solutions](https://learn.microsoft.com/azure/storage/common/storage-choose-data-transfer-solution)
  in the Azure documentation
- [Estimate the cost of AzCopy transfers](https://learn.microsoft.com/azure/storage/blobs/azcopy-cost-estimation)
- [Network routing preferences for Azure Storage](https://learn.microsoft.com/azure/storage/common/network-routing-preference)
- [Azure Blob Storage pricing](https://azure.microsoft.com/pricing/details/storage/blobs/)

When you migrate data from Azure Blob Storage to Cloud Storage, we recommend
that you
[use VPC Service Controls to build a perimeter](https://cloud.google.com/architecture/transferring-data-from-amazon-s3-to-cloud-storage-using-vpc-service-controls-and-storage-transfer-service)
that explicitly denies communication between Google Cloud services unless the
services are authorized.

## **Optimize your Google Cloud environment**

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
[Google Cloud Well-Architected Framework: Performance optimization](https://cloud.google.com/architecture/framework/performance-optimization/).

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

Author: Ido Flatow | Cloud Solutions Architect

Other contributors:

- [Marco Ferrari](https://www.linkedin.com/in/ferrarimark) | Cloud Solutions
  Architect
- [Alex Carciu](https://www.linkedin.com/in/alex-carciu) | Cloud Solutions
  Architect
