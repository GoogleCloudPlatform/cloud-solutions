# GKE Migration Agent

Agent Skills for migrating Amazon Elastic Kubernetes Service (EKS) workloads to
Google Kubernetes Engine (GKE) and upgrading GKE networking.

## Overview

The GKE Migration Agent is a set of Agent Skills that an AI agent can load to
migrate workloads from Amazon EKS to GKE, as well as optimize GKE resources.

The skills are structured as follows:

- **EKS to GKE Workload Migration**: Grouped by persona:
    - **Platform Engineer**: Focus on cluster-wide discovery, infrastructure
      inventory, identity federation, and landing zone preparation.
    - **Application Developer (App Dev)**: Focus on migrating individual
      application workloads (Deployments, StatefulSets, DaemonSets, Jobs) within
      assigned namespaces or clusters using structured handoff artifacts.
- **GKE Resource Optimization**: Independent skills for optimizing and upgrading
  networking resources inside existing GKE environments.

Skills operate on the Amazon Web Services (AWS) and Kubernetes APIs read-only
during discovery, and on Google Cloud during the translation and build phases.
The skills do not modify the source environment.

## Prerequisites

- An agent runtime that supports the Agent Skills format
- AWS Command Line Interface (CLI) v2 configured with a named profile that has
  read-only access to the source AWS account and Amazon EKS clusters (required
  for EKS to GKE migration). The profile must have at least the following
  Identity and Access Management (IAM) permissions:
    - `eks:ListClusters`
    - `eks:DescribeCluster`
    - `eks:ListNodegroups`
    - `eks:DescribeNodegroup`
    - `iam:GetRole`
    - `iam:ListAttachedRolePolicies`
    - `iam:ListRolePolicies`
- `kubectl` v1.33 or later, configured for each in-scope cluster
- `gcloud` v480.0.0 or later
- `python3` 3.13 or later
- `gcloud` CLI for Google Cloud identity and cluster interactions

### Setting up AWS credentials

You must instruct the agent to configure a dedicated read-only AWS profile
before starting. You can have the agent create one and set it as its active
profile by asking it to run the following commands:

```bash
aws configure --profile eks-migration-readonly
export AWS_PROFILE=eks-migration-readonly
```

Provide the agent with the Access Key ID and Secret Access Key for an IAM
identity that has the permissions listed above. The agent uses the
`eks-migration-readonly` profile during execution.

## Getting started

Place the skills where the agent runtime discovers them. Trigger a skill with a
natural-language request that matches its description. The agent selects the
skill. You do not invoke it by name.

### Migration Workflow & Handoff

1.  **Platform Engineer Phase**: The platform operator runs estate discovery and
    assessment (`eks-discovery` and `migration-assessment`). This generates the
    migration inventory and produces two core handoff files:

    - `platform-handoff.json`: Contains target GKE cluster, VPC, and Workload
      Identity Pool infrastructure metadata.
    - `workload-handoff.json`: Contains application workload metadata and
      cluster/namespace specifications.

1.  **App Dev Phase**: The application developer or DevOps engineer consumes
    `platform-handoff.json` and `workload-handoff.json` using
    `app-migration-orchestrator` and `app-dev` skills to translate application
    workloads, images, ingress, storage, and identity configurations to GKE.

### Example Prompts by Persona

#### Platform Engineer Persona

```text
Help me assess our EKS cluster estate, discover workloads, and generate platform-handoff.json and workload-handoff.json for GKE migration.
```

#### App Dev / DevOps Persona

```text
Migrate our application workloads defined in workload-handoff.json and platform-handoff.json from EKS to GKE Autopilot manifests.
```

### EKS to GKE Migration Skills

<!-- markdownlint-disable MD024 -->

### Platform Engineer (`platform-engineer/`)

#### **`eks-discovery`**

Inventory an Amazon EKS estate end-to-end. Use this skill when starting an
Amazon EKS to Google Kubernetes Engine (GKE) migration, or when generating a
pre-migration inventory.

