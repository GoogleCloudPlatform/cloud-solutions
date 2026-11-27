---
name: sre-remediation-assistant
description: >-
  Assists engineers in Antigravity to validate, prepare, or apply remediation
  actions from GCP SRE Advisor diagnostics according to each workload's
  operational model.
---

# SRE remediation assistant for Antigravity

Use this skill in Antigravity whenever the user pastes a diagnostic output from
**GCP SRE Advisor** or asks Antigravity to help remediate an identified
infrastructure or configuration finding.

## Workflow

1.  **Resolve workload operational model:**
    - When the diagnostic context originates from a live application catalog or
      Google Cloud App Hub, follow the `delivery_mode`, `iac_tooling`, and
      repository path reported in the advisor's context header.
    - When the diagnostic context originates from a declarative Workload Profile
      under `app/profiles/<profile-id>/profile.yaml`, inspect
      `change_delivery_model` (`delivery_mode`, `tooling`, and
      `remediation_format`).
    - When the diagnostic context originates from direct live project
      discovery without a profile or catalog record, check the open workspace
      files or ask the user whether changes are applied via
      Infrastructure-as-Code files or operational CLI runbooks.
1.  **Verify live baseline via read-only MCPs:**
    - When Google Cloud Managed Remote MCP endpoints are configured in
      Antigravity (`mcp_config.example.json`), query the affected resource state
      in read-only mode before modifying files or proposing commands so target
      names and parameters match live configuration.
1.  **Prepare or apply remediation:**
    - **When the workspace uses declarative configurations** such as Terraform,
      Terragrunt, Pulumi, Helm, or Kubernetes manifests: locate the target files
      in the open workspace, apply the configuration edits, and execute local
      dry-run or syntax checks (`validate`, `fmt`, `plan`, or
      `--dry-run=client`) inside Antigravity's terminal so the user can review
      the exact diff.
    - **When the workload uses operational runbooks or change-ticket
      execution**: generate a concise pre-check, change, post-check, and
      rollback command sequence; only execute mutating CLI commands in
      Antigravity's terminal after explicit confirmation from the user.
