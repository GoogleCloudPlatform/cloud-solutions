---
name: security-scan
description: >-
  Performs a security audit of the project source code and dependencies to
  identify vulnerabilities and recommend remediations. Use when scanning the
  codebase for security issues. Don't use for functional unit testing or
  style-only code formatting.
---

# Run security code scan

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

- **Project source files:** Application source code, templates, and dependency
  manifests (`requirements.in` and `requirements.txt`) present in the workspace.
- **Development standards:** Workspace rules defined in
  `.agents/rules/dev-rules.md`.
- **Failure handling:** If no source code or configuration files are found in
  the workspace, halt execution and notify the user.

## Workflow

### 1. Discover attack surface and scope

1.  Enumerate all application source files, HTML templates, configuration files,
    and dependency manifests in the project (excluding `venv/`, `.venv/`, and
    `__pycache__/`).
2.  Identify trust boundaries, database queries, external service calls, and
    user input entry points such as HTTP query parameters, form submissions,
    JSON payloads, file uploads, and headers.

### 2. Analyze code for security vulnerabilities

Inspect the codebase against common vulnerability classes from the Open
Worldwide Application Security Project (OWASP) Top 10 and Common Weakness
Enumeration (CWE):

1.  **Injection flaws (CWE-89, CWE-78):** Check for string concatenation or
    f-strings in SQL queries, shell commands (`os.system` or `subprocess` with
    `shell=True`), or template rendering (`render_template_string`).
2.  **Cross-Site Scripting (XSS, CWE-79) and Cross-Site Request Forgery (CSRF,
    CWE-352):** Check HTML templates for unescaped variables (`| safe` or
    `Markup`) and verify state-changing POST/PUT/DELETE forms and routes enforce
    CSRF protection.
3.  **Hardcoded secrets and credentials (CWE-798):** Check for hardcoded API
    keys, passwords, Flask `secret_key` literals, or tokens in source files.
4.  **Authentication, authorization, and session security:** Check cookie flags
    (`HttpOnly`, `Secure`, `SameSite`), access control on sensitive endpoints,
    and input validation.
5.  **Insecure configuration and error exposure (CWE-209, CWE-489):** Check for
    debug mode enabled in code (`debug=True`), overly permissive CORS or host
    bindings, and raw stack traces returned to clients.
6.  **Dependency and container hygiene:** Review `requirements.in` and
    `requirements.txt` for unpinned packages, missing hashes, or known insecure
    library versions, and verify `Dockerfile` configurations (if present)
    against `.agents/rules/dev-rules.md`.

### 3. Generate security findings report

Present a structured security assessment report categorized by severity
(`Critical`, `High`, `Medium`, `Low`):

- **Severity and category:** Severity level and vulnerability class / CWE ID.
- **Location:** File path and line numbers.
- **Impact:** Explanation of how the issue could be exploited.
- **Recommended fix:** Concrete code or configuration change to remediate the
  vulnerability.

Ask the user which findings they want to remediate before modifying source
files.

### 4. Remediate and verify

1.  Upon user approval, apply the recommended security fixes to the affected
    files following `.agents/rules/dev-rules.md`.
2.  Re-inspect the modified files and run the project's test suite (if present)
    to verify that all vulnerabilities are resolved without breaking application
    functionality.
3.  Summarize the remediated vulnerabilities and verification results for the
    user.
