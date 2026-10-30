---
name: app-migration-execution
description: >-
  Applies translated Google Kubernetes Engine (GKE) application manifests and coordinates storage provisioning,
  data migration, and workload exposure in a strict sequence with state persistence and recovery.
  Use when deploying validated translated manifests to a target GKE cluster.
  Don't use for manifest translation or platform cluster creation.
---

# Application migration execution

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

Orchestrate the GKE deployment sequence for a translated Amazon Elastic
Kubernetes Service (EKS) workload, enforcing verification gates, user approval
steps, and utilizing local state persistence to enable recovery from execution
failures.

## When to use this skill

Trigger on:

- "Deploy the translated manifests to GKE"
- "Execute application migration execution phase"
- "Run the deployment sequence on GKE"

## Prerequisites

- `python3` version 3.10 or later
- Install dependencies listed in `scripts/requirements.txt`:
  `pip install --require-hashes -r scripts/requirements.txt`
- `kubectl` version 1.30 or later
- Path to directory containing translated GKE manifests, for example
  `./translated-manifests/`
- Active target GKE cluster context configured in `kubectl`

## Assets and references

The following schema files under `assets/schemas/` define the JSON contracts
used by this skill:

- `workload-handoff.schema.json`: Schema for cluster-level workload handoff
  specifications.
- `workload-handoff-namespace.schema.json`: Schema for namespace-level workload
  handoff specifications.
- `platform-handoff.schema.json`: Schema for platform infrastructure handoffs.
- `identity-map.schema.json`: Schema for ServiceAccount identity mappings.
- `image-map.schema.json`: Schema for container image repository mappings.
- `network-map.schema.json`: Schema for ingress and network policy mappings.
- `observability-map.schema.json`: Schema for metrics and observability
  mappings.
- `storage-map.schema.json`: Schema for StorageClass mappings.

> [!NOTE] When executing `scripts/execute_migration.py`, the script
> automatically scans the handoff directory and validates all present handoff
> and mapping JSON specifications against the schemas above using Python
> `jsonschema` prior to manifest deployment.

## Procedure

### Step 1 — Verify cluster connectivity

Ensure the active `kubectl` context matches the target cluster.

### Step 2 — Run the deployment execution script

Execute the orchestrator script to manage the multi-phase deployment sequence:

```bash
python3 scripts/execute_migration.py \
  --manifests-dir ./translated-manifests \
  --namespace production-app \
  --auto-approve
```

The script runs the sequence in 5 distinct Phases:

- **Phase 1: Namespace and Identity:** Includes `Namespace`, `ServiceAccount`,
  `CustomResourceDefinition`, and RBAC resources.
- **Phase 2: Storage and Data Sync:** Includes `StorageClass`,
  `PersistentVolumeClaim` (PVC), and `VolumeSnapshot` resources.
    - Provisions GKE target volumes by applying the translated PVC and
      StorageClass manifests.
    - **Approval Gate:** You MUST ask the user if they want to perform active
      data replication/sync. If approved, guide them through executing the
      replication using the strategies in
      [pvc_migration_strategies.md](../storage-translation/references/pvc_migration_strategies.md).
      If not, proceed to Phase 3 with empty target volumes.
- **Phase 3: Workloads Deployment:** Includes `Deployment`, `StatefulSet`,
  `DaemonSet`, `Job`, and custom workload operator resources.
- **Phase 4: Observability Integration:** Includes `PodMonitoring`,
  `ClusterPodMonitoring`, and `ServiceMonitor` resources.
- **Phase 5: Network Exposure:** Includes `Gateway`, `HTTPRoute`, `Service`,
  `Ingress`, and `NetworkPolicy` resources.

> [!NOTE] For any custom CRDs or third-party custom resources that fall outside
> standard built-in kinds, evaluate their function and place or organize them
> into the appropriate Phase directory or apply them during the relevant phase,
> for example CRD definitions in Phase 1, custom workload CRs in Phase 3, or
> custom network policies in Phase 5.

### Step 3 — State recovery

If the migration script aborts or fails at any Phase:

1.  Resolve the underlying error, such as target resource limits, quota, or
    Identity and Access Management (IAM) configuration issues.
2.  Re-run the script with the same parameters.
3.  The script will automatically detect `migration-execution-state.json` and
    prompt you to **Resume** (skip completed phases and verify dependencies) or
    **Start Fresh**.
