---
okf_version: "0.2"
document_id: "DOC-FV-SEC-17A4-2026"
tenant_id: "tenant-finvault-alpha"
trust_tier: "ATTESTED_ENTERPRISE_COMPLIANCE"
freshness_ttl_seconds: 86400
cmek_key: "finvault-alpha-cmek"
---

# FinVault Bank — SEC Rule 17a-4 Wire Settlement Escalation Procedure

1.  Confirm `tenant_id == 'tenant-finvault-alpha'` and
    `subscription_tier == 'enterprise'`.
1.  Redact all customer SSNs (`[REDACTED_US_SSN]`) and ABA routing numbers
    (`[REDACTED_ABA_ROUTING]`) via Hop 4 Cloud DLP.
1.  Escalate P1 wire settlement anomalies exceeding 4 hours to the OCC via
    `finvault_regulatory_escalation_agent` and link Jira Cloud issue
    `FINVAULT-1`.
