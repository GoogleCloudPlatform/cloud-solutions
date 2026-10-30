---
name: observability-translation
description: >-
  Translates Prometheus scrape annotations into Google Kubernetes Engine (GKE)
  Managed Service for Prometheus (GMP) PodMonitoring Custom Resource
  Definitions (CRD), and maps AWS CloudWatch metric configurations to Google
  Cloud Monitoring. Use when converting prometheus.io/scrape annotations into
  GKE PodMonitoring specifications. Don't use for network ingress routing or
  IAM role mapping.
---

# Observability translation

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

Automate the mapping and translation of application scraping configurations from
Prometheus annotations to Google Kubernetes Engine (GKE) Managed Service for
Prometheus (GMP) Custom Resource Definitions (CRDs).

## When to use this skill

Trigger on:

- "Translate Prometheus scrape annotations to GKE Managed Prometheus"
- "Convert prometheus.io/scrape to PodMonitoring YAMLs"
- "Map CloudWatch alarms to GKE alerting policies"

## Prerequisites

- `python3` version 3.10 or later
- Install dependencies listed in `scripts/requirements.txt`:
  `pip install --require-hashes -r scripts/requirements.txt`
- Path to handoff directory containing `workload-handoff.json` (or
  `workload-handoff-namespace.json`) and `observability-map.json`

## Assets and references

The following schema files under `assets/schemas/` define the JSON contracts
used by this skill:

- `observability-map.schema.json`: Schema for validating metrics and
  observability mappings.
- `workload-handoff.schema.json`: Schema for cluster-level workload handoff
  specifications.
- `workload-handoff-namespace.schema.json`: Schema for namespace-level workload
  handoff specifications.

The following reference documents under `references/` provide translation
guidance:

- [references/prometheus_to_gmp.md](references/prometheus_to_gmp.md): Guidance
  for translating Prometheus scrape configs to GKE PodMonitoring.
- [references/alerting_policies.md](references/alerting_policies.md): Guidance
  for mapping CloudWatch alarms to Google Cloud alerting policies.
- [references/metrics_and_dashboards.md](references/metrics_and_dashboards.md):
  Metrics and dashboard mapping guidelines.

The following dependency files under `scripts/` are used by this skill:

- `scripts/requirements.in`: Input dependencies for python validation scripts.
- `scripts/requirements.txt`: Hashed dependency lockfile for python validation
  scripts. Install using:
  `pip install --require-hashes -r scripts/requirements.txt`

## Procedure

### Step 1 — Validate observability mapping completeness

Verify that every workload that has scrape annotations enabled has a
corresponding scraping target entry in `observability-map.json`:

```bash
python3 scripts/validate_observability_map.py --handoff-dir "${HANDOFF_DIR:-.}"
```

### Step 2 — Translate observability resources

#### Prometheus resources to GKE Managed Service for Prometheus (GMP)

1.  Identify workloads with Pod templates having Prometheus scrape annotations:
    - `prometheus.io/scrape: "true"` (required trigger annotation)
    - `prometheus.io/path` (e.g. `"/metrics"`, defaults to `"/metrics"` if
      omitted)
    - `prometheus.io/port` (e.g. `"8080"`, defaults to `"8080"` if omitted)

    > [!NOTE]
    >
    > Port and path values above are illustrative examples. Extract whatever
    > port and path values are specified on the target workload.

2.  Strip these annotations from the Pod templates to prevent double scraping
    (if both GMP and legacy Prometheus are running in the cluster).
3.  Read the mapping from `observability-map.json` using the workload key
    (`namespace/workload-name`).
4.  Generate a `PodMonitoring` Custom Resource (`monitoring.googleapis.com/v1`)
    targeting the workload selector with the specified scrape endpoint and port
    as described in
    [references/prometheus_to_gmp.md](references/prometheus_to_gmp.md).
5.  For Grafana dashboards querying Prometheus or AMP, update the datasource to
    GMP (standard PromQL queries remain compatible).
6.  Automated translation of native Prometheus `Alertmanager` / `PrometheusRule`
    alerting rules is tracked as a future expansion item (refer to
    [references/alerting_policies.md](references/alerting_policies.md) for
    details).

#### CloudWatch metrics, alarms, and dashboards translation

1.  Read metric mappings from
    [references/metrics_and_dashboards.md](references/metrics_and_dashboards.md)
    to convert CloudWatch metric names (e.g. `AWS/ECS/CPUUtilization`) to Google
    Cloud Monitoring equivalents (e.g.
    `kubernetes.io/container/cpu/limit_utilization`).
2.  If a metric is unmapped, attempt LLM semantic resolution. If unsupported,
    log a warning in the migration summary report.
3.  Convert CloudWatch alarms into Google Cloud Monitoring alerting policies
    using [references/alerting_policies.md](references/alerting_policies.md).
4.  Update Grafana dashboard datasources and rewrite CloudWatch metric math
    queries into PromQL or MQL.
