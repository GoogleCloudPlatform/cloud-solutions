---
name: workload-profile-bootstrapper
description: >-
  Generates or updates Workload Profiles (profile.yaml and context.md) in
  Antigravity by combining Cloud Asset Inventory discovery, workspace
  repositories, and architecture documentation.
---

# Workload profile bootstrapper

Use this skill in Antigravity to generate a new Workload Profile under
`app/profiles/<profile-id>/` for greenfield onboarding or to refresh an existing
profile.

## Workflow

1.  **Cloud inventory discovery:** Run
    `python3 cli.py bootstrap <project-id> <profile-id>` (optionally passing
    `--region <region>`, `--zone <zone>`, and `--iac-dir <path>`) or query
    `cloudasset.googleapis.com` and read-only MCP endpoints to populate
    `environment_and_projects`, `active_stack`, and resource labels.
1.  **Operational tooling inspection:** If an infrastructure repository or
    runbook directory is open in the Antigravity workspace, inspect it to refine
    `change_delivery_model`, network constraints, and multi-project mappings.
1.  **Business and risk context:** Extract SLO targets, peak windows, external
    dependencies, and documented `accepted_exceptions` from existing
    architecture records. Keep `context.md` concise and store detailed
    operational runbooks in the Gemini Enterprise knowledge base connector.
1.  **Validation and publication:** Run `python3 cli.py validate <profile-id>`
    and `python3 cli.py drift <profile-id>`, then publish to Cloud Storage via
    `python3 cli.py sync`.
