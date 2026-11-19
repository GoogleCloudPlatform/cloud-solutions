# ADR-0011: Memory Envelope Encryption and Tenant + User Qualified Memory

- **Status**: Accepted; implemented (`v2` record format in
  `agents/memory_crypto.py`; follow-ups listed under Decision)
- **Date**: 2026-10-27
- **Applies To**: Hop 3 (Memory Bank, ADK sessions, RAG); inventory rows #2-#6,
  #14, #15 in [Tenant Isolation Assurance](../tenant_isolation_assurance.md);
  deployment audit finding F1
- **Code**: [`agents/memory_crypto.py`](../../agents/memory_crypto.py),
  [`agents/memory_bank.py`](../../agents/memory_bank.py),
  [`agents/gcp_live_bridge.py`](../../agents/gcp_live_bridge.py)
  (`LiveFirestoreMemoryBank`, `LiveADKVertexRunner`)
- **Tests**:
  [`tests/security/test_memory_encryption.py`](../../tests/security/test_memory_encryption.py),
  [`tests/security/test_memory_write_rules.py`](../../tests/security/test_memory_write_rules.py)

## Context

- **The memory key was derived, not protected.** The data key was
  `sha256("cymbal-cmek-dek-v1:" + kms_key_name)`, and the key name was stored
  next to the ciphertext. Cloud KMS was never called. Anyone able to read
  Firestore (for example the 9 project Viewers) could decrypt every tenant's
  memory (F1).
- **Sessions were keyed by IdP subject only** (`user_id = sub`). Subjects are
  unique per IdP, not globally, so two tenants' users could share a persisted
  session.
- **Private memory was not bound to its user.** USER / SESSION memory was keyed
  `tenant/scope/session/actor`; any user in the tenant could read it, and RAG
  returned it.
- **Shared memory was writable by anyone.** Any role, or an injected tool
  output, could write TENANT or cross-tenant GLOBAL memory (poisoning).

## Decision

1.  **Envelope encryption, format `v2`.** A random 256-bit data key per record
    encrypts the payload (AES-256-GCM). Cloud KMS wraps the data key with the
    tenant's key **as the tenant's service account** (credential broker from
    ADR-0010). Stored: ciphertext, nonce, wrapped data key, key name. Nothing
    stored lets a reader derive the key.
1.  **AAD binds the record to its owner and place**: canonical JSON of
    `[v2, tenant, user, scope, composite_key]`, computed from the **caller's**
    verified identity and the key's parsed shape. Namespace and scope come only
    from the key, never from stored fields; a stored scope or KMS key name that
    disagrees with the key is refused.
1.  **Tenant + user qualified identifiers.** ADK `user_id = "{tenant}:{sub}"`.
    Keys: USER `{tenant}/{user}/user/_/{actor}` (persists across sessions),
    SESSION `{tenant}/{user}/session/{session}/{actor}`, TENANT/STRATEGY
    `{tenant}/_tenant/{scope}/{actor}`, GLOBAL `global/global/{actor}`.
    `user = sha256(tenant:sub)[:16]`; empty subjects are rejected. The tenant ID
    `global` and key `cymbal-platform-global` are reserved. Firestore document
    IDs are `sha256(key)`, and reads verify the stored key.
1.  **Write rules.** GLOBAL is written only by operator tooling
    (`scripts/curate_global_memory.py`) with an explicit `OperatorPrincipal`
    (operator plus a different approver), only content whose hash matches the
    reviewed dry run, and never silently overwritten. It is sealed with the
    platform key `cymbal-platform-global`. **IAM is the enforcing control:** the
    serving identity has decrypt-only on that key and curators have
    encrypt-only, so serving code cannot forge GLOBAL entries. A best-effort
    filter refuses content naming a tenant (IDs, names, distinctive words,
    separators, common look-alike letters). TENANT / STRATEGY writes need the
    `memory:tenant.write` scope, granted to `sre_admin` only.
1.  **Injection screen on every read.** Direct reads and RAG screen every string
    leaf of a decrypted record (not its `repr`). A flagged record is marked
    `quarantined` in the store, logged as a security event (key fingerprint
    only), and refused from then on. RAG candidates are filtered by the same
    read rule (own tenant shared, own user private, GLOBAL). The live Firestore
    bank has no RAG method yet; its direct read path is screened. Payloads the
    screen cannot inspect (nested beyond 32 levels, non-JSON types) fail closed.
    _Known limits:_ curator/approver names and the content hash are advisory
    (self-asserted, outside the AAD). The serving identity keeps Firestore
    write, so it cannot forge GLOBAL entries but could delete, roll back to an
    older sealed version, or quarantine one; a version counter in the AAD and
    Firestore IAM conditions are follow-ups.
1.  **Legacy `v1` records are refused**, never decrypted with the derived key.
1.  **Unwrapped data keys are cached** for at most 60 seconds per (principal,
    key, AAD, record), bounded in size, never logged or persisted. Each user
    unwraps through KMS at least once, so every principal is audited. Disabling
    a key takes effect within the TTL; `clear_cache()` makes it immediate.
1.  **Platform capabilities need an asserted role.** `memory:tenant.write` is
    granted only when the IdP explicitly asserts `sre_admin`; a token without
    `user_role` never receives it. The OBO signature covers scopes and the CMEK
    key, and sub-agent hops refuse unsigned state.

## Consequences

- **F1 closed at the data layer.** A Viewer or a leaked Firestore export sees
  ciphertext only. The Validator role (PR 4) remains as defense in depth.
- **Every memory read is a KMS audit event** (first read per cache window), and
  disabling a tenant's key crypto-shreds its memory.
- **Cost / latency:** one KMS `encrypt` per write and at most one `decrypt` per
  record per cache window.
- **Migration:** existing `v1` documents are unreadable by design. In the
  sandbox they are synthetic and are deleted, not re-encrypted.
- **Operational:** the platform GLOBAL key must exist before GLOBAL memory is
  curated; Terraform imports it in PR 4.

## Alternatives considered

- **Re-derive per tenant with a secret pepper:** still a shared secret in the
  runtime; no IAM boundary, no audit trail, no crypto-shredding.
- **Per-tenant (not per-record) data key:** fewer KMS calls but a single leaked
  data key exposes all of a tenant's memory; the cache gives most of the latency
  benefit.
- **Managed Agent Engine Memory Bank:** evaluated separately; it changes who
  holds the keys.
