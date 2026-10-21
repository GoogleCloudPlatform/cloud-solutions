---
name: documentation
description: >-
  Generates and updates project README documentation based on codebase changes.
  Use when generating or updating application documentation. Don't use for
  inline code comments or docstring-only refactoring.
---

# Update documentation

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

- **Application source files:** Project source code, configuration files, and
  dependency manifests (`requirements.in` and `requirements.txt`) present in the
  workspace.
- **Development standards:** Workspace rules defined in
  `.agents/rules/dev-rules.md`.
- **Failure handling:** If no application source files exist in the target
  directory, inform the user before creating placeholder documentation.

## Workflow

### 1. Analyze codebase and recent changes

1.  Inspect the application directory structure, entry points, data models,
    routes or CLI commands, and dependency manifests (`requirements.in` and
    `requirements.txt`).
2.  Check `git status` and `git diff` (if inside a Git repository) to identify
    newly added features, modified endpoints, or updated configuration options.
3.  Read the existing `README.md` file in the application directory (if present)
    to preserve valid custom sections and project context.

### 2. Draft or update `README.md`

Create a new `README.md` file in the application directory (or update the
existing file) with the following structured sections:

1.  **Project overview:** Concise summary of the application's purpose, key
    features, and technology stack.
2.  **Project structure:** Overview of the main directories and source files.
3.  **Prerequisites and setup:** Required Python runtime version, virtual
    environment setup, dependency compilation and installation, and environment
    variable configuration following `.agents/rules/dev-rules.md`.
4.  **Running the application:** Exact commands to start the application locally
    and the local URL/port to access it.
5.  **API reference and usage:** Summary of available HTTP endpoints (method,
    path, request parameters, and response behavior) or user workflows.
6.  **Running tests:** Commands to execute the unit test suite.

### 3. Verify accuracy and formatting

1.  Verify that all file paths, shell commands, environment variables, and port
    numbers in `README.md` match the actual codebase.
2.  Ensure Markdown formatting uses proper heading hierarchy, language-tagged
    fenced code blocks, and valid relative links.
3.  Summarize the documentation updates for the user.
