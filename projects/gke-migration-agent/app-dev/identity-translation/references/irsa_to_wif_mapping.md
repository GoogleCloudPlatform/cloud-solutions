# EKS IRSA and Pod Identity to GKE Workload Identity mapping reference

This document describes how to map Amazon Elastic Kubernetes Service (EKS) pod
identities (IAM Roles for Service Accounts (IRSA) and Amazon EKS Pod Identity)
to Google Kubernetes Engine (GKE) Workload Identity.

## AWS IRSA (source)

Amazon EKS uses Kubernetes ServiceAccount annotations to associate a Pod with an
Amazon Web Services (AWS) IAM Role.

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: my-app-sa
  namespace: production-app
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/eks-pod-role
    eks.amazonaws.com/sts-regional-endpoints: "true"
```

## Amazon EKS Pod Identity (source)

Amazon EKS Pod Identity associates IAM roles with Kubernetes ServiceAccounts
through the Amazon EKS control plane API (`CreatePodIdentityAssociation`) rather
than manifest annotations. The source `ServiceAccount` manifest contains no
`eks.amazonaws.com/role-arn` annotations:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: my-app-sa
  namespace: production-app
```

Upstream `eks-discovery` resolves these associations and normalizes them into
`dependencies.irsa_role_arn` in `workload-handoff.json` (or
`workload-handoff-namespace.json`).

When translating a ServiceAccount lacking IRSA annotations:

1.  Cross-reference `workload-handoff.json` matching
    `(namespace, service_account)`.
1.  Extract `dependencies.irsa_role_arn`.
1.  Map the extracted ARN to the target Google Service Account email using
    `identity-map.json`.
1.  Add `iam.gke.io/gcp-service-account: <GSA_EMAIL>` to the ServiceAccount.

## GKE Workload Identity (target)

GKE maps a Kubernetes ServiceAccount (KSA) to a Google Service Account (GSA) by
annotating the KSA.

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: my-app-sa
  namespace: production-app
  annotations:
    iam.gke.io/gcp-service-account: my-gsa@gke-migration-demo-project.iam.gserviceaccount.com
```

## Mapping schema (identity-map.json)

The identity map matches AWS IAM Role ARNs (`source`) to target Google Service
Account emails (`target`).

> [!NOTE]
>
> Target Google Service Account emails must end with `.gserviceaccount.com`.
> Dedicated user-managed service accounts ending in `.iam.gserviceaccount.com`
> are recommended.

```json
[
  {
    "source": "arn:aws:iam::123456789012:role/eks-pod-role",
    "target": "my-gsa@gke-migration-demo-project.iam.gserviceaccount.com"
  }
]
```

## Workload Identity IAM binding (Google Cloud side)

To allow the Kubernetes ServiceAccount to act as the Google Service Account,
create the following IAM policy binding on the GSA:

- **Role:** `roles/iam.workloadIdentityUser`
- **Member:** `serviceAccount:<PROJECT_ID>.svc.id.goog[<NAMESPACE>/<KSA_NAME>]`

Example `gcloud` command for the Platform Operator:

```bash
gcloud iam service-accounts add-iam-policy-binding my-gsa@gke-migration-demo-project.iam.gserviceaccount.com \
    --role="roles/iam.workloadIdentityUser" \
    --member="serviceAccount:gke-migration-demo-project.svc.id.goog[production-app/my-app-sa]"
```
