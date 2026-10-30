# Metrics and dashboards translation reference

This reference details the translation of Amazon CloudWatch/Prometheus metric
names to Google Cloud Monitoring metrics and dashboard conversion strategies.

## Metric name translation

| AWS CloudWatch Metric        | Google Cloud Monitoring Metric                         | Description                                |
| :--------------------------- | :----------------------------------------------------- | :----------------------------------------- |
| `AWS/ECS/CPUUtilization`     | `kubernetes.io/container/cpu/limit_utilization`        | Container CPU utilization against limit    |
| `AWS/ECS/MemoryUtilization`  | `kubernetes.io/container/memory/limit_utilization`     | Container Memory utilization against limit |
| `AWS/ELB/RequestCount`       | `loadbalancing.googleapis.com/https/request_count`     | External L7 LB HTTPS request count         |
| `AWS/ELB/TargetResponseTime` | `loadbalancing.googleapis.com/https/backend_latencies` | External L7 LB latency response time       |

## Grafana dashboard porting strategy

If using Grafana dashboards in both environments, update the datasource and
queries:

1.  **Data Source:** Change datasource type from AWS CloudWatch / AWS Prometheus
    to Google Cloud Monitoring / Google Managed Prometheus (GMP).
1.  **Query Migration:**
    - Standard Prometheus metrics queries (e.g. `up`,
      `container_cpu_usage_seconds_total`) remain compatible.
    - CloudWatch metric math queries must be rewritten into MQL (Monitoring
      Query Language) or PromQL equivalents querying the `kubernetes.io/` metric
      namespaces.

## Fallback strategy for unmapped metrics

When encountering metrics or dashboards not explicitly listed in the translation
table:

1.  **LLM Semantic Resolution:** Attempt to identify equivalent Google Cloud
    Monitoring metrics (`kubernetes.io/container/*`, `kubernetes.io/pod/*`,
    `loadbalancing.googleapis.com/*`) based on metric semantics, labels, and
    units.
1.  **Unsupported Metric Handling & Warnings:** If a metric cannot be translated
    (for example, proprietary vendor metric or unsupported CloudWatch metric
    type), log a warning in the migration summary report:
    - Record the original metric name, source resource, and affected dashboard
      or alert.
    - Flag the item for manual review or custom OpenTelemetry collector
      configuration.
