# GKE Ingress to Gateway API migration analysis report

**Generated On:** 2026-07-21 16:34:21 **Target Cluster:** demo-app-cluster
**Kubernetes Engine Version:** 1.35.5-gke.1000000 **Tool Version:**
`ingress2gateway` v1.4.0

## 1. Executive summary

This report analyzes the legacy GKE Ingress resources currently deployed in the
cluster and evaluates their readiness for migration to the modern, role-oriented
Kubernetes Gateway API.

## 2. Cluster migration readiness inventory

| Namespace | Ingress Name         | Controller Class | Found Rules                   | Compatibility Status | Action Required                   |
| :-------- | :------------------- | :--------------- | :---------------------------- | :------------------- | :-------------------------------- |
| `default` | `fanout-ingress`     | `gce`            | \* (Paths: 2)                 | **Fully Compatible** | Ready to translate automatically. |
| `default` | `my-app-ingress`     | `nginx`          | my-app.example.com (Paths: 1) | **Fully Compatible** | Ready to translate automatically. |
| `default` | `sample-app-ingress` | `gce`            | \* (Paths: 1)                 | **Fully Compatible** | Ready to translate automatically. |

## 3. Recommended architectural mapping

[Populated in Phase 5 & 6]

## 4. Discovered manifest anomalies and warnings

### 🛑 Critical Blockers

- None detected. All targets are valid for automated routing transitions.

## 5. Next steps and execution plan

[Populated in Phase 6]
