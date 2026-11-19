# ADR-0002: 5-Hop Cryptographic Context Chain with RFC 8693 OBO, RFC 9449 DPoP & ADK `contextvars`

- **Status**: Accepted
- **Date**: 2026-10-08
- **Applies To**: Subsystem 1 (Edge), Subsystem 2 (Ingress PEP), Subsystem 3
  (ADK Runtime)

## Context

Traditional web multi-tenancy validates a bearer JWT at the API edge and passes
a string `tenant_id` header to downstream microservices. In autonomous
multi-turn agentic loops:

1.  Client-supplied headers (`X-Tenant-ID`) can be spoofed if edge stripping is
    misconfigured.
1.  Passing raw end-user tokens or using ambient runtime service accounts
    creates a **Confused Deputy** vulnerability when an agent is targeted by
    prompt injection or chains sub-agents.
1.  Stolen bearer tokens can be replayed across turns or across MCP tool
    servers.

## Decision

1.  **Hop 1 (Edge Header Stripping & OIDC Verification)**: Cloud Armor and
    Identity-Aware Proxy (IAP) unconditionally strip any client-supplied
    `X-Tenant-ID` or `X-Subscription-Tier` headers and verify the federated IdP
    token (Google Workspace OIDC for FinVault Bank; Microsoft Entra ID for
    RetailStream Corp).
1.  **Hop 2 (RFC 8693 OBO + RFC 9449 DPoP Binding)**: The Ingress PEP exchanges
    the inbound OIDC identity for a short-lived On-Behalf-Of (OBO)
    `ContextEnvelope` encoding three immutable dimensions (`SecurityContext`,
    `TenantContext`, `RequestContext`) bound to the sender's cryptographic key
    thumbprint (`dpop_jkt`) and single-use `jti`.
1.  **Hop 3 (Immutable `temp:tenant_id` & Sub-Agent Propagation)**: The ADK 2.0
    runtime binds the verified envelope into `contextvars`
    (`_ACTIVE_TENANT_ENVELOPE`) and `temp:tenant_id` in `InvocationContext`.
    Sub-agent delegation (`propagate_to_subagent`) explicitly propagates
    `temp:*` claims and fails closed (`E_SUBAGENT_PRINCIPAL_DROP`) rather than
    falling back to the ambient runtime service account.

## Consequences

- **Positive**: Eliminates header spoofing, token replay, and sub-agent
  principal drops end-to-end.
- **Negative**: Every hop and sub-agent invocation must carry and verify the
  signed `ContextEnvelope`.
