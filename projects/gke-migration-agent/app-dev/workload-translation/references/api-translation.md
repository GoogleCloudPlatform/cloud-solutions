# Annotation and API translation reference

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

Refer to the official Google Cloud documentation for the latest API
specifications:

- [Gateway API Concepts & Setup](https://gateway-api.sigs.k8s.io/reference/api-types/)
- [GKE Gateway Controller Policies (HealthCheckPolicy, GCPBackendPolicy)](https://cloud.google.com/kubernetes-engine/docs/how-to/configure-gateway-resources)
- [GKE Workload Identity Federation Guide](https://cloud.google.com/iam/docs/reference/rest/v1/projects.serviceAccounts/setIamPolicy)
- [GKE Autopilot Security Limits & Constraints](https://cloud.google.com/kubernetes-engine/docs/concepts/autopilot-security)
- [GKE Persistent Disks & CSI Storage Drivers](https://cloud.google.com/kubernetes-engine/docs/concepts/persistent-volumes)
- [Access Filestore using Filestore CSI Driver](https://cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes-filestore-csi)

The annotation-by-annotation map skills cite when translating manifests. If
something isn't here, treat it as an escalation rather than guessing.

## Service / Ingress

### Service annotations

| EKS / AWS                                                                        | GKE / Google Cloud                                                                      | Notes                                                                 |
| -------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| `service.beta.kubernetes.io/aws-load-balancer-type: external`                    | drop                                                                                    | Type is implied by `Service.spec.type` and Gateway selection          |
| `service.beta.kubernetes.io/aws-load-balancer-nlb-target-type: ip`               | drop                                                                                    | Use Container-native LB using NEG annotations                         |
| `service.beta.kubernetes.io/aws-load-balancer-scheme: internet-facing`           | drop (for Service); for L4 use Service `type: LoadBalancer` without internal annotation |                                                                       |
| `service.beta.kubernetes.io/aws-load-balancer-scheme: internal`                  | `networking.gke.io/load-balancer-type: "Internal"`                                      |                                                                       |
| `service.beta.kubernetes.io/aws-load-balancer-cross-zone-load-balancing-enabled` | (default behavior on Google Cloud)                                                      | Google Cloud regional LBs are cross-zone by default within the region |
| `service.beta.kubernetes.io/aws-load-balancer-ssl-cert: <ACM ARN>`               | TLS through Gateway listener `tls.certificateRefs` or Certificate Manager attachment    |                                                                       |
| `service.beta.kubernetes.io/aws-load-balancer-ssl-ports: "443"`                  | Gateway listener port + protocol                                                        |                                                                       |
| `service.beta.kubernetes.io/aws-load-balancer-attributes: …`                     | `GCPBackendPolicy` (timeout, drainingTimeout, sessionAffinity, etc.)                    |                                                                       |
| `external-dns.alpha.kubernetes.io/hostname`                                      | Same — external-dns supports Cloud DNS provider; reconfigure provider                   |                                                                       |
| `external-dns.alpha.kubernetes.io/aws-…`                                         | drop; use Cloud DNS-equivalent annotations or Cloud DNS built-in                        |                                                                       |

### Ingress / Gateway annotations

| EKS / AWS                                                   | GKE / Google Cloud                                                                            | Notes                                          |
| ----------------------------------------------------------- | --------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| `kubernetes.io/ingress.class: alb`                          | replace with Gateway API resources                                                            | Drop `Ingress`; create `Gateway` + `HTTPRoute` |
| `alb.ingress.kubernetes.io/scheme: internet-facing`         | `gatewayClassName: gke-l7-global-external-managed`                                            |                                                |
| `alb.ingress.kubernetes.io/scheme: internal`                | `gatewayClassName: gke-l7-rilb`                                                               | Regional internal                              |
| `alb.ingress.kubernetes.io/target-type: ip`                 | (default for NEG-based Gateway)                                                               |                                                |
| `alb.ingress.kubernetes.io/listen-ports: '[{"HTTPS":443}]'` | Gateway listener with `protocol: HTTPS`                                                       |                                                |
| `alb.ingress.kubernetes.io/certificate-arn: <ACM ARN>`      | Gateway `tls.certificateRefs` to a `Secret`, or `networking.gke.io/certmap` annotation        | Re-issue cert in Certificate Manager           |
| `alb.ingress.kubernetes.io/wafv2-acl-arn: …`                | `GCPBackendPolicy.spec.default.securityPolicy: <Cloud Armor policy>`                          |                                                |
| `alb.ingress.kubernetes.io/healthcheck-path: /healthz`      | `HealthCheckPolicy.spec.default.config.httpHealthCheck.requestPath`                           |                                                |
| `alb.ingress.kubernetes.io/healthcheck-port: traffic-port`  | `HealthCheckPolicy.spec.default.config.httpHealthCheck.port`                                  |                                                |
| `alb.ingress.kubernetes.io/load-balancer-attributes`        | `GCPBackendPolicy.spec.default.timeoutSec` and other backend fields                           |                                                |
| `alb.ingress.kubernetes.io/group.name`                      | One Gateway per group; merge HTTPRoutes onto a shared Gateway                                 |                                                |
| `alb.ingress.kubernetes.io/group.order`                     | Use HTTPRoute rules' implicit order or explicit `match` priority                              |                                                |
| `alb.ingress.kubernetes.io/actions.<svc>: …`                | Rewrite as HTTPRoute filters (e.g., `RequestRedirect`, `URLRewrite`, `RequestHeaderModifier`) |                                                |
| `alb.ingress.kubernetes.io/auth-type: Cognito`              | Identity-Aware Proxy (IAP) on the backend service via `IAPConfig`                             | Different identity provider model              |
| `alb.ingress.kubernetes.io/auth-type: oidc`                 | IAP with custom OIDC, or in-app handling                                                      |                                                |
| `alb.ingress.kubernetes.io/conditions.<svc>`                | HTTPRoute `match` block (header/query/path)                                                   |                                                |
| `alb.ingress.kubernetes.io/load-balancer-name: <name>`      | Static external IP and Gateway name                                                           |                                                |
| `alb.ingress.kubernetes.io/security-groups: <SG IDs>`       | VPC firewall rules + Gateway frontend access control via Cloud Armor                          |                                                |

## ServiceAccount / Identity

| EKS / AWS                                             | GKE / Google Cloud                                                    | Notes                |
| ----------------------------------------------------- | --------------------------------------------------------------------- | -------------------- |
| `eks.amazonaws.com/role-arn: arn:aws:iam::…:role/foo` | `iam.gke.io/gcp-service-account: foo@PROJECT.iam.gserviceaccount.com` | Identity translation |
| `eks.amazonaws.com/sts-regional-endpoints: "true"`    | drop                                                                  |                      |
| `eks.amazonaws.com/audience: sts.amazonaws.com`       | drop                                                                  |                      |
| `eks.amazonaws.com/token-expiration: "86400"`         | drop                                                                  |                      |
| `eks.amazonaws.com/skip-containers: "init-container"` | drop                                                                  |                      |

## Pod / scheduling

### Node selectors

| EKS                                          | GKE                                                                                                                                                                              |
| -------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `eks.amazonaws.com/nodegroup: <ng>`          | `cloud.google.com/gke-nodepool: <pool>`                                                                                                                                          |
| `karpenter.sh/capacity-type: spot`           | `cloud.google.com/gke-spot: "true"`                                                                                                                                              |
| `karpenter.sh/capacity-type: on-demand`      | (omit; default)                                                                                                                                                                  |
| `karpenter.sh/nodepool: <name>`              | label match against the corresponding GKE node pool                                                                                                                              |
| `node.kubernetes.io/instance-type: m5.large` | translate to GCE machine type (e.g., `e2-standard-2`) or GKE Custom Compute Class (e.g., `cloud.google.com/compute-class`); use `cloud.google.com/machine-family` if family-only |
| `topology.kubernetes.io/region: us-east-1`   | `topology.kubernetes.io/region: us-central1`                                                                                                                                     |
| `topology.kubernetes.io/zone: us-east-1a`    | `topology.kubernetes.io/zone: us-central1-a`                                                                                                                                     |
| `eks.amazonaws.com/compute-type: fargate`    | drop; ensure cluster is Autopilot if Fargate-equivalent is desired                                                                                                               |

> [!NOTE]
>
> **Custom Compute Classes (GKE Autopilot and NAP):** When translating
> instance-type node selectors or Karpenter node pools for GKE Autopilot or Node
> Auto-Provisioning (NAP), consider mapping workloads to GKE Custom Compute
> Classes (using the `cloud.google.com/compute-class` selector, such as
> `Performance` or `Scale-Out`) rather than pinning specific GCE machine types.
> Fine-grained custom compute class optimization across all workload types is
> planned for a future iteration.

### Tolerations

| EKS taint                            | GKE taint                                                                                                  |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------- |
| `karpenter.sh/disruption=NoSchedule` | (no equivalent; GKE Standard uses `cloud.google.com/gke-preemptible` or `gke-spot` taints when applicable) |
| Custom Karpenter NodePool taint      | Apply same taint name to the target GKE node pool                                                          |

### Container security

| EKS / pod spec                       | GKE / pod spec                                                              | Notes |
| ------------------------------------ | --------------------------------------------------------------------------- | ----- |
| `securityContext.runAsNonRoot: true` | Same; Autopilot enforces                                                    |       |
| `securityContext.privileged: true`   | Same on Standard; **denied on Autopilot**                                   |       |
| `hostNetwork: true`                  | Same on Standard; **denied on Autopilot**                                   |       |
| `hostPath` volumes                   | Same on Standard; **restricted on Autopilot** (only specific paths allowed) |       |
| `runtimeClassName: crun`             | Same                                                                        |       |

## Storage / PVC

| EKS                                                        | GKE                                                                          | Notes |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------- | ----- |
| StorageClass `provisioner: ebs.csi.aws.com`                | StorageClass `provisioner: pd.csi.storage.gke.io`                            |       |
| StorageClass parameter `type: gp3`                         | StorageClass parameter `type: pd-balanced`                                   |       |
| StorageClass parameter `type: io2`                         | StorageClass parameter `type: hyperdisk-extreme`                             |       |
| StorageClass parameter `encrypted: "true" / kmsKeyId: ...` | StorageClass parameter `disk-encryption-kms-key: projects/…/cryptoKeys/…`    |       |
| StorageClass parameter `iops: "...", throughput: "..."`    | `provisioned-iops-on-create`, `provisioned-throughput-on-create` (Hyperdisk) |       |
| StorageClass `provisioner: efs.csi.aws.com`                | StorageClass `provisioner: filestore.csi.storage.gke.io`                     |       |
| StorageClass `provisioner: fsx.csi.aws.com` (Lustre)       | StorageClass `provisioner: parallelstore.csi.storage.gke.io`                 |       |
| `volumeBindingMode: WaitForFirstConsumer`                  | Same — required for zonal correctness                                        |       |

## Image references

| EKS                                                         | GKE                                                 |
| ----------------------------------------------------------- | --------------------------------------------------- |
| `123456789012.dkr.ecr.us-east-1.amazonaws.com/<repo>:<tag>` | `<region>-docker.pkg.dev/<ar-project>/<repo>:<tag>` |
| `public.ecr.aws/<image>:<tag>`                              | mirror to AR or use AR pull-through cache           |

## Logging / sidecars

| EKS                                                | GKE                                                               | Notes |
| -------------------------------------------------- | ----------------------------------------------------------------- | ----- |
| Fluent Bit DaemonSet to CloudWatch                 | drop; GKE built-in logging covers it                              |       |
| ADOT Collector                                     | Use the OTel Collector pointing at Cloud Trace / Cloud Monitoring |       |
| `eks.amazonaws.com/cloudwatch-observability` addon | drop; built-in                                                    |       |

## Webhooks / cluster add-ons

| EKS                                                     | GKE                                   |
| ------------------------------------------------------- | ------------------------------------- |
| `aws-pod-identity-webhook` MutatingWebhookConfiguration | drop; built-in Workload Identity      |
| `aws-load-balancer-controller` Deployment + CRDs        | drop; built-in GKE Gateway controller |
| `aws-ebs-csi-driver` addon                              | drop; GKE installs PD CSI by default  |
| `aws-efs-csi-driver` addon                              | replace with Filestore CSI            |
| `kube-proxy` (managed addon)                            | replaced by Dataplane V2 eBPF         |
| `coredns` (managed addon)                               | provided by GKE                       |

## CRDs of note

| Source CRD (group)                                                 | Action                                                                              |
| ------------------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| `nodepools.karpenter.sh`, `ec2nodeclasses.karpenter.k8s.aws`       | drop; rebuild as GKE node pools (or NAP rules) in landing-zone                      |
| `targetgroupbindings.elbv2.k8s.aws`                                | drop; replace with NEG-based service backends                                       |
| `appmesh.k8s.aws/Mesh, VirtualNode, VirtualService`                | drop manifest; unsupported (service mesh migration is out of scope)                 |
| `acmpca.aws.com/AWSPCAClusterIssuer` (cert-manager external)       | replace with `clusterissuer` for ACME via Cloud DNS or Certificate Manager attestor |
| `secrets-store.csi.x-k8s.io` SecretProviderClass with AWS provider | swap provider to Google Cloud Secret Manager provider                               |

## Metadata, status and finalizers cleanup

These rules apply globally to all resources during the post-processing phase.

### Runtime metadata and status

| Field / Path                                                               | Action | Notes                                                |
| -------------------------------------------------------------------------- | ------ | ---------------------------------------------------- |
| `metadata.uid`                                                             | drop   | Cluster-specific identifier                          |
| `metadata.resourceVersion`                                                 | drop   | Cluster-specific resource version                    |
| `metadata.creationTimestamp`                                               | drop   | Cluster-specific creation timestamp                  |
| `metadata.generation`                                                      | drop   | Cluster-specific generation metadata                 |
| `metadata.selfLink`                                                        | drop   | Cluster-specific self link                           |
| `metadata.managedFields`                                                   | drop   | Cluster-specific managed fields metadata             |
| `metadata.annotations["kubectl.kubernetes.io/last-applied-configuration"]` | drop   | Strip to ensure clean apply on GKE                   |
| `status`                                                                   | drop   | Discard the status block from all resource manifests |

### AWS finalizers

| EKS / AWS Finalizer                                                                                              | Action | Notes                                              |
| ---------------------------------------------------------------------------------------------------------------- | ------ | -------------------------------------------------- |
| Any finalizer containing `aws` or `eks` (e.g., `service.k8s.aws/resources`, `external-attacher/ebs-csi-aws-com`) | drop   | Prevents resources from hanging on deletion in GKE |

### AWS-specific ConfigMaps and resources

| Resource / Kind                      | Action         | Notes                                                                |
| ------------------------------------ | -------------- | -------------------------------------------------------------------- |
| `ConfigMap` named `kube-root-ca.crt` | drop / discard | EKS cluster's root certificate. GKE automatically provisions its own |

## Port alignment

These rules ensure port consistency between Services and workload Pods.

### Service and workload port alignment

- Verify alignment between Service `spec.ports[*].targetPort` and container
  `ports[*].containerPort` in the targeted workload. Unless intentional port
  mapping or proxying is configured, ensure `targetPort` correctly routes to the
  container's listening port.
- If a Service references a named port (e.g., `targetPort: http`), verify that
  the matching container defines a port with that exact name.

## Declarative resource translation examples

These reference YAML patterns guide the post-processing phase (Step 3b) when
converting AWS Ingress resources, Prometheus scrape annotations, and AWS load
balancer health checks into their corresponding GKE Gateway API (`Gateway` +
`HTTPRoute`), Google Managed Prometheus (`PodMonitoring`), and GKE Policy
(`HealthCheckPolicy` + `GCPBackendPolicy`) resources.

### 1. Ingress to Gateway and HTTPRoute

#### Source EKS Ingress (AWS ALB)

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: hello-world
  namespace: test-workloads
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
spec:
  rules:
  - host: hello.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: hello-world-service
            port:
              number: 80
```

#### Translated GKE Gateway and HTTPRoute

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: hello-world-gateway
  namespace: test-workloads
spec:
  gatewayClassName: gke-l7-global-external-managed
  listeners:
  - name: http
    protocol: HTTP
    port: 80
    allowedRoutes:
      namespaces:
        from: Same
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: hello-world-route
  namespace: test-workloads
spec:
  parentRefs:
  - name: hello-world-gateway
  hostnames:
  - hello.example.com
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /
    backendRefs:
    - name: hello-world-service
      port: 80
```

### 2. Prometheus annotations to PodMonitoring

#### Source EKS Workload (Prometheus Scraping Annotations)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hello-world-app
  namespace: test-workloads
spec:
  template:
    metadata:
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/path: "/metrics"
        prometheus.io/port: "80"
      labels:
        app: hello-world
...
```

#### Translated GKE PodMonitoring

Strip the `prometheus.io/*` annotations from the Deployment's Pod template and
generate the following `PodMonitoring` resource:

```yaml
apiVersion: monitoring.googleapis.com/v1
kind: PodMonitoring
metadata:
  name: hello-world-app-scrape
  namespace: test-workloads
spec:
  selector:
    matchLabels:
      app: hello-world
  endpoints:
  - port: 80
    path: /metrics
    interval: 30s
```

### 3. Load balancer health check and security policies

#### Source EKS Ingress Annotations

```yaml
metadata:
  annotations:
    alb.ingress.kubernetes.io/healthcheck-path: /healthz
    alb.ingress.kubernetes.io/healthcheck-port: "8080"
    alb.ingress.kubernetes.io/wafv2-acl-arn: arn:aws:wafv2:us-west-2:123456789012:regional/webacl/my-waf/123456
```

#### Translated GKE HealthCheckPolicy & GCPBackendPolicy

```yaml
apiVersion: networking.gke.io/v1
kind: HealthCheckPolicy
metadata:
  name: hello-world-service-hc
  namespace: test-workloads
spec:
  default:
    config:
      type: HTTP
      httpHealthCheck:
        requestPath: /healthz
        port: 8080
  targetRef:
    group: ""
    kind: Service
    name: hello-world-service
---
apiVersion: networking.gke.io/v1
kind: GCPBackendPolicy
metadata:
  name: hello-world-service-waf
  namespace: test-workloads
spec:
  default:
    securityPolicy: my-waf
  targetRef:
    group: ""
    kind: Service
    name: hello-world-service
```
