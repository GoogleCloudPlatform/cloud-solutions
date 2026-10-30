---
name: network-translation
description: >-
  Translates Amazon Elastic Kubernetes Service (EKS) Application Load Balancer
  (ALB) Ingress annotations and AWS Web Application Firewall (WAF)
  configurations into Google Kubernetes Engine (GKE) Gateway API resources,
  Cloud Armor policies, and Google Cloud backend policies. Use when converting
  AWS ALB ingress annotations to GKE Gateway API and HTTPRoute resources.
  Don't use for IAM service account mapping or storage PVC remapping.
---

# Network translation

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

Automate the mapping and translation of Amazon Elastic Kubernetes Service (EKS)
ALB (Application Load Balancer) Ingress annotations (external routing, path
mapping, TLS termination, health check endpoints) and AWS WAF (Web Application
Firewall) protection settings into Google Kubernetes Engine (GKE) Gateway API
configuration resources.

## When to use this skill

Trigger on:

- "Translate EKS ALB Ingress to GKE Gateway"
- "Map Ingress annotations to HTTPRoute rules"
- "Convert AWS WAF to Cloud Armor security policies"

## Prerequisites

- `python3` version 3.10 or later
- Install dependencies listed in `scripts/requirements.txt`:
  `pip install --require-hashes -r scripts/requirements.txt`
- Path to handoff directory containing `workload-handoff.json` (or
  `workload-handoff-namespace.json`) and `network-map.json`
- Path to directory containing raw EKS manifests (`--raw-manifests-dir`)

## Assets and references

The following schema files under `assets/schemas/` define the JSON contracts
used by this skill:

- `network-map.schema.json`: Schema for validating network policy and ingress
  mappings.
- `workload-handoff.schema.json`: Schema for cluster-level workload handoff
  specifications.
- `workload-handoff-namespace.schema.json`: Schema for namespace-level workload
  handoff specifications.

The following reference documents under `references/` provide translation
guidance:

- [references/ingress_to_gateway_mapping.md](references/ingress_to_gateway_mapping.md):
  Guidance for converting EKS ALB Ingress rules to GKE Gateway API.
- [references/cloud_armor_waf_rules.md](references/cloud_armor_waf_rules.md):
  Guidance for translating AWS WAF rules to Google Cloud Armor policies.

The following dependency files under `scripts/` are used by this skill:

- `scripts/requirements.in`: Input dependencies for python validation scripts.
- `scripts/requirements.txt`: Hashed dependency lockfile for python validation
  scripts. Install using:
  `pip install --require-hashes -r scripts/requirements.txt`

## Procedure

### Step 1 — Validate network mapping completeness

Verify that all Ingress/Gateway classes, TLS certificates, and NetworkPolicy
CIDRs referenced in the raw manifests have valid GKE and Google Cloud target
mappings in `network-map.json`:

```bash
python3 scripts/validate_network_map.py \
  --handoff-dir "${HANDOFF_DIR:-.}" \
  --raw-manifests-dir "${RAW_MANIFESTS_DIR:-./raw-manifests}"
```

### Step 2 — Translate network resources

When translating the workload manifests:

1.  **Ingress and Gateway Class mapping:**
    - Parse EKS `Ingress` or `Gateway` resources.
    - Replace the EKS `ingressClassName` / `gatewayClassName` (or
      `kubernetes.io/ingress.class` annotations) with the corresponding GKE
      `GatewayClass` name from `class_mappings`.
2.  **Route and Annotation translation:**
    - Translate EKS `Ingress` resources into GKE `Gateway` and `HTTPRoute`
      resources (using portable fields for hostnames, paths, and backend
      references).
    - Strip AWS-specific annotations (`alb.ingress.kubernetes.io/*`).
    - Use GKE-native policies (like `HealthCheckPolicy` or `GCPBackendPolicy`)
      for custom health checks and Cloud Armor configurations.
3.  **TLS Certificate mapping:**
    - Replace AWS ACM certificate ARNs or local TLS secret references with GKE
      and Google Cloud certificate references using the `certificates` map.
4.  **Domain mapping:**
    - Update all rules/hostnames to map custom domains using `domain_mappings`.
5.  **NetworkPolicy translation:**
    - Scan `NetworkPolicy` resources for hardcoded EKS/AWS CIDR blocks.
    - Rewrite `ipBlock.cidr` values using target Google Cloud VPC and subnet
      CIDRs from `cidr_mappings`.
