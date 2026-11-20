# ADR-0001: 3-Plane Operational Decomposition & 80% Reusable Core Across Patterns A, B, and C

- **Status**: Accepted
- **Date**: 2026-10-08
- **Applies To**: Workstreams 2 (Pattern A: Pooled), 3 (Pattern B: Siloed), and
  4 (Pattern C: Hybrid)

## Context

B2B SaaS Independent Software Vendors (ISVs) serve customers across a wide
spectrum of regulatory and commercial tiers—from standard self-serve e-commerce
tenants (**RetailStream Corp**) to regulated financial institutions (**FinVault
Bank**). If an engineering team builds separate codebases for pooled, hybrid,
and siloed deployments, they suffer from severe "snowflake drift," duplicated
security bugs, and unsustainable SRE overhead.

## Decision

1.  **Decompose the platform into three strict operational planes**:
    - **Control Plane**: Agent Registry in Gemini (ARD catalog PDP), GCP Agent
      Identity (2LO/3LO Auth Manager), and BigQuery Agent Analytics
      (OpenTelemetry COGS sink).
    - **Compute Plane**: Cloud Armor + IAP Edge, Ingress/Egress Agent Gateways
      (PEPs), ADK 2.0 Agent Runtime with gVisor sandboxes, and Vertex AI Model
      Garden.
    - **Data & Memory Plane**: Stateless MCP Tool Servers, AlloyDB for
      PostgreSQL with Row-Level Security (RLS), Cloud Firestore (5-Level Memory
      Bank), and Cloud Memorystore for Redis (token-bucket bulkheads).
1.  **Enforce an 80% Reusable Core Codebase Mandate**:
    - All agent definitions (`agents/`), interceptor hooks
      (`before_agent_callback`), cryptographic context envelopes
      (`ContextEnvelope`), stateless MCP tool implementations (`mcp_server/`),
      and automated breach simulations (`tests/`) are topology-agnostic.
    - Migrating a tenant from **Pattern A (Pooled)** to **Pattern B (Dedicated
      Single-Tenant Silo)** or **Pattern C (Hybrid PSC Bridge)** requires zero
      changes to agent or MCP application code—only a 20% infrastructure/routing
      delta in Terraform (`terraform/`).

## Consequences

- **Positive**: One unified codebase, runbook, and security test suite governs
  all three tenancy topologies.
- **Negative**: Requires strict discipline that no agent or MCP tool ever relies
  on ambient project-level credentials or hardcoded single-tenant state.
