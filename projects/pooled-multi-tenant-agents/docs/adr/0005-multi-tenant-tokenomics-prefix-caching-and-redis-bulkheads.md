# ADR-0005: Multi-Tenant AI Tokenomics — Shared Prompt Prefix Caching, Redis Bulkheads & BigQuery OTel Attribution

- **Status**: Accepted
- **Date**: 2026-10-08
- **Applies To**: Subsystem 5 (Foundation Models & Caching), Subsystem 6 (Egress
  Gateway & BigQuery FinOps)

## Context

Multi-turn autonomous reasoning loops introduce variable, non-linear inference
costs (COGS). Without FinOps guardrails:

1.  Repeating identical base system instructions and DDL schemas across
    thousands of tenant turns wastes up to 90% of input token spend.
1.  A single Standard-tier tenant (**RetailStream Corp**) experiencing a runaway
    reasoning loop can exhaust shared regional model quota (**Noisy Neighbor**)
    and degrade latency for Enterprise-tier tenants (**FinVault Bank**).
1.  Platform operators lack per-tenant gross-margin visibility when all requests
    share a pooled runtime fleet.

## Decision

1.  **Global Shared Prompt Prefix Caching (`ContextCacheConfig`)**:
    - Base system instructions (`SHARED_SYSTEM_PROMPT_PREFIX`) and common tool
      schemas are cached globally across tenants while tenant-specific state
      (`temp:tenant_id`) is injected dynamically per turn, amortizing cached
      input token costs by up to 90%.
1.  **Tier-Aware Thinking Budgets & Redis Token-Bucket Bulkheads**:
    - `TokenBucketBulkhead` enforces strict tier ceilings prior to model/tool
      execution:
        - **FinVault Bank (Enterprise)**: 8,000 thinking-token budget, 120 RPM,
          250,000 TPM.
        - **RetailStream Corp (Standard)**: 4,000 thinking-token cap, 30 RPM,
          40,000 TPM (`429 Too Many Requests` when exceeded).
1.  **Per-Tenant Margin Attribution in BigQuery Agent Analytics**:
    - Every agent turn emits an `OTelAuditSpan` carrying mandatory `tenant_id`,
      `subscription_tier`, `agent_id`, `model_id`, `prompt_cache_hit`, and
      `billable_tokens` into the partitioned BigQuery table
      `cymbal_agent_analytics.tenant_otel_spans` and rollup view
      `v_tenant_tokenomics_cogs`.

## Consequences

- **Positive**: Protects Enterprise SLOs from Standard-tier noisy neighbors and
  provides real-time per-tenant COGS chargeback/showback.
- **Negative**: System prompts must be structured so static shared prefixes
  precede dynamic tenant-specific context to maximize cache hit rates.
