# Security Policy

## Scope

This project is an open-source **reference implementation** demonstrating pooled
multi-tenant AI agent isolation on Google Cloud. It runs with **synthetic
tenants and synthetic data fixtures** (`FinVault Bank`, `RetailStream Corp`).
Before deploying this architecture with production customer data, complete every
item in the readiness checklist in
[Gate: no customer data until these are true](README.md#gate-no-customer-data-until-these-are-true).

## Supported Versions

Active security updates apply to the `main` branch of this reference
implementation.

## Reporting a Vulnerability

Please **do not** post exploit details, tokens, or private keys in public GitHub
issues or pull requests.

To report a security vulnerability in Google Cloud open-source samples or
Google-maintained repositories, submit a report through Google's official
vulnerability reporting portal:

- **Report a vulnerability:** <https://g.co/vulnz>

When submitting a report, please include:

- The affected file path, endpoint, or Terraform module, along with reproduction
  steps, expected behavior, and observed behavior.
- Whether the issue crosses a tenant, user, role, or agent workload boundary.
- Any relevant configuration flags or environment prerequisites.

## Documented Architectural Scope & Known Limits

Architectural boundaries and open roadmap items are documented transparently in
the repository. Please review them when evaluating deployment posture:

- [Missing components and known gaps](README.md#missing-components-and-known-gaps)
- [What if a component is compromised?](README.md#what-if-a-component-is-compromised)
- [Isolation invariants](README.md#isolation-invariants) and
  [Tenant isolation assurance](docs/tenant_isolation_assurance.md)

Residual trust-root note: with `ADR-0014` B5 and `ADR-0016` enabled, per-agent
Cloud Run runtimes hold zero Cloud KMS signing or `TokenCreator` permissions;
`cymbal-pooled-gateway` serves as the context-token signing trust root (holding
zero `TokenCreator` and zero invoker access on `cymbal-credential-broker`), with
automated Cloud KMS signing-volume alerting tracked in
[Known gaps (#5)](README.md#missing-components-and-known-gaps).
