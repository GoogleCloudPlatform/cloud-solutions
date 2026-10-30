# Prometheus annotations to GKE Managed Service for Prometheus (GMP)

Refer to the official Google Cloud documentation for the latest API
specifications:

- [GKE Managed Service for Prometheus API reference](https://github.com/GoogleCloudPlatform/prometheus-engine/blob/main/doc/api.md)

When loading API documentation during migration, specifically load the official
API reference page and report a failure if the reference page is unavailable.

This reference document maps traditional Prometheus pod annotations to GKE
Managed Service for Prometheus (GMP) `PodMonitoring` configurations.

## Concept mapping

| Prometheus Annotation            | PodMonitoring Schema Field | Description                                   |
| :------------------------------- | :------------------------- | :-------------------------------------------- |
| `prometheus.io/scrape: "true"`   | (Triggers generation)      | Determines if PodMonitoring should be created |
| `prometheus.io/path: "/metrics"` | `spec.endpoints[].path`    | Path to scrape metrics                        |
| `prometheus.io/port: "8080"`     | `spec.endpoints[].port`    | Port name or number to scrape                 |

## Translation example

### EKS pod spec annotations

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: production-app
spec:
  template:
    metadata:
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/path: "/metrics"
        prometheus.io/port: "8080"
...
```

### Generated GKE PodMonitoring resource

```yaml
apiVersion: monitoring.googleapis.com/v1
kind: PodMonitoring
metadata:
  name: frontend-monitoring
  namespace: production-app
spec:
  selector:
    matchLabels:
      app: frontend
  endpoints:
  - port: 8080
    path: /metrics
    interval: 30s
```

## Mapping schema (observability-map.json)

```json
[
  {
    "source": {
      "signal_type": "metric",
      "name": "frontend",
      "namespace": "production-app",
      "provider": "prometheus",
      "identifier": "prometheus.io/scrape"
    },
    "target": {
      "signal_type": "metric",
      "name": "frontend-monitoring",
      "namespace": "production-app",
      "provider": "gmp",
      "identifier": "PodMonitoring"
    }
  }
]
```
