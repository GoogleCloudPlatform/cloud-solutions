# Contributing

This is an internal reference implementation that runs on synthetic tenants
only. Keep changes small, reviewed and honestly labelled.

## Branch and pull request

- Branch from `main`, one topic per pull request. Don't push directly to `main`.
- Keep security changes small enough to review in one sitting (ADR-0014 shipped
  one PR per stage, B1–B4).
- Security-relevant changes also update the relevant ADR in
  [`docs/adr/`](docs/adr/),
  [`docs/tenant_isolation_assurance.md`](docs/tenant_isolation_assurance.md)
  and, if behaviour changes, the status labels in the
  [README](README.md#at-a-glance).

## Gates (run before opening a PR)

```bash
uv run python scripts/verify_repo_sanitized.py     # default checks (see its docstring); not the publish gate
uv run ruff check .
uv run pytest -q                                   # hermetic suite; live tests skip
uv run python run_breach_simulations.py            # breach matrix, 10/10 PASS
uv run python scripts/run_extended_golden_e2e.py   # golden end-to-end, 55 PASS
uv run python scripts/run_verifiable_batch_audit.py
CYMBAL_LOCAL_CONTEXT_SIGNER=1 uv run python scripts/run_5act_demo.py
```

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs the sanitizer,
ruff and pytest; run the simulation scripts locally. The docs tests check that
every relative link and `path:line` citation in `README.md` and `docs/`
resolves.

## Review

- Every PR gets an independent review.
- Code that touches identity, tokens, keys, IAM, tenant isolation, guardrails or
  the credential broker needs a reviewer who did not write it, and should add or
  update a test that fails without the change.

## Live GCP changes

- Only the WS2 owner changes the live sandbox (IAM, Cloud Run, KMS, Secret
  Manager).
- Follow a runbook (see [`docs/runbooks/`](docs/runbooks/)) with a read-only
  snapshot before and after each stage, verification, and a rollback step.
  Operator access is time-boxed.
- Contributors don't run `gcloud` against the sandbox from a PR; propose the
  change in code, Terraform or a runbook instead.

## Never commit

- Secrets, tokens, keys or credential files. If a local secrets hook blocks a
  commit, fix the content; never bypass the hook.
- Internal or corp links, personal email addresses or home-directory paths. The
  sanitizer (`scripts/verify_repo_sanitized.py`) must pass. Its default mode
  checks only the classes listed in its docstring; `--public-export`
  (shortlinks, document links, project/org/tenant identifiers, names, via
  `scripts/public_export_denylist.txt`) is the gate for a tree that is about to
  be published and is expected to fail on this internal repository.
- Real customer or personal data. Test data is synthetic.

## Honest labels

Mark claims as live, simulated, modeled, built-not-live or not built (see the
[README legend](README.md#at-a-glance)). Cost and latency numbers are "modeled"
unless they come from billing data or a measured run.
