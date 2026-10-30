---
name: gke-landing-zone
description: >-
  Designs and provisions the Google Cloud target environment for an Amazon Elastic Kubernetes Service (EKS) migration using Terraform. Use when setting up the Google Kubernetes Engine (GKE) landing zone or target infrastructure. Don't use for applying Terraform configuration or upgrading existing landing zones.
---

<!--
 Copyright 2026 Google LLC
 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at
      https://www.apache.org/licenses/LICENSE-2.0
 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
-->

# GKE landing zone

<!--
  Disabling markdownlint MD029 to provide explicit ordering to avoid
  confusing the LLM.
-->
<!-- markdownlint-disable MD029 -->

<!--
    Disabling markdownlint MD030 to allow the list overflowing to numbers
    >=10.
-->
<!-- markdownlint-disable MD030 -->

You are a Google Cloud landing-zone architect. Build the target environment from
published Google-maintained Terraform registry modules and write up the design.
Do not apply Terraform. Hand the plan to a human. Two rules:

1.  Reuse over authorship. If a registry module can create a resource, use the
    module. Raw resources are limited to the short list below.
2.  Build only what the migration needs. Scope comes from the inventory and the
    readiness report.

## Prerequisites

- Target Google Cloud project IDs with billing enabled. This skill creates no
  projects and no folders.
- `01-discovery/inventory.json` and a `escalation.md` with zero FAIL rows.
- `02-assessment/scorecard.json` and `readiness-report.md`. Node bounds,
  availability targets, and data dependencies feed the cluster sizing.
- The operator holds Owner or equivalent on each target project.
- `terraform`, `gcloud`, and `kubectl` installed locally. Stop if any
  prerequisite is missing and tell the operator which one. Ensure you are
  authenticated by running `gcloud auth application-default login` and
  `gcloud auth login`. Verify tools are working by running `terraform version`,
  `gcloud --version`, and `kubectl version --client`.

## Module sources

Refer to the module sources in
[Module sources reference](references/module_sources.md).

> [!IMPORTANT]
>
> **Provider version constraints** When generating `main.tf`, you MUST
> dynamically fetch and specify the required provider versions for both
> `hashicorp/google` and `hashicorp/google-beta` by inspecting the Terraform
> Registry metadata of the pinned Google-maintained modules, such as
> `kubernetes-engine`. Do not hardcode the entire bound, but DO ensure the
> minimum provider version is at least `>= 6.0` while respecting the module's
> upper bound, for example, `< 8.0.0`, to ensure compatibility and access to
> recent features. Ensure that you generate a Terraform dependency lock file
> (`.terraform.lock.hcl`). Raw `google_*` resources are allowed for org
> policies, the Key Management Service (KMS) keyring and key when
> Customer-Managed Encryption Keys (CMEK) is on, and fleet membership and
> features when a decision names them. Nothing else. If a module input falls
> short, record the gap in `design-decisions.md` and raise it. Do not fork the
> module.

## Procedure

### Step 1 — Confirm the design inputs

Walk the Decision points table with the user. Confirm each default or record the
deviation with its reason. Then, explicitly use the `ask_question` tool to
collect the following inputs:

1.  Target Google Cloud project ID and target region for the landing zone.

### Step 2 — IP plan

GKE secondary ranges cannot change after cluster creation, and overlap with the
source estate prevents future hybrid connectivity. Treat this as the one
irreversible decision. It goes to the human in the Step 3 review with the
verification work shown.

1.  Build the exclusion set from the inventory's `clusters[].network` arrays:
    `vpc_cidrs`, `subnet_cidrs`, `peered_cidrs`, `tgw_route_cidrs`, plus the EKS
    `service_cidr`. If the inventory lacks the network block, read the raw VPC,
    subnet, peering, and route dumps under `01-discovery/raw/`. If the VPC
    Classless Inter-Domain Routing (CIDR) is still missing, stop and ask the
    user to provide the source CIDRs (the discovery phase must be updated to
    capture this).
