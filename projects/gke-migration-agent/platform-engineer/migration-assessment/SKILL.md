---
name: migration-assessment
description: >-
  Evaluates an Amazon Elastic Kubernetes Service (EKS) estate's readiness for migration to Google Kubernetes Engine (GKE). Generates a graded readiness report with blockers, risk ratings, and a phased plan. Use when assessing migration readiness.
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

# Migration assessment

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

You are a migration architect. Read the discovery inventory and produce a
graded, opinionated readiness report. Your output represents the document a
migration consultant would write after week one.

## Purpose

Convert the raw inventory into a decision-ready document. This document includes
a scorecard, blockers list, per-workload risk ratings, a phased plan, and an
effort estimate.

## When to use this skill

- To assess an Amazon Elastic Kubernetes Service (EKS) estate's readiness for
  migration to Google Kubernetes Engine (GKE).
- To analyze raw discovery inventory and identify migration blockers.
- To generate a phased migration plan, effort estimates, and workload risk
  scores.

## Prerequisites

- The following files from the discovery phase must exist in the input
  directory:
    - `<output_dir>/01-discovery/inventory.json`
    - `<output_dir>/01-discovery/irsa-map.tsv`
    - `<output_dir>/01-discovery/inventory-summary.md`
    - `<output_dir>/01-discovery/workload-handoffs/` (directory containing
      per-namespace workload data)
- The `check-jsonschema` CLI tool must be installed and available in the
  environment.
- If the executing agent does not find these prerequisites, it must halt
  execution and report the missing requirements to the user.

## Procedure

### Step 1 — Load inputs

Read `<output_dir>/01-discovery/inventory.json`,
`<output_dir>/01-discovery/irsa-map.tsv`,
`<output_dir>/01-discovery/inventory-summary.md`, and the namespace workload
files under `<output_dir>/01-discovery/workload-handoffs/`. Build a structured
model: clusters → namespaces → workloads → dependencies.

### Step 2 — Score each workload

Score every workload in the namespace workload files under
`<output_dir>/01-discovery/workload-handoffs/` on four axes using the following
0-3 scale. **Architectural Rule:** You MUST base your scores strictly on the
data present in the `workload-handoff.json` structures (e.g., the `storage`,
`services`, `ingresses`, and `data_dependencies` arrays) and the `irsa-map.tsv`
file. Do not hallucinate dependencies that are not listed in these files.

- **Statelessness:**
    - Ready: Fully stateless.
    - Tractable: Ephemeral state or easily reproducible cache.
    - High-risk: Stateful with ReadWriteOnce (RWO) or ReadWriteMany (RWX)
      PersistentVolumeClaims (PVCs). These require cross-cloud backup/restore
      such as Velero and impose cutover downtime proportional to data gravity.
    - Blocked: Tied to local hostPath or specific node hardware.
- **Identity portability:**
    - Ready: No Amazon Web Services (AWS) Identity and Access Management (IAM)
      dependency.
    - Tractable: Basic AWS IAM usage that can be entirely replaced by standard
      Google Cloud IAM (e.g., simple data-plane access like S3 GetObject or SQS
      ReceiveMessage). _Note: Review the extracted IAM inline and attached
      policy JSON files to verify if the usage is truly basic (limited scope, no
      complex cross-service dependencies). If you cannot definitively verify,
      default to High-risk._
    - High-risk: Relies on IAM Roles for Service Accounts (IRSA) to access
      services staying in AWS (e.g., DynamoDB). This requires complex
      cross-cloud Workload Identity Federation (OIDC) to retain AWS access.
    - Blocked: Hardcoded credentials or unsupported built-in AWS IAM
      integrations.
- **Network portability:**
    - Ready: Standard ClusterIP/NodePort.
    - Tractable: Standard generic LoadBalancer or simple Ingress without
      specific cloud annotations.
    - High-risk: Relies heavily on AWS Load Balancer Controller
      (`alb.ingress.kubernetes.io/*`) annotations or AWS Security Groups for
      Pods.
    - Blocked: Deeply coupled to AWS Virtual Private Cloud (VPC) Container
      Network Interface (CNI) built-in IP routing features or custom AWS
      networking.
