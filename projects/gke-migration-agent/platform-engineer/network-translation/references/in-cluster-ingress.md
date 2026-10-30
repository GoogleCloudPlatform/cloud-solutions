# In-cluster ingress controller migration reference

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

Use the tables below to select the migration path, remediate EKS-specific
gotchas, and translate enterprise ingress patterns to Google Cloud.

## 1. Architecture selection and gotcha remediation

| Dimension           | Golden Path: GKE Gateway API (`Gateway` + `HTTPRoute`)                    | Compatibility Path: Helm L4 Service (`Service type: LoadBalancer`)                       |
| :------------------ | :------------------------------------------------------------------------ | :--------------------------------------------------------------------------------------- |
| **When to Use**     | Default for all standard HTTP/S ingress workloads                         | Only when workloads require incompatible NGINX Lua scripts or custom rewrites            |
| **Load Balancing**  | Container-native NEGs via Google Cloud L7 Application Load Balancer       | External pass-through TCP via Google Cloud L4 Network Load Balancer                      |
| **TLS / Certs**     | Google Cloud Certificate Manager (`ManagedCertificate` or pre-shared SSL) | In-cluster `cert-manager` with Kubernetes Secrets (replaces AWS ACM)                     |
| **Proxy Protocol**  | Not applicable (L7 terminates at edge)                                    | Must set `use-proxy-protocol: "false"` in ConfigMap with `externalTrafficPolicy: Local`  |
| **AWS Annotations** | Not applicable (translated to `HTTPRoute`)                                | Strip `alb.ingress.kubernetes.io/*` and replace `ingressClassName: alb` with `nginx`     |
| **Health Checks**   | Automatically managed by GFE / `HealthCheckPolicy`                        | Allow TCP from `130.211.0.0/22` and `35.191.0.0/16` in VPC Firewalls and `NetworkPolicy` |
| **WAF / DDoS**      | Built-in Google Cloud Armor WAF at the edge                               | Unsupported on L4 pass-through; requires an edge proxy                                   |

## 2. Enterprise use case translation matrix

| Enterprise Scenario             | EKS Source Pattern                                  | GKE Gateway API (Golden Path)                                           | GKE Helm Controller (Compatibility Path)                              |
| :------------------------------ | :-------------------------------------------------- | :---------------------------------------------------------------------- | :-------------------------------------------------------------------- |
| **Internal / Private Ingress**  | NLB annotation `aws-load-balancer-internal: "true"` | `Gateway` class `gke-l7-rilb`                                           | Service annotation `networking.gke.io/load-balancer-type: "Internal"` |
| **Multi-Tenancy Isolation**     | Separate `ingressClassName` per team                | Separate `Gateway` per namespace or shared `Gateway` + `ReferenceGrant` | Override `controller.ingressClassResource.name` per tenant            |
| **Auth Rewrites (OIDC / IAP)**  | NGINX annotation `auth-url`                         | `BackendConfig.spec.iap` (Google Cloud IAP)                             | Retain `auth-url` + in-cluster OAuth2 Proxy                           |
| **Canary Traffic Splitting**    | NGINX annotation `canary-weight: "20"`              | `HTTPRoute.spec.rules.backendRefs[].weight`                             | Retain `canary-weight` annotations                                    |
| **Static / BYOIP Allowlisting** | Reserved AWS EIP attached to NLB                    | Google Cloud Global External IP via `Gateway.spec.addresses`            | Google Cloud Regional External IP via `Service.spec.loadBalancerIP`   |

## 3. Helm compatibility quick-start (nginx-values.yaml)

```yaml
controller:
  replicaCount: 3
  service:
    type: LoadBalancer
    externalTrafficPolicy: Local
    annotations:
      cloud.google.com/l4-rbs: "enabled"
  config:
    use-proxy-protocol: "false"
  ingressClassResource:
    name: nginx
    enabled: true
    default: false
  minAvailable: 2
  affinity:
    podAntiAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        - labelSelector:
            matchExpressions:
              - key: app.kubernetes.io/name
                operator: In
                values:
                  - ingress-nginx
          topologyKey: topology.kubernetes.io/zone
```
