---
name: open-pr
description: >-
  Commits local changes to a new Git branch and opens a GitHub pull request
  through the configured GitHub MCP server. Use when proposing code changes in a
  new pull request. Don't use for local-only commits without a remote GitHub
  repository.
---

# Open pull request

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

- **Git repository and remote:** Local Git repository initialized (`git status`)
  with a GitHub remote configured (`git remote -v`).
- **GitHub MCP server:** Configured in `.agents/mcp_config.json` with a valid
  `GITHUB_PERSONAL_ACCESS_TOKEN` granted `Contents` (read/write),
  `Pull requests` (read/write), and `Metadata` (read-only) permissions.
- **Development standards:** Workspace rules defined in
  `.agents/rules/dev-rules.md`.
- **Failure handling:** If the directory is not a Git repository, has no remote
  configured, or the GitHub MCP server tools are unavailable, halt before
  pushing or creating the pull request and instruct the user on how to complete
  the missing setup.

## Workflow

### 1. Inspect repository state and hygiene

1.  Run `git status` and `git remote -v` to verify the working tree and target
    GitHub repository (`owner/repo`).
2.  Verify that `.gitignore` exclusions and secret hygiene comply with
    `.agents/rules/dev-rules.md`. Never stage credentials, tokens, or `.env`
    files.

### 2. Analyze changes and draft pull request metadata

1.  Inspect staged and unstaged changes using `git status` and `git diff`.
2.  Draft a concise pull request title and a structured description containing:
    - **Summary:** High-level overview of the purpose of the changes.
    - **Key changes:** Bullet list of added or modified components, tests, and
      documentation.
    - **Verification:** Summary of unit tests, security checks, and local
      validation performed.

### 3. Create feature branch, commit, and push

1.  Check the current branch with `git branch --show-current`. If on `main` or
    `master`, create and switch to a descriptive feature branch:

    ```bash
    git switch -c feat/<short-description>
    ```

2.  Stage the relevant project files (`git add <files>`) and verify staged files
    with `git status`.
3.  Create a descriptive commit (`git commit -m "<type>: <summary>"`) and push
    the feature branch to the `origin` remote (`git push -u origin HEAD`), or
    use the GitHub MCP server branch/commit tools if preferred.

### 4. Create pull request through GitHub MCP server

1.  Invoke the GitHub MCP server tool (such as `create_pull_request`) with the
    repository owner, repository name, head branch, base branch (`main`), title,
    and description.
2.  Verify that the pull request is created and report the pull request number
    and URL to the user.