- **Data dependencies:**
    - Ready: No external data dependencies.
    - Tractable: Querying an AWS managed database such as RDS from GKE over a
      VPN/Interconnect without moving the database itself.
    - High-risk: Actively migrating data sinks, for example RDS to Cloud SQL or
      DynamoDB to Bigtable, alongside the cluster migration. This requires
      dedicated database migration tools, such as DMS, and extensive cutover
      planning.
    - Blocked: Explicit notes in `inventory-summary.md` indicating strict
      latency limits or unmigratable hardware dependencies that prevent a phased
      cross-cloud migration.

**Important Note on Data Dependencies:** Because the discovery script
intentionally does not extract plaintext Kubernetes Secrets, `data_dependencies`
will often be empty. If you cannot detect stateful mappings, you MUST default to
**Score 1** (not Score 3) to prevent false confidence, and add a standard Risk
Guardrail in the report that states: "Stateful database mappings must be
validated offline via source code review."

After determining the scores for each axis, use the following simple integer
logic to assign the overall readiness bucket (do not use division or decimals):

1. **Blocked:** If **ANY** axis scores a `0`, the workload is immediately
   Blocked, regardless of the other scores.
2. Otherwise, calculate the **Sum** of all 4 axes (which will be between 4 and
   12):
    - **Ready (Sum 10 - 12):** Low risk, fits standard automated migration
      templates.
    - **Tractable (Sum 7 - 9):** Translatable with explicit custom plan;
      requires infrastructure translation, but application logic changes are
      unlikely.
    - **High-Risk (Sum 4 - 6):** Requires dry-runs, extra API validation, or
      rebuilding sub-components.

### Step 3 — Cluster-level scoring

Aggregate workload scores per cluster, plus add cluster-level signals to detect
platform-level version drift:

- **Control Plane Version Drift**: Compare the discovered EKS version against
  current GKE-supported versions to identify drift that requires an upgrade path
  prior to migration.
- **CRD & Operator Density**: Count custom CRDs/Operators in use (more equals
  more manual YAML translation work).
- **DaemonSets**: High counts of platform-level DaemonSets increase parallel
  infrastructure configuration overhead.
- **Authentication Mappings**: Identify if the cluster uses the legacy
  `CONFIG_MAP` mode (`aws-auth`). Flag it for transition to GKE IAM/Role-Based
  Access Control (RBAC).
- **Secrets Parity**: Check if Key Management Service (KMS) envelope encryption
  is enabled in EKS to plan matching GKE KMS encryption.

### Step 4 — Identify blockers

Walk the cluster-level escalations in `<output_dir>/01-discovery/inventory.json`
and the workload scoring. Identify active blockers by checking against the
common blockers. Propose appropriate mitigation recommendations. For example:

- **AWS VPC CNI specific features or Custom CNI** -> Migrate to GKE Dataplane V2
  default (or Cilium-on-GKE if eBPF API parity is strictly required).
- **hostNetwork: true Workloads** -> Re-host on GKE using identical node-host
  tolerations; validate via canary namespaces.
- **RWX PVCs not backed by EFS** -> Identify custom CSI and map to Google Cloud
  Filestore Enterprise or NetApp Volumes.
- **Karpenter custom NodePools** -> Translate EKS taints/labels to GKE Node
  Pools or GKE Node Auto-Provisioning (NAP) rules.
- **Federated SSO via AWS IAM Identity Center** -> Re-platform to GKE Workforce
  Identity Federation.
- **Compliance Scope (FedRAMP/HIPAA)** -> Verify all GCP target service mapping
  regions are in compliance scope; flag variables immediately.

### Step 5 — Effort profiling

Profile the effort required based on the workload buckets determined in Step 2.
Create a concrete, itemized To-Do list of the foreseen technical tasks required
for this migration based on the workloads you analyzed.

Explicitly show the workload counts (e.g., 10 Ready, 5 Tractable) alongside the
To-Do list of foreseen tasks in the effort profile section of the final report
so the customer can determine the effort themselves.

### Step 6 — Phased plan

Produce a recommended phased plan according to the structure in the template.

Since you do not have the user's target migration window, provide a generic
relative sequence (e.g., Phase 1: Foundation and internal tools, Phase 2:
Stateless business apps, Phase 3: Stateful and mission-critical apps).

