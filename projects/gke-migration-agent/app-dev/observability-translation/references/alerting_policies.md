# Alerting policies translation reference

This reference documents the mapping of Amazon CloudWatch alarms to Google Cloud
monitoring alerting policies.

## Threshold alarm conversion example

### Amazon CloudWatch alarm (CPU high)

- Metric: `AWS/ECS/CPUUtilization`
- Statistic: `Average`
- Period: `300s`
- Threshold: `> 80%`
- Evaluation Periods: `2`

### Google Cloud Monitoring alert policy

- Target Resource: `gke_container`
- Metric: `kubernetes.io/container/cpu/limit_utilization`
- Aggregation Aligner: `ALIGN_MEAN`
- Alignment Period: `300s`
- Condition Trigger: `value > 0.8`
- Trigger count: `for: 10m` (equivalent to 2 evaluation periods of 5 minutes)

## Google Cloud alerting policy declarative YAML format

Cloud Monitoring alerting policies can be defined using Terraform or the
`gcloud alpha monitoring policies` commands. For AppDev workloads, alerting is
often packaged as Prometheus Rules inside `Rules` Custom Resources evaluated by
GMP.

```yaml
apiVersion: monitoring.googleapis.com/v1
kind: Rules
metadata:
  name: frontend-rules
  namespace: production-app
spec:
  groups:
  - name: frontend-alerts
    rules:
    - alert: HighCPUUsage
      expr: container_cpu_usage_seconds_total{container="frontend"} > 0.8
      for: 5m
      labels:
        severity: critical
      annotations:
        summary: "High CPU usage on container {{ $labels.container }}"
```

## Prometheus alerting rules (Self-managed Prometheus)

> [!NOTE]
>
> Translating native Prometheus `Alertmanager` rules or self-managed Prometheus
> `PrometheusRule` / `Rules` CRDs into GKE Managed Service for Prometheus (GMP)
> `Rules` CRDs is tracked as a future expansion item.

When translating self-managed Prometheus alerting rules:

1.  Verify if rule expressions evaluate metrics supported by GMP (for example,
    `container_cpu_usage_seconds_total`).
1.  Package translated alert expressions into GMP `Rules` Custom Resources
    (`apiVersion: monitoring.googleapis.com/v1`).
