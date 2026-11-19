# Secrets Management: Secret Manager Is the Single Source of Truth

## Rule

| Mode                                                     | Where connector secrets come from                                                                                               | `.env`                  |
| :------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------ | :---------------------- |
| **Live** (`CYMBAL_LIVE_GCP=1` or `RUN_LIVE_GCP_TESTS=1`) | **GCP Secret Manager only**, read as the tenant's own service account ([ADR-0010](adr/0010-tenant-blast-radius-containment.md)) | **Ignored** for secrets |
| **Offline local sandbox** (default)                      | `.env` if present, otherwise deterministic local simulation                                                                     | Allowed                 |

Covered secrets:

| Secret Manager ID                            | Owner tenant               | Used by                           |
| :------------------------------------------- | :------------------------- | :-------------------------------- |
| `cymbal-finvault-jira-credentials`           | `tenant-finvault-alpha`    | `LiveAtlassianJiraConnector`      |
| `cymbal-retailstream-servicenow-credentials` | `tenant-retailstream-beta` | `LiveServiceNowITOMConnector`     |
| `cymbal-retailstream-entra-credentials`      | `tenant-retailstream-beta` | `LiveMicrosoftEntraOIDCConnector` |

Non-secret configuration (project ID, region, template IDs) can still come from
environment variables.

## Why

Previously, the Jira, ServiceNow, and Entra connectors read `.env` **before**
Secret Manager, even in live mode. The Jira rotation script also updated `.env`
first and pushed to Secret Manager only "if gcloud auth is active", skipping
that step silently otherwise.

That produced real drift on 2026-10-26:

- The working Jira token lived only in one developer's `.env`.
- Secret Manager still held the token created on 2026-10-12, which Jira rejected
  (401).
- Fresh clones, CI, and Cloud Run all read the stale secret.
- Jira treats bad credentials as an anonymous user, so searches returned **0
  issues instead of an error**.

## Guarantees now

1.  **Live mode never reads secrets from `.env`.** A stale local file cannot
    shadow a rotated credential. Tested in
    `tests/unit/test_secret_source_of_truth.py`.
1.  **Invalid third-party credentials fail loudly.** The Jira connector checks
    `/rest/api/3/myself` once per connector and raises
    `E_3P_CREDENTIALS_INVALID` instead of returning empty results. If Secret
    Manager itself is unreachable (or a secret is missing a required field),
    Jira, ServiceNow and Entra connectors raise `E_3P_SECRET_UNAVAILABLE`
    instead of silently falling back to simulated demo data. Isolation denials
    still surface as `PermissionError`.
1.  **Rotation goes through Secret Manager or not at all.**
    `scripts/rotate_jira_api_token.sh`:
    - aborts if gcloud is not authenticated;
    - verifies the new token against Jira **before** storing it;
    - adds a new secret version;
    - disables all older versions.

    Updating a local `.env` is opt-in (`--also-update-local-env`) and only
    affects the offline sandbox.

1.  **Each secret is readable only by its tenant's service account.**
    Cross-tenant secret reads are denied by IAM.

## Rotating a credential

```bash
gcloud auth login <admin-account> --force --no-launch-browser
./scripts/rotate_jira_api_token.sh "<NEW_TOKEN>"
RUN_LIVE_GCP_TESTS=1 uv run pytest tests/integration/test_live_gcp_integration.py -k jira
```

ServiceNow and Entra secrets: use `scripts/configure_3p_connectors.py`, which
writes to Secret Manager, then disable the previous version.

## Teammates and CI

- No secrets are shared by file. Teammates and CI read secrets through their own
  IAM access (or a tenant service account they may impersonate).
- If you keep a `.env` for offline work, treat it as disposable. It is never
  authoritative.
