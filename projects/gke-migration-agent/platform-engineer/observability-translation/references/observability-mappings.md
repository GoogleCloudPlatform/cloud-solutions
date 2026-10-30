# EKS-to-GKE observability mapping and few-shot reference

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

<!-- markdownlint-disable MD013 -->

This reference defines the provider mappings, metric translation decision
tables, log routing rules, and X-shot examples for translating Amazon Elastic
Kubernetes Service (EKS) observability stacks to Google Kubernetes Engine (GKE)
and Google Cloud Operations.

## Architectural decision points

| Decision                                  | Default                           | When to deviate                                                                                       |
| :---------------------------------------- | :-------------------------------- | :---------------------------------------------------------------------------------------------------- |
| Grafana host vs Cloud Monitoring built-in | Cloud Monitoring built-in         | Self-host Grafana if dashboards are deeply customized OR org-wide Grafana standardization             |
| GMP vs self-managed Prometheus            | GMP                               | Self-managed only when you need Thanos / specific operator features GMP doesn't yet expose            |
| PromQL rules vs Cloud Monitoring policies | GMP `Rules` / `ClusterRules` CRDs | Use Cloud Monitoring policies for Google Cloud built-in metrics (e.g., GKE Load Balancers, Cloud SQL) |
| X-Ray retention vs OTel migration         | OTel migration                    | Stay on X-Ray briefly only if SDK swap is a long pole                                                 |
| Alarm severity mapping                    | P1=PagerDuty, P2=ticket           | Use existing org severity matrix                                                                      |

## Signal architecture mapping table

| Observability Signal               | EKS / AWS Source                                   | GKE / Google Cloud Target                             | Target Resource Manifest                                                           |
| :--------------------------------- | :------------------------------------------------- | :---------------------------------------------------- | :--------------------------------------------------------------------------------- |
| **App Workload Metrics**           | AMP / Prometheus Scrapes                           | Google Managed Service for Prometheus (GMP)           | `PodMonitoring` CRDs (`monitoring.googleapis.com/v1`)                              |
| **Cluster System Metrics**         | CloudWatch Container Insights                      | GMP / Cloud Monitoring System Metrics                 | `ClusterPodMonitoring` CRDs / Built-in GKE Ingestion                               |
| **Prometheus Rules & Alerts**      | AMP Recording & Alerting Rules                     | GMP Managed Rule Evaluator                            | `Rules` / `ClusterRules` CRDs (`monitoring.googleapis.com/v1`)                     |
| **Container & Control Plane Logs** | CloudWatch Log Groups                              | Cloud Logging Buckets with Log Analytics & Log Scopes | `google_logging_project_bucket_config` & `google_logging_project_sink` (Terraform) |
| **CloudWatch Alarms**              | CloudWatch Alarms                                  | Cloud Monitoring Alerting Policies                    | `monitoring.googleapis.com/v3` Alert Policies                                      |
| **Distributed Traces**             | AWS X-Ray                                          | Cloud Trace                                           | OpenTelemetry Collector Deployment (`trace.gke.io`)                                |
| **Dashboards & Panels**            | Amazon Managed Grafana (AMG) / Self-Hosted Grafana | Cloud Monitoring Dashboards / GKE Grafana             | Cloud Monitoring Dashboard JSON or Grafana JSON                                    |
| **SLO Definitions**                | CloudWatch ServiceLens / Custom                    | Cloud Monitoring `ServiceLevelObjective`              | `monitoring.googleapis.com/v3` SLO CRDs                                            |

## Metric translation table

| CloudWatch Metric                           | Cloud Monitoring Metric Type                               | Filter / Aggregation Notes                                        |
| :------------------------------------------ | :--------------------------------------------------------- | :---------------------------------------------------------------- |
| `AWS/EKS:cluster_failed_request_count`      | `kubernetes.io/container/restart_count`                    | Closest container metric; supplement with `kubernetes.io/api/...` |
| `AWS/EKS:apiserver_request_total`           | `kubernetes.io/api/apiserver/request_count`                | Native GKE API server metric                                      |
| `AWS/EBS:VolumeReadOps`                     | `compute.googleapis.com/instance/disk/read_ops_count`      | Persistent Disk read operations                                   |
| `AWS/EBS:VolumeWriteOps`                    | `compute.googleapis.com/instance/disk/write_ops_count`     | Persistent Disk write operations                                  |
| `AWS/RDS:CPUUtilization`                    | `cloudsql.googleapis.com/database/cpu/utilization`         | Cloud SQL CPU utilization                                         |
| `AWS/ELBv2:RequestCount`                    | `loadbalancing.googleapis.com/https/request_count`         | GKE Gateway / ALB request count                                   |
| `AWS/ApplicationELB:HTTPCode_ELB_5XX_Count` | `loadbalancing.googleapis.com/https/backend_request_count` | Filter by `response_code_class=500`                               |
| `AWS/ApplicationELB:TargetResponseTime`     | `loadbalancing.googleapis.com/https/backend_latencies`     | Distribution metric; align by latency percentile                  |

> [!NOTE]
>
> For Google Cloud metric types outside this table, refer to the official
> [Google Cloud Monitored Resource and Metric Types Documentation](https://cloud.google.com/monitoring/api/metrics_gcp)
> or run:
>
> ```bash
> gcloud monitoring metric-descriptors list --project="<PROJECT_ID>" --format="value(type,description)"
> ```

## X-shot mapping examples for observability-map.json

### Example 1: Infrastructure disk metric translation

```json
[
  {
    "source": {
      "signal_type": "metric",
      "name": "EBS Volume Read Ops",
      "namespace": "storefront",
      "provider": "cloudwatch",
      "identifier": "AWS/EBS:VolumeReadOps"
    },
    "target": {
      "signal_type": "metric",
      "name": "Persistent Disk Read Ops",
      "namespace": "storefront",
      "provider": "cloud_monitoring",
      "identifier": "compute.googleapis.com/instance/disk/read_ops_count"
    }
  }
]
```

### Example 2: Prometheus scrape translation to GMP PodMonitoring

```json
[
  {
    "source": {
      "signal_type": "metric",
      "name": "Payments API Metrics",
      "namespace": "payments",
      "provider": "amp",
      "identifier": "/metrics:8080"
    },
    "target": {
      "signal_type": "metric",
      "name": "Payments API Scrape",
      "namespace": "payments",
      "provider": "gmp",
      "identifier": "PodMonitoring/payments-api"
    }
  }
]
```

### Example 3: CloudWatch alarm to Cloud Monitoring alerting policy

```json
[
  {
    "source": {
      "signal_type": "alert",
      "name": "Payments-5xx-High",
      "namespace": "payments",
      "provider": "cloudwatch",
      "identifier": "arn:aws:cloudwatch:us-east-1:123456789012:alarm:Payments-5xx-High"
    },
    "target": {
      "signal_type": "alert",
      "name": "Payments API — 5xx error rate > 1%",
      "namespace": "payments",
      "provider": "cloud_monitoring",
      "identifier": "projects/obs-prod/alertPolicies/7890123"
    }
  }
]
```
