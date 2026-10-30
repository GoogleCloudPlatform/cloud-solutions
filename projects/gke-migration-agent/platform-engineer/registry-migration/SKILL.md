---
name: registry-migration
description: >-
  Migrates container images from Amazon Elastic Container Registry (ECR) to Google Artifact Registry.
  Use when the user asks to "migrate ECR to Artifact Registry", "set up image registries on Google Cloud", or as Phase 3 of a Google Kubernetes Engine (GKE) migration.
---

# Registry Migration

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

You move container images from ECR to Artifact Registry, set up vulnerability
scanning, update build pipelines, and produce a mapping file the rest of the
orchestration uses to rewrite image references.

## Purpose

Every container image referenced from any Kubernetes workload has to be
reachable from GKE — preferably from a regional Artifact Registry — at low
latency, with vulnerability scanning, and, when in scope, with Binary
Authorization attestations.

## Prerequisites

- **Context Dependencies:** `platform-handoff.json` and
  `01-discovery/inventory.json` must exist in the `<RUN_DIR>`.
- **Infrastructure:** `03-landing-zone/plan.md` with the `artifact-registry`
  shared project provisioned.
- **Tools:** `gcloud`, `aws`, `gcrane`, and `jq` must be installed.
- **Authentication:** Credentials for both AWS ECR and Google Artifact Registry
  must be configured.
- **Failure Handling:** If any of these tools are missing or authentication
  fails, inform the user and request they install the tools or authenticate
  before proceeding.

## Procedure

### Step 1 — Plan the Artifact Registry (AR) repo layout

Default layout:
`projects/artifact-registry/locations/<region>/repositories/<repo-name>` Naming:
one AR repository per ECR repository, same name. Multi-region repos for global
distribution if cross-region pulls matter.

Decide repo format:

- **Standard repository**: contains images directly. One per environment and
  team is the typical shape.
- **Virtual repository**: aggregates upstream registries.
- **Remote repository**: mirrors a single upstream such as Docker Hub or NPM.

For this migration:

- Plan a _standard_ AR repo per ECR repo, in the user's primary region, for
  example, `us-central1`.
- Plan a _remote_ repo for `docker.io` and `quay.io` if the workloads pull
  public images directly.

### Step 2 — Provision AR repos

Generate Terraform per repo into `<OUTPUT_DIR>/terraform/artifact-registry.tf`
using the template provided in `assets/artifact-registry.tf.template`, which is
relative to this skill's directory.

### Step 3 — Mirror images and build the mirror plan

1.  **Filter Application Images**: Ensure that you strictly migrate application
    workload images. Do NOT migrate proprietary AWS infrastructure images such
    as `kube-proxy`, `aws-ebs-csi-driver`, `aws-load-balancer-controller`,
    `amazon-k8s-cni`, or `karpenter`. These must be filtered out as GKE uses its
    own managed components.
2.  Run the image migration script to copy images while preserving digests and
    generate the mapping file. Replace `<SKILL_DIR>` with the absolute path to
    this skill:

    ```bash
    <SKILL_DIR>/scripts/migrate_images.sh <RUN_DIR> <OUTPUT_DIR> [aws_profile]
    ```

### Step 4 — Update build pipelines

For each upstream pipeline, plan a dual-push co-existence period:

- **CodeBuild / CodePipeline**: add a parallel push step that pushes to AR using
  a service account key or, preferably, federated identity into Google Cloud.
- **Cloud Build / Cloud Deploy**: built-in push to AR.
- **Tekton**: add a second `image-push` task targeting AR.

Produce a checklist `<OUTPUT_DIR>/pipelines.md` listing every pipeline, the
change to make, and the verification step.

### Step 5 — Vulnerability scanning + Binary Authorization

Enable Artifact Analysis on the AR project. Surface findings in
`<OUTPUT_DIR>/vuln-baseline.md`.

For Binary Authorization, when in scope:

1. Plan an attestor in `<OUTPUT_DIR>/binauthz/`.
2. Plan an attestation policy on the cluster, starting in `EVALUATION` mode.
3. Wire CI to attest on push, for example, using Cloud Build built-in support or
   `cosign sign`.

### Step 6 — Cutover and decommission plan

Produce `<OUTPUT_DIR>/ecr-decommission.md`:

- Per-repo decommission date, default to 30 days post final cutover.
- Final image archive plan.
- IAM cleanup plan.

## Decision points

| Decision             | Default                          | When to deviate                               |
| -------------------- | -------------------------------- | --------------------------------------------- |
| AR repo structure    | One AR repo per ECR repo         | Restructure if ECR layout was painful         |
| Region               | Same region as primary GKE       | Multi-region replication for >2 regions       |
| Pull-through caches  | `docker.io`, `quay.io`           | Skip if you mirror everything explicitly      |
| Cleanup policy       | Keep 100 + delete untagged > 30d | Tighter, such as 10 most recent, for non-prod |
| Binary Authorization | `EVALUATION` mode initially      | `ENFORCE` mode only after >2 weeks cleanly    |

## Outputs / Deliverables

The output artifacts correspond to the inline steps above. Ensure they are
placed in `<OUTPUT_DIR>`.

## Validation

- Every image referenced by any translated workload exists in AR with matching
  digest.
- `gcloud container images describe <full-ref>` succeeds for every image in
  `image-map.json`.
- A test pod on GKE successfully pulls a representative image without auth
  issues, for example, KSA → GSA with `roles/artifactregistry.reader` on the AR
  project.

## Escalation triggers

- ECR images in repos using lifecycle rules whose retention exceeds AR cleanup
  policies.
- Images larger than AR's per-image limits.
- Cross-cloud egress costs from initial mirror exceed tolerance.
- ECR repos referenced by workloads in _another_ AWS account.

## Common pitfalls

- **Pushing without preserving digests.** Re-built images get new digests and
  break digest-pinned deployments.
- **Forgetting Workload Identity → AR reader.** GSAs that pull from AR need
  `roles/artifactregistry.reader`.
- **Pipelines that hardcode AWS region in image refs.**
- **Pull-through caches that tag-pin.**
- **Not seeding the cache.**
