---
name: identity-translation
description: >-
  Translates Amazon Elastic Kubernetes Service (EKS) IAM Roles for Service
  Accounts (IRSA) and Amazon EKS Pod Identity configurations into Google
  Kubernetes Engine (GKE) Workload Identity configurations. Maps Kubernetes
  ServiceAccounts (KSAs) to Google Service Accounts (GSAs). Use when remapping
  EKS service account role annotations or Pod Identity associations to GKE
  Workload Identity annotations. Don't use for cluster-level IAM pool setup or
  StorageClass remapping.
---

# Identity translation

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

## Purpose

Automate the mapping and translation of application-level service account
identities from Amazon Elastic Kubernetes Service (EKS) IRSA (IAM Roles for
Service Accounts) and Amazon EKS Pod Identity to Google Kubernetes Engine (GKE)
Workload Identity.

## When to use this skill

Trigger on:

- "Translate EKS ServiceAccount annotations to GKE Workload Identity
  annotations"
- "Map AWS IRSA to GKE Workload Identity"
- "Translate EKS Pod Identity associations to GKE Workload Identity"
- "Generate Workload Identity mapping for Kubernetes ServiceAccounts in cluster
  production"

## Prerequisites

- `python3` version 3.10 or later
- Install dependencies listed in `scripts/requirements.txt`:
  `pip install --require-hashes -r scripts/requirements.txt`
- Path to handoff directory containing `workload-handoff.json` (or
  `workload-handoff-namespace.json`) and `identity-map.json`

## Assets and references

The following schema files under `assets/schemas/` define the JSON contracts
used by this skill:

- `identity-map.schema.json`: Schema for validating ServiceAccount identity
  mappings.
- `workload-handoff.schema.json`: Schema for cluster-level workload handoff
  specifications.
- `workload-handoff-namespace.schema.json`: Schema for namespace-level workload
  handoff specifications.

The following reference document under `references/` provides identity mapping
guidance:

- [references/irsa_to_wif_mapping.md](references/irsa_to_wif_mapping.md):
  Guidance for translating AWS IRSA roles to GKE Workload Identity Federation
  (WIF).

The following dependency files under `scripts/` are used by this skill:

- `scripts/requirements.in`: Input dependencies for python validation scripts.
- `scripts/requirements.txt`: Hashed dependency lockfile for python validation
  scripts. Install using:
  `pip install --require-hashes -r scripts/requirements.txt`

## Procedure

### Step 1 — Validate identity mapping completeness

Verify that every EKS Kubernetes ServiceAccount (KSA) requiring cloud resource
access has a corresponding Google Service Account (GSA) email mapping in
`identity-map.json`:

> [!IMPORTANT]
>
> Point `${HANDOFF_DIR}` to a clean, specific directory for the current
> migration run (for example, containing only the relevant
> `workload-handoff.json` and `identity-map.json`). If multiple or archived
> migration runs exist in subdirectories, validation fails to prevent ambiguous
> mappings.

```bash
python3 scripts/validate_identity_map.py --handoff-dir "${HANDOFF_DIR:-.}"
```

#### Failure handling and remediation

If `validate_identity_map.py` reports errors, take the following actions:

- **Missing mappings (`Verification failed!`):**
    - Locate unmapped ServiceAccounts in the error output (for example,
      `<namespace>/<sa-name> (requires: <irsa-role-arn>)`).
    - Request the target Google Service Account email from the platform
      engineer, or create a dedicated GSA with the necessary Google Cloud IAM
      roles.
    - Add the missing mapping to `identity-map.json`:

        ```json
        {
          "source": "<irsa-role-arn>",
          "target": "<gsa-name>@<project-id>.iam.gserviceaccount.com"
        }
        ```

    - Re-run `validate_identity_map.py` to confirm all mappings resolve.

- **Conflicting IRSA Role ARNs for a ServiceAccount:**
    - Multiple workloads in the same namespace share a ServiceAccount name but
      specify conflicting IRSA Role ARNs.
    - GKE Workload Identity annotations attach per ServiceAccount, not per Pod
      or workload.
    - Refactor the workloads in the source cluster to use distinct
      ServiceAccounts, or standardize them to share a single IAM role.

- **Conflicting duplicate source ARNs in `identity-map.json`:**
    - The same AWS IAM Role ARN maps to multiple differing GSA target emails.
    - Edit `identity-map.json` to resolve the conflict so each source role
      unambiguously maps to a single target GSA.

- **Missing schema or handoff files (`FileNotFoundError`):**
    - Verify that `${HANDOFF_DIR}` contains `workload-handoff.json` (or
      `workload-handoff-namespace.json`) and `identity-map.json`.
    - Verify that `assets/schemas/identity-map.schema.json` exists in the skill
      directory.

### Step 2 — Translate workload annotations

When translating each `ServiceAccount` manifest:

1.  Identify any `ServiceAccount` resource with its `namespace` (defaulting to
    `default` if unspecified) and `name`.
2.  Resolve the source AWS IAM Role ARN:
    - **IRSA (Manifest annotation):** If `metadata.annotations` exists and
      contains `eks.amazonaws.com/role-arn`:
        - Extract the AWS IAM Role ARN from `eks.amazonaws.com/role-arn`.
        - Remove all EKS-specific annotations:
            - `eks.amazonaws.com/role-arn`
            - `eks.amazonaws.com/sts-regional-endpoints`
    - **EKS Pod Identity (Handoff cross-reference):** If `metadata.annotations`
      does not exist or lacks `eks.amazonaws.com/role-arn`:
        - Cross-reference `workload-handoff.json` (or
          `workload-handoff-namespace.json`) matching
          `(namespace, service_account)` against
          `workloads[].dependencies.service_account`.
        - Extract `dependencies.irsa_role_arn` (upstream `eks-discovery`
          resolves both IRSA annotations and EKS Pod Identity associations into
          this field).
3.  Add the GKE Workload Identity annotation:
    - If a source AWS IAM Role ARN resolves via step 2:
        - Retrieve `<GSA_EMAIL>` from the target mapping of that ARN in
          `identity-map.json`.
        - Add the annotation: `iam.gke.io/gcp-service-account: <GSA_EMAIL>`.
    - If no role ARN resolves, leave the `ServiceAccount` unannotated.