2.  Propose per environment: a nodes range, a /16 pods range, a /20 services
    range, and one unique master /28 per cluster. Allocate the /28s here.
3.  Write a verification table into `landing-zone-plan.md` with one row per
    proposed range against every exclusion CIDR and every other proposed range.

### Step 3 — Draft the plan and decision documents. The gate

Write the first half of both documents (`landing-zone-plan.md` and
`design-decisions.md`) before any Terraform. Refer to the Outputs section for
the detailed contents of each document. Stop for human approval. Several GKE
features can only be set at cluster creation, so changes after this point mean a
rebuild.

### Step 4 — Project readiness

The projects already exist. You MUST explicitly run the following command using
the terminal BEFORE running any `terraform` commands, as missing APIs will cause
the apply to fail:

```bash
gcloud services enable compute.googleapis.com container.googleapis.com cloudresourcemanager.googleapis.com
```

Then, configure the `project_services` submodule using the template in
`assets/project-services.tf`. Enable `cloudkms.googleapis.com` only when CMEK is
on. You must also enable `cloudresourcemanager.googleapis.com` and
`serviceusage.googleapis.com` out-of-band using `gcloud` prior to running
`terraform plan` when using organization metadata data sources.

### Step 5 — VPC

Instantiate one Shared VPC network module in the host project, per the network
scope decision. Feed subnets and secondary ranges from the approved IP plan in
`landing-zone-plan.md`. Enable Private Google Access and flow logs through the
module inputs. Add Cloud NAT, Cloud Router, and the baseline firewall rules
through the companion submodules: deny inbound public, allow Identity-Aware
Proxy (IAP), allow the Google health-check ranges.

### Step 6 — Clusters

Create one module instantiation per cluster. Autopilot environments use
`beta-autopilot-private-cluster`. Standard environments use `safer-cluster`,
which already carries the hardening defaults: Shielded nodes, Workload Identity,
private nodes, a dedicated node service account, release channel. CRITICAL: You
MUST explicitly set `create_service_account = true` to provision a dedicated
least-privilege GKE Node Service Account, `grant_registry_access = true` to
automatically grant `roles/artifactregistry.reader` access to Artifact Registry
repositories, `private_cluster_config { enable_private_nodes = true }` to comply
with `constraints/compute.vmExternalIpAccess` org policies, and
`enable_secure_boot = true` in the module inputs for node pools to prevent
`constraints/compute.requireShieldedVm` org policy violations during creation.
Workload Identity bindings MUST set
`depends_on = [google_container_cluster.primary]` to ensure the identity pool is
initialized before member bindings are applied. Configure through inputs only.
Before writing the Terraform cluster blocks, you MUST read the module variable
definitions. Do not hallucinate module inputs. Only use variables that are
explicitly defined in those schemas.

Use the skeletons provided in `assets/beta-autopilot-private-cluster.tf` (for
Autopilot) and `assets/safer-cluster.tf` (for Standard) as a starting point.
Every other input keeps the module default unless a confirmed decision overrides
it. Node pools on Standard mirror the discovery node groups: taints, labels, and
autoscaling bounds plus 20 percent. Set CMEK and Binary Authorization inputs
only when the confirmed decisions turned them on. Register the cluster with
`google_gke_hub_membership` by default. If a confirmed decision names a fleet
feature, enable only that feature (e.g., Config Sync for a GitOps estate, Policy
Controller for a Gatekeeper estate). Walk Google's current cluster-hardening
checklist at
<https://docs.cloud.google.com/kubernetes-engine/docs/how-to/hardening-your-cluster>
and record in `landing-zone-plan.md` any control the module inputs do not
already satisfy. Do not copy the checklist into this skill.

### Step 7 — Identity and Access Management (IAM) and Organization Policy

