# Contributing

Contributions to this reference implementation are welcome and appreciated. Keep
pull requests focused, well-tested, and accurately labeled.

## Contributor License Agreement

Contributions to this repository must be accompanied by a
[Google Individual or Corporate Contributor License Agreement (CLA)](https://cla.developers.google.com/).
You (or your employer) retain the copyright to your contribution; the CLA gives
Google permission to use and redistribute your contributions as part of the
project.

## Branch and Pull Request Workflow

- Create a feature branch from `main` with one logical change per pull request.
- Keep security-sensitive changes small enough to review thoroughly in one pass.
- Changes affecting identity, token signing, IAM, tenant isolation, guardrails,
  or credential brokering must update the corresponding ADR in
  [docs/adr/](docs/adr/),
  [docs/tenant_isolation_assurance.md](docs/tenant_isolation_assurance.md), and
  the status table in [README.md](README.md#at-a-glance), and include a
  regression test that fails when the guard branch is mutated.

## Pre-Submission Verification Gates

Run the local verification suite before opening or updating a pull request:

```bash
uv run python scripts/verify_repo_sanitized.py
uv run ruff check .
uv run pytest -q
uv run python run_breach_simulations.py
uv run python scripts/run_extended_golden_e2e.py
uv run python scripts/run_verifiable_batch_audit.py
CYMBAL_LOCAL_CONTEXT_SIGNER=1 uv run python scripts/run_5act_demo.py
```

Documentation governance tests verify that every relative Markdown link and
`path:line` citation across `README.md` and `docs/` resolves cleanly.

## Security & Data Hygiene Rules

- **Never commit secrets:** Do not commit API keys, OAuth tokens, private keys,
  or credential files. Use `.env.example` and Secret Manager resource shells.
- **Synthetic fixtures only:** Never commit real customer data, personal
  identifiers, corporate hostnames, or non-public links. All test and demo data
  must remain synthetic.
- **Accurate status labels:** Label capabilities honestly as **Live**,
  **Simulated**, **Modeled**, **Built, not live**, or **Not built** (see the
  [README status legend](README.md#at-a-glance)). Mark cost and capacity
  calculations as **Modeled** unless backed by measured telemetry.