#### **`gke-landing-zone`**

Designs and provisions the Google Cloud target environment for an Amazon EKS
migration using Terraform.

#### **`identity-translation`**

Translates AWS IAM policies and IAM Roles for Service Accounts (IRSA) service
account bindings to Google Cloud Workload Identity Google Service Accounts
(GSAs) and IAM member bindings.

#### **`migration-assessment`**

Evaluate Amazon EKS workloads and analyze migration readiness. Use this skill to
process the outputs of the `eks-discovery` skill and generate the migration
assessment.

#### **`network-translation`**

Translates Amazon EKS ingress and network architecture to GKE Gateway API, Cloud
Armor Web Application Firewall (WAF) security policies, and Cloud DNS private
zones.

#### **`observability-translation`**

Translates AWS CloudWatch alarms, metrics, and logs to Google Cloud Managed
Service for Prometheus, Cloud Logging, and Cloud Monitoring alert policies.

#### **`platform-orchestrator`**

Orchestrates the end-to-end EKS-to-GKE migration pipeline across all discovery,
assessment, translation, landing zone, and validation phases.

#### **`registry-migration`**

Migrates container images from Amazon Elastic Container Registry (Amazon ECR) to
Google Cloud Artifact Registry and updates image references in Kubernetes
manifests.

#### **`storage-translation`**

Translates Amazon EKS storage classes and PersistentVolumeClaims to GKE
persistent disks (`pd-balanced` with `pd.csi.storage.gke.io`).

#### **`validation`**

Validates all consolidated migration artifacts including Terraform code,
per-cluster JSON maps, target Kubernetes manifests, pre-deployment identity
permissions, and AWS namespace exclusions.

### Application Developer (`app-dev/`)

#### **`app-migration-execution`**

Apply translated GKE application manifests and coordinate storage provisioning,
data migration, and workload exposure in a strict sequence with state
persistence and recovery.

#### **`app-migration-orchestrator`**

Orchestrates the EKS-to-GKE migration for the AppDev or DevOps persona.
Coordinates application-specific discovery, manifest translation, and deployment
to GKE, using the verified platform and workload handoffs from the platform
operator.

#### **`identity-translation`**

Translate EKS IAM Roles for Service Accounts (IRSA) configurations to GKE
Workload Identity configurations. Maps Kubernetes ServiceAccounts (KSAs) to
Google Service Accounts (GSAs).

#### **`network-translation`**

Translate EKS ALB Ingress annotations and AWS WAF configurations into GKE
Gateway API resources, Cloud Armor policies, and Google Cloud Backend Policies.

#### **`observability-translation`**

Translate Prometheus scrape annotations into GKE Managed Service for Prometheus
(GMP) PodMonitoring Custom Resources, and map AWS CloudWatch metric configs to
Google Cloud Monitoring.

#### **`storage-translation`**

Translate EKS PersistentVolumeClaims and StorageClasses to GKE-compatible PV/PVC
resources and GKE StorageClasses. Supports mapping block-level GP2/GP3 to
Persistent Disks and EFS to GKE Filestore.

#### **`workload-translation`**

Translates EKS application workload manifests (Deployments, StatefulSets,
DaemonSets, CronJobs, Jobs, ReplicaSets) from `workload-handoff.json`
(cluster-level or namespace-level tenancy) into GKE Autopilot or GKE Standard
Kubernetes manifests. It handles annotation stripping, Workload Identity
Federation (WIF) binding, security context adjustments, and compatibility
readiness checks.

<!-- markdownlint-enable MD024 -->

## GKE Optimization Skills

### `ingress2gateway`

Automates the discovery, analysis, risk-profiling, and translation of legacy GKE
and NGINX Ingress resources into GKE Gateway API specifications using the
`ingress2gateway` tool. It generates a migration analysis report, validates
manifests with dry-run checks, and requires interactive operator sign-off before
applying changes.
