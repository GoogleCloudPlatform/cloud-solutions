---
name: unit-tests
description: >-
  Generates and executes Python unit tests for methods in the project. Use when
  creating or updating unit test suites for Python files. Don't use for
  end-to-end browser testing or security vulnerability scanning.
---

# Generate unit tests

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

- **Python 3.11 or higher:** Verify host availability with `python3 --version`.
- **Project virtual environment (`venv`):** Located in the application directory
  with project dependencies installed according to `.agents/rules/dev-rules.md`.
- **Test runner:** `pytest` or Python's built-in `unittest` module.
- **Failure handling:** If no Python source files exist in the workspace, halt
  and inform the user. If the virtual environment or `pytest` dependency is
  missing, configure `venv` and compile and install dependencies following
  `.agents/rules/dev-rules.md`, or fall back to
  `./venv/bin/python -m unittest`.

## Workflow

### 1. Analyze target Python modules

1.  Locate all Python source files in the project directory, excluding `venv/`,
    `.venv/`, and existing `test_*.py` files.
2.  Identify public functions, class methods, data models, request handlers, and
    validation logic that require test coverage.

### 2. Generate unit test files

1.  For each target Python module `<module>.py`, create or update a
    corresponding test file named `test_<module>.py`.
2.  Write isolated unit tests covering:
    - **Standard execution paths:** Verify expected return values, status codes,
      and state changes for valid inputs.
    - **Edge and boundary cases:** Test empty inputs, boundary values, and
      optional parameters.
    - **Error handling:** Verify that invalid inputs or missing records raise
      expected exceptions or return appropriate error responses.
3.  Use test fixtures, temporary databases (such as in-memory SQLite), or mocks
    so tests run deterministically without mutating production data.
4.  Include clear docstrings for test functions and follow the coding standards
    in `.agents/rules/dev-rules.md`.

### 3. Execute and validate test suite

1.  Run the test suite using the project virtual environment:

    ```bash
    ./venv/bin/python -m pytest -v
    ```

    Or with `unittest`:

    ```bash
    ./venv/bin/python -m unittest discover -s . -p "test_*.py" -v
    ```

2.  Inspect the test execution output. If any test fails, determine whether the
    defect is in the test setup or the application code, apply the fix following
    `.agents/rules/dev-rules.md`, and re-run the test suite until all tests
    pass.

### 4. Report results

1.  Summarize the generated `test_*.py` files, scenarios covered, and final test
    execution output for the user.
