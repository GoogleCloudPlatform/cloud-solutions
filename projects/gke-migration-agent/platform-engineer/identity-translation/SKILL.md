---
name: identity-translation
description: >-
  Translates AWS IAM Roles for Service Accounts (IRSA) to Google Cloud Workload Identity.
  Generates Terraform for Google Service Accounts, IAM bindings, and AWS OIDC federation.
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
<!--
    Disabling markdownlint MD029 to provide explicit ordering to avoid confusing
    the LLM.
-->
<!-- markdownlint-disable MD029 -->
<!--
    Disabling markdownlint MD030 to allow the list overflowing to numbers
    >=10.
-->
<!-- markdownlint-disable MD030 -->

# Identity translation and federation

You are a cloud identity architect. Your job is to translate Amazon EKS IAM
Roles for Service Accounts (IRSA) into Google Kubernetes Engine (GKE) Workload
Identity.

Because applications migrating to GKE may still need to access legacy AWS
resources, such as S3 or SQS, during a phased migration, you must also generate
AWS OIDC federation Terraform. This allows the new GKE workloads to seamlessly
assume their old AWS roles without application code changes.

## When to use this skill

- Phase 2 (Design), after `network-translation`.
- When the orchestrator explicitly invokes `identity-translation`.

## Prerequisites

- `<output_dir>/01-discovery/irsa-map.tsv` containing the mapping of Kubernetes
  Service Accounts (KSAs) to AWS IAM Roles.
- `<output_dir>/03-landing-zone/landing-zone-plan.md` (to extract the target
  Google Cloud project ID).
- `terraform`, `gcloud`, `aws`, and `check-jsonschema` CLIs installed locally.

### Missing prerequisites

If you cannot meet any prerequisite, stop immediately. Tell the user the exact
missing requirement and instruct them to resolve it.

## Procedure

### Step 1 — Map Identity

1. Read the `irsa-map.tsv`.
2. For every unique AWS IAM Role listed, propose a Google Service Account (GSA)
   name, for example, `app-backend-gsa`.
3. Generate `<OUTPUT_DIR>/05-identity-translation/identity-map.json` mapping the
   KSA, the target GSA, and the legacy AWS IAM Role ARN, adhering strictly to
   the schema provided in `assets/identity-map.schema.json`.
4. Validate the generated map using `check-jsonschema`:

    ```bash
    check-jsonschema --schemafile <SKILL_DIR>/assets/identity-map.schema.json <OUTPUT_DIR>/05-identity-translation/identity-map.json
    ```

### Step 2 — Generate Google Cloud Terraform

1. Write
   `<OUTPUT_DIR>/05-identity-translation/terraform/google-service-accounts.tf`
   and `iam-bindings.tf`.
    - Use the
      `terraform-google-modules/kubernetes-engine/google//modules/workload-identity`
      module to provision the GSAs and automatically bind them to the KSAs,
      rather than using raw `google_service_account` resources.

### Step 3 — Generate AWS Federation Terraform

To allow the GKE pods to continue accessing AWS, AWS must trust the Google Cloud
OIDC provider.

1. Write `<OUTPUT_DIR>/05-identity-translation/aws-federation/oidc-provider.tf`
   using the `aws_iam_openid_connect_provider` resource pointing to
   `https://accounts.google.com`.
2. Write
   `<OUTPUT_DIR>/05-identity-translation/aws-federation/trust-policies.tf`.
    - For every AWS IAM Role that was used by an EKS pod, generate an
      `aws_iam_role_policy_attachment` or `aws_iam_policy_document` that amends
      the Trust Policy to allow `sts:AssumeRoleWithWebIdentity` from the Google
      OIDC provider, specifically condition-matching the Google Service
      Account's `sub` or `email` claim. Reference `assets/aws-trust-policy.json`
      for the exact format.

### Step 4 — Generate KSA Manifests

1. Write the Kubernetes manifests to
   `<OUTPUT_DIR>/05-identity-translation/manifests/serviceaccounts/`. Base them
   on `assets/ksa.yaml`.
2. Ensure every KSA includes the critical annotation:
   `iam.gke.io/gcp-service-account: <GSA_NAME>@<PROJECT_ID>.iam.gserviceaccount.com`.
3. Optionally provision network policy blocking the metadata server based on
   `assets/block-metadata-server.yaml` if requested.

## Outputs / Deliverables

The orchestrator requires this exact structure:

```text
05-identity-translation/
├── identity-map.json
├── identity-map.md        # Human-readable summary
├── manifests/
│   └── serviceaccounts/   # KSA YAML cluster level
├── terraform/
│   ├── google-service-accounts.tf
│   └── iam-bindings.tf
├── aws-federation/        # AWS-side OIDC providers + role trust amendments
└── escalations.md
```
