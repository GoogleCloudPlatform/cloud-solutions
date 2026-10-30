---
name: storage-translation
description: >-
  Translates Amazon Elastic Kubernetes Service (EKS) storage components (StorageClasses, PersistentVolumeClaims (PVCs)) to Google Kubernetes Engine (GKE) equivalents. Generates translated YAML, snapshot strategies, and data migration plans. Use when migrating persistent storage or planning stateful workload moves.
---

# Storage translation

You translate the storage layer: StorageClasses, PVCs, PersistentVolumes (PVs),
and the data movement plan for each stateful workload. You produce the design,
the StorageClass set, and the per-PVC handoff.

## Purpose

Map every Amazon Elastic Block Store (EBS) / Amazon Elastic File System (EFS) /
FSx volume and every StorageClass to a GKE equivalent and produce the snapshot
or live-replication plan.

## When to use this skill

- Phase 3, after `gke-landing-zone`.
- The user asks to "translate storage", "convert StorageClasses", "plan stateful
  workload migration".

## Prerequisites

- Installed and configured the following CLI tools:
    - `check-jsonschema` for schema validation.
    - `velero` for backup and restore.
    - `gcloud` (Google Cloud CLI) authenticated to the target project.
    - `gcsfuse` or equivalent data mover tooling.
- `<output_dir>/01-discovery/inventory.json` storage section (PVs, PVCs,
  StorageClasses, EBS volumes, EFS file systems).
- Target GKE clusters from `<output_dir>/03-landing-zone`.
- No databases: The inventory must not contain any stateful databases. If
  databases are present, stop and escalate immediately.

### Missing prerequisites

If you cannot meet any prerequisite, stop immediately. Tell the user the exact
missing requirement and instruct them to resolve it.

## Procedure

### Step 1 — translate StorageClasses

For each source StorageClass:

For each source StorageClass, refer to the mapping in
[StorageClass mapping reference](references/storage-class-mapping.md).

> [!TIP]
>
> Prefer using built-in GKE StorageClasses (`standard-rwo`, `premium-rwo`)
> before generating custom StorageClass YAML, unless specific customizations
> (like CMEK, custom parameters, or non-default disk types) are required.

Sample translated `StorageClass`:

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: gp3-encrypted
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"
provisioner: pd.csi.storage.gke.io
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true
reclaimPolicy: Delete
parameters:
  type: pd-balanced
  disk-encryption-kms-key: projects/data-prod/locations/us-central1/keyRings/gke-migration/cryptoKeys/disk
  csi.storage.k8s.io/fstype: ext4
```

Always set `volumeBindingMode: WaitForFirstConsumer` — it prevents pods from
being scheduled to a zone where their PD doesn't exist. Always set
`allowVolumeExpansion: true` globally on all dynamic StorageClasses so capacity
adjustments can be executed online without pod restarts.

Generate `<OUTPUT_DIR>/06-storage-translation/storage-map.json` mapping the
source StorageClass to the target StorageClass, adhering strictly to the schema
provided in `assets/storage-map.schema.json`.

Validate the generated map using `check-jsonschema`:

```bash
check-jsonschema --schemafile <SKILL_DIR>/assets/storage-map.schema.json <OUTPUT_DIR>/06-storage-translation/storage-map.json
```

### Step 2 — per-PVC migration plan

For each PVC in `inventory.json`:

Capture:

- Owning workload (StatefulSet / Deployment).
- Current size, access modes, current usage.
- Underlying volume type (EBS gp3 / io2 / EFS / FSx).
- Snapshot capability (already snapshotted? interval?).
- RPO/RTO targets from the readiness report.

Produce a per-PVC plan with one of these strategies:

#### Strategy A — cold migration using backup tool (Velero)

Best for: workloads with an acceptable downtime window, no replication tooling,
simple snapshot/restore semantics.

```bash
# On EKS
velero backup create payments-pvc-${TS} \
  --include-namespaces payments \
  --include-resources persistentvolumes,persistentvolumeclaims \
  --selector app=payments

