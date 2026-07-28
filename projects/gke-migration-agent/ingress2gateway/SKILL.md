---
name: ingress2gateway
description: >-
  Automates migrating legacy GKE Ingress resources to the modern Gateway API.
  Use when migrating legacy GKE or NGINX Ingress resources to GKE Gateway API
  specifications.
---

# Skill name: ingress2gateway

## Intent and objective

Automate the discovery, analysis, risk-profiling, and translation of legacy GKE
and NGINX Ingress resources into native GKE Gateway API specifications using the
`ingress2gateway` tool.

### Activation criteria

- **Use when:** Migrating legacy GKE or NGINX Ingress manifests to native GKE
  Gateway API specifications (Gateway, HTTPRoute)

## Prerequisites and sandbox configuration

### 1. Environment sandbox specification

This skill runs in a local sandbox environment with the following
specifications:

- **Type:** `local-sandbox`
- **Python Version:** `>=3.10`
- **Virtual Environment Path:** `.agent/skills/ingress2gateway/scripts/.venv`
- **Requirements Lockfile:**
  `.agent/skills/ingress2gateway/scripts/requirements.txt`

### 2. Host binary constraints (prerequisites validation)

Before execution, verify the following host binary constraints:

- **python3:** Must be version `>=3.10` (check using `python3 --version`).
- **gcloud:** Required to handle identity challenges, project queries, and GKE
  cluster authentication (check using `gcloud --version`).
- **kubectl:** Must be version `>=1.30` (check using
  `kubectl version --client -o json`). Required to interact with GKE 1.30+
  compatible APIs.

### 3. Secure outbound network allowlists (egress guardrails)

The sandbox requires outbound HTTPS access to the following domains:

- `github.com`: To verify network download access to the `ingress2gateway`
  repository releases without downloading assets.
- `*.googleapis.com`: To authenticate Google Cloud identities and communicate
  with GKE Control Planes.
- `dl.google.com`: To download Google Cloud SDK framework assets and `kubectl`
  components if missing.
- `bootstrap.pypa.io`: As a secure fallback to fetch `get-pip.py` if the host
  environment lacks pip and ensurepip completely.

## Interactive JSON exchange protocol (crucial)

This skill utilizes a strict JSON payload protocol on `stdout` (delimited by
`__AGENT_UI_DATA_START__` and `__AGENT_UI_DATA_END__`) and expects a JSON
response on `stdin` for every user input step.

The executing agent must:

1.  **Never truncate or summarize any JSON payloads** emitted between
    `__AGENT_UI_DATA_START__` and `__AGENT_UI_DATA_END__`. Display them in full
    to the user.
1.  **Never make assumptions or skip user input.** Prompt the user for input at
    every single stage the script pauses and waits for `stdin`.
1.  **Format user choices as the required JSON structure and append a**
    **newline (`\n`)** before writing to the script's `stdin`.
1.  **Render Risk Profiles Visually:** When presenting the risk profile at Phase
    4, the agent must render a clear Markdown table of the compatible (Green
    Lane) and incompatible (Red Lane) resources, detailing the risks/blockers,
    so the operator can make an informed decision.

## Strict execution lifecycle and master report pipeline

### Master report markdown template (to be updated incrementally)

The structural markdown template for the migration analysis report is maintained
in `assets/report_template.md`.

When initialized or updated across the pipeline phases, the runtime engine
automatically copies this template to output
`GKE_Ingress_to_Gateway_API_Migration_Analysis_Report.md` and incrementally
populates its section placeholders.

## Structured macro-pipeline execution phases

You will advance strictly through these 6 consecutive operational phases.

- **Phase 1:** Environment Sandbox Pre-flight Validation.
- **Phase 2:** Identity & Context Resolution
- **Phase 3:** Resource Discovery & Target Inventory.
- **Phase 4:** Ingress scanning & Risk Profiling.
- **Phase 5:** Translation & Dry Run validation.
- **Phase 6:** Approval and execution

### Phase 1: Environment sandbox pre-flight validation

