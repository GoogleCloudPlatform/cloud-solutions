# Ingress to Gateway API mapping reference

This document maps AWS ALB Ingress annotations to GKE Gateway API resources.

## Routing concepts

| AWS ALB Ingress (EKS)                               | GKE Gateway API (GKE)   | Resource Generated                       |
| :-------------------------------------------------- | :---------------------- | :--------------------------------------- |
| Ingress Resource                                    | HTTPRoute + Gateway     | `gateway.networking.k8s.io`              |
| `alb.ingress.kubernetes.io/scheme: internet-facing` | Gateway class selection | `gke-l7-global-external-managed`         |
| `alb.ingress.kubernetes.io/certificate-arn`         | Gateway listener TLS    | `Gateway` listener with `CertificateMap` |
| Host / Path routing                                 | HTTPRoute Rules         | `HTTPRoute` with `rules.matches`         |

## Health checks

AWS ALB uses Ingress annotations to define Target Group health checks. GKE
Gateway API maps this to a `HealthCheckPolicy` custom resource (part of GKE
custom policies).

### EKS ingress

```yaml
alb.ingress.kubernetes.io/healthcheck-path: /healthz
alb.ingress.kubernetes.io/healthcheck-port: "80"
```

### GKE HealthCheckPolicy

```yaml
apiVersion: networking.gke.io/v1
kind: HealthCheckPolicy
metadata:
  name: frontend-hc-policy
  namespace: production-app
spec:
  default:
    config:
      type: HTTP
      httpHealthCheck:
        requestPath: /healthz
        port: 80
  targetRef:
    group: ""
    kind: Service
    name: frontend-service
```

## Mapping schema (`network-map.json`)

```json
{
  "class_mappings": {
    "alb": "gke-l7-global-external-managed"
  },
  "certificates": {
    "arn:aws:acm:us-west-2:123456789012:certificate/abc-123": "projects/my-project/locations/global/certificates/shop-cert"
  },
  "domain_mappings": {
    "shop.example.com": "shop.gke.example.com"
  },
  "cidr_mappings": {
    "10.0.0.0/16": "172.16.0.0/16"
  }
}
```
