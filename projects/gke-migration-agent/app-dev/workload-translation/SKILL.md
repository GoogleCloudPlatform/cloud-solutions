---
name: workload-translation
description: >-
  Translates Kubernetes manifests, Helm charts, and Kustomize overlays from Amazon Elastic Kubernetes Service (EKS)
  conventions to Google Kubernetes Engine (GKE) conventions.
  Use when an app developer needs to migrate Deployments, StatefulSets, DaemonSets, or Jobs from EKS to GKE.
  Don't use for cluster infrastructure provisioning, Google Cloud account registration, or service mesh migrations.
---

# Workload translation

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

## Purpose

Automate the migration readiness evaluation and manifest translation of
application workloads (Deployments, StatefulSets, DaemonSets, CronJobs, Jobs,
ReplicaSets) from Amazon Elastic Kubernetes Service (EKS) to Google Kubernetes
Engine (GKE), targeting either GKE Autopilot or GKE Standard mode.

## When to use

- Application developers receive a `workload-handoff.json` file from platform
  operators and need to generate GKE-compatible YAML manifests.
- User asks "migrate my app from EKS to GKE", "translate my Kubernetes
  workloads", or "prepare manifests for GKE Autopilot".
- Updating workload identity annotations, image pull secrets, or security
  contexts for GKE compatibility.

## Prerequisites

- `python3` version 3.10 or later
- Install dependencies listed in `scripts/requirements.txt`:
  `pip install --require-hashes -r scripts/requirements.txt`
- `kubectl` version 1.30 or later (for dry-run validation against GKE target
  clusters)
- Input JSON handoff artifact (`workload-handoff.json` or per-namespace
  equivalent) conforming to schema definitions in `assets/schemas/`.
- Required environment variable:
    - `HANDOFF_DIR` — Absolute or relative path to the handoff directory
      containing the workload handoff and map files.
- Optional environment variables:
    - `TARGET_MODE` — Target GKE cluster mode: `autopilot` (default) or
      `standard`.
    - `OUTPUT_DIR` — Destination directory for translated YAML manifests and
      reports (default: `./translated-workloads`).

## Assets and references

The following schema files under `assets/schemas/` define the JSON contracts
used by this skill:

- `workload-handoff.schema.json`: Schema for cluster-level workload handoff
  specifications.
- `workload-handoff-namespace.schema.json`: Schema for namespace-level workload
  handoff specifications.
- `identity-map.schema.json`: Schema for ServiceAccount identity mappings.
- `image-map.schema.json`: Schema for container image repository mappings.
- `network-map.schema.json`: Schema for ingress and network policy mappings.
- `storage-map.schema.json`: Schema for StorageClass mappings.

The following reference document under `references/` provides translation
guidance:

- [references/api-translation.md](references/api-translation.md): API
  translation guidelines for converting EKS resources to GKE.

### Missing prerequisites

If any prerequisite is not met, stop immediately. Inform the user of the exact
missing requirement and instruct them to resolve it before re-running the skill.

## Procedure

### Step 1 — Validate input handoff schema

Execute the translation engine to ingest the handoff directory. The engine
automatically detects and normalizes both cluster-level and namespace-level
tenancy structures:

```bash
python3 scripts/translate_workload.py --handoff-dir "$HANDOFF_DIR" --validate-only
```

### Step 2 — Evaluate Autopilot and security compatibility

Review the workload compatibility readiness flags in `workload-handoff.json`
(`autopilot_compatible` and `pod_security_baseline_passes`).

Workload Pod specifications are evaluated against GKE Autopilot security
baseline constraints:

- **Workload blockers**: If workloads contain Autopilot blockers (such as
  `hostNetwork: true`, `hostPID: true`, `hostIPC: true`, `hostPath` volumes,
  privileged containers, or restricted Linux capabilities), resolve or refactor
  them in the workload manifests before proceeding.
- **Infrastructure compatibility**: Note that platform-level Autopilot readiness
  (e.g. storage driver or networking plugin compatibility) is evaluated
  separately by platform engineer skills.

### Step 3 — Run workload manifest translation

Run the translation engine to mutate workload definitions, replace AWS IRSA
annotations with GKE Workload Identity Federation (WIF) bindings, and output
clean GKE manifests:

```bash
python3 scripts/translate_workload.py \
  --handoff-dir "$HANDOFF_DIR" \
  --target-mode "${TARGET_MODE:-autopilot}" \
  --output-dir "${OUTPUT_DIR:-./translated-workloads}"
```

### Step 3b — LLM post-processing and cleanup

After executing the translation engine script, you must post-process the
translated manifests in `$OUTPUT_DIR` using LLM capabilities to remove all
cluster-specific metadata and resolve remaining AWS constructs.

> [!IMPORTANT]
>
> You MUST perform these cleanups directly on the generated YAML files using
> your file editing tools. Do NOT create helper scripts (such as Python, Bash,
> or Go scripts) to automate this cleanup.

Follow the specific rules and tables in `references/api-translation.md`:

1.  **Metadata and Status Cleanup**: Strip runtime metadata fields (`uid`,
    `resourceVersion`, `creationTimestamp`, `managedFields`, etc.) and `status`
    blocks per `references/api-translation.md#runtime-metadata-and-status`.
2.  **AWS Controllers, Classes and Finalizers**: Remove AWS-specific finalizers
    and controller annotations per
    `references/api-translation.md#aws-finalizers`.
3.  **Scheduling and Topology**: Map AWS node selectors, node groups, and
    Karpenter spot selectors to GKE equivalents per
    `references/api-translation.md#pod--scheduling`.
4.  **CRDs and Custom Resources**: Drop AWS-specific CRDs and instances
    (`TargetGroupBinding`, Karpenter node pools, App Mesh) per
    `references/api-translation.md#crds-of-note`.
5.  **GKE Custom Resource Translation**: Translate Ingresses to
    Gateway/HTTPRoute, extract health checks to `HealthCheckPolicy`, and convert
    Prometheus annotations to `PodMonitoring` following
    `references/api-translation.md#declarative-resource-translation-examples`.

- Save all newly generated resources as new YAML files in `$OUTPUT_DIR`.

### Step 4 — Validate manifests with dry-run

Validate the post-processed GKE manifests for schema compliance and Autopilot
compatibility using the helper script:

```bash
scripts/.venv/bin/python3 scripts/validate_manifests.py --manifests-dir "${OUTPUT_DIR:-./translated-workloads}"
```

### Step 5 — Present summary report to application developer

Display the generated summary report located at
`$OUTPUT_DIR/migration_summary_report.md` to the user, highlighting manual
action items such as updating database connection strings and verifying secret
references.
