---
name: network-translation
description: >-
  Translates EKS network constructs to GKE equivalents and produces a network design diff.
  Use when the user asks to "translate ingress", "convert ALB to Gateway API", or "what's the network plan".
  Don't use for identity translation (use identity-translation instead).
---

# Network translation

You translate Amazon Elastic Kubernetes Service (EKS) networking — load
balancers, ingress, services, security groups, Domain Name System (DNS), Web
Application Firewall (WAF) — into the Google Kubernetes Engine (GKE)
equivalents. You produce diff'd manifests and a network design document.

## Purpose

Every Service, Ingress, Application Load Balancer (ALB) or Network Load Balancer
(NLB), Route 53 record, security group, and WAF rule that crosses traffic into
the EKS cluster needs a GKE counterpart. This skill produces that mapping with
auditable manifests.

> [!NOTE]
>
> **Role Boundaries:** The platform engineering team provisions the GKE Gateway
> API controller infrastructure (`gateway_api_config`), Cloud Armor WAF
> policies, and Cloud DNS records in Terraform. Application `Gateway` and
> `HTTPRoute` manifests are generated as reference templates for application
> developers to own and deploy into their application namespaces.

## When to use this skill

- The user asks to "translate ingress", "set up GKE Gateway equivalents",
  "design the GKE network".

