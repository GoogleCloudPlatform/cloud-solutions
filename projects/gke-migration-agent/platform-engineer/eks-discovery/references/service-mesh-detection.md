<!--
 Copyright 2026 Google LLC

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

      https://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
-->

# Service mesh detection

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

Use this reference in Step 4 of the Amazon EKS discovery procedure. All evidence
comes from the files under `01-discovery/raw/`. You write nothing back to Amazon
Web Services (AWS), and you do not stop discovery when you find a service mesh.

## Signals by provider

| Provider                            | API groups                        | Namespace or Pod signal                                                                      | Sidecar container                                                            |
| ----------------------------------- | --------------------------------- | -------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Istio, including Cloud Service Mesh | `*.istio.io`                      | Labels `istio-injection=enabled`, `istio.io/rev=<rev>`, or `istio.io/dataplane-mode=ambient` | `istio-proxy`. Ambient mode has no sidecar. `ztunnel` runs in `istio-system` |
| Linkerd                             | `linkerd.io`, `policy.linkerd.io` | Annotation `linkerd.io/inject=enabled`                                                       | `linkerd-proxy`                                                              |
| Consul                              | `consul.hashicorp.com`            | Pod annotation `consul.hashicorp.com/connect-inject=true`                                    | `consul-dataplane`                                                           |
| AWS App Mesh                        | `appmesh.k8s.aws`                 | Label `appmesh.k8s.aws/sidecarInjectorWebhook=enabled`                                       | `envoy` with an `aws-appmesh-envoy` image                                    |
| Kuma                                | `kuma.io`                         | Label `kuma.io/sidecar-injection=enabled`                                                    | `kuma-sidecar`                                                               |

## Collect the evidence

The CSVs store labels and annotations as JSON, so `istio-injection=enabled`
appears as `"istio-injection": "enabled"`. Only the values `enabled` or `true`
count, never `disabled`. In `pods.csv` the namespace is the first column and
`cluster_id` is the last. Empty output means no signal.

```bash
RAW="01-discovery/raw"
# Mesh API groups installed as CRDs
grep -E -i 'istio\.io|linkerd\.io|consul\.hashicorp\.com|appmesh\.k8s\.aws|kuma\.io' "$RAW/crds.csv" || true
# Injection labels or annotations on namespaces
grep -E 'istio-injection|istio\.io/rev|istio\.io/dataplane-mode|linkerd\.io/inject|appmesh\.k8s\.aws/sidecarInjectorWebhook|kuma\.io/sidecar-injection|consul\.hashicorp\.com/connect-inject' "$RAW/namespaces.csv" || true
# Sidecar or data-plane container NAMES or IMAGES in application Pods
# (skip Pods whose namespace, the first column, is a mesh control plane)
grep -E "'name': '(istio-proxy|linkerd-proxy|consul-dataplane|kuma-sidecar|envoy)'|aws-appmesh-envoy" "$RAW/pods.csv" | grep -v -E '^(istio-system|istio-ingress|linkerd|linkerd-viz|consul|appmesh-system|kuma-system|kube-system),' || true
```

## Decision rules

1.  A service mesh is **in use** only when an application namespace carries an
    injection label or annotation, or an application Pod runs a sidecar
    container. An idle control plane, or Istio used only as an ingress gateway,
    is an anomaly and not a blocker.
2.  Linkerd, and Istio with Kubernetes native sidecar containers enabled, inject
    the proxy as an init container, which `pods.csv` does not record. The
    namespace label or annotation is sufficient evidence on its own.
3.  A standalone `envoy` container, Amazon VPC Lattice, and mesh Custom Resource
    Definitions (CRDs) with no custom resources and no injected namespaces or
    Pods are not a service mesh. Record them as anomalies in `escalations.md`.
4.  If `crds.csv` is empty and `extraction_errors.log` contains entries, the
    read-only identity could not list CRDs. Record "service mesh detection
    inconclusive" in `escalations.md`. Do not report "none".

## Escalation entry

Append one entry per affected cluster and provider under a
`## Migration blockers` heading in `01-discovery/escalations.md`. State the
provider, the mode as `sidecar` or `ambient`, the affected namespaces, the
number of injected workloads, and the evidence files. Also add a bold **Service
mesh detected** line to section 5 of `inventory-summary.md`.
