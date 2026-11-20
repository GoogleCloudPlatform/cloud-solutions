# Security

## Reporting a vulnerability

To report a security issue, please use [g.co/vulnz](https://g.co/vulnz). The
Google Security Team will respond within 5 working days of your report on
g.co/vulnz.

We use g.co/vulnz for intake, and coordinate and disclose here using GitHub
Security Advisories to privately discuss and fix the issue. Please do not post
exploit details, tokens or keys in public issues or pull requests.

When you report, it helps to include:

- what you did (request, endpoint or test), what you expected and what happened;
- whether it crosses a tenant, user or role boundary;
- whether it affects a deployment or only the code.

## Scope

This repository is a reference implementation. It is designed to run with
**synthetic tenants and synthetic data only**. Do not load customer data or real
personal data into it; the gate for that is in
[`docs/implementation_status.md`](docs/implementation_status.md#gate-no-customer-data-until-these-are-true).

## Known limits

Known gaps are listed openly; please check them before reporting:

- [Missing components and known gaps](docs/implementation_status.md#missing-components-and-known-gaps)
- [What if a component is compromised?](docs/implementation_status.md#what-if-a-component-is-compromised)
  (the component compromise table covering before B5 and today's live B5 +
  ADR-0016 split)
- [Isolation invariants](docs/implementation_status.md#isolation-invariants) and
  [`docs/tenant_isolation_assurance.md`](docs/tenant_isolation_assurance.md)

DLP false positives: the egress DLP filter matches card numbers by digit pattern
alone (no checksum). A platform identifier that happens to be all digits (about
1 random sandbox ID in 1,200) is redacted as a card number in tool output. This
over-redacts; it does not leak.

Residual trust-root note: with ADR-0014 B5 and ADR-0016 live, per-agent runtimes
hold zero KMS signing or `TokenCreator` permissions; `cymbal-pooled-gateway`
remains the context-token signing trust root (holding zero `TokenCreator` and
zero invoker access on `cymbal-credential-broker`), with automated KMS
signing-volume alerting tracked in
[Known gaps (#5)](docs/implementation_status.md#missing-components-and-known-gaps).
