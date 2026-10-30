---
name: app-migration-orchestrator
description: >-
  Orchestrates the Amazon Elastic Kubernetes Service (EKS) to Google Kubernetes Engine (GKE) migration
  for the AppDev or DevOps persona. Coordinates application-specific discovery, manifest translation,
  and deployment to GKE using platform and workload handoffs from the platform operator.
  Use when orchestrating the end-to-end application migration pipeline.
  Don't use for cluster-level VPC network creation or platform-wide infrastructure assessment.
---

# Application migration orchestrator

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

You are a DevOps engineer or developer responsible for a specific application's
migration from Amazon Elastic Kubernetes Service (EKS) to Google Kubernetes
Engine (GKE). You assume the necessary infrastructure in the Google Cloud
environment (VPC, GKE Clusters, Workload Identity Pool) is already setup and
verified.

## Purpose

Take an application team from "our service is on EKS" to "our service is
deployed on GKE" by running the application migration orchestrator skill graph.
Consumes `platform-handoff.json` and `workload-handoff.json` to ensure alignment
with organizational infrastructure.

## When to use this skill

Trigger on:

- "Migrate our application from EKS to GKE"
- "Translate our Helm charts and migrate the workloads to GKE"
- "Run the application migration phase for the namespace"

Do NOT trigger when:

- The platform handoff metadata (`platform-handoff.json`) or workload handoff
  metadata (`workload-handoff.json`) is not available.
- You need to provision GKE clusters, VPCs, subnets, or register GKE Workload
  Identity Pools (refer the user to the platform engineering team or the
  `platform-orchestrator` skill).
- The task is a platform-wide EKS estate discovery or global infrastructure
  assessment (refer the user to the `eks-discovery` skill).

## Prerequisites

- `python3` version 3.10 or later
- Install dependencies listed in `scripts/requirements.txt`
- Ensure you have run the localized pre-flight environment setup and validation
  checklist as documented in
  [references/preflight_validation.md](references/preflight_validation.md) to
  initialize the virtual environment (`scripts/.venv`).

## Assets & References

The following schema files under `assets/schemas/` define the JSON contracts
used by this skill:

- `platform-handoff.schema.json`: Schema for validating platform infrastructure
  handoffs.
- `workload-handoff.schema.json`: Schema for cluster-level workload handoff
  specifications.
- `workload-handoff-namespace.schema.json`: Schema for namespace-level workload
  handoff specifications.
- `identity-map.schema.json`: Schema for ServiceAccount identity mappings.
- `image-map.schema.json`: Schema for container image repository mappings.
- `network-map.schema.json`: Schema for ingress and network policy mappings.
- `observability-map.schema.json`: Schema for metrics and observability
  mappings.
- `storage-map.schema.json`: Schema for StorageClass mappings.

The following reference documents under `references/` provide validation and
translation guidance:

- [references/api-translation.md](references/api-translation.md): Annotation and
  API resource translation rules.
- [references/preflight_validation.md](references/preflight_validation.md):
  Environment initialization and preflight validation checklist.

Before starting Phase 1 of the app migration, the orchestrator gathers the input
configuration and writes the state and file paths to
`00-app-migration-state.json`:

1.  **Platform Handoff**
    - Path to `platform-handoff.json` (required). This file contains the target
      VPCs, Cluster Names, and Workload Identity Pool URLs.
    - Path to `image-map.json` (required). This file contains the mapping of EKS
      container images to Artifact Registry target paths.
2.  **App Scope** (Defines the input workloads and manifests to migrate):
    - Migration Scope (Cluster-level vs Namespace-level).
    - Namespace(s) or labels identifying the application workloads in EKS.
    - Source Manifests location: either a Git repository URL/branch, or a path
      to raw EKS manifests/YAMLs on the local host.
3.  **Translation Map Paths** (Tracks the paths of maps generated during Phase
    2):
    - Path to `identity-map.json` (output from identity-translation).
    - Path to `network-map.json` (output from network-translation).
    - Path to `storage-map.json` (output from storage-translation).
    - Path to `observability-map.json` (output from observability-translation).

## Procedure

### Step 1 — Verify Platform Readiness

1.  Read `platform-handoff.json`.
2.  Run pre-flight validation on the handoff files provided by the platform
    operator:

    ```bash
    scripts/.venv/bin/python3 scripts/validate_platform_readiness.py \
      --handoff-dir "${HANDOFF_DIR}" \
      --raw-manifests-dir "${RAW_MANIFESTS_DIR}"
    ```

3.  Confirm readiness with the user.

### Step 2 — Phase 1: Discover (App Scope)

1.  Verify the presence of `image-map.json` provided by the platform operator.
2.  Perform validation checks to verify that all target Artifact Registry images
    listed in `image-map.json` exist and are accessible from the host
    environment.

### Step 3 — Phase 2: Validate Translation Mappings

Run the translation sub-skills in sequence to validate the completeness of the
mapping files provided by the platform operator:

1.  **`identity-translation`**: Validate EKS KSA to GSA target identity mappings
    in `identity-map.json`.
2.  **`network-translation`**: Validate AWS ALB ingress classes and domain
    settings in `network-map.json`.
3.  **`storage-translation`**: Validate StorageClass mappings in
    `storage-map.json`.
4.  **`observability-translation`**: Validate prometheus scraping mappings in
    `observability-map.json`.

### Step 4 — Phase 3: Workload Assembly & Dry-run

1.  **`workload-translation`**: Ingest the generated map files
    (`image-map.json`, `identity-map.json`, `network-map.json`,
    `storage-map.json`, `observability-map.json`) and apply them to the raw
    manifests/charts located in the source directory (either the cloned
    repository or the path provided by the operator).
2.  **LLM-based Post-Processing**: Read the output YAML files in the
    workspace-local `./translated-manifests` directory and use your LLM
    capabilities to clean up EKS-specific properties, finalizers, and AWS
    annotations using `references/api-translation.md` as standard rules. Ensure
    all EKS runtime metadata (e.g. `creationTimestamp`, `uid`,
    `resourceVersion`), ECR config, AWS finalizers, and Karpenter taints are
    stripped or mapped to GKE target properties.

    > [!IMPORTANT]
    >
    > Always write the translated manifests to a workspace-local directory
    > (e.g., `./translated-manifests`). Do not write output files or run cleanup
    > commands (such as `rm -rf`) on paths outside the repository workspace.
    >
    > You MUST perform these cleanups directly on the generated YAML files using
    > your file editing tools. Do NOT create helper scripts (such as Python or
    > Bash scripts) to automate this cleanup.

3.  **Wait for Post-Processing Completion**: You MUST ensure that the LLM
    post-processing changes to the YAML manifests are fully written and saved
    before proceeding to the validation step.
4.  **Validate GKE Manifests**: Validate the post-processed GKE manifests using
    the helper script:

    ```bash
    scripts/.venv/bin/python3 scripts/validate_manifests.py --manifests-dir ./translated-manifests
    ```

## Outputs / Deliverables

- `00-app-migration-summary.md`: Summary of the migrated application, endpoints,
  and status.
- `translated-manifests/`: Final GKE-ready YAML.

## Escalation triggers

- **Identity Mismatch**: The app requires a permission that the
  `platform-handoff.json` explicitly forbids or doesn't support.
- **Network Isolation**: The app cannot reach a required legacy service in AWS
  VPC from the GKE Shared VPC.
