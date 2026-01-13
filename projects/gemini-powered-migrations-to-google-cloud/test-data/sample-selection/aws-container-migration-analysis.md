# AWS EKS Migration Assessment

## EKS Cluster Analysis Summary

| Workload Name      | Namespace | Type (Stateless/Stateful) | External Dependencies (DB/Cache) | Complexity  | Migration Action                  |
| ------------------ | --------- | ------------------------- | -------------------------------- | ----------- | --------------------------------- |
| balancereader      | default   | Stateless                 | PostgreSQL (Assumed RDS)         | 🟡 Moderate | Lift & Shift, Reconfigure DB      |
| contacts           | default   | Stateless                 | Not specified                    | 🟢 Simple   | Lift & Shift                      |
| frontend           | default   | Stateless                 | Not specified                    | 🟡 Moderate | Lift & Shift, Reconfigure Ingress |
| ledgerwriter       | default   | Stateless                 | PostgreSQL (Assumed RDS)         | 🟡 Moderate | Lift & Shift, Reconfigure DB      |
| loadgenerator      | default   | Stateless                 | Not specified                    | 🟢 Simple   | Lift & Shift                      |
| transactionhistory | default   | Stateless                 | PostgreSQL (Assumed RDS)         | 🟡 Moderate | Lift & Shift, Reconfigure DB      |
| userservice        | default   | Stateless                 | Not specified                    | 🟢 Simple   | Lift & Shift                      |

## Recommendations for GKE Migration

**Infrastructure Provisioning:**

- **Recommended GKE Cluster Mode:** GKE Autopilot is highly recommended. The
  current EKS cluster has a single worker node, which indicates that the
  workloads are not resource-intensive. GKE Autopilot will provide a hands-off
  operational experience by managing the underlying nodes automatically.
- **Recommended Cloud SQL sizing:** Based on the presence of PostgreSQL
  connection strings in the ConfigMaps, it is recommended to provision a Cloud
  SQL for PostgreSQL instance. The size should be determined after a performance
  baseline analysis of the source RDS instance. A good starting point would be a
  `db-n1-standard-2` instance.

**Workload Strategy:**

- **Stateless Workloads (Lift & Shift)**: All identified workloads are stateless
  and can be redeployed to GKE without modification to the container images. The
  following workloads are ready for immediate redeployment:
    - `contacts`
    - `loadgenerator`
    - `userservice`
- **Data Migration (External Dependencies)**: The `balancereader`,
  `ledgerwriter`, and `transactionhistory` workloads are dependent on an
  external PostgreSQL database, which is assumed to be an AWS RDS instance.
    - **Strategy:** Utilize Google Cloud's Database Migration Service (DMS) to
      migrate the RDS instance to Cloud SQL for PostgreSQL. A continuous
      replication job should be set up to minimize downtime during the cutover.
    - **Configuration Changes:** The `accounts-db-config` and `ledger-db-config`
      ConfigMaps will need to be updated with the new Cloud SQL connection
      details.
- **Stateful Workloads (Refactoring Required)**: No stateful workloads requiring
  storage migration were identified.
- **Networking Changes:** The `frontend` workload uses an AWS ALB Ingress.
    - **Strategy:** The AWS-specific annotations (`alb.ingress.kubernetes.io/*`)
      must be removed from the Ingress manifest and replaced with a GKE-native
      Ingress configuration. For simple HTTP routing, a standard GKE Ingress
      object pointing to the `frontend` service will suffice.

**Missing Data / Assumptions:**

- It is assumed that the database connection details in the `accounts-db-config`
  and `ledger-db-config` ConfigMaps point to an AWS RDS instance. The actual
  database endpoints were not available in the provided data.
- Secrets are not readable, so any credentials stored in Kubernetes Secrets will
  need to be manually recreated in the GKE cluster.
- The actual size and performance metrics of the source database are unknown.
  The recommendation for Cloud SQL sizing is an educated guess and should be
  verified.