**CRITICAL REQUIREMENT:** Do not output a generic boilerplate plan. You MUST map
the actual discovered namespaces and named workloads into these generic phases
based on their dependency graphs and risk scores (e.g., "Phase 2: Migrate
`payment-service` and `user-service`").

### Step 7 — Risks and guardrails

For each named risk, propose a guardrail:

- "RDS to Cloud SQL homogeneous move replication lag during cutover" →
  guardrail: replication-lag SLO, pause if > 30s for 5 minutes.
- "Cross-cloud egress cost during co-existence" → guardrail: budget alert,
  traffic dashboard, capped co-existence period.
- "Workload Identity (WI) binding drift" → guardrail: Continuous Integration
  (CI) check that compares IRSA to WI map to daily live state.
- "GKE cluster cost overrun versus EKS baseline" → guardrail: monthly FinOps
  review and an auto-scaler tuning playbook.

### Step 8 — Compose the report and scorecard

Render the deliverables listed in the **Outputs** section below from their
respective templates in `assets/` such as `assets/readiness-report-template.md`
and `assets/blockers-template.md`.

Additionally, generate a structured `scorecard.json` file in
`<output_dir>/02-assessment/`. This JSON must include:

- A full dump of the scoring rubric and the final assessment for each workload.
- The 0-3 scores for each workload across all four axes, **including a brief
  `reasoning` string explaining why that score was given**.
- The readiness buckets assigned to each workload.
- The recommended GKE mode (`Autopilot` vs `Standard`) and `version_drift`
  details.
- The derived GKE node pool requirements.
- Extracted cluster sizing metrics needed for the landing zone, such as EKS node
  group / Karpenter taints, labels, and baseline autoscaling minimum/maximum
  bounds.
- Validation: Run
  `check-jsonschema --schemafile assets/scorecard.schema.json <output_dir>/02-assessment/scorecard.json`
  to ensure the structure is correct.

When generating the blockers checklist (`blockers-template.md`), produce a
self-contained checklist with owner and target close date. The template rows are
common potential blockers. Include only blockers you detected in this estate,
delete every row you found no evidence for, and cite the evidence file that
triggered each included row in the `Evidence` column. When you detect zero
blockers, state that explicitly and leave the table empty.

## Decision points

- **Workload Criticality:** To construct the phased plan, workloads must be
  grouped by criticality. Default to the criticality or phase mappings the user
  explicitly provided in their request or instructions; if not stated, infer by
  workload name, dependencies, and potential revenue impact, then surface these
  assumptions for confirmation in the report.
- **Data migration strategy.** Default to keeping existing managed databases,
  such as RDS, in AWS to avoid scope creep. Migrating the data layer, even
  homogeneous moves like RDS to Cloud SQL, should be treated as a separate,
  subsequent project phase unless explicitly requested by the user.
- **GKE Autopilot vs Standard at the cluster level.** Default to Autopilot for
  clusters where more than 80% of workloads are stateless and fit within
  Autopilot's resource constraints. Do not recommend Autopilot if the cluster
  relies on privileged DaemonSets, custom node configurations, or strict
  mutating admission controllers. Otherwise, recommend Standard. Explicitly
  recommend the cluster mode in the report.

## Outputs

```text
<output_dir>/02-assessment/
├── scorecard.json        # Structured JSON containing workload scores and cluster sizing/node pool metrics.
├── readiness-report.md   # The headline document.
└── blockers.md           # Checklist of every blocker.
```

## Validation

- The readiness report evaluates and reflects every workload in the workload
  files under `<output_dir>/01-discovery/workload-handoffs/`.
- The blockers list provides a resolution path for every blocker, leaving none
  as "TBD".
- `blockers.md` and the readiness report agree on the blocker count.

## Escalation triggers

- Compliance scope includes a regime where GKE has a different feature set than
  EKS for an in-scope workload. Surface explicitly.
- Escalate if the effort profile shows more than 50% of workloads in the
  "High-risk" or "Blocked" buckets. Recommend that the user revisit the scope.

## Common pitfalls

- **Assuming Workload Identity replaces IRSA.** Workload Identity grants Google
  Cloud IAM permissions, not AWS IAM. Retaining AWS access requires OIDC
  Federation, and moving to Google Cloud services requires application SDK
  rewrites. They do not map 1:1.
- **Listing risks without guardrails.** A risk without a guardrail is a guess.
  Every risk gets a measurable guardrail.
