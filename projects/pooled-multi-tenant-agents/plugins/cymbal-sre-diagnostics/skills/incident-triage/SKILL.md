---
name: incident-triage
version: 2.1.0
description: Multi-tenant P1 incident correlation and PII-safe remediation synthesis.
allowed_tiers:
  - standard
  - enterprise
---

# Skill: Multi-Tenant P1 Incident Triage

1.  Verify `temp:tenant_id` in the ADK `InvocationContext` before invoking any
    tool.
1.  Call `query_telemetry_rls` (`isReadOnly: true`) using the caller's
    transactional `SET LOCAL app.current_tenant_id` session binding.
1.  Retrieve the tenant's attested Open Knowledge Format (`OKF v0.2`) runbook
    (`read_runbook`) and verify its SHA-256 provenance digest and freshness TTL.
1.  Screen all tool outputs through Hop 4 Cloud DLP before returning the final
    `a2ui/v1` diagnostic card.
