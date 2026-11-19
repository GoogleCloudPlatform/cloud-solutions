# Security

## Scope

This repository is an **internal** reference implementation. It runs in a
sandbox project with **synthetic tenants and synthetic data only**. Do not load
customer data or real personal data into it; the gate for that is in the README
([Gate: no customer data until these are true](README.md#gate-no-customer-data-until-these-are-true)).

## Reporting an issue

Report suspected vulnerabilities or isolation failures to the **WS2 owner
through the team channel**. Please include:

- what you did (request, endpoint or test), what you expected and what happened;
- whether it crosses a tenant, user or role boundary;
- whether it affects the hosted sandbox or only the code.

Do not post exploit details, tokens or keys in public issues or pull requests.
Do not test against the hosted gateway beyond your own named, time-boxed access.

## Known limits

Known gaps are listed openly; please check them before reporting:

- [Missing components and known gaps](README.md#missing-components-and-known-gaps)
- [What if a component is compromised?](README.md#what-if-a-component-is-compromised)
  (the component compromise table covering before B5 and today's live B5 +
  ADR-0016 split)
- [Isolation invariants](README.md#isolation-invariants) and
  [`docs/tenant_isolation_assurance.md`](docs/tenant_isolation_assurance.md)

Residual trust-root note: with ADR-0014 B5 and ADR-0016 live, per-agent runtimes
hold zero KMS signing or `TokenCreator` permissions; `cymbal-pooled-gateway`
remains the context-token signing trust root (holding zero `TokenCreator` and
zero invoker access on `cymbal-credential-broker`), with automated KMS
signing-volume alerting tracked in
[Known gaps (#5)](README.md#missing-components-and-known-gaps).
