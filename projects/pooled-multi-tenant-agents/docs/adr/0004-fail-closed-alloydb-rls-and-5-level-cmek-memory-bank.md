# ADR-0004: Fail-Closed AlloyDB Row-Level Security (`SET LOCAL`) & 5-Level CMEK Memory Bank Partitioning

- **Status**: Accepted
- **Date**: 2026-10-08
- **Applies To**: Subsystem 4 (5-Level Memory Bank), Subsystem 7 (AlloyDB RLS
  Persistence)

## Context

In a high-density pooled architecture, multiple tenants share a connection pool
to AlloyDB for PostgreSQL and a managed Memory Bank store. Two critical failure
modes must be prevented:

1.  **Connection Pool State Bleed & Missing Context**: If a connection sets
    session-level state (`SET app.current_tenant_id`) without resetting it on
    transaction commit, or if a query runs when `app.current_tenant_id` is
    unset, rows could leak across pooled requests.
1.  **Cross-Scope Memory Retrieval**: Multi-scope memory read operations must
    not allow one tenant to read another tenant's episodic or strategy memories,
    and regulated tenants require cryptographic key separation (CMEK).

## Decision

1.  **Transactional `SET LOCAL` with Fail-Closed RLS Policy**:
    - Every database checkout in `RLSDatabasePool` opens an explicit transaction
      and executes `SET LOCAL app.current_tenant_id = $1;`, which PostgreSQL
      automatically resets when the transaction ends.
    - Tables enforce `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY`
      with a fail-closed predicate:

        ```sql
        USING (
          NULLIF(current_setting('app.current_tenant_id', true), '') IS NOT NULL
          AND tenant_id = current_setting('app.current_tenant_id', true)
        )
        ```

    - `RLSDatabasePool.validate_sql_safety` blocks any query containing
      `SET LOCAL`, `RESET`, or tautology injections (`OR 1=1`).

1.  **5-Level Composite Memory Bank Keys + Per-Tenant CMEK Verification**:
    - All non-global Memory Bank records are keyed as
      `{tenant_id}/{scope}/{session_id}/{actor}` across the 5 logical scopes
      (`global`, `tenant`, `strategy`, `user`, `session`).
    - `MemoryBankPartitioner.read_memory` verifies both the caller's
      `{tenant_id}/` prefix and matching per-tenant Cloud KMS CMEK key
      identifier before returning state.

## Consequences

- **Positive**: Guarantees 0 rows returned if tenant context is ever omitted and
  prevents connection-pool state bleed across async workers.
- **Negative**: Every database read/write must execute inside a transaction
  block.
