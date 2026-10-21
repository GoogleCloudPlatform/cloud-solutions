---
name: code-review
description: >-
  Reviews project source code against workspace development standards covering
  copyright headers, documentation completeness, PEP 8 style, logging, error
  handling, and dependency hygiene. Use when performing a local code review or
  checking code quality. Don't use for GitHub pull request creation or
  dependency installation.
---

# Perform project code review

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

- **Project source files:** Application Python files, dependency manifests, and
  configuration files present in the workspace.
- **Development standards:** Workspace rules defined in
  `.agents/rules/dev-rules.md`.
- **Failure handling:** If no source files are found in the workspace, halt
  execution and inform the user.

## Workflow

### 1. Discover files in scope

1.  Locate all project source files, dependency manifests (`requirements.in` and
    `requirements.txt`), and container files (`Dockerfile` and `.dockerignore`,
    if present), excluding `venv/`, `.venv/`, and `__pycache__/`.
2.  Inspect `git status` and `git diff` (if available) to prioritize recently
    added or modified files while reviewing overall project consistency.

### 2. Evaluate against project standards

Review each file against the rules and evaluation criteria defined in
`.agents/rules/dev-rules.md` (`Prerequisites`, `Code architecture and style`,
`Runtime rules and configuration`, and `Container build standards` when a
`Dockerfile` is present).

### 3. Report code review findings

1.  Present a structured review report listing each finding with:
    - **File and line number**
    - **Category:** Rule section in `.agents/rules/dev-rules.md`
    - **Description and recommended fix**
2.  Ask the user whether to apply the recommended fixes.

### 4. Apply fixes and verify

1.  Upon user approval, update the source files and project manifests in
    accordance with `.agents/rules/dev-rules.md`.
2.  Run the project's unit tests (if present) to verify that the changes
    introduce no regressions.
3.  Summarize the applied improvements and verification status for the user.
