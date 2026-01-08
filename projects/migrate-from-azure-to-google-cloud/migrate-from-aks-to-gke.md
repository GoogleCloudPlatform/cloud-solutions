# Migrate to Google Cloud: Migrate from Azure Kubernetes Service to GKE

Google Cloud provides tools, products, guidance, and professional services to
migrate from Azure Kubernetes Service (AKS) to
[Google Kubernetes Engine](https://cloud.google.com/kubernetes-engine) (GKE).
This document helps you to design, implement, and validate a plan to migrate
from AKS to GKE. This document also provides guidance if you're evaluating the
opportunity to migrate and want to explore what migration might look like.

GKE is a Google-managed Kubernetes service that you can use to deploy and
operate containerized applications at scale using Google's infrastructure, and
provides features that help you manage your Kubernetes environment, such as:

- [Industry-unique service level agreement for Pods](https://cloud.google.com/kubernetes-engine/sla)
  when using GKE Autopilot in multiple zones.
- Automated node pool creation and deletion with
  [node auto-provisioning](https://cloud.google.com/kubernetes-engine/docs/concepts/node-auto-provisioning).
- Google-managed
  [multi-cluster networking](https://cloud.google.com/kubernetes-engine/docs/concepts/choose-mc-lb-api)
  to help you design and implement highly available, distributed architectures
  for your workloads.

For more information about GKE, see
[GKE overview](https://cloud.google.com/kubernetes-engine/docs/concepts/kubernetes-engine-overview)

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

This document focuses on migrating workloads and data from AKS to GKE. For more
information about migrating other kinds of resources, such as objects storage,
and databases from Azure to Google Cloud, see the
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

### Build your inventories

To scope your migration, you create two inventories:

1.  The inventory of your clusters.
1.  The inventory of your workloads that are deployed in those clusters.

After you build these inventories, you:

1.  Assess your deployment and operational processes for your source
    environment.
1.  Assess supporting services and external dependencies.

#### Build the inventory of your clusters

To build the inventory of your clusters, consider the following for each
cluster:

- **Number and type of nodes**. When you know how many nodes and the
  characteristics of each node that you have in your current environment, you
  size your clusters when you move to GKE. The nodes in your new environment
  might run on a different hardware architecture or generation than the ones you
  use in your environment. The performance of each architecture and generation
  is different, so the number of nodes you need in your new environment might be
  different from your environment. Evaluate any type of hardware that you're
  using in your nodes, such as high-performance storage devices, GPUs, and TPUs.
  Assess which operating system image that you're using on your nodes.
- **Internal or external cluster**. Evaluate which actors, either internal to
  your environment or external, that each cluster is exposed to. To support your
  use cases, this evaluation includes the workloads running in the cluster, and
  the [interfaces](https://kubernetes.io/docs/concepts/overview/kubernetes-api/)
  that interact with your clusters.
- **Multi-tenancy**. If you're managing multi-tenant clusters in your
  environment, assess if it works in your new Google Cloud environment. Now is a
  good time to evaluate how to improve your multi-tenant clusters because your
  multi-tenancy strategy influences how you build your foundation on Google
  Cloud.
- **Kubernetes version**. Gather information about the Kubernetes version of
  your clusters to assess if there is a mismatch between those versions and the
  [ones available in GKE](https://cloud.google.com/kubernetes-engine/versioning).
  If you're running an older or a recently released Kubernetes version, you
  might be using features that are unavailable in GKE. The features might be
  deprecated, or the Kubernetes version that ships them is not yet available in
  GKE.
- **Kubernetes upgrade cycle**. To maintain a reliable environment, understand
  how you're handling Kubernetes upgrades and how your upgrade cycle relates to
  [GKE upgrades](https://cloud.google.com/kubernetes-engine/docs/concepts/cluster-upgrades).
- **Node pools**. If you're using any form of node grouping, you might want to
  consider how these groupings map to the concept of
  [node pools in GKE](https://cloud.google.com/kubernetes-engine/docs/concepts/node-pools)
  because your grouping criteria might not be suitable for GKE.
- **Node initialization**. Assess how you initialize each node before marking it
  as available to run your workloads so you can port those initialization
  procedures over to GKE.
- **Network configuration**. Assess the network configuration of your clusters,
  their IP address allocation, how you configured their networking plugins, how
  you configured their DNS servers and DNS service providers, if you configured
  any form of NAT or SNAT for these clusters, and whether they are part of a
  multi-cluster environment.
- **Compliance**: Assess any compliance and regulatory requirements that your
  clusters are required to satisfy, and whether you're meeting these
  requirements.
- **Quotas and limits**. Assess how you configured quotas and limits for your
  clusters. For example, how many Pods can each node run? How many nodes can a
  cluster have?
- **Labels and tags**. Assess any metadata that you applied to clusters, node
  pools, and nodes, and how you're using them. For example, you might be
  generating reports with detailed, label-based cost attribution.

#### Build the inventory of your Kubernetes Namespaces and security configuration objects

After you complete the Kubernetes clusters inventory, build the inventory of
your Namespaces and of the Kubernetes objects that you deployed to secure your
AKS clusters:

- **Namespaces**. If you use Kubernetes
  [Namespaces](https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/)
  in your clusters to logically separate resources, assess which resources are
  in each Namespace, and understand why you created this separation. For
  example, you might be using Namespaces as part of your multi-tenancy strategy.
  You might have workloads deployed in Namespaces reserved for Kubernetes system
  components, and you might not have as much control in GKE.
- **Role-based access control (RBAC)**. If you use
  [RBAC authorization](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
  in your clusters, list a description of all ClusterRoles and
  ClusterRoleBindings that you configured in your clusters.
- **Network policies**. List all
  [network policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
  that you configured in your clusters, and understand
  [how network policies work in GKE](https://cloud.google.com/kubernetes-engine/docs/how-to/network-policy).
- **Pod security contexts**. Capture information about the
  [Pod security contexts](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/)
  that you configured in your clusters and
  [learn how they work in GKE](https://cloud.google.com/kubernetes-engine/docs/how-to/pod-security-policies).
- **Service accounts**. If any process in your cluster is interacting with the
  Kubernetes API server, capture information about the
  [service accounts](https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/)
  that they're using.

When you build the inventory of your Kubernetes clusters, you might find that
some of the clusters need to be decommissioned as part of your migration. Make
sure that your migration plan includes retiring these resources.

#### Build the inventory of your Kubernetes workloads

After you complete the Kubernetes Namespaces inventory, build the inventory of
the workloads and Kubernetes objects deployed in those clusters. When evaluating
your workloads, gather information about the following aspects:

- **[Pods](https://kubernetes.io/docs/concepts/workloads/pods/pod/) and
  [controllers](https://kubernetes.io/docs/concepts/architecture/controller/)**.
  To size the clusters in your new environment, assess how many instances of
  each workload you have deployed, and if you're using
  [Resource quotas](https://kubernetes.io/docs/concepts/policy/resource-quotas/)
  and
  [compute resource consumption limits](https://kubernetes.io/docs/concepts/configuration/manage-compute-resources-container/).
  Gather information about the workloads that are running on the control plane
  nodes of each cluster and the controllers that each workload uses. For
  example, how many
  [Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
  are you using? How many
  [DaemonSets](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/)
  are you using?
- **[Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/)** and
  **[CronJobs](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/)**.
  Your clusters and workloads might need to run Jobs or CronJobs as part of
  their initialization or operation procedures. Assess how many instances of
  Jobs and CronJobs you have deployed, and the responsibilities and completion
  criteria for each instance.
- **Kubernetes Autoscalers**. To migrate your autoscaling policies in the new
  environment, learn how
  [the Horizontal Pod Autoscaler](https://cloud.google.com/kubernetes-engine/docs/concepts/horizontalpodautoscaler)
  and
  [the Vertical Pod Autoscaler](https://cloud.google.com/kubernetes-engine/docs/concepts/verticalpodautoscaler),
  work on GKE.
- **Stateless and stateful workloads**. Stateless workloads don't store data or
  state in the cluster or to persistent storage. Stateful applications save data
  for later use. For each workload, assess which components are stateless and
  which are stateful, because migrating
  [stateful workloads](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)
  is typically harder than migrating stateless ones.
- **Kubernetes features**. From the cluster inventory, you know which Kubernetes
  version each cluster runs. Review the
  [release notes](https://kubernetes.io/docs/setup/release/) of each Kubernetes
  version to know which features it ships and which features it deprecates. Then
  assess your workloads against the Kubernetes features that you need. The goal
  of this task is to know whether you're using deprecated features or features
  that are not yet available in GKE. If you find any unavailable features,
  migrate away from deprecated features and adopt the new ones when they're
  [available in GKE](https://cloud.google.com/kubernetes-engine/docs/release-notes).
- **Storage**. For stateful workloads, assess if they use
  [PersistenceVolumeClaims](https://kubernetes.io/docs/concepts/storage/persistent-volumes/#persistentvolumeclaims).
  List any storage requirements, such as size and access mode, and how these
  PersistenceVolumeClaims map to PersistenceVolumes. To account for future
  growth, assess if you need to
  [expand any PersistenceVolumeClaim](https://kubernetes.io/docs/concepts/storage/persistent-volumes/#expanding-persistent-volumes-claims).
- **Configuration and secret injection**. To avoid rebuilding your deployable
  artifacts every time there is a change in the configuration of your
  environment, inject configuration and secrets into Pods using
  [ConfigMaps](https://cloud.google.com/kubernetes-engine/docs/concepts/configmap)
  and [Secrets](https://kubernetes.io/docs/concepts/configuration/secret/). For
  each workload, assess which ConfigMaps and Secrets that workload is using, and
  how you're populating those objects.
- **Dependencies**. Your workloads probably don't work in isolation. They might
  have dependencies, either internal to the cluster, or from external systems.
  For each workload, capture the dependencies, and if your workloads have any
  tolerance for when the dependencies are unavailable. For example, common
  dependencies include distributed file systems, databases, secret distribution
  platforms, identity and access management systems, service discovery
  mechanisms, and any other external systems.
- **Kubernetes Services**. To expose your workloads to internal and external
  clients, use
  [Services](https://kubernetes.io/docs/concepts/services-networking/service/).
  For each Service, you need to know its type. For externally exposed services,
  assess how that service interacts with the rest of your infrastructure. For
  example, how is your infrastructure supporting
  [LoadBalancer services](https://kubernetes.io/docs/concepts/services-networking/service/#loadbalancer),
  [Gateway objects](https://kubernetes.io/docs/concepts/services-networking/gateway/),
  and
  [Ingress objects](https://kubernetes.io/docs/concepts/services-networking/ingress/)?
  Which
  [Ingress controllers](https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/)
  did you deploy in your clusters?
- **Service mesh**. If you're using a service mesh in your environment, you
  assess how it's configured. You also need to know how many clusters it spans,
  which services are part of the mesh, and how you modify the topology of the
  mesh.
- **[Taints and tolerations](https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/)**
  and
  **[affinity and anti-affinity](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/#affinity-and-anti-affinity)**.
  For each Pod and Node, assess if you configured any Node taints, Pod
  tolerations, or affinities to customize the scheduling of Pods in your
  Kubernetes clusters. These properties might also give you insights about
  possible non-homogeneous Node or Pod configurations, and might mean that
  either the Pods, the Nodes, or both need to be assessed with special focus and
  care. For example, if you configured a particular set of Pods to be scheduled
  only on certain Nodes in your Kubernetes cluster, it might mean that the Pods
  need specialized resources that are available only on those Nodes.
- **Authentication**: Assess how your workloads authenticate against resources
  in your cluster, and against external resources.

#### Assess supporting services and external dependencies

After you assess your clusters and their workloads, evaluate the rest of the
supporting services and aspects in your infrastructure, such as the following:

- **StorageClasses and PersistentVolumes**. Assess how your infrastructure is
  backing PersistentVolumeClaims by listing
  [StorageClasses](https://kubernetes.io/docs/concepts/storage/storage-classes/)
  for
  [dynamic provisioning](https://kubernetes.io/docs/concepts/storage/persistent-volumes/#dynamic),
  and
  [statically provisioned](https://kubernetes.io/docs/concepts/storage/persistent-volumes/#static)
  [PersistentVolumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/#persistent-volumes).
  For each PersistentVolume, consider the following: capacity, volume mode,
  access mode, class, reclaim policy, mount options, and node affinity.
- **[VolumeSnapshots](https://kubernetes.io/docs/concepts/storage/volume-snapshots/)**
  and
  **[VolumeSnapshotContents](https://kubernetes.io/docs/concepts/storage/volume-snapshots/)**.
  For each PersistentVolume, assess if you configured any VolumeSnapshot, and if
  you need to migrate any existing VolumeSnapshotContents.
- **Container Storage Interface (CSI) drivers**. If deployed in your clusters,
  assess if these drivers are compatible with GKE, and if you need to adapt the
  configuration of your volumes to work with
  [CSI drivers that are compatible with GKE](https://cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/install-csi-driver).
- **Data storage**. If you depend on external systems to provision
  PersistentVolumes, provide a way for the workloads in your GKE environment to
  use those systems. Data locality has an impact on the performance of stateful
  workloads, because the latency between your external systems and your GKE
  environment is proportional to the distance between them. For each external
  data storage system, consider its type, such as block volumes, file storage,
  or object storage, and any performance and availability requirements that it
  needs to satisfy.
- **Custom resources and Kubernetes add-ons**. Collect information about any
  [custom Kubernetes resources](https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/)
  and any
  [Kubernetes add-ons](https://kubernetes.io/docs/concepts/cluster-administration/addons/)
  that you might have deployed in your clusters, because they might not work in
  GKE, or you might need to modify them. For example, if a custom resource
  interacts with an external system, you assess if that's applicable to your
  Google Cloud environment.
- **Backup**. Assess how you're backing up the configuration of your clusters
  and stateful workload data in your source environment.

#### Tools to build the inventory and assess your source environment

To gather the necessary data points about your AKS clusters and objects, use the
following tools:

- **AKS cluster discovery, nodes discovery and assessment**. To discover your
  AKS clusters, we recommend that you use
  [Kubernetes Cluster Discovery Tool](https://github.com/GoogleCloudPlatform/professional-services/tree/main/tools/k8s-discovery),
  and that you refine the inventory with
  [Azure Resource Manager](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/overview)
  and [Azure Resource Inventory](https://github.com/microsoft/ARI).
- **Kubernetes object inventory**. To build the inventory of the objects that
  are deployed in your Kubernetes clusters, we recommend that you use
  [Kubernetes Cluster Discovery Tool](https://github.com/GoogleCloudPlatform/professional-services/tree/main/tools/k8s-discovery).
- **Kubernetes object assessment**. To assess your Kubernetes objects, we
  recommend that you use [Gemini CLI](https://geminicli.com/). For example, you
  can add the inventory files that list the Kubernetes objects in your clusters
  to the Gemini CLI context and then prompt Gemini to help you assess those
  objects. For more information, see
  [Gemini-powered migrations to Google Cloud](https://googlecloudplatform.github.io/cloud-solutions/gemini-powered-migrations-to-google-cloud/).

### Refine the inventory of your AKS clusters and workloads

The data that inventory building tools provide might not fully capture the
dimensions that you're interested in. In that case, you can integrate that data
with the results from other data-collection mechanisms that you create that are
based on Azure APIs, Azure developer tools, and the Azure command-line
interface.

In addition to the data that you get from these tools, consider the following
data points for each AKS cluster that you want to migrate:

- Consider AKS-specific aspects and features, including the following:
    - Microsoft Entra integration
    - Azure Linux nodes
    - AKS add-ons, such as managed NGINX Ingress, and Application Gateway
      Ingress Controller
    - AKS extensions and integrations
    - Azure Dedicated Hosts
    - AKS Long-term support
    - CoreDNS configuration customization
- Assess how you're authenticating against your AKS clusters and how you
  configured Azure Identity and Access Management for AKS.
- Assess the networking configuration of your AKS clusters.

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

The following sections integrate the considerations in Migrate to Google Cloud:
Plan and build your foundation.

### Plan for multi-tenancy

To design an efficient resource hierarchy, consider how your business and
organizational structures map to Google Cloud. For example, if you need a
multi-tenant environment on GKE, you can choose between the following options:

- Creating one Google Cloud Project for each tenant.
- Sharing one project among different tenants, and provisioning multiple GKE
  clusters.
- Using Kubernetes namespaces.

Your choice depends on your isolation, complexity, and scalability needs. For
example, having one project per tenant isolates the tenants from one another,
but the resource hierarchy becomes more complex to manage due to the high number
of projects. However, although managing Kubernetes Namespaces is relatively
easier than a complex resource hierarchy, this option doesn't guarantee as much
isolation. For example, the control plane might be shared between tenants. For
more information, see
[Cluster multi-tenancy](https://cloud.google.com/kubernetes-engine/docs/concepts/multitenancy-overview).

### Configure identity and access management

GKE supports multiple options for managing access to resources within your
Google Cloud Project and its clusters using RBAC. For more information, see
[Access control](https://cloud.google.com/kubernetes-engine/docs/concepts/access-control).

### Configure GKE networking

Network configuration is a fundamental aspect of your environment. Before
provisioning and configure any cluster, we recommend that you assess the
[GKE network model](https://cloud.google.com/kubernetes-engine/docs/concepts/network-overview),
the
[best practices for GKE networking](https://cloud.google.com/kubernetes-engine/docs/best-practices/networking),
and how to
[plan IP addresses when migrating to GKE](https://cloud.google.com/kubernetes-engine/docs/concepts/gke-ip-address-mgmt-strategies).

### Set up monitoring and alerting

Having a clear picture of how your infrastructure and workloads are performing
is key to finding areas of improvement. GKE has
[deep integrations with Cloud Observability Suite](https://cloud.google.com/kubernetes-engine/docs/concepts/observability),
so you get logging, monitoring, and profiling information about your GKE
clusters and workloads inside those clusters.

### Configure identity providers and IAM

In your source AKS environment, you might be using Microsoft Entra ID as your
identity provider. Migrating your existing identity provider from Azure to
Google Cloud as part of your migration from AKS to GKE might require significant
effort, and can therefore increase the complexity of your migration. To help you
manage this complexity, you can:

1.  Start by
    [federating your existing Microsoft Entra ID environment with Cloud Identity](https://cloud.google.com/architecture/identity/federating-gcp-with-azure-active-directory)
    while the AKS to GKE migration is ongoing.
1.  Migrate from Microsoft Entra ID to Cloud Identity as a separate, dedicated
    migration project, after you complete the migration from AKS to GKE.

If your workloads require Microsoft Entra ID specifically and you don’t want to
refactor them to use other identity providers, you might consider migrating from
Microsoft Entra ID to
[Managed Service for Microsoft Active Directory](https://cloud.google.com/security/products/managed-microsoft-ad/docs/overview).

After you configure Cloud Identity, we recommend that you provision the
necessary service accounts and roles for your workloads. When deploying
workloads on GKE, we recommend that you use
[Workload Identity Federation for GKE](https://cloud.google.com/kubernetes-engine/docs/concepts/workload-identity)
to help you securely authenticate them.

## Migrate your data and deploy workloads

Although AKS and GKE are both managed Kubernetes services, they differ in
design, features, and implementation. Before provisioning and configuring any
GKE cluster, we recommend that you review how AKS architecture concepts map to
similar GKE architecture concepts.

The following table helps you map common AKS architecture concepts to similar
GKE architecture concepts:

| Architectural area                                     | AKS                                                 | GKE                                                                                                                                                                             |
| :----------------------------------------------------- | :-------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Operation mode                                         | AKS                                                 | GKE Standard                                                                                                                                                                    |
|                                                        | N/A                                                 | GKE Autopilot                                                                                                                                                                   |
| Availability                                           | AKS cluster across availability zones               | Regional cluster                                                                                                                                                                |
|                                                        | AKS cluster in a single availability zone           | Zonal cluster                                                                                                                                                                   |
| Cluster version                                        | Cluster auto-upgrade channels                       | Release channel                                                                                                                                                                 |
| Network routing                                        | Flat network model                                  | VPC-native cluster                                                                                                                                                              |
|                                                        | Overlay network model                               | VPC-native cluster with [IP masquerade agent](https://cloud.google.com/kubernetes-engine/docs/concepts/ip-masquerade-agent)                                                     |
| Container Networking Interface                         | Azure Container Networking Interface                | [GKE Dataplane V2](https://cloud.google.com/kubernetes-engine/docs/concepts/dataplane-v2)                                                                                       |
| Cluster DNS management                                 | CoreDNS                                             | [Kube-dns and Cloud DNS](https://cloud.google.com/kubernetes-engine/docs/concepts/service-discovery)                                                                            |
| Cluster Ingress                                        | NGINX ingress controller, Azure Application Gateway | [GKE Ingress](https://cloud.google.com/kubernetes-engine/docs/concepts/ingress), [GKE Gateway controller](https://cloud.google.com/kubernetes-engine/docs/concepts/gateway-api) |
| Network isolation                                      | Private AKS cluster                                 | Private GKE cluster                                                                                                                                                             |
|                                                        | Public AKS cluster                                  | Public GKE cluster                                                                                                                                                              |
| Workload isolation                                     | Azure Dedicated Hosts                               | [Sole-tenant nodes](https://cloud.google.com/kubernetes-engine/docs/how-to/sole-tenancy)                                                                                        |
| Kubernetes APIs                                        | Production (stable), and beta Kubernetes APIs       | Production (stable), and beta Kubernetes APIs                                                                                                                                   |
|                                                        | Not supported                                       | Alpha Kubernetes APIs                                                                                                                                                           |
| Service mesh                                           | Managed Istio-based add-on                          | [Cloud Service Mesh](https://cloud.google.com/service-mesh/docs/overview)                                                                                                       |
| Multi-cluster networking                               | Self-managed                                        | Multi-cluster Services Multi-cluster Gateways Multi-cluster Cloud Service Mesh                                                                                                  |
| Multi-cluster management                               | Fleet Manager                                       | Fleet management                                                                                                                                                                |
| Node images                                            | Ubuntu, Azure Linux, Windows Server                 | [Node images](https://cloud.google.com/kubernetes-engine/docs/concepts/node-images): Container-Optimized OS, Ubuntu, Windows Server                                             |
| AI/ML acceleratorML and AI-specific hardware resources | GPUs                                                | [GPUs](https://cloud.google.com/kubernetes-engine/docs/concepts/gpus), [Cloud TPUs](https://cloud.google.com/kubernetes-engine/docs/concepts/tpus)                              |
| Confidential computing                                 | Intel SGX based enclaves                            | [Confidential GKE Nodes](https://cloud.google.com/kubernetes-engine/docs/how-to/confidential-gke-nodes)                                                                         |
| Container Storage Interface                            | Azure Disks driver                                  | [Persistent Disks, Google Cloud Hyperdisks, Local SSDs](https://cloud.google.com/kubernetes-engine/docs/concepts/storage-overview)                                              |
|                                                        | Azure Files driver                                  | [GKE Filestore driver](https://cloud.google.com/kubernetes-engine/docs/concepts/filestore-for-gke)                                                                              |
|                                                        | Azure Blob storage driver                           | [Cloud Storage FUSE](https://cloud.google.com/storage/docs/gcs-fuse)                                                                                                            |
| Workload authentication                                | Microsoft Entra Workload ID                         | Workload Identity Federation for GKE                                                                                                                                            |

The following table helps you map source environment-specific features such as
AKS add-ons, extensions, and integrations to suitable alternative GKE solutions:

| AKS Add-on, extension, or integration name                       | Alternative GKE solution                                                                                                                                                                                      | Management model               |
| :--------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :----------------------------- |
| Web application routing (managed NGINX ingress controller) addon | GKE Gateway controller                                                                                                                                                                                        | Google-managed                 |
|                                                                  | GKE Ingress                                                                                                                                                                                                   | Google-managed                 |
|                                                                  | [Custom Ingress controller](https://cloud.google.com/kubernetes-engine/docs/how-to/custom-ingress-controller)                                                                                                 | Self-managed                   |
| Application Gateway Ingress Controller addon                     | GKE Gateway controller                                                                                                                                                                                        | Google-managed                 |
|                                                                  | GKE Ingress                                                                                                                                                                                                   | Google-managed                 |
| Kubernetes Event-driven Autoscaling (KEDA) addon                 | [Cluster autoscaling](https://cloud.google.com/kubernetes-engine/docs/concepts/cluster-autoscaler), [node auto-provisioning](https://cloud.google.com/kubernetes-engine/docs/concepts/node-auto-provisioning) | Google-managed                 |
| Azure Monitor, Azure Monitor Logs, Container Insights            | [Cloud Logging, Cloud Monitoring](https://cloud.google.com/kubernetes-engine/docs/concepts/observability)                                                                                                     |                                |
| Managed Prometheus monitoring addon                              | [Managed Service for Prometheus](https://cloud.google.com/stackdriver/docs/managed-prometheus)                                                                                                                | Google-managed                 |
| Azure Policy for AKS addon                                       | [Policy Controller](https://cloud.google.com/kubernetes-engine/enterprise/policy-controller/docs/overview)                                                                                                    | Google-managed or self-managed |
| Azure Key Vault Secrets Provider addon                           | [Secret Managed add-on](https://cloud.google.com/secret-manager/docs/secret-manager-managed-csi-component)                                                                                                    | Google-managed                 |
| Open Service Mesh addon                                          | [Cloud Service Mesh](https://cloud.google.com/service-mesh/docs/overview)                                                                                                                                     | Google-managed or self-managed |
| Dapr extension                                                   | [Set up Dapr on GKE](https://docs.dapr.io/operations/hosting/kubernetes/cluster/setup-gke/)                                                                                                                   | Self-managed                   |
| Azure App Configuration extension                                | [Config Sync](https://cloud.google.com/kubernetes-engine/enterprise/config-sync/docs/overview)                                                                                                                | Google-managed                 |
| Azure Machine Learning extension                                 | [AI/ML orchestration on GKE](https://cloud.google.com/kubernetes-engine/docs/integrations/ai-infra)                                                                                                           | N/A                            |
| Flux extension                                                   | Config Sync                                                                                                                                                                                                   | Google-managed                 |
| Azure Container Storage extension                                | [Storage for GKE clusters](https://cloud.google.com/kubernetes-engine/docs/concepts/storage-overview)                                                                                                         | Google-managed                 |
| Azure Backup for AKS extension                                   | [Backup for GKE](https://cloud.google.com/kubernetes-engine/docs/add-on/backup-for-gke/concepts/backup-for-gke)                                                                                               | Google-managed                 |
| AKS integration with Azure Event Grid                            | [GKE integration with Pub/Sub](https://cloud.google.com/kubernetes-engine/docs/concepts/cluster-notifications)                                                                                                | Google-managed                 |
| Helm integration                                                 | [Store Helm charts in Artifact Registry](https://cloud.google.com/artifact-registry/docs/helm/store-helm-charts)                                                                                              | Self-managed                   |
| Prometheus integration                                           | Managed Service for Prometheus                                                                                                                                                                                | Google-managed                 |
|                                                                  | [Prometheus Helm chart](https://github.com/prometheus-community/helm-charts)                                                                                                                                  | Self-managed                   |
| Grafana integration                                              | [Deploy Grafana on Kubernetes](https://grafana.com/docs/grafana/latest/installation/kubernetes/)                                                                                                              | Self-managed                   |
| Couchbase integration                                            | [Install the Couchbase Operator on Kubernetes](https://docs.couchbase.com/operator/current/install-kubernetes.html)                                                                                           | Self-managed                   |
| OpenFaaS integration                                             | [Deploy OpenFaaS to Kubernetes](https://docs.openfaas.com/deployment/kubernetes/)                                                                                                                             | Self-managed                   |
| Apache Spark integration                                         | [Run Apache Spark on Kubernetes](https://spark.apache.org/docs/latest/running-on-kubernetes.html)                                                                                                             | Self-managed                   |
| Istio integration                                                | [Setup Istio on GKE](https://istio.io/latest/docs/setup/platform-setup/gke/)                                                                                                                                  | Self-managed                   |
| Linkerd integration                                              | [Install Linkerd](https://linkerd.io/2.15/tasks/install/), and [configure it for GKE](https://linkerd.io/2.15/reference/cluster-configuration/)                                                               | Self-managed                   |
| Consul integration                                               | [Deploy Consul on GKE](https://developer.hashicorp.com/consul/tutorials/archive/kubernetes-gke-google)                                                                                                        | Self-managed                   |

In the deployment phase, you do the following:

1.  Provision and configure your GKE environment.
1.  Configure your GKE clusters.
1.  Refactor your workloads.
1.  Refactor deployment and operational processes.
1.  Migrate data from your source environment to Google Cloud.
1.  Deploy your workloads in your GKE environment.
1.  Validate your workloads and GKE environment.
1.  Expose workloads running on GKE.
1.  Shift traffic from the source environment to the GKE environment.
1.  Decommission the source environment.

### Provision and configure your Google Cloud environment

Before moving any workload to your new Google Cloud environment, you provision
the GKE clusters.

GKE supports enabling certain features on existing clusters, but there might be
features that you can only enable at cluster creation time. To help you avoid
disruptions and simplify the migration, we recommend that you enable the cluster
features that you need at cluster creation time. Otherwise, you might need to
destroy and recreate your clusters in case the cluster features you need cannot
be enabled after creating a cluster.

After the assessment phase, you now know how to provision the GKE clusters in
your new Google Cloud environment to meet your needs. To provision your
clusters, consider the following:

- The number of clusters, the number of nodes per cluster, the types of
  clusters, the configuration of each cluster and each node, and the
  [scalability plans of each cluster](https://cloud.google.com/kubernetes-engine/docs/concepts/planning-scalability).
- The mode of operation of each cluster. GKE offers two modes of operation for
  clusters: GKE Autopilot and GKE Standard.
- The number of
  [private clusters](https://cloud.google.com/kubernetes-engine/docs/how-to/private-clusters).
- The choice between
  [VPC-native or router-based networking](https://cloud.google.com/kubernetes-engine/docs/concepts/types-of-clusters#vpc-clusters).
- The
  [Kubernetes versions and release channels](https://cloud.google.com/kubernetes-engine/docs/concepts/release-channels)
  that you need in your GKE clusters.
- The node pools to logically group the nodes in your GKE clusters, and if you
  need to automatically create node pools with
  [node auto-provisioning](https://cloud.google.com/kubernetes-engine/docs/how-to/node-auto-provisioning).
- The initialization procedures that you can port from your environment to the
  GKE environment and new procedures that you can implement. For example, you
  can
  [automatically bootstrap GKE nodes](https://cloud.google.com/kubernetes-engine/docs/tutorials/automatically-bootstrapping-gke-nodes-with-daemonsets)
  by implementing one or multiple, eventually privileged, initialization
  procedures for each node or node pool in your clusters.
- The scalability plans for each cluster.
- The additional GKE features that you need, such as Cloud Service Mesh, and GKE
  add-ons, such as
  [Backup for GKE](https://cloud.google.com/kubernetes-engine/docs/add-on/backup-for-gke/concepts/backup-for-gke).

For more information about provisioning GKE clusters, see:

- [About cluster configuration choices](https://cloud.google.com/kubernetes-engine/docs/concepts/types-of-clusters).
- [Manage, configure, and deploy GKE clusters](https://cloud.google.com/kubernetes-engine/docs/how-to/).
- Understanding
  [GKE security](https://cloud.google.com/kubernetes-engine/docs/concepts/security-overview).
- [Harden your cluster's security](https://cloud.google.com/kubernetes-engine/docs/how-to/hardening-your-cluster).
- [GKE networking overview](https://cloud.google.com/kubernetes-engine/docs/concepts/network-overview).
- [Best practices for GKE networking](https://cloud.google.com/kubernetes-engine/docs/best-practices/networking).
- [Storage for GKE clusters overview](https://cloud.google.com/kubernetes-engine/docs/concepts/storage-overview).

#### Fleet management

When you provision your GKE clusters, you might realize that you need a large
number of them to support all the use cases of your environment. For example,
you might need to separate production from non-production environments, or
separate services across teams or geographies. For more information, see
[multi-cluster use cases](https://cloud.google.com/kubernetes-engine/fleet-management/docs/multi-cluster-use-cases).

As the number of clusters increases, your GKE environment might become harder to
operate because managing a large number of clusters poses significant
scalability and operational challenges. GKE provides tools and features to help
you manage _fleets_, a logical grouping of Kubernetes clusters. For more
information, see
[Fleet management](https://cloud.google.com/kubernetes-engine/docs/fleets-overview).

#### Multi-cluster networking

To help you improve the reliability of your GKE environment, and to distribute
your workloads across several GKE clusters, you can use:

- Multi-Cluster Services, a cross-cluster service discovery and invocation
  mechanism. Services are discoverable and accessible across GKE clusters. For
  more information, see
  [Multi-Cluster Services](https://cloud.google.com/kubernetes-engine/docs/concepts/multi-cluster-services).
- Multi-cluster gateways, a cross-cluster ingress traffic load balancing
  mechanism. For more information, see
  [Deploying multi-cluster Gateways](https://cloud.google.com/kubernetes-engine/docs/how-to/deploying-multi-cluster-gateways).
- Multi-cluster mesh on managed Cloud Service Mesh. For more information, see
  [Set up a multi-cluster mesh](https://cloud.google.com/service-mesh/docs/operate-and-maintain/multi-cluster).

For more information about migrating from a single-cluster GKE environment to a
multi-cluster GKE environment, see
[Migrate to multi-cluster networking](https://cloud.google.com/kubernetes-engine/docs/how-to/migrate-gke-multi-cluster).

### Configure your GKE clusters

After you provision your GKE clusters and before deploying any workload or
migrating data, you configure namespaces, RBAC, network policies, service
accounts, and other Kubernetes and GKE objects for each GKE cluster.

To configure Kubernetes and GKE objects in your GKE clusters, we recommend that
you:

1.  Ensure that you have the necessary credentials and permissions to access
    both the clusters in your source environment, and in your GKE environment.
1.  Assess if the objects in the Kubernetes clusters your source environment are
    compatible with GKE, and how the implementations that back these objects
    differ from the source environment and GKE.
1.  Refactor any incompatible object to make it compatible with GKE, or retire
    it.
1.  Create these objects to your GKE clusters.
1.  Configure any additional objects that your need in your GKE clusters.

#### Config Sync

To help you adopt [GitOps](https://opengitops.dev/) best practices to manage the
configuration of your GKE clusters as your GKE scales, we recommend that you use
[Config Sync](https://cloud.google.com/kubernetes-engine/enterprise/config-sync/docs/overview),
a GitOps service to deploy configurations from a source of truth. For example,
you can store the configuration of your GKE clusters in a Git repository, and
use Config Sync to apply that configuration.

For more information, see
[Config Sync architecture](https://cloud.google.com/kubernetes-engine/enterprise/config-sync/docs/concepts/architecture).

#### Policy Controller

Policy Controller helps you apply and enforce programmable policies to help
ensure that your GKE clusters and workloads run in a secure and compliant
manner. As your GKE environment scales, you can use Policy Controller to
automatically apply policies, policy bundles, and constraints to all your GKE
clusters. For example, you can restrict the repositories from where container
images can be pulled from, or you can require each namespace to have at least
one label to help you ensure accurate resource consumption tracking.

For more information, see
[Policy Controller](https://cloud.google.com/kubernetes-engine/enterprise/policy-controller/docs/overview).

### Refactor your containerized workloads

A best practice to design containerized workloads is to avoid dependencies on
the container orchestration platform. This might not always be possible in
practice due to the requirements and the design of your workloads. For example,
your workloads might depend on environment-specific features that are available
in your source environment only, such as add-ons, extensions, and integrations.

Although you might be able to migrate most workloads as-is to GKE, you might
need to spend additional effort to refactor workloads that depend on
environment-specific features, in order to minimize these dependencies,
eventually switching to alternatives that are available on GKE.

To refactor your workloads before migrating them to GKE, you do the following:

1.  Review source environment-specific features, such as add-ons, extensions,
    and integrations.
1.  Adopt suitable alternative GKE solutions.
1.  Refactor your workloads.

#### Review source environment-specific features

If you're using source environment-specific features, and your workloads depend
on these features, you need to:

1.  Find suitable alternatives GKE solutions.
1.  Refactor your workloads in order to make use of the alternative GKE
    solutions.

As part of this review, we recommend that you do the following:

- Consider whether you can deprecate any of these source environment-specific
  features.
- Evaluate how critical a source environment-specific feature is for the success
  of the migration.

#### Adopt suitable alternative GKE solutions

After you reviewed your source environment-specific features, and mapped them to
suitable GKE alternative solutions, you adopt these solutions in your GKE
environment. To reduce the complexity of your migration, we recommend that you
do the following:

- Avoid adopting alternative GKE solutions for source environment-specific
  features that you aim to deprecate.
- Focus on adopting alternative GKE solutions for the most critical source
  environment-specific features, and plan dedicated migration projects for the
  rest.

#### Refactor your workloads

While most of your workloads might work as is in GKE, you might need to refactor
some of them, especially if they depended on source environment-specific
features for which you adopted alternative GKE solutions.

This refactoring might involve:

- Kubernetes object descriptors, such as Deployments, and Services expressed in
  YAML format.
- Container image descriptors, such as Dockerfiles and Containerfiles.
- Workloads source code.

To simplify the refactoring effort, we recommend that you focus on applying the
least amount of changes that you need to make your workloads suitable for GKE,
and critical bug fixes. You can plan other improvements and changes as part of
future projects.

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

#### Adopt Google Cloud provisioning tools

In your Azure environment, you might be using Azure-specific provisioning and
configuration tools. The following table helps you map AKS provisioning tools to
similar Google Cloud provisioning tools:

| AKS                    | GKE                                                                                     |
| :--------------------- | :-------------------------------------------------------------------------------------- |
| Azure CLI              | [Google Cloud CLI](https://cloud.google.com/sdk/gcloud)                                 |
| Azure PowerShell       | [Cloud Client Libraries](https://cloud.google.com/apis/docs/cloud-client-libraries)     |
| Azure Portal           | Cloud Console                                                                           |
| Azure Resource Manager | [Infrastructure Manager](https://cloud.google.com/infrastructure-manager/docs/overview) |
| Terraform              | [Terraform](https://cloud.google.com/docs/terraform/terraform-overview)                 |

If you’re using any of these provisioning tools in your automated deployment and
operational processes, you need to refactor these processes to provision GKE
resources in your Google Cloud environment instead of provisioning AKS resources
in your Azure environment.

### Migrate data

GKE supports several data storage services, such as block storage, raw block
storage, file storage, and object storage. For more information, see
[Storage for GKE clusters overview](https://cloud.google.com/kubernetes-engine/docs/concepts/storage-overview).

To migrate data to your GKE environment, you do the following:

1.  Provision and configure all necessary storage infrastructure.
1.  Configure
    [StorageClass provisioners](https://kubernetes.io/docs/concepts/storage/storage-classes/#provisioner),
    in your GKE clusters. Not all StorageClass provisioners are compatible with
    all environments. Before deploying a StorageClass provisioner, we recommend
    that you evaluate its compatibility with GKE, and its dependencies.
1.  Configure StorageClasses.
1.  Configure PersistentVolumes and PersistentVolumeClaims to store the data to
    migrate.
1.  Migrate data from your source environment to these PersistentVolumes. The
    specifics of this data migration depend on the characteristics of the source
    environment.

To migrate data from your source environment to your Google Cloud environment,
we recommend that you design a data migration plan by following the guidance in
[Migrate to Google Cloud: Transfer large datasets](https://cloud.google.com/architecture/migration-to-google-cloud-transferring-your-large-datasets).

#### Migrate data from AKS to GKE

Azure provides several data storage options for AKS. This document focuses on
the following data migration scenarios:

- Migrate data from Azure Disks volumes to GKE PersistentVolume resources.
- Migrate data from Azure Files to Filestore.
- Migrate data from Azure NetApp Files to NetApp Cloud Volumes Service.

#### Migrate data from Azure Disks volumes to GKE PersistentVolume resources

You can migrate data from Azure Disks volumes to GKE PersistentVolume resources
by adopting one of the following approaches:

- Directly copy data from Azure Disks volumes to Compute Engine persistent
  disks:
    1.  Provision Azure Virtual Machines instances and attach the Azure Disks
        volumes that contain the data to migrate.
    1.  Provision Compute Engine instances with empty persistent disks that have
        sufficient capacity to store the data to migrate.
    1.  Run a data synchronization tool, such as rsync, to copy data from the
        Azure Disks volumes to the Compute Engine persistent disks.
    1.  Detach the persistent disks from the Compute Engine instances.
    1.  Decommission the Compute Engine instances.
    1.  Configure the persistent disks as GKE PersistentVolume resources.

- Migrate Azure Virtual Machines instances and Azure Disks volumes to Compute
  Engine:
    1.  Provision Azure Virtual Machines instances and attach the Azure Disks
        volumes that contain the data to migrate.
    1.  Migrate the Azure Virtual Machines instances and the Azure Disks volumes
        to Compute Engine with Migrate for Virtual Machines.
    1.  Detach the persistent disks from the Compute Engine instances.
    1.  Decommission the Compute Engine instances.
    1.  Configure the persistent disks as GKE PersistentVolume resources.

- Copy data from Azure Disks volumes to an interim media, and migrate to GKE
  PersistentVolumes:
    1.  Upload data from Azure Disks volumes to an interim media such as an
        Azure Blob Storage bucket or a Cloud Storage bucket.
    1.  Download the data from the interim media to your GKE PersistentVolume
        resources.

For more information about migrating Azure Virtual Machines instances to Compute
Engine, see
[Migrate from Azure Virtual Machines to Compute Engine](./migrate-from-azure-vms-to-compute-engine.md).

For more information about migrating from Azure Blob Storage to Cloud Storage,
see
[Migrate from Azure Blob Storage to Cloud Storage](./migrate-from-azure-blob-storage-to-cloud-storage.md).

For more information about using Compute Engine persistent disks as GKE
PersistentVolume resources, see
[Using pre-existing persistent disks as PersistentVolumes](https://cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/preexisting-pd).

##### Choose a migration option

The best migration option for you depends on your specific needs and
requirements, such as the following considerations:

- The amount of data that you need to migrate.
    - If you have a small amount of data to migrate, such as a few data files,
      consider tools like rsync to copy the data directly to Compute Engine
      persistent disks. This option is relatively quick, but it might not be
      suitable for a large amount of data.
    - If you have a large amount of data to migrate, consider using
      [Migrate to Virtual Machines](https://cloud.google.com/migrate/virtual-machines)
      to migrate the data to Compute Engine. This option is more complex than
      directly copying data, but it's more reliable and scalable.

- The type of data that you need to migrate.
- Your network connectivity between the source and the target environments.
    - If you can't establish direct network connectivity between your Azure
      Virtual Machines and Compute Engine instances, you might want to consider
      using Azure Blob Storage or Cloud Storage to store the data temporarily
      while you migrate it to Compute Engine. This option might be less
      expensive because you won't have to keep your Azure Virtual Machines and
      Compute Engine instances running simultaneously.

- Your migration timeline.
    - If you have limited network bandwidth or a large amount of data, and your
      timeline isn't tight, you can also consider using a
      [Transfer Appliance](https://cloud.google.com/transfer-appliance) to move
      your data from Azure to Google Cloud.

No matter which option you choose, it's important that you test your migration
before you make it live. Testing will help you to identify any potential
problems and help to ensure that your migration is successful.

#### Migrate data from Azure Files to Filestore

Filestore supports copying data from several sources to Filestore file shares.
For example, you can copy data from a Cloud Storage bucket or a computer in your
environment to a Filestore file share.

To migrate data from Azure Files file shares to Filestore file shares, you do
the following for each Azure Files file share to migrate:

1.  Provision an Azure Virtual Machine.
1.  Mount the Azure Files file share on the Azure Virtual Machine.
1.  Provision a Compute Engine instance.
1.  [Mount the Filestore file share on the Compute Engine instance](https://cloud.google.com/filestore/docs/mounting-fileshares).
1.  [Configure a Storage Transfer Service job](https://cloud.google.com/storage-transfer/docs/file-to-file)
    between the Azure Files file share and the Filestore file share.
1.  Wait for the job to complete.
1.  Unmount the Filestore file share from the Compute Engine instance.
1.  [Configure your GKE clusters to access the Filestore file share](https://cloud.google.com/filestore/docs/filestore-for-gke).

### Deploy your workloads

When your deployment processes are ready, you deploy your workloads to GKE. For
more information, see
[Overview of deploying workloads](https://cloud.google.com/kubernetes-engine/docs/how-to/deploying-workloads-overview).

To prepare the workloads to deploy for GKE, we recommend that you analyze your
Kubernetes descriptors because some Google Cloud resources that GKE
automatically provisions for you are configurable by using Kubernetes
[labels](https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/)
and
[annotations](https://kubernetes.io/docs/concepts/overview/working-with-objects/annotations/),
instead of having to manually provision these resources. For example, you can
provision an
[internal load balancer](https://cloud.google.com/load-balancing/docs/internal/)
instead of an external one by
[adding an annotation to a LoadBalancer Service](https://cloud.google.com/kubernetes-engine/docs/how-to/internal-load-balancing#overview).

### Validate your workloads

After you deploy workloads in your GKE environment, but before you expose these
workloads to your users, we recommend that you perform extensive validation and
testing. This testing can help you verify that your workloads are behaving as
expected. For example, you may:

- Perform integration testing, load testing, compliance testing, reliability
  testing, and other verification procedures that help you ensure that your
  workloads are operating within their expected parameters, and according to
  their specifications.
- Examine logs, metrics, and error reports in
  [Cloud Observability Suite](https://cloud.google.com/stackdriver/docs) to
  identify any potential issues, and to spot trends to anticipate problems
  before they occur.

For more information about workload validation, see
[Testing for reliability](https://sre.google/sre-book/testing-reliability/).

### Expose your workloads

Once you complete the validation testing of the workloads running in your GKE
environment, expose your workloads to make them reachable.

To expose workloads running in your GKE environment, you can use Kubernetes
Services, and a service mesh.

For more information about exposing workloads running in GKE, see:

- [About Services](https://cloud.google.com/kubernetes-engine/docs/concepts/service)
- [About service networking](https://cloud.google.com/kubernetes-engine/docs/concepts/service-networking)
- [About Gateway](https://cloud.google.com/kubernetes-engine/docs/concepts/gateway-api)

### Shift traffic to your Google Cloud environments

After you have verified that the workloads are running in your GKE environment,
and after you have exposed them to clients, you shift traffic from your source
environment to your GKE environment. To help you avoid big-scale migrations and
all the related risks, we recommend that you gradually shift traffic from your
source environment to your GKE.

Depending on how you designed your GKE environment, you have several options to
implement a load balancing mechanism that gradually shifts traffic from your
source environment to your target environment. For example, you may implement a
DNS resolution policy that resolves DNS records according to some policy to
resolve a certain percentage of requests to IP addresses belonging to your GKE
environment. Or you can implement a load balancing mechanism using virtual IP
addresses and network load balancers.

After you start gradually shifting traffic to your GKE environment, we recommend
that you monitor how your workloads behave as their loads increase.

Finally, you perform a _cutover_, which happens when you shift all the traffic
from your source environment to your GKE environment.

For more information about load balancing, see
[Load balancing at the frontend](https://sre.google/sre-book/load-balancing-frontend/).

### Decommission the source environment

After the workloads in your GKE environment are serving requests correctly, you
decommission your source environment.

Before you start decommissioning resources in your source environment, we
recommend that you do the following:

- Back up any data to help you restore resources in your source environment.
- Notify your users before decommissioning the environment.

To decommission your source environment, do the following:

1.  Decommission the workloads running in the clusters in your source
    environment.
1.  Delete the clusters in your source environment.
1.  Delete the resources associated with these clusters, such as security
    groups, load balancers, and virtual networks.

To avoid leaving orphaned resources, the order in which you decommission the
resources in your source environment is important. For example, certain
providers require that you decommission Kubernetes Services that lead to the
creation of load balancers before being able to decommission the virtual
networks containing those load balancers.

## Optimize your environment

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
[Google Cloud Well-Architected Framework: Performance optimization](https://cloud.google.comarchitecture/framework/performance-optimization/).

### Establish your optimization requirements

Optimization requirements help you narrow the scope of the current optimization
iteration. For more information about optimization requirements and goals, see
[Establish your optimization requirements and goals](https://cloud.google.com/architecture/migration-to-google-cloud-optimizing-your-environment#establish_your_optimization_requirements_and_goals).

To establish your optimization requirements for your GKE environment, start by
consider the following aspects:

- **Security, privacy, and compliance**: help you enhance the security posture
  of your GKE environment.
- **Reliability**: help you improve the availability, scalability, and
  resilience of your GKE environment.
- **Cost optimization**: help you optimize the resource consumption and
  resulting spending of your GKE environment.
- **Operational efficiency**: help you maintain and operate your GKE environment
  efficiently.
- **Performance optimization**: help you optimize the performance of the
  workloads deployed in your GKE environment.

#### Security, privacy, and compliance

- **Monitor the security posture of you GKE clusters.** You can use the
  [security posture dashboard](https://cloud.google.com/kubernetes-engine/docs/concepts/about-security-posture-dashboard)
  to get opinionated, actionable recommendations to help you improve the
  security posture of your GKE environment.
- **Harden your GKE environment.** Understand the
  [GKE security model](https://cloud.google.com/kubernetes-engine/docs/concepts/security-overview),
  and how to harden
  [harden your GKE clusters](https://cloud.google.com/kubernetes-engine/docs/how-to/hardening-your-cluster).
- **Protect your software supply-chain.** For security-critical workloads,
  Google Cloud provides a modular set of products that implement
  [software supply chain security](https://cloud.google.com/software-supply-chain-security/docs/overview)
  best practices across the software lifecycle.

#### Reliability

- **Improve the reliability of your clusters.** To help you design a GKE cluster
  that is more resilient to unlikely zonal outages, prefer
  [regional clusters](https://cloud.google.com/kubernetes-engine/docs/concepts/regional-clusters)
  over zonal or multi-zonal ones.

- **Workload backup and restore.** Configure a workload backup and restore
  workflow with
  [Backup for GKE](https://cloud.google.com/kubernetes-engine/docs/add-on/backup-for-gke/concepts/backup-for-gke).

#### Cost optimization

For more information about optimizing the cost of your GKE environment, see:

- [Right-size your GKE workloads at scale](https://cloud.google.com/kubernetes-engine/docs/tutorials/right-size-workloads-at-scale).
- [Reducing costs by scaling down GKE clusters during off-peak hours](https://cloud.google.com/kubernetes-engine/docs/tutorials/reducing-costs-by-scaling-down-gke-off-hours).
- [Identify idle GKE clusters](https://cloud.google.com/kubernetes-engine/docs/how-to/idle-clusters).

#### Operational efficiency

To help you avoid issues that affect your production environment, we recommend
that you:

- **Design your GKE clusters to be fungible.** By considering your clusters as
  fungible and by automating their provisioning and configuration, you can
  streamline and generalize the operational processes to maintain them and also
  simplify future migrations and GKE cluster upgrades. For example, if you need
  to upgrade a fungible GKE cluster to a new GKE version, you can automatically
  provision and configure a new, upgraded cluster, automatically deploy
  workloads in the new cluster, and decommission the old, outdated GKE cluster.
- **Monitor metrics of interest.** Ensure that all the metrics of interest about
  your workloads and clusters are properly collected. Also, verify that all the
  relevant alerts that use these metrics as inputs are in place, and working.

For more information about configuring monitoring, logging, and profiling in
your GKE environment, see:

- [Observability for GKE](https://cloud.google.com/kubernetes-engine/docs/concepts/observability)
- [GKE Cluster notifications](https://cloud.google.com/kubernetes-engine/docs/concepts/cluster-notifications)

#### Performance optimization

- **Set up cluster autoscaling and node auto-provisioning.** Automatically
  resize your GKE cluster according to demand by using
  [cluster autoscaling](https://cloud.google.com/kubernetes-engine/docs/concepts/cluster-autoscaler)
  and
  [node auto-provisioning](https://cloud.google.com/kubernetes-engine/docs/concepts/node-auto-provisioning).
- **Automatically scale workloads.** GKE supports several scaling mechanisms,
  such as:
    - Automatically scale workloads
      [based on metrics](https://cloud.google.com/kubernetes-engine/docs/concepts/custom-and-external-metrics).
    - Automatically scale workloads by changing the shape of the number of Pods
      your Kubernetes workloads by configuring
      [Horizontal Pod autoscaling](https://cloud.google.com/kubernetes-engine/docs/concepts/horizontalpodautoscaler).
    - Automatically scale workloads by adjusting resource requests and limits by
      configuring
      [Vertical Pod autoscaling](https://cloud.google.com/kubernetes-engine/docs/concepts/verticalpodautoscaler).

For more information, see
[About GKE scalability](https://cloud.google.com/kubernetes-engine/docs/best-practices/scalability).

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

Authors:

- [Marco Ferrari](https://www.linkedin.com/in/ferrarimark) | Cloud Solutions
  Architect
- Xiang Shen | Cloud Solutions Architect
- Ido Flatow | Cloud Solutions Architect
