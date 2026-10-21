---
name: pre-commit
description: >-
  Runs pre-commit verification steps including documentation updates, unit test
  generation and execution, and security code analysis. Use when preparing
  changes before creating a commit or pull request. Don't use for initial
  application scaffolding or opening remote pull requests.
---

# Run pre-commit checks

<!--
  Disabling markdownlint MD029 to provide explicit ordering to avoid
  confusing the LLM.
-->
<!-- markdownlint-disable MD029 -->

<!--
    Disabling markdownlint MD030 to allow the list overflowing to numbers
    >=10.
-->
<!-- markdownlint-disable MD030 -->

## Prerequisites

- **Project source files:** Application code, `requirements.in`, and
  `requirements.txt` present in the workspace.
- **Python 3.11+ and virtual environment (`venv`):** Verify host Python version
  (`python3 --version`) and local `venv` readiness to execute unit tests.
- **Development standards:** Workspace rules defined in
  `.agents/rules/dev-rules.md`.
- **Failure handling:** If no source files exist, halt and notify the user. If
  any verification step fails (such as failing unit tests or critical security
  findings), remediate the issue and re-verify before reporting pre-commit
  readiness.

## Workflow

Execute the following pre-commit verification stages in sequence:

### 1. Update documentation

1.  Inspect recent codebase changes and review the project's `README.md`.
2.  Create or update `README.md` so project overview, setup instructions,
    dependencies, and API endpoints accurately reflect the current code.

### 2. Generate and run unit tests

1.  Ensure unit test files (`test_<module>.py`) cover all new and modified
    functions, classes, and routes.
2.  Execute the test suite inside the project virtual environment:

    ```bash
    ./venv/bin/python -m pytest -v
    ```

    Or with `unittest`:

    ```bash
    ./venv/bin/python -m unittest discover -s . -p "test_*.py" -v
    ```

3.  Resolve any test failures and re-run until all unit tests pass.

### 3. Perform security code scan

1.  Audit all source files, templates, and dependency manifests
    (`requirements.in` and `requirements.txt`, excluding `venv/`) for common
    security vulnerabilities, including SQL/command injection, Cross-Site
    Scripting (XSS), missing Cross-Site Request Forgery (CSRF) protection,
    hardcoded secrets, debug mode enabled in code (`debug=True`), and
    non-compliant dependencies or container files against
    `.agents/rules/dev-rules.md`.
2.  Remediate any identified high or critical security issues following
    `.agents/rules/dev-rules.md` and re-run the unit tests to confirm no
    regressions.

### 4. Verify workspace readiness

1.  Check `git status` (if in a Git repository) to confirm `.gitignore`
    exclusions and workspace hygiene comply with `.agents/rules/dev-rules.md`.
2.  Present a consolidated pre-commit report summarizing documentation updates,
    unit test pass status, and security scan results.
