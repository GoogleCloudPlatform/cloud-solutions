---
name: validation
description: >-
  Validates all consolidated migration artifacts including Terraform code, per-cluster JSON maps, target Kubernetes manifests, and AWS namespace exclusions.
  Use when validating migration outputs prior to infrastructure deployment or handing off deliverables to operators and developers.
  Don't use for applying Terraform configurations or deploying application workloads into live clusters.
---

# Migration deliverables validation

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

You validate all consolidated output artifacts generated during an Amazon EKS to
Google Kubernetes Engine (GKE) migration program. You ensure that Terraform
infrastructure code, per-cluster mapping JSON files, and target Kubernetes
application manifests are complete, schema-compliant, and free of AWS-specific
system resources.

## Purpose

Provide a single, hyper-rigorous validation gate before platform infrastructure
is deployed or handed off to application developers.

## When to use this skill

- Validate consolidated migration deliverables in `<output_dir>/` after running
  the specialist migration skills or `platform-orchestrator`.
- Verify schema compliance across all 7 mapping JSON files under
  `maps/<cluster_name>/`.
- Confirm that `terraform validate` passes cleanly for consolidated
  infrastructure under `terraform/`.
- Ensure AWS-specific system namespaces (`amazon-*`, `aws-*`, `kube-*`, `eks-*`)
  are completely excluded from target application manifests under `manifests/`.

## Don't use for

- Applying Terraform configurations or provisioning target cloud infrastructure
  (follow `deployment-instructions.md` manually or via deployment automation).
- Mirroring container images or applying application manifests to live clusters.

## Prerequisites

- Required CLI tools installed and authenticated: `check-jsonschema`,
  `terraform`, `kubectl`.
- Consolidated migration outputs directory populated with `terraform/`,
  `maps/<cluster_name>/`, and `manifests/<cluster_name>/`.

## Validation checklist

Perform the following checks to validate the migration outputs. You may use any
available read-only tools or CLI commands to verify these conditions.

### 1. Terraform validity and infrastructure audit

- [ ] **HCL Validation**: Run `terraform validate` (after
      `terraform init -backend=false`) in the `terraform/` directory and ensure
      it passes cleanly.
- [ ] **Workload Identity Syntax**: Inspect `workload-identity.tf` (or
      equivalent) to verify that Workload Identity bindings use the correct
      Google Cloud format:
      `serviceAccount:<project_id>.svc.id.goog[<namespace>/<ksa_name>]`.
- [ ] **Google Cloud IAM Assignments**: Verify that Google Service Accounts
      (GSAs) have appropriate IAM roles assigned (e.g.,
      `roles/storage.objectViewer`) corresponding to their discovered AWS
      permissions.
- [ ] **GKE Node Permissions**: Verify the custom node service account has at
      least `roles/artifactregistry.reader` (or `grant_registry_access`),
      `roles/logging.logWriter`, and `roles/monitoring.metricWriter`.
- [ ] **Artifact Registry Repository**: Verify that `artifact-registry.tf` (or
      equivalent) defines the required Artifact Registry repository resources
      matching the migration plan.
- [ ] **Fleet Membership**: Verify that the cluster is registered to a Fleet
      (`google_gke_hub_membership`) unless explicitly waived.
- [ ] **Binary Authorization**: Verify that Binary Authorization is enabled
      (`google_container_cluster.binary_authorization`) in audit or enforcement
      mode.
- [ ] **Maintenance Policy**: Verify that `maintenance_policy` is defined with
      exclusion windows protecting critical business hours.
- [ ] **Master Authorized Networks**: Verify that
      `master_authorized_networks_config` is configured and not exposed to
      `0.0.0.0/0` (unless explicitly waived).

### 2. JSON schema compliance

Validate all mapping files in `<output_dir>/workload-handoff/<cluster>/maps/`
(or `<output_dir>/maps/<cluster>/`) against their schemas in `assets/schemas/`
(located at the root of the project).

- [ ] **`platform-handoff.json`**: Passes schema validation.
- [ ] **`workload-handoff.json`**: Passes schema validation.
- [ ] **`network-map.json`**: Passes schema validation.
- [ ] **`identity-map.json`**: Passes schema validation.
- [ ] **`storage-map.json`**: Passes schema validation.
- [ ] **`image-map.json`**: Passes schema validation.
- [ ] **`observability-map.json`**: Passes schema validation.

### 3. Application manifests and exclusion audit

Audit `<output_dir>/workload-handoff/<cluster>/manifests/` (or
`<output_dir>/manifests/<cluster>/`).

- [ ] **System Namespace Exclusion**: Confirm ZERO directories or manifests
      belong to AWS or Kubernetes system namespaces (`amazon-cloudwatch`,
      `aws-system`, `kube-system`, `kube-public`, `kube-node-lease`,
      `eks-system`).
- [ ] **Empty Namespace Exclusion**: Confirm that namespaces with zero
      application workloads (e.g., an empty `default` namespace) are omitted.
- [ ] **Namespace Resource Presence**: Each workload namespace directory
      contains a valid `namespace.yaml`.
- [ ] **ReplicaSet Exclusion**: No `replicasets.yaml` files exist (deployments
      handle ReplicaSet lifecycle).
- [ ] **1:1 Raw Integrity**: Verify manifests are an exact 1:1 untranslated copy
      from `01-discovery/raw/manifests/` (aside from exclusions above). They
      must NOT contain premature Google Cloud translations (e.g., no image
      rewrites, no Gateway translations yet).

### 4. Cluster-scoped primitives audit

- [ ] **StorageClass Translation**: Verify
      `<output_dir>/cluster-manifests/<cluster>/storageclasses.yaml` defines
      Google Cloud storage provisioners (e.g., `pd.csi.storage.gke.io`) and
      contains NO AWS EBS CSI provisioners (`ebs.csi.aws.com`).

## Remediation and reporting

1.  **Record Findings**: Document the status of each check.
2.  **Autonomous Remediation**: If a check fails, identify the root cause and
    apply the appropriate remediation (e.g., regenerate a map, fix a path, or
    edit a configuration). You may choose the best method to resolve the issue.
3.  **Validation Report**: Generate a summary report in
    `<output_dir>/09-validation/validation-report.md` listing all checks and
    their outcomes.
