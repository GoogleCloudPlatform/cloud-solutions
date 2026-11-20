# How to contribute

We would love to accept your patches and contributions to this project.

## Before you begin

### Sign our Contributor License Agreement

Contributions to this project must be accompanied by a
[Contributor License Agreement](https://cla.developers.google.com/about) (CLA).
You (or your employer) retain the copyright to your contribution; this simply
gives us permission to use and redistribute your contributions as part of the
project.

If you or your current employer have already signed the Google CLA (even if it
was for a different project), you probably don't need to do it again.

Visit <https://cla.developers.google.com/> to see your current agreements or to
sign a new one.

### Review our community guidelines

This project follows
[Google's Open Source Community Guidelines](https://opensource.google/conduct/).

## Contribution process

### Code reviews

All submissions, including submissions by project members, require review. We
use GitHub pull requests for this purpose. Consult
[GitHub Help](https://docs.github.com/articles/about-pull-requests) for more
information on using pull requests.

- One topic per pull request. Keep security changes small enough to review in
  one sitting.
- Code that touches identity, tokens, keys, IAM, tenant isolation, guardrails or
  the credential broker should add or update a test that fails without the
  change.
- Security-relevant changes also update the relevant ADR in
  [`docs/adr/`](docs/adr/),
  [`docs/tenant_isolation_assurance.md`](docs/tenant_isolation_assurance.md)
  and, if behaviour changes, the status labels in
  [`docs/implementation_status.md`](docs/implementation_status.md#at-a-glance).

### Checks to run before opening a pull request

```bash
uv run python scripts/verify_repo_sanitized.py
uv run ruff check .
uv run pytest -q                                   # hermetic suite; live tests skip
uv run python run_breach_simulations.py            # breach matrix
uv run python scripts/run_extended_golden_e2e.py   # golden end-to-end
uv run python scripts/run_verifiable_batch_audit.py
uv run python scripts/run_5act_demo.py
```

### Never commit

- Secrets, tokens, keys or credential files.
- Real customer or personal data. Test data is synthetic.

### Honest labels

Mark claims as live, simulated, modeled, built-not-live or not built (see the
[status legend](docs/implementation_status.md#at-a-glance)). Cost and latency
numbers are "modeled" unless they come from billing data or a measured run.