Before executing any Python scripts or processing cluster manifests, you
**must** verify and initialize the local environment by reading and following
the pre-flight validation instructions in `references/preflight_validation.md`.

### Phase 2: Identity and context resolution

1.  **Invoke the Core Python Script:** Instantly upon entering Phase 2, run the
    python orchestrator script:

    ```bash
    python3 .agent/skills/ingress2gateway/scripts/main.py
    ```

1.  **Cluster Discovery UI Payload:** The script discovers GKE clusters and
    emits a JSON payload (`select_cluster`). Intercept this payload, present
    options to the operator, and write the choice to the script's `stdin`.
1.  **Kubeconfig Sandboxing:** Once selected, the script configures local
    sandboxed credentials for the chosen GKE cluster.

### Phase 3: Resource discovery and target inventory

1.  **Orchestrated Scanning:** The active script scans the target GKE cluster
    context to discover Ingress manifests.
1.  **Incremental Report Generation:** The script copies the report template to
    `GKE_Ingress_to_Gateway_API_Migration_Analysis_Report.md` and updates the
    `[Populated in Phase 3]` placeholder with the target inventory.
1.  **Intermediate UI Exchange:** The script does not pause at this stage, but
    advances to Phase 4.

### Phase 4: Ingress scanning and risk profiling

1.  **Automated Risk Triage:** The scanner.py sub-component will
    programmatically evaluate metadata arrays for custom or native rewrite
    snippets.

1.  **Incremental Document Update:** The script replaces the [Populated in Phase
    4] placeholder with a breakdown of Critical Blockers and Translation
    Warnings discovered during verification.

1.  **Interactive JSON Handoff Gate:** The agent must capture the script's
    emitted stdout payload between **AGENT_UI_DATA_START** and
    **AGENT_UI_DATA_END**. Display the comprehensive risk inventory full-string
    array to the operator, pause processing execution, and wait for a structured
    JSON map selection on stdin identifying approved migration asset targets.

### Phase 5: Translation and dry run validation

1.  **Translation Execution:** The engine passes approved target JSON structures
    to translator.py, which pulls down and runs the pre-compiled ingress2gateway
    compiler to generate native Gateway API resource maps.

1.  **Validation & Safety Check:** The script executes the dry-run
    `kubectl apply --dry-run=server -f {GATEWAY_API_MANIFEST_YAML}` command
    against the target cluster context. It analyzes the resulting stdout/stderr
    for validation errors and captures the server response using Kubernetes API.

1.  **Incremental Document Update:** The script replaces the [Populated in Phase
    5 & 6] placeholder with the consolidated raw Gateway, HttpRoute and URLMap
    API manifest, the detected server-side validation results, and a detailed
    explanation of any translation or deployment anomalies.

1.  **Interactive Deployment Signature:** The script prints out the compilation
    details using the approve_deployment UI protocol template. The agent must
    display this text entirely and halt, blocking the runtime sequence until the
    user submits a signed APPROVE or CANCEL string map to stdin.

1.  **Conditional Execution Gate:**

    - If the validation response indicates zero deploy-time errors, the agent
      immediately proceeds to Phase 6 (Execution).
    - If validation errors are returned, the agent **must halt**, append a
      comprehensive error report to the bottom of the Markdown document, display
      the final document, and explicitly **ask the user for permission to
      proceed with manual correction or bypass strict validation rules.**

### Phase 6: Approval and execution

1.  **Live Data Plane Injection:** If the interaction response on stdin reads
    APPROVE, the script applies the manifests to the cluster using kubectl apply
    -f -. It then overwrites the final placeholders with a complete transaction
    receipt string block.

1.  **Conditional Execution Gate:** If the response reads CANCEL, the script
    intercepts the rejection, dumps the fully compiled Gateway configurations
    locally into a migration-fallback.yaml asset backup, and posts a Deployment
    Paused status block to the analysis file.

1.  **Mandatory Hold & Exit:** Once the underlying script lifecycle gracefully
    exits, the agent must present a final execution summary to the workspace
    terminal and wait for further user interaction commands.