- IAM: bind the Step 1 groups with `google_project_iam_member` at the project
  level. Never bind individuals directly to project roles. If IAM groups need to
  be provisioned, never hardcode customer IDs or user email addresses. Instead,
  declare input variables for `domain_name` and `admin_user_email`, retrieve the
  customer ID dynamically using
  `data "google_organization" "org" { domain = var.domain_name }`, and provision
  parameterized `google_cloud_identity_group` and
  `google_cloud_identity_group_membership` resources (specifying both `"MEMBER"`
  and `"OWNER"` role blocks for `var.admin_user_email` to satisfy Cloud Identity
  API requirements). To prevent Application Default Credentials (ADC) quota
  errors (403 SERVICE_DISABLED) during Cloud Identity group provisioning, ensure
  both `google` and `google-beta` provider blocks include
  `user_project_override = true` and `billing_project = var.project_id`. Ensure
  `google_project_iam_member` resources explicitly depend on group creation.
  Namespaces, quotas, and Role-Based Access Control (RBAC) belong to
  `identity-translation`.
- Org policy, raw resources, project level only: deny external IPs, require
  Shielded VMs, disable service account key creation, enforce uniform
  bucket-level access. Add data-residency constraints only when a confirmed
  decision names them. Folder and org level policy belongs to whoever owns the
  org.
- When CMEK is on, create one KMS keyring and key per environment. No other
  skill creates them. The cluster and storage CMEK hooks both consume them.
- Alert policies, dashboards, and metrics scopes belong to
  `observability-translation`.

### Step 8 — Finalize and hand off

Run the structural checks, format the code, and run a credentialed plan:

```bash
terraform fmt -recursive
terraform init -upgrade
terraform validate
terraform plan -out=tfplan
```

Once the plan is generated, explicitly use the `ask_question` tool to ask the
user if they want to deploy the Terraform to the Google Cloud project. If they
answer yes, execute `terraform apply "tfplan"`. Write the `backend "gcs"` block
into every root module. The README tells the human to create the versioned state
bucket once before the first real apply, and to pre-check quotas: regional node
pools need roughly 300 GB Solid State Drive (SSD) quota, and per-minute API
quotas throttle large applies. Re-check every CIDR in the final Terraform
variables against the exclusion set and append the results to the verification
table. The generated values must match the approved plan. Finish
`landing-zone-plan.md` with the hardening notes from Step 6 and a short plan
summary covering projects, networks, clusters, bindings, and policies. Finish
`design-decisions.md` with anything that changed during generation.

## Decision points

Refer to the decision points in
[Decision points reference](references/decision_points.md).

## Outputs

- `03-landing-zone/landing-zone-plan.md`: Covers what the landing zone is.
  Includes project layout and cluster facts (sized from inventory plus 20%
  headroom), the IP plan (with exclusion set and verification table), the
  post-apply acceptance checklist, and a Mermaid diagram of the project layout,
  VPC, and clusters.
- `03-landing-zone/design-decisions.md`: Covers why. Includes each decision
  (question, answer, reason), pinned module versions, and any module gap
  escalations.
- `03-landing-zone/terraform/envs/<env>/main.tf`: Module instantiations and
  backend.
- `03-landing-zone/terraform/README.md`: How to plan and apply.

## Validation

Before handoff the agent checks:

- Every CIDR in the final Terraform variables appears in the verification table
  with an `ok` verdict.
- `terraform init -backend=false`, `terraform validate`, and
  `terraform fmt -check` run clean with pinned module versions resolving. After
  the human applies, the acceptance checklist in `landing-zone-plan.md` covers:
- `kubectl get ns` succeeds against each cluster.
- Workload Identity and Dataplane V2 show enabled in
  `gcloud container clusters describe`.

## Escalation triggers

- The exclusion set is empty or discovery output is missing. Stop and ask for
  the source CIDRs.
- No free range of the required size exists given the exclusion set. A human
  chooses between renumbering and NAT.
- A required capability has no registry module input. Record the gap in
  `design-decisions.md` and raise it. Do not fork the module.
- Compliance scope this skill cannot validate against public guidance. Stop and
  produce a gap doc.
