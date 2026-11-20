-- Copyright 2026 Google LLC
--
-- Licensed under the Apache License, Version 2.0 (the "License");
-- you may not use this file except in compliance with the License.
-- You may obtain a copy of the License at
--
--     http://www.apache.org/licenses/LICENSE-2.0
--
-- Unless required by applicable law or agreed to in writing, software
-- distributed under the License is distributed on an "AS IS" BASIS,
-- WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-- See the License for the specific language governing permissions and
-- limitations under the License.

-- ============================================================================
-- Cymbal SaaS Pattern A (Pooled Tier) — AlloyDB for PostgreSQL RLS Schema
-- Enforces Hop 5 Fail-Closed Row-Level Security via `app.current_tenant_id`
-- ============================================================================

CREATE TABLE IF NOT EXISTS tenant_incidents (
    incident_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    service_name TEXT NOT NULL,
    severity TEXT NOT NULL,
    summary TEXT NOT NULL,
    pii_notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tenant_runbooks (
    runbook_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    title TEXT NOT NULL,
    remediation_steps TEXT NOT NULL
);

-- Least-Privilege PostgreSQL RBAC Posture (`cymbal_mcp_app` runtime role):
-- 1. Non-superuser, non-bypass-RLS application role (`NOBYPASSRLS`).
-- 2. Default `PUBLIC` privileges explicitly revoked.
-- 3. Column-scoped `SELECT` and restricted `UPDATE (severity, summary)` privileges (never `tenant_id` or `incident_id`).
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cymbal_mcp_app') THEN
        CREATE ROLE cymbal_mcp_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION;
    END IF;
END
$$;

REVOKE ALL ON TABLE tenant_incidents, tenant_runbooks FROM PUBLIC;
GRANT SELECT (incident_id, tenant_id, service_name, severity, summary, pii_notes, created_at)
    ON TABLE tenant_incidents TO cymbal_mcp_app;
GRANT UPDATE (severity, summary)
    ON TABLE tenant_incidents TO cymbal_mcp_app;
GRANT SELECT (runbook_id, tenant_id, title, remediation_steps)
    ON TABLE tenant_runbooks TO cymbal_mcp_app;

-- Enable and FORCE Row-Level Security even for table owners
ALTER TABLE tenant_incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_incidents FORCE ROW LEVEL SECURITY;

ALTER TABLE tenant_runbooks ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_runbooks FORCE ROW LEVEL SECURITY;

-- Fail-Closed RLS + RBAC Policy:
-- `current_setting(..., true)` returns NULL/empty when unset. All three session GUCs
-- (`app.current_tenant_id`, `app.current_user_role`, and `app.current_agent_id`) MUST be
-- explicitly bound and allowlisted inside the transaction, guaranteeing 0 rows on any missing claim.
DROP POLICY IF EXISTS tenant_incidents_rls_policy ON tenant_incidents;
CREATE POLICY tenant_incidents_rls_policy ON tenant_incidents
    USING (
        NULLIF(current_setting('app.current_tenant_id', true), '') IS NOT NULL
        AND tenant_id = current_setting('app.current_tenant_id', true)
        AND NULLIF(current_setting('app.current_user_role', true), '') IS NOT NULL
        AND current_setting('app.current_user_role', true) IN (
            'sre_admin',
            'compliance_officer',
            'read_only_analyst',
            'incident_responder',
            'support_viewer',
            'analyst'
        )
        AND NULLIF(current_setting('app.current_agent_id', true), '') IS NOT NULL
        AND current_setting('app.current_agent_id', true) IN (
            'cymbal_shared_diagnostic_agent',
            'finvault_regulatory_escalation_agent',
            'sre_diagnostic_agent'
        )
    );

-- Restrictive Write RBAC Policy: only mutating SRE/incident roles may UPDATE incident status/summary.
DROP POLICY IF EXISTS tenant_incidents_write_rbac_policy ON tenant_incidents;
CREATE POLICY tenant_incidents_write_rbac_policy ON tenant_incidents
    AS RESTRICTIVE
    FOR UPDATE
    USING (
        NULLIF(current_setting('app.current_tenant_id', true), '') IS NOT NULL
        AND tenant_id = current_setting('app.current_tenant_id', true)
        AND NULLIF(current_setting('app.current_user_role', true), '') IS NOT NULL
        AND current_setting('app.current_user_role', true) IN (
            'sre_admin',
            'incident_responder'
        )
        AND NULLIF(current_setting('app.current_agent_id', true), '') IS NOT NULL
        AND current_setting('app.current_agent_id', true) IN (
            'cymbal_shared_diagnostic_agent',
            'sre_diagnostic_agent'
        )
    )
    WITH CHECK (
        NULLIF(current_setting('app.current_tenant_id', true), '') IS NOT NULL
        AND tenant_id = current_setting('app.current_tenant_id', true)
        AND current_setting('app.current_user_role', true) IN (
            'sre_admin',
            'incident_responder'
        )
    );

DROP POLICY IF EXISTS tenant_runbooks_rls_policy ON tenant_runbooks;
CREATE POLICY tenant_runbooks_rls_policy ON tenant_runbooks
    USING (
        NULLIF(current_setting('app.current_tenant_id', true), '') IS NOT NULL
        AND tenant_id = current_setting('app.current_tenant_id', true)
        AND NULLIF(current_setting('app.current_user_role', true), '') IS NOT NULL
        AND current_setting('app.current_user_role', true) IN (
            'sre_admin',
            'compliance_officer',
            'read_only_analyst',
            'incident_responder',
            'support_viewer',
            'analyst'
        )
        AND NULLIF(current_setting('app.current_agent_id', true), '') IS NOT NULL
        AND current_setting('app.current_agent_id', true) IN (
            'cymbal_shared_diagnostic_agent',
            'finvault_regulatory_escalation_agent',
            'sre_diagnostic_agent'
        )
    );