Do NOT use to translate identity (that's `identity-translation`).

## Prerequisites

- `<output_dir>/01-discovery/inventory.json` with the network section populated.
- `<output_dir>/03-landing-zone/plan.md` with VPCs, subnets, and clusters
  defined.
- Required CLI tools installed and authenticated: `gcloud`, `kubectl`,
  `check-jsonschema`, and `terraform`.

### Missing prerequisites

If you cannot meet any prerequisite, stop immediately. Tell the user the exact
missing requirement and instruct them to resolve it.

## Procedure

### Step 1 — Build the source-side network model

From `inventory.json`, enumerate per cluster:

- ALBs: ARN, originating Ingress, hostnames (`spec.rules[].host`), TLS cert ARN,
  target groups, target type (instance/ip), listener rules, attached WAF.
- NLBs: ARN, originating Service, hostnames (Route 53), target groups, port
  mappings.
- Internal vs internet-facing.
- VPC ID and subnets the LBs live in.
- Security groups attached to LBs and to nodes.
- Route 53 records pointing at LB DNS names (and which hosted zones).
- AWS WAF web ACLs and their rules.

### Step 2 — Map LBs to GKE constructs

Read and follow the decision table and X-shot examples in
`references/class-mappings.md` to map source EKS load balancer classes, ingress
classes, and Gateway classes (`alb`, `gateway.k8s.aws/alb`, `nginx`, `nlb`) to
target GKE classes (`gke-l7-global-external-managed`, `gke-l7-rilb`,
`gke-l4-regional-external-managed`).

Produce one `Gateway` per (LB, scope) tuple. Multiple Ingresses fronting the
same ALB merge into multiple `HTTPRoute`s attached to the same `Gateway`.

See `assets/source-ingress.yaml` for an example of a source EKS Ingress, and
`assets/target-gateway.yaml` for the translated GKE Gateway API equivalents.

> [!TIP]
>
> If a workload requires retaining an in-cluster ingress controller (such as
> `nginx-ingress` with custom Lua scripts), read and follow the deployment
> instructions in `references/in-cluster-ingress.md`.

### Step 3 — TLS / certificates

Decide per hostname:

- **Google-managed certificate** (Certificate Manager) — preferred for any
  hostname you control using Cloud DNS or you can prove with DNS01.
- **Self-managed certificate** — when the cert needs to come from your CA, or
  when ACME issuance is centralized elsewhere.

Plan the migration of every ACM-issued cert: usually re-issue in Certificate
Manager rather than export/import (private keys can't always be exported).

### Step 4 — Cloud Armor (replaces AWS WAF)

Read and follow the decision tables, OWASP CRS paranoia levels, and CEL
pre-filter expressions in `references/cloud-armor-waf.md` to translate AWS WAF
Managed Rule Groups and custom rules into Google Cloud Armor Security Policies.

Reference the Terraform policy skeleton in `assets/cloud-armor.tf` to generate
the Cloud Armor security policy Terraform. Attach security policies using
`GCPBackendPolicy.spec.default.securityPolicy` targeting the relevant Service.

### Step 5 — DNS

For every Route 53 record that points at an LB DNS name:

1.  Plan a Cloud DNS record in the target zone (or the same zone, depending on
    TLD ownership). For apex hostnames, GKE Gateway gives you an IP; use an `A`
    record. For subdomains, you can `CNAME` to the Gateway address — but you'll
    need a deterministic Gateway hostname or static IP.
1.  For weighted DNS, use Cloud DNS routing policies (`weighted_round_robin`) or
    move the records to a CDN/global LB that supports weighted backends
    directly.
1.  If the existing zone is in Route 53 and you can't move it yet, plan
    delegation using NS records, or configure the cutover to update Route 53
    directly.

Capture every DNS change as a `dns-plan.md` under the run directory.

### Step 6 — Security groups → VPC firewall + NetworkPolicy

EKS security groups attached to nodes and LBs map to:

- **Node-to-node traffic**: GKE handles intra-cluster networking through the VPC
  subnet's firewall rules. The Shared VPC's hierarchical firewall plus
  `gke-cluster-name-` rules cover most.
- **External-to-LB**: GFE health check ranges and your allow-listed CIDRs become
  VPC firewall `INGRESS` rules targeting the LB's network tag.
- **Pod-to-pod within cluster**: implement as Kubernetes NetworkPolicy
  (Dataplane V2 enforces). Translate any `aws-load-balancer-controller`
  annotation that restricts pod ingress into a NetworkPolicy.

Produce per-namespace NetworkPolicy YAML only if there were equivalent pod-level
restrictions in EKS. This is a strict like-for-like migration; do not introduce
a default-deny policy or other optimizations if the source did not have one.

### Step 7 — Egress

EKS pods typically egressed through NAT Gateway with no per-pod identity. GKE
pods egress through Cloud NAT, with Workload Identity providing per-workload
identity for Google Cloud API calls.

For external (non-Google Cloud) egress destinations:

- Static egress IPs: reserve in Cloud NAT and document.
- Allow-listed destinations on the partner side: send the partner the new IPs
  ahead of cutover.
- VPC peering / TGW reachability: re-create with VPC peering or NCC (Network
  Connectivity Center).

### Step 8 — Output the design diff

Render `<output_dir>/04-network-translation/network-design.md` with:

- Diagram (ASCII or Mermaid) of source vs target network topologies, side by
  side.
- Table mapping every source LB ARN to the target Gateway/Service, explicitly
  documenting architectural shifts like Gateway's built-in use of NEGs over
  target-type annotations.
- Cert migration plan.
- Cloud Armor policy mapping table.
- DNS cutover plan (which records, which TTLs, planned change windows).
- Firewall rule changes.

Render `<output_dir>/04-network-translation/manifests/` with one file per
Gateway and HTTPRoute, plus per-namespace NetworkPolicy.

Record the chosen ingress controller migration strategy (`gateway_api` or
`in_cluster_nginx`) in `platform-handoff.json` under
`network.ingress_architecture` so downstream observability and landing-zone
skills configure appropriate scrape targets and firewall rules.

Render `<output_dir>/04-network-translation/network-map.json` matching the
schema defined in `assets/network-map.schema.json` to hand off target Gateway
parent references, assigned hostnames, TLS settings, and policy bindings to
application developers.

Validate the generated `network-map.json` against the schema using
`check-jsonschema`:

```bash
check-jsonschema --schemafile assets/network-map.schema.json <output_dir>/04-network-translation/network-map.json
```

## Decision points

| Decision                                                   | Default                                                                                                               | When to deviate                                                                                                                                                                                                                                      |
| ---------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Gateway API vs Ingress vs L4 Service                       | Strict like-for-like mapping. If source is L4, use L4. If source is ALB (L7), use Gateway API.                        | Do not deviate. Leave optimizations for a later phase.                                                                                                                                                                                               |
| In-cluster Ingress Controller (`nginx`, `kong`, `traefik`) | Translate directly to GKE Gateway API (`Gateway` + `HTTPRoute`) with Google Cloud Certificate Manager and Cloud Armor | Deviate to deploying with Helm with Google Cloud L4 Service annotations (`cloud.google.com/l4-rbs: "enabled"`) + `cert-manager` per `references/in-cluster-ingress.md` only when workloads require incompatible NGINX custom snippets or Lua scripts |
| Global vs regional Gateway                                 | Regional, like-for-like with AWS region                                                                               | Do not deviate unless explicitly requested.                                                                                                                                                                                                          |
| ACM cert reuse vs Certificate Manager re-issue             | Certificate Manager re-issue                                                                                          | Reuse only if private key export is feasible and required                                                                                                                                                                                            |
| AWS WAF preconfigured rules → Cloud Armor preconfigured    | 1:1 by category                                                                                                       | Custom rewrites for org-specific rules                                                                                                                                                                                                               |
| Egress IP Preservation (NAT)                               | Allocate new static IPs in Cloud NAT and plan firewall updates                                                        | Reuse BYOIPs only if explicitly brought to Google Cloud (rare)                                                                                                                                                                                       |

## Outputs / deliverables

```text
<output_dir>/04-network-translation/
├── network-design.md
├── network-map.json
├── manifests/
│   ├── gateways/
│   ├── httproutes/
│   ├── network-policies/
│   ├── healthcheck-policies/
│   └── backend-policies/
├── terraform/
│   ├── cloud-armor/
│   ├── certificates/
│   └── dns/
├── dns-plan.md
└── escalations.md
```

## Validation

- Every ALB/NLB in `inventory.json` has a target Gateway/Service in the
  manifests.
- Every host in any source Ingress is covered by exactly one target HTTPRoute.
- Every TLS cert ARN in source has a planned Certificate Manager entry or
  self-managed cert.
- Cloud Armor mapping has been reviewed by the user; non-trivial WAF rules have
  explicit acceptance.
- Apply manifests to a non-prod cluster and confirm: `kubectl describe gateway`
  shows `Programmed: True`; the Gateway has an external IP; `curl https://...`
  succeeds against a backend that already exists or against a placeholder.
- NetworkPolicy doesn't break existing flows in the soak test.

## Escalation triggers

- Workloads using `LoadBalancerSourceRanges` with overlapping or conflicting
  CIDRs across namespaces — surface for review.
- TLS certs that cannot be reissued (private CA chain, customer-supplied) —
  surface for human plan.
- Custom AWS WAF JS challenge / CAPTCHA flows — Cloud Armor reCAPTCHA Enterprise
  has a different UX; needs product decision.
- Egress dependencies on AWS-only endpoints, for example, an S3 VPC endpoint —
  needs cross-cloud egress plan.

## Common pitfalls

- **Forgetting health check paths.** The ALB health check path is in an
  annotation; in GKE it's a `HealthCheckPolicy`. Skip and your backends look
  unhealthy.
- **Not setting `BackendConfig`/`GCPBackendPolicy`.** Timeouts default to 30s.
  Many workloads need longer. Translate explicitly.
- **TLS hostname mismatches.** ACM SANs migrate cleanly; ACM wildcards plus
  exotic SANs sometimes don't. Verify each cert.
- **Cloud Armor preconfigured WAF tuning level.** `cve-canary` is sensitive;
  `cve-stable` is the production default. Match severity.
- **Introducing new security controls.** Do not introduce NetworkPolicies or
  Cloud Armor unless they map to existing AWS controls. Stick to like-for-like
  translation.
- **GKE ManagedCertificate stays in `FAILED_NOT_VISIBLE` until LB IP attaches
  and DNS resolves to it.** Sequence the cutover so DNS is updated _before_ the
  cert is expected to validate, not after.
- **ManagedCertificate doesn't work with nginx-ingress.** Decision point:
  Gateway+ManagedCertificate, or nginx-ingress+cert-manager. Make it up-front.
- **Gateway API on GKE expects a pre-shared SslCertificate**, not a
  ManagedCertificate CR. When targeting Gateway API, plan TLS using Certificate
  Manager from the start.
- **ALB `group.name` semantics don't translate to Gateway API.** Rebuild as one
  Gateway with multiple HTTPRoutes.
- **Target Port Mismatches.** Ensure the Google Cloud LoadBalancer or Gateway
  `targetPort` exactly matches the port that the backing container actually
  listens on, for example, `8080` vs `80`. Mismatches will cause Google Cloud
  health checks to silently fail, leaving external IPs inaccessible.
