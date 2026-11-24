---
okf_version: "0.2"
document_id: "ROA-2026-8812"
tenant_id: "tenant-retailstream-beta"
trust_tier: "ATTESTED_STANDARD_RUNBOOK"
freshness_ttl_seconds: 86400
cmek_key: "retailstream-beta-cmek"
---

# RetailStream Corp — POS Checkout Redis Connection Pool Starvation Runbook

1.  Confirm `tenant_id == 'tenant-retailstream-beta'` and
    `subscription_tier == 'standard'`.
1.  Redact all customer payment card PANs (`[REDACTED_PAYMENT_PAN]`) via Hop 4
    Cloud DLP.
1.  Cross-reference ServiceNow ITOM incident `INC0010001`
    (`correlation_id=ROA-2026-8812`) and drain stale POS checkout connections.
