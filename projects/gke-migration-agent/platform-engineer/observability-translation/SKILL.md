---
name: observability-translation
description: >-
  Translates EKS observability stacks (CloudWatch, Amazon Managed Service for Prometheus, X-Ray) to GKE equivalents and produces a telemetry design diff.
  Use when the user asks to "translate observability", "convert CloudWatch alarms", or "set up GKE monitoring".
  Don't use for general GKE cluster provisioning or deploying application workloads.
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

You translate the observability surface — logs, metrics, traces, dashboards,
alerts, SLOs — from EKS/CloudWatch/Amazon Managed Service for Prometheus (AMP)
into GKE/Cloud Operations/Google Cloud Managed Service for Prometheus (GMP). You
produce translated configurations and a parity report.

## Purpose

Ensure operational parity on GKE before traffic shifts.

## When to use this skill

- Translate observability stacks, dashboards, or alarms from EKS to GKE.
- Set up monitoring or SLOs on GKE.

## Don't use for

- Provisioning GKE clusters or non-observability infrastructure.
- Deploying application workloads.

## Prerequisites

- **Source Telemetry Inventory**: `<output_dir>/01-discovery/inventory.json`
  (CloudWatch alarms, dashboards, Log Groups, AMP/X-Ray configs) and workload
  scrape endpoints.
- **Target Architecture**: `<output_dir>/03-landing-zone/landing-zone-plan.md`
  defining `obs-<env>` project and GKE cluster monitoring status.
- **Route Targets**: `<output_dir>/04-network-translation/manifests/httproutes/`
  for LB alerting targets.
- **Risk Classifications**: `<output_dir>/02-assessment/scorecard.json` for
  identifying critical workloads.
- **Identity Mappings**:
  `<output_dir>/05-identity-translation/identity-map.json` for Workload Identity
  IAM validation.
- **Access**: `gcloud`, `kubectl`, `terraform` authenticated to target
  environments.

> [!IMPORTANT]
>
> If prerequisites are missing, stop and alert the user.

## Procedure

### Step 1 — Declare Telemetry Infrastructure (Terraform)

Generate declarative Terraform (e.g., `terraform/metrics-scope.tf`) following
`assets/telemetry-infra.tf`. Do not use `gcloud`.

1. **Metrics Scope**: Link central `obs-<env>` project to all workload cluster
   projects via `google_monitoring_monitored_project`.
2. **Telemetry Aggregation**: Verify all GKE clusters are monitored.

### Step 2 — Verify Built-in Ingest

Ensure target GKE clusters have Logging (`SYSTEM_COMPONENTS`, `WORKLOADS`) and
Monitoring (`SYSTEM_COMPONENTS`, `managedPrometheusConfig.enabled = true`)
active in their specifications.

### Step 3 — Translate Prometheus to GMP CRDs

Translate configurations into `monitoring.googleapis.com/v1` Custom Resources:

- **Scrapes**: Inspect pod template scrape annotations directly so that they
  properly link each scraped workload name to its corresponding GMP target in
  `observability-map.json` (rather than incorrectly associating it with
  `cloudwatch-agent`). Rewrite targets as `PodMonitoring` (namespace) or
  `ClusterPodMonitoring` (cluster). Use `metricRelabeling` to optimize costs
  (see `assets/pod-monitoring.yaml`).
- **Rules/Alerts**: Convert AMP rules to GMP `Rules` or `ClusterRules` (see
  `assets/prometheus-rules.yaml`).
- **Federation**: Repoint external federation to GMP query endpoint.

### Step 4 — Translate Dashboards

1. **Self-hosted Grafana**: Deploy on GKE, link to GMP/Cloud Monitoring, import
   JSON, and update metric names.
2. **Cloud Monitoring**: Convert Grafana panels to native widgets.

Follow mappings in `references/observability-mappings.md` and build
`metric-map.md`.

### Step 5 — Declare Log Routing (Terraform)

Generate Terraform (`terraform/log-buckets.tf`, `terraform/log-sinks.tf`)
following `assets/telemetry-infra.tf`.

1. **Log Buckets & Analytics**: Declare buckets via
   `google_logging_project_bucket_config` with `enable_analytics = true`.
2. **Log Scopes**: Configure virtual multi-project views.
3. **Log Sinks**: Route logs via `google_logging_project_sink` to external
   platforms or custom buckets.

### Step 6 — Establish Dual Alerting Fabric

1. **App Alerts (GMP)**: PromQL alerts via `Rules`/`ClusterRules` CRDs.
2. **Infra Alerts (Cloud Monitoring)**: Terraform
   (`google_monitoring_alert_policy`) or YAML (`assets/alerting-policy.yaml`)
   for:
    - SLO burn rates, node saturation (>85%), API server errors, and LB 5xx
      rates.

Define channels in `terraform/notification-channels.tf`.

### Step 7 — Translate Traces (OTel)

Recommend switching AWS X-Ray SDK to OpenTelemetry (OTel) SDK. Configure OTel
Collector (`trace.gke.io`) for Cloud Trace export. Produce per-app migration
notes.

### Step 8 — Declare SLOs

Translate existing SLOs or declare basic ones (Availability, Latency) for
critical services via Cloud Monitoring CRDs or Terraform (see
`assets/slo.yaml`). Document in `obs-design.md`.

### Step 9 — Generate Deliverables

Render output artifacts and `observability-map.json` (per
`assets/observability-map.schema.json`).

## Decision points

See `Architectural decision points` in `references/observability-mappings.md`.

## Outputs / deliverables

```text
08-observability-translation/
├── obs-design.md
├── observability-map.json
├── manifests/
│   ├── podmonitorings/
│   ├── clusterpodmonitorings/
│   └── rules/
├── terraform/
│   ├── log-buckets.tf
│   ├── log-sinks.tf
│   └── notification-channels.tf
├── dashboards/
│   ├── grafana/
│   └── cloud-monitoring/
├── metric-map.md
├── alarm-translation.md
└── escalations.md
```

## Validation

- Every CloudWatch alarm has a target policy in `alarm-translation.md`.
- Dashboards ported with confirmed metrics.
- Control plane/container logs visible in Cloud Logging.
- GMP scrapes return data.
- Alerting policies fire in test.

## Escalation triggers

- Custom CloudWatch metrics from EC2 SDK (requires code change).
- Grafana dashboards using AWS-only data sources (Athena, etc.).
- AMG-specific features without Google analogue.

## Common pitfalls

- **Double counting**: Tag with cluster labels during co-existence.
- **Log cost**: Watch ingestion; use `metricRelabeling` to drop metrics.
- **Lost runbooks**: Ensure alert documentation includes runbook links.
