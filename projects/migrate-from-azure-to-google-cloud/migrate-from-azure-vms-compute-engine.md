# Migrate from Azure to Google Cloud: Migrate Azure Virtual Machines to Compute Engine

Google Cloud provides tools, products, guidance, and professional services to
migrate Azure Virtual Machines (Azure VMs) from Azure to Google Cloud. This
document helps you to design, implement, and validate a plan to migrate Azure
VMs from Azure to Google Cloud. This document also provides guidance if you're
evaluating the opportunity to migrate and want to explore what migration might
look like.

This document is part of a multi-part series about migrating from Azure to
Google Cloud. For more information about the series, see
[Get started](./README.md).

Google Cloud provides [Compute Engine](https://cloud.google.com/compute/docs), a
managed service to run VMs. In this document, we focus on Compute Engine as the
target environment to migrate Azure VMs to.

For a comprehensive mapping between Azure and Google Cloud services, see
[compare AWS and Azure services to Google Cloud services](https://cloud.google.com/free/docs/aws-azure-gcp-service-comparison).

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

This document focuses on migrating Azure VMs from Azure to Compute Engine. For
more information about migrating other kinds of resources, such as objects
storage, and databases from Azure to Google Cloud, see the
[Migrate from Azure to Google Cloud document series](./README.md).

## Assess the source environment

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

For more information about the assessment phase and these tasks, see
[Migrate to Google Cloud: Assess and discover your workloads](https://cloud.google.com/architecture/migration-to-gcp-assessing-and-discovering-your-workloads).
The following sections are based on information in that document.

### Build an inventory of your Azure VMs

To scope your migration, you create an inventory of your Azure VMs. You can then
use the inventory to assess your deployment and operational processes for
provisioning and configuring these Azure VMs.

To build the inventory of your Azure VMs, we recommend that you use
[Migration Center](https://cloud.google.com/migration-center/docs/migration-center-overview),
Google Cloud’s unified platform that helps you accelerate your end-to-end cloud
journey from your current environment to Google Cloud. Migration Center lets you
[import data from Azure VMs and other Azure resources](https://cloud.google.com/migration-center/docs/import-data-cloud-providers).
Migration Center then recommends relevant Google Cloud services that you can
migrate to.

The data that Migration Center provides might not fully capture the dimensions
that you're interested in. In that case, you can integrate that data with the
results from other data-collection mechanisms that you create that are based on
Azure APIs, Azure developer tools, and the Azure command-line interface.

In addition to the data that you get from Migration Center, consider the
following data points for each Azure VM that you want to migrate:

- Deployment region and availability zone where you provisioned the VM.
- VM type, series, and size.
- The VM image that the VM is launching from, and if it’s provided by Azure, or
  custom built.
- The operating system (OS) that the VM is running, and how is the OS licensed.
- The VM network configuration and how you configured the public and private IP
  addresses of each network interface of the VM.
- The VM hostname, and how other VMs and workloads use this hostname to
  communicate with the VM.
- The VM tags as well as metadata and user data.
- The VM purchase option, such as on-demand purchase, Azure Spot VMs and Azure
  reservations.
- How the VM stores data, such as using Azure managed disks, the type and size
  of each disk, its performance, and the disk performance that the workloads
  running on the VM require.
- The VM managed identities.
- The VM tenancy configuration and if the VM runs on Azure Dedicated Hosts.
- Whether the VM is in specific VM Scale Sets and Proximity Placement Groups.
- Whether the VM is in specific Availability sets.
- Whether the VM supports nested virtualization workloads.
- Whether the VM supports confidential computing workloads.
- Whether the VM relies on Secure Boot and Trusted Platform Modules.
- The security groups that the VM belongs to.
- Any Azure Firewall configuration that involves the VM.
- Whether the workloads that run on the VM are protected by Azure DDoS Network
  Protection and Azure Web Application Firewall.
- Whether the VM relies on extensions for post-deployment configuration and
  automation.
- How you’re handling updates for the software that’s installed on the VM, and
  if you enabled VM guest patching.
- How you’re protecting the VM with backups and disaster recovery plans.
- How you're exposing workloads that run on the VM to clients that run in your
  Azure environment (such as other workloads) and to external clients.
- How the VMs are organized in Resource Groups.

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

## Plan and build your foundation

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

## Migrate workloads

To migrate Azure VMs to Compute Engine, we recommend that you use Migrate to
Virtual Machines, Google Cloud’s managed service to migrate VMs to Google Cloud.
For more information about Migrate to Virtual Machines see:

- [Migrate to Virtual Machines architecture](https://cloud.google.com/migrate/virtual-machines/docs/5.0/discover/architecture)
- [VM migration lifecycle](https://cloud.google.com/migrate/virtual-machines/docs/5.0/discover/lifecycle)
- [Migration journey with Migrate to VMs](https://cloud.google.com/migrate/virtual-machines/docs/5.0/discover/migrating-vms-migrate-for-compute-engine-getting-started)
- [Migrate to Virtual Machines best practices](https://cloud.google.com/migrate/virtual-machines/docs/5.0/discover/migrating-vms-migrate-for-compute-engine-best-practices)
- [Migrate to Virtual Machines supported operating systems](https://cloud.google.com/migrate/virtual-machines/docs/5.0/discover/supported-os-versions)

To migrate your Azure VMs to Compute Engine, you do the following:

1.  Prepare your environment for the migration.
1.  Migrate VMs, disks, and images from Azure VMs to Compute Engine.
1.  Expose workloads that run on Compute Engine to clients.
1.  Refactor deployment and operational processes to target Google Cloud instead
    of targeting Azure VMs.

The following sections provide details about each of these tasks.

### Prepare your environment for the migration

To prepare your environment for the migration, you do the following:

1.  Ensure that you have the
    [necessary roles and permissions](https://cloud.google.com/migrate/virtual-machines/docs/5.0/reference/roles-reference)
    to configure Migrate to Virtual Machines.
1.  [Enable Migrate to Virtual Machines services](https://cloud.google.com/migrate/virtual-machines/docs/5.0/get-started/enable-services).
1.  [Add a target project](https://cloud.google.com/migrate/virtual-machines/docs/5.0/get-started/target-project).
1.  [Configure permissions on service accounts](https://cloud.google.com/migrate/virtual-machines/docs/5.0/get-started/target-sa-compute-engine).
1.  If needed,
    [configure permissions for a Shared VPC](https://cloud.google.com/migrate/virtual-machines/docs/5.0/get-started/shared-vpc).
1.  If needed,
    [configure VPC Service Controls](https://cloud.google.com/migrate/virtual-machines/docs/5.0/migrate/create-a-service-perimeter)
    to reduce the risk of unauthorized data transfers from your Google Cloud
    environment.
1.  [Create an Azure source](https://cloud.google.com/migrate/virtual-machines/docs/5.0/migrate/create-an-azure-source)
    to migrate your Azure VMs.

### Migrate VMs, disks, and images from Azure VMs to Compute Engine

Migrate to Virtual Machines supports migrating VMs and disks individually or in
groups. You can migrate VMs and disks individually for small migrations and
proofs of concept. When you migrate a VM or a disk individually, Migrate to
Virtual Machines performs all the operations of the VM migration lifecycle on
the VM or disk. To streamline the process of planning and migrating VMs in
batches for non-trivial production environments, we recommend that you migrate
VMs and disks in groups. When you migrate VMs and disks in groups, Migrate to
Virtual Machines performs all the operations of the VM migration lifecycle on
each VM or disk in the group. For more information about the structure of a
migration and how to organize groups, see
[Migration journey with Migrate to Virtual Machines](https://cloud.google.com/migrate/virtual-machines/docs/5.0/discover/migrating-vms-migrate-for-compute-engine-getting-started).

For more information about migrating VMs and disks, see:

- [Migrate individual VMs](https://cloud.google.com/migrate/virtual-machines/docs/5.0/migrate/migrating-vms)
  and
  [Migrate VM groups](https://cloud.google.com/migrate/virtual-machines/docs/5.0/migrate/migrating-vm-groups)
- [Migrate VM disks](https://cloud.google.com/migrate/virtual-machines/docs/5.0/migrate/migrating-disks)
  and
  [Migrate disks in groups](https://cloud.google.com/migrate/virtual-machines/docs/5.0/migrate/migrating-disk-groups)
- [Migration progress details](https://cloud.google.com/migrate/virtual-machines/docs/5.0/migrate/migration-progress-details)

Migrate to Virtual Machines also supports
[importing and exporting a migration plan](https://cloud.google.com/migrate/virtual-machines/docs/5.0/migrate/import-export)
so that you can revise and edit it using your preferred editor, or you can
process it with third-party tools, and then import it back so that Migrate to
Virtual Machines can execute on it.

If you need to import existing virtual disk images from your Azure environment,
you can
[import them to Compute Engine images](https://cloud.google.com/migrate/virtual-machines/docs/5.0/migrate/image_import),
as long as the image format is supported. For example, you can migrate your
virtual disk images as part of an offline migration, differently from what you
would do by live migrating a VM disk. Importing a virtual disk image is a
one-off task, differently from when you migrate a VM, which is a process that
goes through several steps. As part of the import, Migrate to Virtual Machines
adapts the virtual machine images to run on Compute Engine.

Migrate to Virtual Machines always encrypts data at rest. In addition to this,
Migrate to Virtual Machines supports Customer-managed encryption keys to encrypt
data stored during the migration and data on target VMs and disks. For more
information, see
[Use Customer-managed encryption keys with Migrate to Virtual Machines](https://cloud.google.com/migrate/virtual-machines/docs/5.0/migrate/cmek).

### Expose workloads that run on Compute Engine to clients

After you migrate your Azure VMs instances to Compute Engine instances, you
might need to provision and configure your Google Cloud environment to expose
workloads to clients.

Google Cloud offers services and products to expose your workloads to clients.
For workloads that run on your Compute Engine instances, you configure resources
for the following categories:

- Firewalls
- Traffic load balancing
- DNS names, zones, and records
- DDoS protection and web application firewalls

For each of these categories, you can start by implementing a baseline
configuration that’s similar to how you configured Azure services and resources
in the equivalent category. You can then iterate on the configuration and use
additional features that Google Cloud services and products provide.

The following sections explain how to provision and configure Google Cloud
resources in these categories, and how they map to Azure resources in similar
categories.

#### Firewalls

If you configured network security groups in your Azure environment and Azure
Firewall, you can configure
[Cloud Next Generation Firewall policies and rules](https://cloud.google.com/vpc/docs/about-firewalls).
For example, if you use Azure security groups to allow or deny connections to
your Azure VMs, you can configure similar
[Virtual Private Cloud (VPC) firewall rules](https://cloud.google.com/vpc/docs/firewalls)
that apply to your Compute Engine instances. You can also provision
[VPC Service Controls](https://cloud.google.com/vpc-service-controls/docs/overview)
to regulate traffic inside your VPC. You can use VPC Service Controls to control
outgoing traffic from your Compute Engine instances to Google APIs, and to help
mitigate the risk of data exfiltration.

If you connect remotely to your Azure VMs over the internet, using protocols
such as SSH or RDP, you can remove the VM's public IP and connect to the VM
remotely with [IAP](https://cloud.google.com/security/products/iap?hl=en)
(Identity-Aware Proxy).
[IAP TCP forwarding](https://cloud.google.com/iap/docs/using-tcp-forwarding)
allows you to establish an encrypted tunnel over which you can forward SSH, RDP,
and other traffic to VM instances from the internet, without assigning your VMs
public IPs. Connections from the IAP service originate from a reserved public IP
range, requiring you to create matching VPC firewall rules. If you have
Windows-based VMs and you turned on Windows Firewall, verify the Windows
Firewall is not set to block RDP connections from IAP. For additional
information, see
[Troubleshooting RDP](https://cloud.google.com/compute/docs/troubleshooting/troubleshooting-rdp).

If you configured Azure Virtual Network service endpoints to access Azure
service from an Azure VM that only has internal IP addresses, you can configure
[Private Google Access](https://cloud.google.com/vpc/docs/private-google-access)
in order for your Compute Engine instances that only have internal IP addresses
to access Google APIs and services.

If you configured Azure Private Link to access Azure services and third-party
services over a private endpoint from your Azure VMs, you can configure
[Private Service Connect](https://cloud.google.com/vpc/docs/private-service-connect)
in order for your Compute Engine instances to privately access Google services
and services hosted on Google Cloud from inside the Compute Engine instances VPC
network.

#### Traffic load balancing

If you configured Azure Load Balancer and Azure Application Gateway to expose
workloads running on your Azure VMs, you can configure
[Cloud Load Balancing](https://cloud.google.com/load-balancing/docs/load-balancing-overview)
to distribute network traffic to help improve the scalability and reliability of
the workloads running on your Compute Engine instances. Cloud Load Balancing
supports several global and regional
[load balancing products](https://cloud.google.com/load-balancing/docs/load-balancing-overview#summary-of-google-cloud-load-balancers)
that work at different layers of the
[OSI model](https://wikipedia.org/wiki/OSI_model), such as at the transport
layer and at the application layer. You can
[choose a load balancing product](https://cloud.google.com/load-balancing/docs/choosing-load-balancer)
that's suitable for the requirements of your workloads.

Cloud Load Balancing also supports configuring
[Transport Layer Security (TLS) to encrypt network traffic](https://cloud.google.com/load-balancing/docs/ssl-certificates)
and
[mutual TLS authentication (mTLS)](https://cloud.google.com/load-balancing/docs/mtls).
When you configure TLS for Cloud Load Balancing, you can use
[self-managed or Google-managed SSL certificates](https://cloud.google.com/load-balancing/docs/ssl-certificates#certificate-types),
depending on your requirements.

If you configured Azure Front Door and CDN in your Azure environment, you can
use [Cloud CDN](https://cloud.google.com/cdn/docs/overview) to serve content
closer to your users using Google’s global edge network.

If you are using Azure Traffic Manager as a DNS-based traffic load balancer in
your Azure environment, you can use
[Cloud Load Balancing and Cloud DNS](https://cloud.google.com/architecture/global-load-balancing-architectures-for-dns-routing-policies).

#### DNS names, zones, and records

If you’re using Azure DNS in your Azure environment, you can use
[Cloud DNS](https://cloud.google.com/dns/docs/overview) to manage your
[public and private DNS zones](https://cloud.google.com/dns/docs/zones/zones-overview)
and your [DNS records](https://cloud.google.com/dns/docs/records-overview). You
can also
[migrate your DNS zones and records to Cloud DNS](https://cloud.google.com/dns/docs/migrating).

If you want to streamline the registration and management of your domains, you
can use [Cloud Domains](https://cloud.google.com/domains/docs/overview).

#### DDoS protection and web application firewalls

If you configured Azure DDoS Network Protection and Azure Web Application
Firewall, you can use
[Google Cloud Armor](https://cloud.google.com/armor/docs/cloud-armor-overview)
to help protect your Google Cloud workloads from DDoS attacks and from common
exploits.

### Refactor deployment and operational processes

After you refactor your workloads, you refactor your deployment and operational
processes to do the following:

- Provision and configure resources in your Google Cloud environment instead of
  provisioning resources in your source environment.
- Build and configure workloads, and deploy them in your Google Cloud instead of
  deploying them in your source environment.

You gathered information about these processes during the assessment phase
earlier in this process.

The type of refactoring that you need to consider for these processes depends on
how you designed and implemented them. The refactoring also depends on what you
want the end state to be for each process. For example, consider the following:

- You might have implemented these processes in your source environment and you
  intend to design and implement similar processes in Google Cloud. For example,
  you can refactor these processes to use
  [Cloud Build](https://cloud.google.com/build/docs/overview),
  [Cloud Deploy](https://cloud.google.com/deploy/docs/overview), and
  [Infrastructure Manager](https://cloud.google.com/infrastructure-manager/docs/overview).
- You might have implemented these processes in another third-party environment
  outside your source environment. In this case, you need to refactor these
  processes to target your Google Cloud environment instead of your source
  environment.
- A combination of the previous approaches.

Refactoring deployment and operational processes can be complex and can require
significant effort. If you try to perform these tasks as part of your workload
migration, the workload migration can become more complex, and it can expose you
to risks. After you assess your deployment and operational processes, you likely
have an understanding of their design and complexity. If you estimate that you
require substantial effort to refactor your deployment and operational
processes, we recommend that you consider refactoring these processes as part of
a separate, dedicated project.

For more information about how to design and implement deployment processes on
Google Cloud, see:

- [Migrate to Google Cloud: Deploy your workloads](https://cloud.google.com/architecture/migration-to-gcp-deploying-your-workloads)
- [Migrate to Google Cloud: Migrate from manual deployments to automated, containerized deployments](https://cloud.google.com/architecture/migration-to-google-cloud-automated-containerized-deployments)

This document focuses on the deployment processes that produce the artifacts to
deploy, and deploy them in the target runtime environment. The refactoring
strategy highly depends on the complexity of these processes. The following list
outlines a possible, general, refactoring strategy:

1.  Provision artifact repositories on Google Cloud. For example, you can use
    Artifact Registry to store artifacts and build dependencies.
1.  Refactor your build processes to store artifacts both in your source
    environment and in Artifact Registry.
1.  Refactor your deployment processes to deploy your workloads in your target
    Google Cloud environment. For example, you can start by deploying a small
    subset of your workloads in Google Cloud, using artifacts stored in Artifact
    Registry. Then, you gradually increase the number of workloads deployed in
    Google Cloud, until all the workloads to migrate run on Google Cloud.
1.  Refactor your build processes to store artifacts in Artifact Registry only.
1.  If necessary, migrate earlier versions of the artifacts to deploy from the
    repositories in your source environment to Artifact Registry. For example,
    you can copy container images to Artifact Registry.
1.  Decommission the repositories in your source environment when you no longer
    require them.

To facilitate eventual rollbacks due to unanticipated issues during the
migration, you can store container images both in your current artifact
repositories in Google Cloud while the migration to Google Cloud is in progress.
Finally, as part of the decommissioning of your source environment, you can
refactor your container image building processes to store artifacts in Google
Cloud only.

Although it might not be crucial for the success of a migration, you might need
to migrate your earlier versions of your artifacts from your source environment
to your artifact repositories on Google Cloud. For example, to support rolling
back your workloads to arbitrary points in time, you might need to migrate
earlier versions of your artifacts to Artifact Registry. For more information,
see
[Migrate images from a third-party registry](https://cloud.google.com/artifact-registry/docs/docker/migrate-external-containers).

If you're using Artifact Registry to store your artifacts, we recommend that you
configure controls to help you secure your artifact repositories, such as access
control, data exfiltration prevention, vulnerability scanning, and Binary
Authorization. For more information, see
[Control access and protect artifacts](https://cloud.google.com/artifact-registry/docs/protect-artifacts).

### Follow migration best practices

To help you prevent common migration issues, we recommend that you:

- Ensure that you
  [registered a migration source as an application on Azure](https://cloud.google.com/migrate/virtual-machines/docs/5.0/migrate/create-an-azure-source#register-your-app)
  for each region that you need to migrate Azure VMs from.
- Ensure that the Azure custom role that
  [you created for the migration](https://cloud.google.com/migrate/virtual-machines/docs/5.0/migrate/create-an-azure-source#create-a-custom-role)
  has all the necessary permissions, and that you
  [assigned the custom role to the application registration](https://cloud.google.com/migrate/virtual-machines/docs/5.0/migrate/create-an-azure-source#register-your-app).
- When
  [you create an Azure migration source](https://cloud.google.com/migrate/virtual-machines/docs/5.0/migrate/create-an-azure-source#register-your-app),
  ensure that you use the correct Azure location, tenant ID, subscription ID,
  and client ID.
- When you create an Azure migration source, ensure that you use the secret
  value, and not the secret ID.
- Don’t delete any Azure VM while the migration is in progress.

## Optimize your Google Cloud environment

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

Autohor: [Marco Ferrari](https://www.linkedin.com/in/ferrarimark) | Cloud
Solutions Architect

Other contributors:

- Oshri Abutbul
- Ayelet Wald
- Alex Carciu
- Ido Flatow
