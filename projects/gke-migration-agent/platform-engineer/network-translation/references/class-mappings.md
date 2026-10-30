# EKS-to-GKE class mapping and few-shot reference

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

This reference defines the mapping rules for translating Amazon Elastic
Kubernetes Service (Amazon EKS) load balancer classes, ingress classes, and
Gateway classes into Google Kubernetes Engine (GKE) equivalents.

## EKS-to-GKE class mapping decision table

| Source EKS Construct               | Source EKS Class (`source.class`)                             | Scope & Protocol          | Target GKE Class (`target.class`)                                   | Target GKE Resource                 | Notes                                                                           |
| :--------------------------------- | :------------------------------------------------------------ | :------------------------ | :------------------------------------------------------------------ | :---------------------------------- | :------------------------------------------------------------------------------ |
| **Internet-facing ALB**            | `alb` or `gateway.k8s.aws/alb`                                | External L7 (HTTP/S)      | `gke-l7-global-external-managed`                                    | `Gateway` + `HTTPRoute`             | Global L7 external load balancing with edge NEGs                                |
| **Regional External ALB**          | `alb` or `gateway.k8s.aws/alb`                                | Regional External L7      | `gke-l7-regional-external-managed`                                  | `Gateway` + `HTTPRoute`             | Regional L7 external load balancing                                             |
| **Internal ALB**                   | `alb` or `gateway.k8s.aws/alb`                                | Internal L7 (VPC Private) | `gke-l7-rilb`                                                       | `Gateway` + `HTTPRoute`             | Regional internal L7 load balancing                                             |
| **VPC Lattice Gateway**            | `amazon-vpc-lattice`                                          | Internal L7 Service Mesh  | `gke-l7-rilb`                                                       | `Gateway` + `HTTPRoute`             | Multi-cluster or internal service mesh routing                                  |
| **Internet-facing NLB**            | `service.beta.kubernetes.io/aws-load-balancer-type: external` | External L4 (TCP/UDP)     | `LoadBalancer` (`cloud.google.com/l4-rbs: "enabled"`)               | `Service` (`type: LoadBalancer`)    | Regional external L4 pass-through load balancer                                 |
| **Internal NLB**                   | `service.beta.kubernetes.io/aws-load-balancer-type: Internal` | Internal L4 (TCP/UDP)     | `LoadBalancer` (`networking.gke.io/load-balancer-type: "Internal"`) | `Service` (`type: LoadBalancer`)    | Regional internal L4 pass-through load balancer                                 |
| **Global External NLB**            | `nlb` or `gateway.k8s.aws/nlb`                                | External Global L4        | `gke-l4-global-external-managed`                                    | `Gateway` + `TCPRoute`              | Global L4 Gateway API load balancing                                            |
| **In-Cluster NGINX (Golden Path)** | `nginx` or `ingressClassName: nginx`                          | External L7 (HTTP/S)      | `gke-l7-global-external-managed`                                    | `Gateway` + `HTTPRoute`             | Re-platform to built-in GKE Gateway API                                         |
| **In-Cluster NGINX (Fallback)**    | `nginx` (with custom Lua/snippets)                            | External L4 (TCP/UDP)     | `LoadBalancer` (`cloud.google.com/l4-rbs: "enabled"`)               | `Helm` + `Service` + `cert-manager` | Retain NGINX pods behind L4 pass-through per `references/in-cluster-ingress.md` |

## X-shot mapping examples for agent translation

### Example 1: AWS Gateway API ALB to GKE Gateway API

```json
[
  {
    "source": {
      "name": "public-api-alb",
      "namespace": "api",
      "class": "gateway.k8s.aws/alb",
      "parent_resource": "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/public-api/123",
      "hostnames": ["api.example.com"]
    },
    "target": {
      "name": "public-api",
      "namespace": "api",
      "class": "gke-l7-global-external-managed",
      "parent_resource": "external-gateway",
      "hostnames": ["api.example.com"]
    }
  }
]
```

### Example 2: Internal ALB to GKE Internal Gateway

```json
[
  {
    "source": {
      "name": "internal-service-alb",
      "namespace": "backend",
      "class": "alb",
      "parent_resource": "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/internal-alb/456",
      "hostnames": ["internal.example.internal"]
    },
    "target": {
      "name": "internal-service",
      "namespace": "backend",
      "class": "gke-l7-rilb",
      "parent_resource": "internal-gateway",
      "hostnames": ["internal.example.internal"]
    }
  }
]
```

### Example 3: Ingress NGINX re-platforming to GKE Gateway API

```json
[
  {
    "source": {
      "name": "payment-ingress-nginx",
      "namespace": "payments",
      "class": "nginx",
      "parent_resource": "ingress-nginx-controller",
      "hostnames": ["pay.example.com"]
    },
    "target": {
      "name": "payments",
      "namespace": "payments",
      "class": "gke-l7-global-external-managed",
      "parent_resource": "external-gateway",
      "hostnames": ["pay.example.com"]
    }
  }
]
```