# Mirror backup bucket to Cloud Storage
gcloud storage cp -r s3://velero-prod gs://gke-migration-velero-prod

# On GKE
velero restore create payments-pvc-${TS} \
  --from-backup payments-pvc-${TS} \
  --namespace-mappings payments:payments
```

Velero's CSI snapshotter cannot directly translate EBS → PD. Use the data-mover
pattern: Velero packages PV contents into the object store, restore re-creates a
PD-backed PV with the same data.

#### Strategy B — block-level replication (pre-cutover sync)

Best for: high-volume workloads where downtime is small and copy time is large.

1.  Create the target PV+PVC on GKE pinned to a temporary "shadow" pod with
    `dd`/`rsync`/`pgpv-replication`-class tooling.
1.  Initial sync: copy from EKS-side snapshot (exported to object storage as
    image) into the GKE Persistent Disk using a one-shot Job.
1.  Incremental sync: depends on workload (database WAL shipping,
    application-level replication).
1.  At cutover: stop EKS workload, do final delta sync, mount to the target
    StatefulSet.

Produce per-workload Job manifests for the sync.

#### Strategy C — out-of-scope (databases)

Best for: Databases, such as PostgreSQL, MongoDB, or Redis.

If you encounter PVCs belonging to in-cluster databases, STOP. This migration
tooling explicitly forbids migrating databases in containers. Escalate
immediately and advise the user to migrate to managed Google Cloud database
services, such as Cloud SQL, Memorystore, or Firestore. Do not attempt to
translate storage for these workloads.

#### Strategy D — object-storage-fronted (re-platform)

Best for: workloads that _could_ use object storage but happen to use a PVC for
caching. Replace the PVC with a `gcsfuse`-mounted bucket using the Cloud Storage
FUSE CSI driver. This is a re-platform decision and surfaces as an escalation.

#### Strategy E — RWX (multi-pod read-write)

Best for: workloads using EFS access points across many pods.

- Identify per-AP usage patterns and pod counts.
- Map to Filestore Enterprise (recommended) or NetApp Volumes (when you need
  NetApp APIs).
- For very high IOPS / many-pod scale-out, evaluate Parallelstore.
- Produce a migration plan: provision Filestore, copy contents using `gcsfuse`
  intermediate or DataSync (cross-cloud), cut over.

### Step 3 — snapshot, retention, and DR

For each migrated PVC:

1.  Plan a `VolumeSnapshotClass` and snapshot schedule on GKE matching the
    existing EKS schedule.
1.  Verify CMEK encryption parity. If EKS volumes were encrypted with a Key
    Management Service (KMS) key, the GKE PVs use the equivalent Cloud KMS key
    declared in the StorageClass.
1.  Plan cross-region DR if the EKS workload had cross-region snapshot copying —
    use Backup for GKE for application-level backups including PVCs. Explicitly
    plan the backup agent policies.
1.  Draft a Decommissioning Safety Playbook (output to
    `<output_dir>/06-storage-translation/decommissioning-playbook.md`)
    documenting the safe teardown process for AWS EBS CSI finalizers. This
    prevents stuck CSI driver states from locking up API servers during the EKS
    estate decommissioning.

### Step 4 — validate sizing

GKE Persistent Disks have minimum sizes. For example, `pd-balanced` has a
minimum of 10 GiB. Performance scales with size. If a source PVC is smaller than
the GKE minimum, request the user's confirmation before bumping size. Do not
silently change sizes.

### Step 5 — stateful workload pre-cutover dry-run

For at least one representative stateful workload per class (DB, queue, file
share):

1.  Stand up a non-prod copy of the workload on GKE with the translated
    StorageClass and a small PV.
1.  Restore a recent snapshot.
1.  Run the workload's smoke tests.
1.  Capture the timing: snapshot copy, restore, mount-to-ready latency.

This timing feeds `traffic-cutover`'s window calculation.

### Step 6 — output

```text
<output_dir>/06-storage-translation/
├── storage-design.md
├── storage-map.json
├── decommissioning-playbook.md
├── manifests/
│   ├── storageclasses/
│   ├── volumesnapshotclasses/
│   └── filestores/             # Filestore instance manifests where applicable
├── pvc-plans/
│   └── <namespace>-<pvc>.md    # Per-PVC strategy and runbook
├── terraform/
│   └── filestore.tf            # Filestore / Parallelstore as TF where appropriate
└── escalations.md
```

## Decision points

| Decision                   | Default                            | When to deviate                                                   |
| -------------------------- | ---------------------------------- | ----------------------------------------------------------------- |
| Default block disk type    | `pd-balanced`                      | `hyperdisk-extreme` for io2 + IOPS-bound; `pd-standard` for st1   |
| RWX target                 | Filestore Enterprise               | NetApp Volumes if NetApp APIs are required; Parallelstore for HPC |
| Migration strategy default | Velero backup/restore (Strategy A) | Out-of-Scope (Strategy C) for databases                           |
| Filesystem (`fstype`)      | `ext4`                             | `xfs` only when source is xfs and required                        |
| Snapshot retention parity  | Match EKS schedule                 | Tighten if compliance requires                                    |

## Validation

- Every PVC in `inventory.json` has a `pvc-plans/<ns>-<pvc>.md` entry with a
  strategy.
- Every StorageClass referenced by any translated workload exists in
  `manifests/storageclasses/`.
- Provisioning a test PVC on GKE with the new StorageClass succeeds and produces
  a PV in the expected zone.
- `volumeBindingMode: WaitForFirstConsumer` on every translated SC.
- Snapshot/restore round-trip works for a representative PVC of each class.

## Escalation triggers

- PVC backed by storage with no clean GKE equivalent (FSx OpenZFS, certain
  Storage Gateway flavors).
- RWX usage that exceeds Filestore tier limits even at Enterprise.
- Workload with no acceptable downtime AND no application built-in replication
  path. Surface this to the user, who must choose between extending the cutover
  window, accepting downtime, or re-platforming.
- Volumes encrypted with externally-managed keys, such as HSM-backed KMS, where
  the Google Cloud target uses CMEK with Cloud HSM and key import is not yet
  planned.

## Common pitfalls

- **The IOPS Death Trap (gp3):** AWS `gp3` provides a baseline of 3,000 IOPS
  regardless of size. Google Cloud `pd-balanced` performance scales linearly
  with capacity. A 10 GB `gp3` disk is fast. A 10 GB `pd-balanced` disk gives
  ~60 IOPS. You MUST calculate required IOPS and either over-provision
  `pd-balanced` capacity or switch to `hyperdisk-balanced` with explicit IOPS.
- **Treating `gp2` as `pd-standard`.** It's not — gp2 is SSD. Use
  `standard-rwo`.
- **Forgetting `volumeBindingMode`.** Default `Immediate` causes PV provisioning
  at PVC creation time, often in the wrong zone.
- **Snapshot semantics.** EBS snapshots are incremental and account-scoped. PD
  snapshots are also incremental, but you can't directly import an EBS snapshot
  — you copy data.
- **EFS performance modes.** EFS Bursting → Filestore Basic; EFS Provisioned/Max
  IO → Filestore Enterprise or Parallelstore.
- **Quorum on stateful clusters.** This migration explicitly forbids migrating
  databases like MongoDB. For other quorum-based systems, for example, Kafka or
  etcd, do _not_ try to live-extend the quorum across clusters across clouds.
  Build a new quorum on GKE, replicate data, switch consumers.
- **Freshly provisioned PDs ship with a `lost+found` directory** that crashes
  Kafka log scanning. Mount via `subPath` for Kafka-class workloads.
- **Stuck PVs at decommission time** are a known class of CSI finalizer race.
  Verify finalizer cleanup before destroying any source cluster.
